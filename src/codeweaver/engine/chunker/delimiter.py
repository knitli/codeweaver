# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Delimiter-based code chunking implementation.

Implements pattern-based chunking using delimiter pairs (e.g., braces, parentheses).
Uses a three-phase algorithm: match detection, boundary extraction with nesting support,
and priority-based overlap resolution.

Architecture follows the specification in chunker-architecture-spec.md §3.3-3.5.
"""

from __future__ import annotations

import re

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from codeweaver.common.utils import uuid7
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.metadata import Metadata
from codeweaver.core.spans import Span
from codeweaver.core.stores import get_blake_hash
from codeweaver.engine.chunker.base import BaseChunker, ChunkGovernor
from codeweaver.engine.chunker.delimiter_model import Boundary, Delimiter, DelimiterMatch
from codeweaver.engine.chunker.exceptions import (
    BinaryFileError,
    ChunkingError,
    ChunkLimitExceededError,
    ParseError,
)
from codeweaver.engine.chunker.registry import source_id_for


class DelimiterChunker(BaseChunker):
    r"""Pattern-based chunker using delimiter pairs.

    Extracts code chunks based on delimiter patterns (braces, parentheses, etc.)
    with support for nesting and priority-based overlap resolution.

    Algorithm:
        Phase 1: Match Detection - Find all delimiter occurrences
        Phase 2: Boundary Extraction - Match starts with ends, handle nesting
        Phase 3: Priority Resolution - Keep highest-priority non-overlapping boundaries

    Attributes:
        _delimiters: List of delimiter patterns for the target language
        _language: Programming language being processed

    Example:
        >>> from codeweaver.engine.chunker.base import ChunkGovernor
        >>> governor = ChunkGovernor(chunk_limit=1000)
        >>> chunker = DelimiterChunker(governor, language="python")
        >>> chunks = chunker.chunk("def foo():\n    pass")
    """

    _delimiters: list[Delimiter]
    _language: str

    def __init__(self, governor: ChunkGovernor, language: str = "generic") -> None:
        """Initialize delimiter chunker for a specific language.

        Args:
            governor: ChunkGovernor instance for size constraints
            language: Programming language (default: "generic")
        """
        super().__init__(governor)
        self._language = language
        self._delimiters = self._load_delimiters_for_language(language)

    def chunk(
        self, content: str, *, file_path: Path | None = None, context: dict[str, Any] | None = None
    ) -> list[CodeChunk]:
        """Chunk content using delimiter patterns.

        Implements complete delimiter chunking with edge case handling and
        size constraint enforcement.

        Args:
            content: Source code to chunk
            file_path: Optional source file path
            context: Optional additional context

        Returns:
            List of CodeChunk objects

        Raises:
            BinaryFileError: If content contains binary data
            ChunkLimitExceededError: If chunk count exceeds governor limit
            OversizedChunkError: If individual chunks exceed token limit
            ParseError: If delimiter matching fails
        """
        from codeweaver.engine.chunker.governance import ResourceGovernor

        # Edge case: empty content
        if not content or not content.strip():
            return []

        # Edge case: binary content detection
        try:
            _ = content.encode("utf-8")
        except UnicodeEncodeError as e:
            raise BinaryFileError(
                "Binary content detected in file",
                file_path=str(file_path) if file_path else None,
                details={"error": str(e)},
            ) from e

        # Get performance settings from governor, or use defaults
        if self._governor.settings is not None:
            performance_settings = self._governor.settings.performance
        else:
            # Fallback defaults if no settings provided
            from codeweaver.config.settings import PerformanceSettings
            performance_settings = PerformanceSettings()

        with ResourceGovernor(performance_settings) as governor:
            try:
                # Generate consistent source_id for all spans from this file
                source_id = source_id_for(file_path) if file_path else uuid7()

                # Phase 1: Find all delimiter matches
                governor.check_timeout()
                matches = self._find_delimiter_matches(content)

                # Edge case: no matches found
                if not matches:
                    return []

                # Phase 2: Extract boundaries from matches
                governor.check_timeout()
                boundaries = self._extract_boundaries(matches)

                # Edge case: no complete boundaries
                if not boundaries:
                    return []

                # Phase 3: Resolve overlapping boundaries
                governor.check_timeout()
                resolved = self._resolve_overlaps(boundaries)

                # Convert boundaries to chunks
                chunks = self._boundaries_to_chunks(resolved, content, file_path, source_id, context)

                # Register each chunk with the governor for resource tracking
                for _ in chunks:
                    governor.register_chunk()

            except ChunkingError:
                raise
            except Exception as e:
                raise ParseError(
                    f"Delimiter matching failed: {e}",
                    file_path=str(file_path) if file_path else None,
                    details={"error": str(e), "language": self._language},
                ) from e
            else:
                return chunks

    def _enforce_chunk_limit(self, chunks: list[CodeChunk], file_path: Path | None) -> None:
        """Enforce maximum chunk count limit.

        Args:
            chunks: List of chunks to validate
            file_path: Optional source file path

        Raises:
            ChunkLimitExceededError: If chunk count exceeds governor limit
        """
        max_chunks = getattr(self._governor, "max_chunks", 10000)
        if len(chunks) > max_chunks:
            raise ChunkLimitExceededError(
                f"Delimiter chunking produced {len(chunks)} chunks, exceeding limit",
                chunk_count=len(chunks),
                max_chunks=max_chunks,
                file_path=str(file_path) if file_path else None,
            )

    def _find_delimiter_matches(self, content: str) -> list[DelimiterMatch]:
        """Find all delimiter matches in content.

        Phase 1: Uses combined regex to find all delimiter occurrences efficiently.

        Args:
            content: Source code to scan

        Returns:
            List of DelimiterMatch objects ordered by position
        """
        matches: list[DelimiterMatch] = []

        if not self._delimiters:
            return matches

        # Build combined regex for all start and end delimiters
        start_patterns: dict[str, Delimiter] = {d.start: d for d in self._delimiters}
        end_patterns: dict[str, Delimiter] = {d.end: d for d in self._delimiters}

        # Escape patterns and combine
        all_patterns = list(start_patterns.keys()) + list(end_patterns.keys())
        combined_pattern = "|".join(re.escape(p) for p in all_patterns)

        # Find all matches
        for match in re.finditer(combined_pattern, content):
            matched_text = match.group(0)
            pos = match.start()

            # Determine if this is a start or end delimiter
            if matched_text in start_patterns:
                delimiter: Delimiter = start_patterns[matched_text]
                matches.append(
                    DelimiterMatch(
                        delimiter=delimiter,
                        start_pos=pos,
                        end_pos=None,  # Start delimiters have no end_pos
                        nesting_level=0,  # Will be set during boundary extraction
                    )
                )
            elif matched_text in end_patterns:
                delimiter = end_patterns[matched_text]
                matches.append(
                    DelimiterMatch(
                        delimiter=delimiter,
                        start_pos=pos,
                        end_pos=pos + len(matched_text),
                        nesting_level=0,  # Will be set during boundary extraction
                    )
                )

        return matches

    def _extract_boundaries(self, matches: list[DelimiterMatch]) -> list[Boundary]:
        """Extract complete boundaries from delimiter matches.

        Phase 2: Match start delimiters with corresponding end delimiters,
        handling nesting for nestable delimiters.

        Args:
            matches: List of delimiter matches from Phase 1

        Returns:
            List of complete Boundary objects
        """
        boundaries: list[Boundary] = []

        # Group matches by delimiter type
        delimiter_stacks: dict[str, list[tuple[DelimiterMatch, int]]] = {}

        for match in matches:
            # Get delimiter with explicit type
            delimiter: Delimiter = match.delimiter  # type: ignore[assignment]
            delimiter_key: str = f"{delimiter.start}_{delimiter.end}"  # type: ignore[union-attr]

            if delimiter_key not in delimiter_stacks:
                delimiter_stacks[delimiter_key] = []

            if match.is_start:
                # Start delimiter - push to stack
                current_level: int = (
                    len(delimiter_stacks[delimiter_key]) if delimiter.nestable else 0  # type: ignore[union-attr]
                )
                delimiter_stacks[delimiter_key].append((match, current_level))
            else:
                # End delimiter - pop from stack and create boundary
                if not delimiter_stacks[delimiter_key]:
                    # Unmatched end delimiter - skip
                    continue

                start_match, nesting_level = delimiter_stacks[delimiter_key].pop()

                # Create boundary
                try:
                    # Type assertion for end_pos
                    end_pos: int = match.end_pos if match.end_pos is not None else match.start_pos
                    boundary = Boundary(
                        start=start_match.start_pos,
                        end=end_pos,
                        delimiter=delimiter,
                        nesting_level=nesting_level,
                    )
                    boundaries.append(boundary)
                except ValueError:
                    # Invalid boundary (start >= end) - skip
                    continue

        return boundaries

    def _resolve_overlaps(self, boundaries: list[Boundary]) -> list[Boundary]:
        """Resolve overlapping boundaries using priority and tie-breaking rules.

        Phase 3: Keep highest-priority non-overlapping boundaries.

        Tie-breaking rules (in order):
        1. Higher priority wins
        2. Same priority: Longer match wins
        3. Same length: Earlier position wins (deterministic)

        Args:
            boundaries: List of potentially overlapping boundaries

        Returns:
            List of non-overlapping boundaries
        """
        if not boundaries:
            return []

        # Sort by priority (desc), length (desc), position (asc)
        sorted_boundaries = sorted(
            boundaries,
            key=lambda b: (
                -cast(int, b.delimiter.priority),  # type: ignore[union-attr]
                -(b.end - b.start),
                b.start,
            ),
        )

        # Keep non-overlapping boundaries
        result: list[Boundary] = []

        for boundary in sorted_boundaries:
            overlaps = any(self._boundaries_overlap(boundary, selected) for selected in result)
            if not overlaps:
                result.append(boundary)

        # Sort result by position for consistent output
        return sorted(result, key=lambda b: b.start)

    def _boundaries_overlap(self, b1: Boundary, b2: Boundary) -> bool:
        """Check if two boundaries overlap.

        Args:
            b1: First boundary
            b2: Second boundary

        Returns:
            True if boundaries overlap
        """
        return b1.end > b2.start and b2.end > b1.start

    def _boundaries_to_chunks(
        self,
        boundaries: list[Boundary],
        content: str,
        file_path: Path | None,
        source_id: Any,  # UUID7 type
        context: dict[str, Any] | None,
    ) -> list[CodeChunk]:
        """Convert boundaries to CodeChunk objects.

        Args:
            boundaries: Resolved boundaries to convert
            content: Source content
            file_path: Optional source file path
            source_id: Source identifier for all spans from this file
            context: Optional additional context

        Returns:
            List of CodeChunk objects
        """
        from codeweaver.core.metadata import ExtKind

        chunks: list[CodeChunk] = []
        lines = content.splitlines(keepends=True)

        for boundary in boundaries:
            # Get delimiter with explicit type
            delimiter: Delimiter = boundary.delimiter  # type: ignore[assignment]

            # Extract chunk text
            chunk_text = content[boundary.start : boundary.end]

            # Strip delimiters if not inclusive
            if not delimiter.inclusive:  # type: ignore[union-attr]
                chunk_text = self._strip_delimiters(chunk_text, delimiter)  # type: ignore[arg-type]

            # Expand to line boundaries if requested
            if delimiter.take_whole_lines:  # type: ignore[union-attr]
                start_line, end_line = self._expand_to_lines(boundary.start, boundary.end, lines)
            else:
                start_line, end_line = self._pos_to_lines(boundary.start, boundary.end, lines)

            # Build metadata
            metadata = self._build_metadata(boundary, chunk_text, start_line, context)

            # Create chunk with shared source_id
            chunk = CodeChunk(
                content=chunk_text,
                ext_kind=ExtKind.from_file(file_path) if file_path else None,
                line_range=Span(start_line, end_line, source_id),  # type: ignore[call-arg]  # All spans from same file share source_id
                file_path=file_path,
                metadata=metadata,
            )

            chunks.append(chunk)

        return chunks

    def _build_metadata(
        self, boundary: Boundary, text: str, line: int, context: dict[str, Any] | None
    ) -> Metadata:
        """Build metadata for a delimiter chunk.

        Args:
            boundary: Boundary that created this chunk
            text: Chunk content
            line: Starting line number
            context: Optional additional context

        Returns:
            Metadata dictionary
        """
        # Get delimiter with explicit type
        delimiter: Delimiter = boundary.delimiter  # type: ignore[assignment]

        # Build context dict with proper types
        chunk_context: dict[str, Any] = {
            "chunker_type": "delimiter",
            "content_hash": str(get_blake_hash(text)),
            "delimiter_kind": delimiter.kind.name,  # type: ignore[union-attr]
            "delimiter_start": delimiter.start,  # type: ignore[union-attr]
            "delimiter_end": delimiter.end,  # type: ignore[union-attr]
            "priority": int(delimiter.priority),  # type: ignore[arg-type,union-attr]
            "nesting_level": boundary.nesting_level,
        }

        # Merge with provided context
        if context:
            chunk_context |= context

        metadata: Metadata = {
            "chunk_id": uuid7(),
            "created_at": datetime.now(UTC).timestamp(),
            "name": f"{delimiter.kind.name.title()} at line {line}",  # type: ignore[union-attr]
            "context": chunk_context,
        }
        return metadata

    def _load_delimiters_for_language(self, language: str) -> list[Delimiter]:
        """Load delimiter set for language.

        Checks for custom delimiters in settings first, then falls back to
        delimiter families system when implemented.

        Args:
            language: Programming language name

        Returns:
            List of Delimiter objects for the language
        """
        from codeweaver.engine.chunker.delimiter_model import DelimiterKind

        # Check for custom delimiters from settings
        if self._governor.settings is not None and self._governor.settings.custom_delimiters:
            for custom_delim in self._governor.settings.custom_delimiters:
                if custom_delim.language == language or (
                    custom_delim.extensions and
                    any(ext.language == language for ext in custom_delim.extensions if hasattr(ext, 'language'))
                ):
                    # Convert DelimiterPattern to Delimiter objects
                    # TODO: Implement proper conversion when delimiter families are integrated
                    pass

        # TODO: Load from delimiter families system when implemented.
        # For now, use generic delimiters suitable for most C-style languages.
        return [
            Delimiter(
                start="{",
                end="}",
                kind=DelimiterKind.BLOCK,
                priority=100,
                inclusive=True,
                take_whole_lines=True,
                nestable=True,
            ),
            Delimiter(
                start="(",
                end=")",
                kind=DelimiterKind.GENERIC,
                priority=50,
                inclusive=True,
                take_whole_lines=False,
                nestable=True,
            ),
        ]

    def _strip_delimiters(self, text: str, delimiter: Delimiter) -> str:
        """Remove delimiter markers from text.

        Args:
            text: Text potentially containing delimiters
            delimiter: Delimiter definition

        Returns:
            Text with delimiters removed
        """
        # Remove start and end delimiters
        return text.removeprefix(delimiter.start).removesuffix(delimiter.end)

    def _expand_to_lines(self, start_pos: int, end_pos: int, lines: list[str]) -> tuple[int, int]:
        """Expand character positions to full line boundaries.

        Args:
            start_pos: Starting character position
            end_pos: Ending character position
            lines: Source lines with line endings

        Returns:
            Tuple of (start_line, end_line) 1-indexed
        """
        current_pos = 0
        start_line = 1
        end_line = 1

        for i, line in enumerate(lines, start=1):
            line_end = current_pos + len(line)

            # Find line containing start position
            if current_pos <= start_pos < line_end and start_line == 1:
                start_line = i

            # Find line containing end position
            if current_pos <= end_pos <= line_end:
                end_line = i
                break

            current_pos = line_end

        return start_line, max(end_line, start_line)

    def _pos_to_lines(self, start_pos: int, end_pos: int, lines: list[str]) -> tuple[int, int]:
        """Convert character positions to line numbers.

        Args:
            start_pos: Starting character position
            end_pos: Ending character position
            lines: Source lines with line endings

        Returns:
            Tuple of (start_line, end_line) 1-indexed
        """
        # For non-whole-line chunks, use same logic as expand
        return self._expand_to_lines(start_pos, end_pos, lines)


__all__ = ("DelimiterChunker",)
