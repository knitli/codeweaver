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
from typing import TYPE_CHECKING, Any, cast

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


if TYPE_CHECKING:
    from codeweaver.core.discovery import DiscoveredFile


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
        self, content: str, *, file: DiscoveredFile | None = None, context: dict[str, Any] | None = None
    ) -> list[CodeChunk]:
        """Chunk content using delimiter patterns.

        Implements complete delimiter chunking with edge case handling and
        size constraint enforcement.

        Args:
            content: Source code to chunk
            file: Optional DiscoveredFile with metadata and source_id
            context: Optional additional context

        Returns:
            List of CodeChunk objects

        Raises:
            BinaryFileError: If content contains binary data
            ChunkLimitExceededError: If chunk count exceeds governor limit
            OversizedChunkError: If individual chunks exceed token limit
            ParseError: If delimiter matching fails
        """
        from codeweaver.core.types.aliases import UUID7Hex
        from codeweaver.engine.chunker.governance import ResourceGovernor

        # Edge case: empty content
        if not content or not content.strip():
            return []

        # Extract file_path and source_id from DiscoveredFile
        file_path = file.path if file else None

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
        if (
            self.governor.settings is not None
            and hasattr(self.governor.settings, "performance")
            and (performance_settings := self.governor.settings.performance)
        ):
            pass  # performance_settings already assigned in walrus operator
        else:
            from codeweaver.config.chunker import PerformanceSettings

            performance_settings = PerformanceSettings()

        with ResourceGovernor(performance_settings) as governor:
            try:
                # Use the DiscoveredFile's existing source_id instead of generating a new one
                source_id = UUID7Hex(file.source_id.hex) if file else uuid7()

                # Phase 1: Find all delimiter matches
                governor.check_timeout()
                matches = self._find_delimiter_matches(content)

                # Edge case: no matches found - try paragraph fallback
                used_fallback = False
                if not matches:
                    matches = self._fallback_paragraph_chunking(content)
                    used_fallback = True
                    if not matches:
                        return []
                
                # Add fallback indicator to context if needed
                if used_fallback:
                    if context is None:
                        context = {}
                    context["fallback_to_generic"] = True

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
                chunks = self._boundaries_to_chunks(
                    resolved, content, file_path, source_id, context
                )

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
        """Find all delimiter matches in content using two-phase matching.

        Phase 1: Matches explicit start/end pairs (e.g., {...}, (...))
        Phase 2: Matches keyword delimiters with empty ends (e.g., function, def, class)

        Args:
            content: Source code to scan

        Returns:
            List of DelimiterMatch objects ordered by position
        """
        if not self._delimiters:
            return []

        # Separate delimiters by type
        explicit_delimiters = [d for d in self._delimiters if not d.is_keyword_delimiter]
        keyword_delimiters = [d for d in self._delimiters if d.is_keyword_delimiter]

        matches: list[DelimiterMatch] = []

        # Phase 1: Handle explicit start/end pairs (existing logic)
        matches.extend(self._match_explicit_delimiters(content, explicit_delimiters))

        # Phase 2: Handle keyword delimiters with empty ends
        matches.extend(self._match_keyword_delimiters(content, keyword_delimiters))

        return sorted(matches, key=lambda m: m.start_pos)

    def _match_explicit_delimiters(
        self, content: str, delimiters: list[Delimiter]
    ) -> list[DelimiterMatch]:
        """Match delimiters with explicit start/end pairs.

        Uses the original matching logic for delimiters like {...}, (...), etc.

        Args:
            content: Source code to scan
            delimiters: List of delimiters with explicit end markers

        Returns:
            List of DelimiterMatch objects
        """
        matches: list[DelimiterMatch] = []

        if not delimiters:
            return matches

        # Build combined regex for all start and end delimiters
        start_patterns: dict[str, Delimiter] = {d.start: d for d in delimiters}
        end_patterns: dict[str, Delimiter] = {d.end: d for d in delimiters if d.end}

        # Escape patterns and combine
        all_patterns = list(start_patterns.keys()) + list(end_patterns.keys())
        combined_pattern = "|".join(re.escape(p) for p in all_patterns if p)

        if not combined_pattern:
            return matches

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

    def _match_keyword_delimiters(
        self, content: str, keyword_delimiters: list[Delimiter]
    ) -> list[DelimiterMatch]:
        """Match keywords and bind them to structural delimiters.

        Handles delimiters with empty end strings by finding keywords and binding
        them to the next structural delimiter, then finding the matching close.
        For example: "function name() {...}" becomes a FUNCTION chunk.

        Args:
            content: Source code to scan
            keyword_delimiters: List of keyword delimiters with empty end strings

        Returns:
            List of complete Boundary objects for keyword-based structures
        """
        matches: list[DelimiterMatch] = []

        if not keyword_delimiters:
            return matches

        # Filter out delimiters with empty start strings - they match everywhere!
        keyword_delimiters = [d for d in keyword_delimiters if d.start]

        # Define structural delimiters that can complete keywords
        # Map opening structural chars to their closing counterparts
        STRUCTURAL_PAIRS = {
            "{": "}",
            ":": "\n",  # Python uses : followed by indented block (simplified to newline)
            "=>": "",   # Arrow functions often have expression bodies
        }

        for delimiter in keyword_delimiters:
            # Find all keyword occurrences using word boundary matching
            pattern = rf"\b{re.escape(delimiter.start)}\b"

            for match in re.finditer(pattern, content):
                keyword_pos = match.start()

                # Skip if keyword is inside a string or comment
                if self._is_inside_string_or_comment(content, keyword_pos):
                    continue

                # Find the next structural opening after the keyword
                struct_start, struct_char = self._find_next_structural_with_char(
                    content, start=keyword_pos + len(delimiter.start),
                    allowed=set(STRUCTURAL_PAIRS.keys())
                )

                if struct_start is None:
                    continue

                # Find the matching closing delimiter for the structural character
                struct_end = self._find_matching_close(
                    content, struct_start, struct_char, STRUCTURAL_PAIRS.get(struct_char, "")
                )

                if struct_end is not None:
                    # Create a complete match from keyword to closing structure
                    # This represents the entire construct (e.g., function...})
                    matches.append(
                        DelimiterMatch(
                            delimiter=delimiter,
                            start_pos=keyword_pos,
                            end_pos=struct_end,
                            nesting_level=0,  # Will be set during boundary extraction
                        )
                    )

        return matches

    def _find_next_structural_with_char(
        self, content: str, start: int, allowed: set[str]
    ) -> tuple[int | None, str | None]:
        """Find the next structural delimiter and return its position and character.

        Args:
            content: Source code to search
            start: Starting position for search
            allowed: Set of allowed structural delimiter strings

        Returns:
            Tuple of (position of structural delimiter, the delimiter character/string), or (None, None)
        """
        pos = start
        in_string = False
        string_char = None
        paren_depth = 0
        content_len = len(content)

        while pos < content_len:
            char = content[pos]

            # Handle string boundaries
            if char in ('"', "'", "`"):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    # Check if escaped
                    if pos > 0 and content[pos - 1] != "\\":
                        in_string = False
                        string_char = None

            # Skip if inside string
            if in_string:
                pos += 1
                continue

            # Skip line comments
            if pos + 1 < content_len:
                two_chars = content[pos : pos + 2]
                if two_chars in ("//", "#"):
                    # Skip to end of line
                    newline_pos = content.find("\n", pos)
                    if newline_pos == -1:
                        return None, None  # Comment goes to end of file
                    pos = newline_pos + 1
                    continue
                if two_chars == "/*":
                    # Skip block comment
                    end_comment = content.find("*/", pos + 2)
                    if end_comment == -1:
                        return None, None  # Unclosed comment
                    pos = end_comment + 2
                    continue

            # Track parenthesis depth (for skipping parameter lists)
            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1

            # Check for structural delimiter (only at paren depth 0)
            if paren_depth == 0:
                for struct in sorted(allowed, key=len, reverse=True):  # Check longer patterns first
                    struct_len = len(struct)
                    if content[pos : pos + struct_len] == struct:
                        return pos, struct

            pos += 1

        return None, None

    def _find_matching_close(
        self, content: str, open_pos: int, open_char: str, close_char: str
    ) -> int | None:
        """Find the matching closing delimiter for an opening delimiter.

        Handles nesting of the same delimiter type (e.g., nested braces).

        Args:
            content: Source code
            open_pos: Position of the opening delimiter
            open_char: The opening delimiter character/string
            close_char: The closing delimiter character/string to find

        Returns:
            Position after the closing delimiter, or None if not found
        """
        if not close_char:
            # No explicit close (e.g., arrow functions with expression bodies)
            # Find the next statement terminator
            pos = open_pos + len(open_char)
            # For now, just extend to end of line as a simple heuristic
            newline = content.find("\n", pos)
            return newline if newline != -1 else len(content)

        if close_char == "\n":
            # Python-style: find end of indented block
            # For simplicity, find the next line at same/lower indentation
            # This is a simplified heuristic - full Python parsing would be more complex
            return self._find_python_block_end(content, open_pos)

        # Standard brace/bracket matching with nesting support
        pos = open_pos + len(open_char)
        depth = 1
        in_string = False
        string_char = None
        content_len = len(content)

        while pos < content_len and depth > 0:
            char = content[pos]

            # Handle string boundaries
            if char in ('"', "'", "`"):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    # Check if escaped
                    if pos > 0 and content[pos - 1] != "\\":
                        in_string = False
                        string_char = None

            if not in_string:
                # Skip comments
                if pos + 1 < content_len:
                    two_chars = content[pos : pos + 2]
                    if two_chars in ("//", "#"):
                        newline = content.find("\n", pos)
                        if newline == -1:
                            break
                        pos = newline
                        continue
                    if two_chars == "/*":
                        end_comment = content.find("*/", pos + 2)
                        if end_comment == -1:
                            break
                        pos = end_comment + 2
                        continue

                # Check for nested open
                if content[pos : pos + len(open_char)] == open_char:
                    depth += 1
                    pos += len(open_char)
                    continue

                # Check for close
                if content[pos : pos + len(close_char)] == close_char:
                    depth -= 1
                    if depth == 0:
                        return pos + len(close_char)
                    pos += len(close_char)
                    continue

            pos += 1

        return None  # No matching close found

    def _find_python_block_end(self, content: str, colon_pos: int) -> int | None:
        """Find the end of a Python indented block starting after a colon.

        This is a simplified heuristic that finds the next line at the same or
        lower indentation level.

        Args:
            content: Source code
            colon_pos: Position of the colon that starts the block

        Returns:
            Position of the end of the block, or None if not found
        """
        # Find the line with the colon and calculate its indentation
        line_start = content.rfind("\n", 0, colon_pos)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1  # Move past the newline

        # Get the line content up to the colon
        line_with_colon = content[line_start:colon_pos]
        # Calculate base indentation (number of leading spaces/tabs)
        base_indent = len(line_with_colon) - len(line_with_colon.lstrip())

        # Find lines after the colon
        pos = content.find("\n", colon_pos)
        if pos == -1:
            return len(content)  # Block goes to end of file

        pos += 1  # Move past newline

        while pos < len(content):
            # Get the indentation of the current line
            current_line_start = pos
            line_end = content.find("\n", pos)
            if line_end == -1:
                line_end = len(content)

            line = content[current_line_start:line_end]

            # Skip empty lines and comment lines
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                pos = line_end + 1 if line_end < len(content) else len(content)
                continue

            # Calculate indentation of this line
            indent = len(line) - len(stripped)

            # If we find a line at same or lower indentation, that's the end
            if indent <= base_indent:
                return current_line_start

            pos = line_end + 1 if line_end < len(content) else len(content)

        return len(content)  # Block goes to end of file

    def _is_inside_string_or_comment(self, content: str, pos: int) -> bool:
        """Check if a position is inside a string literal or comment.

        This is a simplified check that scans backward from the position to
        determine context. Used to avoid matching keywords in strings/comments.

        Args:
            content: Source code
            pos: Position to check

        Returns:
            True if position is inside a string or comment
        """
        # Simple heuristic: scan backward to start of line
        line_start = content.rfind("\n", 0, pos) + 1
        prefix = content[line_start:pos]

        # Check for line comment before position
        if "//" in prefix or "#" in prefix:
            comment_pos = max(prefix.rfind("//"), prefix.rfind("#"))
            # If comment is before our position and not in quotes, we're in a comment
            before_comment = prefix[:comment_pos]
            if before_comment.count('"') % 2 == 0 and before_comment.count("'") % 2 == 0:
                return True

        # Check for unclosed string quotes
        single_quotes = prefix.count("'")
        double_quotes = prefix.count('"')
        backticks = prefix.count("`")

        # Odd number of quotes means we're inside a string
        return bool(single_quotes % 2 == 1 or double_quotes % 2 == 1 or backticks % 2 == 1)

    def _fallback_paragraph_chunking(self, content: str) -> list[DelimiterMatch]:
        """Fallback to paragraph-based chunking when no delimiters match.
        
        Uses double newlines (\n\n) as paragraph boundaries for plain text.
        Creates matches for the content between paragraph breaks.
        
        Args:
            content: Content with no delimiter matches
            
        Returns:
            List of DelimiterMatch objects for paragraph boundaries
        """
        from codeweaver.engine.chunker.delimiter_model import Delimiter, DelimiterKind
        
        # Create a paragraph delimiter - we'll create complete boundaries directly
        # by finding text blocks separated by double newlines
        paragraph_delim = Delimiter(
            start="",
            end="",
            kind=DelimiterKind.PARAGRAPH,
            priority=40,
            inclusive=True,  # Include the text content itself
            take_whole_lines=True,
            nestable=False,
        )
        
        # Split by double newlines and find the positions of each paragraph
        matches: list[DelimiterMatch] = []
        paragraphs = re.split(r'\n\n+', content)
        
        current_pos = 0
        for para in paragraphs:
            if para.strip():  # Only create matches for non-empty paragraphs
                # Find the actual position of this paragraph in the content
                para_start = content.find(para, current_pos)
                if para_start >= 0:
                    para_end = para_start + len(para)
                    matches.append(
                        DelimiterMatch(
                            delimiter=paragraph_delim,
                            start_pos=para_start,
                            end_pos=para_end,
                            nesting_level=0,
                        )
                    )
                    current_pos = para_end
        
        return matches

    def _extract_boundaries(self, matches: list[DelimiterMatch]) -> list[Boundary]:
        """Extract complete boundaries from delimiter matches.

        Phase 2: Match start delimiters with corresponding end delimiters,
        handling nesting for nestable delimiters. Also handles keyword delimiters
        that already have complete boundaries.

        Args:
            matches: List of delimiter matches from Phase 1

        Returns:
            List of complete Boundary objects
        """
        boundaries: list[Boundary] = []

        # Separate keyword delimiter matches (which are already complete boundaries)
        # from explicit delimiter matches (which need start/end pairing)
        keyword_matches: list[DelimiterMatch] = []
        explicit_matches: list[DelimiterMatch] = []

        for match in matches:
            delimiter: Delimiter = match.delimiter  # type: ignore[assignment]
            # Keyword delimiters with empty ends that have been matched already have both positions
            # Also treat matches with both start and end positions as complete
            if (delimiter.is_keyword_delimiter and match.end_pos is not None) or \
               (match.end_pos is not None and delimiter.start == "" and delimiter.end == ""):  # type: ignore[union-attr]
                keyword_matches.append(match)
            else:
                explicit_matches.append(match)

        # Handle keyword delimiter matches - they're already complete
        for match in keyword_matches:
            delimiter: Delimiter = match.delimiter  # type: ignore[assignment]
            try:
                boundary = Boundary(
                    start=match.start_pos,
                    end=match.end_pos,  # type: ignore[arg-type]
                    delimiter=delimiter,
                    nesting_level=0,  # Keyword delimiters are typically top-level structures
                )
                boundaries.append(boundary)
            except ValueError:
                # Invalid boundary (start >= end) - skip
                continue

        # Handle explicit delimiter matches - need start/end pairing
        # Group matches by delimiter type
        delimiter_stacks: dict[str, list[tuple[DelimiterMatch, int]]] = {}

        for match in explicit_matches:
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
            metadata = self._build_metadata(boundary, chunk_text, start_line, end_line, context)

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
        self, boundary: Boundary, text: str, start_line: int, end_line: int, context: dict[str, Any] | None
    ) -> Metadata:
        """Build metadata for a delimiter chunk.

        Args:
            boundary: Boundary that created this chunk
            text: Chunk content
            start_line: Starting line number
            end_line: Ending line number
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
            "name": f"{delimiter.kind.name.title()} at line {start_line}",  # type: ignore[union-attr]
            "kind": delimiter.kind,  # Add kind at top level for test compatibility
            "nesting_level": boundary.nesting_level,  # Add nesting_level at top level too
            "priority": int(delimiter.priority),  # Add priority at top level
            "line_start": start_line,  # Add line_start for test compatibility
            "line_end": end_line,  # Add line_end for test compatibility
            "context": chunk_context,
        }
        
        # Add fallback indicator at top level if present in context
        if context and context.get("fallback_to_generic"):
            metadata["fallback_to_generic"] = True  # type: ignore[typeddict-unknown-key]
        
        return metadata

    def _load_delimiters_for_language(self, language: str) -> list[Delimiter]:
        """Load delimiter set for language.

        Checks for custom delimiters in settings first, then falls back to
        delimiter families system.

        Args:
            language: Programming language name

        Returns:
            List of Delimiter objects for the language
        """
        from codeweaver.engine.chunker.delimiter_model import Delimiter, DelimiterKind
        from codeweaver.engine.chunker.delimiters.families import (
            LanguageFamily,
            get_family_patterns,
        )

        # Check for custom delimiters from settings
        if (
            self._governor.settings is not None
            and hasattr(self._governor.settings, "custom_delimiters")
            and self._governor.settings.custom_delimiters
        ):
            for custom_delim in self._governor.settings.custom_delimiters:
                if custom_delim.language == language or (
                    custom_delim.extensions
                    and any(
                        ext.language == language
                        for ext in custom_delim.extensions
                        if hasattr(ext, "language")
                    )
                ):
                    # Convert DelimiterPattern to Delimiter objects
                    # TODO: Implement proper conversion when delimiter families are integrated
                    pass

        # Load from delimiter families system
        family = LanguageFamily.from_known_language(language)
        patterns = get_family_patterns(family)

        # Convert patterns to delimiters
        delimiters: list[Delimiter] = []
        for pattern in patterns:
            delimiters.extend(Delimiter.from_pattern(pattern))

        # Always add common code element patterns as fallback (for generic/unknown languages)
        # These catch function/class/def keywords across many languages
        from codeweaver.engine.chunker.delimiters.patterns import (
            CLASS_PATTERN,
            CONDITIONAL_PATTERN,
            FUNCTION_PATTERN,
            LOOP_PATTERN,
        )

        common_patterns = [FUNCTION_PATTERN, CLASS_PATTERN, CONDITIONAL_PATTERN, LOOP_PATTERN]
        for pattern in common_patterns:
            # Only add if not already present (avoid duplicates from family patterns)
            pattern_delimiters = Delimiter.from_pattern(pattern)
            for delim in pattern_delimiters:
                # Check if this delimiter already exists
                if not any(
                    d.start == delim.start and d.end == delim.end and d.kind == delim.kind
                    for d in delimiters
                ):
                    delimiters.append(delim)

        # Always add generic fallback delimiters with LOWER priority than semantic ones
        # These catch any structural delimiters not already matched by language-specific patterns
        delimiters.extend([
            Delimiter(
                start="{",
                end="}",
                kind=DelimiterKind.BLOCK,
                priority=30,  # Same as BLOCK default priority
                inclusive=False,
                take_whole_lines=False,
                nestable=True,
            ),
            Delimiter(
                start="(",
                end=")",
                kind=DelimiterKind.GENERIC,
                priority=3,  # Same as GENERIC default priority
                inclusive=False,
                take_whole_lines=False,
                nestable=True,
            ),
        ])

        return delimiters

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
