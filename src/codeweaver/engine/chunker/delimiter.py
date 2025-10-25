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
from typing import Any

from uuid_extensions import uuid7

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

        try:
            # Phase 1: Find all delimiter matches
            matches = self._find_delimiter_matches(content)

            # Edge case: no matches found
            if not matches:
                return []

            # Phase 2: Extract boundaries from matches
            boundaries = self._extract_boundaries(matches)

            # Edge case: no complete boundaries
            if not boundaries:
                return []

            # Phase 3: Resolve overlapping boundaries
            resolved = self._resolve_overlaps(boundaries)

            # Convert boundaries to chunks
            chunks = self._boundaries_to_chunks(resolved, content, file_path, context)

            # Enforce chunk limit
            self._enforce_chunk_limit(chunks, file_path)

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
        start_patterns = {d.start: d for d in self._delimiters}
        end_patterns = {d.end: d for d in self._delimiters}

        # Escape patterns and combine
        all_patterns = list(start_patterns.keys()) + list(end_patterns.keys())
        combined_pattern = "|".join(re.escape(p) for p in all_patterns)

        # Find all matches
        for match in re.finditer(combined_pattern, content):
            matched_text = match.group(0)
            pos = match.start()

            # Determine if this is a start or end delimiter
            if matched_text in start_patterns:
                delimiter = start_patterns[matched_text]
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
            delimiter_key = f"{match.delimiter.start}_{match.delimiter.end}"

            if delimiter_key not in delimiter_stacks:
                delimiter_stacks[delimiter_key] = []

            if match.is_start:
                # Start delimiter - push to stack
                current_level = (
                    len(delimiter_stacks[delimiter_key]) if match.delimiter.nestable else 0
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
                    boundary = Boundary(
                        start=start_match.start_pos,
                        end=match.end_pos,  # type: ignore[arg-type]
                        delimiter=match.delimiter,
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
            boundaries, key=lambda b: (-b.delimiter.priority, -(b.end - b.start), b.start)
        )

        # Keep non-overlapping boundaries
        result: list[Boundary] = []

        for boundary in sorted_boundaries:
            # Check if this boundary overlaps with any already selected
            overlaps = False
            for selected in result:
                if self._boundaries_overlap(boundary, selected):
                    overlaps = True
                    break

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
        return not (b1.end <= b2.start or b2.end <= b1.start)

    def _boundaries_to_chunks(
        self,
        boundaries: list[Boundary],
        content: str,
        file_path: Path | None,
        context: dict[str, Any] | None,
    ) -> list[CodeChunk]:
        """Convert boundaries to CodeChunk objects.

        Args:
            boundaries: Resolved boundaries to convert
            content: Source content
            file_path: Optional source file path
            context: Optional additional context

        Returns:
            List of CodeChunk objects
        """
        chunks: list[CodeChunk] = []
        lines = content.splitlines(keepends=True)

        for boundary in boundaries:
            # Extract chunk text
            chunk_text = content[boundary.start : boundary.end]

            # Strip delimiters if not inclusive
            if not boundary.delimiter.inclusive:
                chunk_text = self._strip_delimiters(chunk_text, boundary.delimiter)

            # Expand to line boundaries if requested
            if boundary.delimiter.take_whole_lines:
                start_line, end_line = self._expand_to_lines(boundary.start, boundary.end, lines)
            else:
                start_line, end_line = self._pos_to_lines(boundary.start, boundary.end, lines)

            # Build metadata
            metadata = self._build_metadata(boundary, chunk_text, start_line, context)

            # Create chunk
            chunk = CodeChunk(
                content=chunk_text,
                line_range=Span(start=start_line, end=end_line),
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
        metadata: Metadata = {
            "chunk_id": uuid7(),
            "created_at": datetime.now(UTC).timestamp(),
            "name": f"{boundary.delimiter.kind.name.title()} at line {line}",
            "context": {
                "chunker_type": "delimiter",
                "content_hash": str(get_blake_hash(text)),
                "delimiter_kind": boundary.delimiter.kind.name,
                "delimiter_start": boundary.delimiter.start,
                "delimiter_end": boundary.delimiter.end,
                "priority": boundary.delimiter.priority,
                "nesting_level": boundary.nesting_level,
                **(context or {}),
            },
        }
        return metadata

    def _load_delimiters_for_language(self, language: str) -> list[Delimiter]:
        """Load delimiter set for language.

        TODO: Load from delimiter families system when implemented.
        For now, use generic delimiters suitable for most C-style languages.

        Args:
            language: Programming language name

        Returns:
            List of Delimiter objects for the language
        """
        from codeweaver.engine.chunker.delimiter_model import DelimiterKind

        # Generic delimiters for most C-style languages
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
