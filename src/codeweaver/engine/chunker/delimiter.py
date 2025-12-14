# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Delimiter-based code chunking implementation.

Implements pattern-based chunking using delimiter pairs (e.g., braces, parentheses).
Uses a three-phase algorithm: match detection, boundary extraction with nesting support,
and priority-based overlap resolution.
"""

from __future__ import annotations

import re

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple, cast

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


PERFORMANCE_THRESHOLD_MS = 1000.0  # 1 second


class StringParseState(NamedTuple):
    """State for tracking string boundaries during parsing.

    Attributes:
        in_string: Whether currently inside a string literal
        delimiter: The string delimiter character ('"', "'", or '`'), or None if not in string
    """

    in_string: bool
    delimiter: str | None


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
        self,
        content: str,
        *,
        file: DiscoveredFile | None = None,
        context: dict[str, Any] | None = None,
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
        import time

        from codeweaver.core.types.aliases import UUID7Hex
        from codeweaver.engine.chunker.governance import ResourceGovernor

        # Edge case: empty content
        if not content or not content.strip():
            return []

        file_path = file.path if file else None
        self._validate_content_encoding(content, file_path)
        performance_settings = self._get_performance_settings()

        start_time = time.perf_counter()

        with ResourceGovernor(performance_settings) as governor:
            try:
                source_id = UUID7Hex(file.source_id.hex) if file else uuid7()

                if context is None:
                    context = {}

                if matches := self._get_matches_with_fallback(content, governor, context):
                    chunks = self._process_matches_to_chunks(
                        matches, content, file_path, source_id, context, governor
                    )

                else:
                    return []

            except ChunkingError:
                raise
            except Exception as e:
                raise ParseError(
                    f"Delimiter matching failed: {e}",
                    file_path=str(file_path) if file_path else None,
                    details={"error": str(e), "language": self._language},
                ) from e
            else:
                # Check for performance warnings
                duration_ms = (time.perf_counter() - start_time) * 1000

                if duration_ms > PERFORMANCE_THRESHOLD_MS:
                    from codeweaver.engine.chunker import _logging as chunker_logging

                    chunker_logging.log_chunking_performance_warning(
                        file_path=file_path or Path("<unknown>"),
                        chunker_type=self,
                        duration_ms=duration_ms,
                        threshold_ms=PERFORMANCE_THRESHOLD_MS,
                        extra_context={"chunk_count": len(chunks), "file_size_bytes": len(content)},
                    )

                return chunks

    def _validate_content_encoding(self, content: str, file_path: Path | None) -> None:
        """Validate that content is valid UTF-8 encoded text.

        Args:
            content: Content to validate
            file_path: Optional file path for error reporting

        Raises:
            BinaryFileError: If content contains binary data
        """
        try:
            _ = content.encode("utf-8")
        except UnicodeEncodeError as e:
            raise BinaryFileError(
                "Binary content detected in file",
                file_path=str(file_path) if file_path else None,
                details={"error": str(e)},
            ) from e

    def _get_performance_settings(self) -> Any:
        """Get performance settings from governor or use defaults.

        Returns:
            Performance settings instance
        """
        if (
            self.governor.settings is not None
            and hasattr(self.governor.settings, "performance")
            and (performance_settings := self.governor.settings.performance)
        ):
            return performance_settings

        from codeweaver.config.chunker import PerformanceSettings

        return PerformanceSettings()

    def _get_matches_with_fallback(
        self, content: str, governor: Any, context: dict[str, Any] | None
    ) -> list[DelimiterMatch]:
        """Find delimiter matches with fallback to paragraph chunking.

        Args:
            content: Source code to scan
            governor: Resource governor for timeout checks
            context: Optional context to update with fallback indicator

        Returns:
            List of delimiter matches
        """
        governor.check_timeout()
        matches = self._find_delimiter_matches(content)

        if not matches:
            matches = self._fallback_paragraph_chunking(content)
            if matches and context is not None:
                context["fallback_to_generic"] = True

        return matches

    def _process_matches_to_chunks(
        self,
        matches: list[DelimiterMatch],
        content: str,
        file_path: Path | None,
        source_id: Any,
        context: dict[str, Any] | None,
        governor: Any,
    ) -> list[CodeChunk]:
        """Process delimiter matches into code chunks.

        Args:
            matches: Delimiter matches to process
            content: Source code content
            file_path: Optional file path
            source_id: Source identifier
            context: Optional context
            governor: Resource governor for tracking

        Returns:
            List of code chunks
        """
        # Phase 2: Extract boundaries from matches
        governor.check_timeout()
        boundaries = self._extract_boundaries(matches)

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
        structural_pairs = {
            "{": "}",
            ":": "\n",  # Python uses : followed by indented block (simplified to newline)
            "=>": "",  # Arrow functions often have expression bodies
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
                    content,
                    start=keyword_pos + len(delimiter.start),
                    allowed=set(structural_pairs.keys()),
                )

                if struct_start is None:
                    continue

                # Find the matching closing delimiter for the structural character
                struct_end = self._find_matching_close(
                    content,
                    struct_start,
                    struct_char or "",
                    structural_pairs.get(struct_char, ""),  # type: ignore
                )

                if struct_end is not None:
                    # Calculate nesting level by counting parent structures
                    nesting_level = self._calculate_nesting_level(content, keyword_pos)

                    # Create a complete match from keyword to closing structure
                    # This represents the entire construct (e.g., function...})
                    matches.append(
                        DelimiterMatch(
                            delimiter=delimiter,
                            start_pos=keyword_pos,
                            end_pos=struct_end,
                            nesting_level=nesting_level,
                        )
                    )

        return matches

    def _calculate_nesting_level(self, content: str, pos: int) -> int:
        """Calculate nesting level at a given position by counting braces.

        Args:
            content: Source code
            pos: Position to check nesting at

        Returns:
            Nesting level (0 = top level, 1+ = nested)
        """
        # Count opening and closing braces before this position
        # Ignore braces in strings and comments
        brace_depth = 0
        i = 0
        in_string = False
        string_char = None

        while i < pos:
            c = content[i]

            # Handle strings
            if c in ('"', "'", "`") and (i == 0 or content[i - 1] != "\\"):
                if not in_string:
                    in_string = True
                    string_char = c
                elif c == string_char:
                    in_string = False
                    string_char = None

            # Handle comments (simplified - just check for // and /*)
            elif not in_string:
                if content[i : i + 2] == "//":
                    # Skip to end of line
                    next_newline = content.find("\n", i)
                    i = next_newline if next_newline >= 0 else len(content)
                    continue
                if content[i : i + 2] == "/*":
                    # Skip to end of comment
                    end_comment = content.find("*/", i + 2)
                    i = end_comment + 2 if end_comment >= 0 else len(content)
                    continue
                if c == "{":
                    brace_depth += 1
                elif c == "}":
                    brace_depth = max(0, brace_depth - 1)

            i += 1

        return brace_depth

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
        string_state = StringParseState(in_string=False, delimiter=None)
        paren_depth = 0
        content_len = len(content)

        while pos < content_len:
            char = content[pos]

            # Handle string boundaries
            if self._is_string_boundary(char):
                string_state = self._update_string_state(content, pos, char, string_state)

            # Skip if inside string
            if string_state.in_string:
                pos += 1
                continue

            # Skip comments
            comment_skip = self._skip_comment(content, pos, content_len)
            if comment_skip is not None:
                if comment_skip == -1:
                    return None, None
                pos = comment_skip
                continue

            # Track parenthesis depth
            paren_depth = self._update_paren_depth(char, paren_depth)

            # Check for structural delimiter (only at paren depth 0)
            if paren_depth == 0 and (
                found := self._check_structural_delimiter(content, pos, allowed)
            ):
                return found

            pos += 1

        return None, None

    def _is_string_boundary(self, char: str) -> bool:
        """Check if character is a string boundary.

        Args:
            char: Character to check

        Returns:
            True if character is a string delimiter
        """
        return char in {'"', "'", "`"}

    def _update_string_state(
        self, content: str, pos: int, char: str, state: StringParseState
    ) -> StringParseState:
        """Update string state based on current character.

        Args:
            content: Source code
            pos: Current position
            char: Current character
            state: Current string parse state

        Returns:
            Updated StringParseState
        """
        if not state.in_string:
            return StringParseState(in_string=True, delimiter=char)
        if char == state.delimiter and pos > 0 and content[pos - 1] != "\\":
            return StringParseState(in_string=False, delimiter=None)
        return state

    def _skip_comment(self, content: str, pos: int, content_len: int) -> int | None:
        """Skip comment if found at current position.

        Args:
            content: Source code
            pos: Current position
            content_len: Length of content

        Returns:
            New position after comment, -1 if comment to EOF, None if no comment
        """
        if pos + 1 >= content_len:
            return None

        two_chars = content[pos : pos + 2]

        # Line comments
        if two_chars in ("//", "#"):
            newline_pos = content.find("\n", pos)
            return -1 if newline_pos == -1 else newline_pos + 1
        # Block comments
        if two_chars == "/*":
            end_comment = content.find("*/", pos + 2)
            return -1 if end_comment == -1 else end_comment + 2
        return None

    def _update_paren_depth(self, char: str, paren_depth: int) -> int:
        """Update parenthesis depth counter.

        Args:
            char: Current character
            paren_depth: Current depth

        Returns:
            Updated depth
        """
        if char == "(":
            return paren_depth + 1
        return paren_depth - 1 if char == ")" else paren_depth

    def _check_structural_delimiter(
        self, content: str, pos: int, allowed: set[str]
    ) -> tuple[int, str] | None:
        """Check if current position has a structural delimiter.

        Args:
            content: Source code
            pos: Current position
            allowed: Set of allowed delimiters

        Returns:
            (position, delimiter) tuple or None
        """
        for struct in sorted(allowed, key=len, reverse=True):
            struct_len = len(struct)
            if content[pos : pos + struct_len] == struct:
                return pos, struct
        return None

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
        # Handle special cases
        if not close_char:
            return self._handle_no_close_char(content, open_pos, open_char)

        if close_char == "\n":
            return self._find_python_block_end(content, open_pos)

        # Standard brace/bracket matching with nesting support
        return self._find_nested_close(content, open_pos, open_char, close_char)

    def _handle_no_close_char(self, content: str, open_pos: int, open_char: str) -> int:
        """Handle delimiters with no explicit close character.

        Args:
            content: Source code
            open_pos: Position of opening delimiter
            open_char: Opening delimiter string

        Returns:
            Position after statement end
        """
        # No explicit close (e.g., arrow functions with expression bodies)
        # Find the next statement terminator
        pos = open_pos + len(open_char)
        # For now, just extend to end of line as a simple heuristic
        newline = content.find("\n", pos)
        return newline if newline != -1 else len(content)

    def _find_nested_close(
        self, content: str, open_pos: int, open_char: str, close_char: str
    ) -> int | None:
        """Find matching close with nesting support.

        Args:
            content: Source code
            open_pos: Position of opening delimiter
            open_char: Opening delimiter string
            close_char: Closing delimiter string

        Returns:
            Position after closing delimiter, or None if not found
        """
        pos = open_pos + len(open_char)
        depth = 1
        string_state = StringParseState(in_string=False, delimiter=None)
        content_len = len(content)

        while pos < content_len and depth > 0:
            char = content[pos]

            # Handle string boundaries
            string_state = self._process_string_in_matching(content, pos, char, string_state)

            if not string_state.in_string:
                # Skip comments
                comment_skip = self._skip_comment_in_matching(content, pos, content_len)
                if comment_skip is not None:
                    if comment_skip == -1:
                        break
                    pos = comment_skip
                    continue

                # Check for nested open or close
                depth_change = self._check_delimiter_nesting(
                    content, pos, open_char, close_char, depth
                )
                if depth_change is not None:
                    depth, new_pos = depth_change
                    if depth == 0:
                        return new_pos
                    pos = new_pos
                    continue

            pos += 1

        return None  # No matching close found

    def _process_string_in_matching(
        self, content: str, pos: int, char: str, state: StringParseState
    ) -> StringParseState:
        """Process string state during delimiter matching.

        Args:
            content: Source code
            pos: Current position
            char: Current character
            state: Current string parse state

        Returns:
            Updated StringParseState
        """
        if char in {'"', "'", "`"}:
            if not state.in_string:
                return StringParseState(in_string=True, delimiter=char)
            if char == state.delimiter and pos > 0 and content[pos - 1] != "\\":
                return StringParseState(in_string=False, delimiter=None)
        return state

    def _skip_comment_in_matching(self, content: str, pos: int, content_len: int) -> int | None:
        """Skip comment during delimiter matching.

        Args:
            content: Source code
            pos: Current position
            content_len: Length of content

        Returns:
            New position, -1 if end reached, None if no comment
        """
        if pos + 1 >= content_len:
            return None

        two_chars = content[pos : pos + 2]

        if two_chars in ("//", "#"):
            newline = content.find("\n", pos)
            return -1 if newline == -1 else newline
        if two_chars == "/*":
            end_comment = content.find("*/", pos + 2)
            return -1 if end_comment == -1 else end_comment + 2
        return None

    def _check_delimiter_nesting(
        self, content: str, pos: int, open_char: str, close_char: str, depth: int
    ) -> tuple[int, int] | None:
        """Check for nested open or close delimiters.

        Args:
            content: Source code
            pos: Current position
            open_char: Opening delimiter
            close_char: Closing delimiter
            depth: Current nesting depth

        Returns:
            (new_depth, new_position) or None if no match
        """
        # Check for nested open
        if content[pos : pos + len(open_char)] == open_char:
            return depth + 1, pos + len(open_char)

        # Check for close
        if content[pos : pos + len(close_char)] == close_char:
            new_depth = depth - 1
            new_pos = pos + len(close_char)
            return new_depth, new_pos

        return None

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
        return single_quotes % 2 == 1 or double_quotes % 2 == 1 or backticks % 2 == 1

    def _fallback_paragraph_chunking(self, content: str) -> list[DelimiterMatch]:
        r"""Fallback to paragraph-based chunking when no delimiters match.

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
        paragraphs = re.split(r"\n\n+", content)

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
            if (delimiter.is_keyword_delimiter and match.end_pos is not None) or (
                match.end_pos is not None and delimiter.start == "" and delimiter.end == ""
            ):  # type: ignore[union-attr]
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
                    nesting_level=match.nesting_level,  # Use the calculated nesting level from matching
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
        However, preserve nested structures (boundaries completely contained within others)
        to maintain nesting information.

        Tie-breaking rules (in order):
        1. Higher priority wins
        2. Same priority: Longer match wins
        3. Same length: Earlier position wins (deterministic)

        Args:
            boundaries: List of potentially overlapping boundaries

        Returns:
            List of non-overlapping boundaries (with nested structures preserved)
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

        # Keep non-overlapping boundaries, but allow nested structures with same priority
        result: list[Boundary] = []

        for boundary in sorted_boundaries:
            # Check if this boundary overlaps with any selected boundary
            # Allow nesting only if priorities are equal (true nested structures like functions inside functions)
            should_add = True
            for selected in result:
                if self._boundaries_overlap(boundary, selected):
                    # Check if one is nested inside the other
                    is_nested = (
                        boundary.start >= selected.start and boundary.end <= selected.end
                    ) or (selected.start >= boundary.start and selected.end <= boundary.end)

                    # Only allow nesting if priorities are equal (same kind of structure)
                    same_priority = boundary.delimiter.priority == selected.delimiter.priority  # type: ignore[union-attr]

                    if not (is_nested and same_priority):
                        # Not a same-priority nested structure, skip this boundary
                        should_add = False
                        break

            if should_add:
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
            # Extract chunk text
            chunk_text = content[boundary.start : boundary.end]

            # Always calculate line ranges first
            # For proper line range metadata, always expand to full lines
            start_line, end_line = self._expand_to_lines(boundary.start, boundary.end, lines)

            # Extract the full lines
            line_start_pos = sum(len(line) for line in lines[: start_line - 1])
            line_end_pos = sum(len(line) for line in lines[:end_line])
            chunk_text = content[line_start_pos:line_end_pos]
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
        self,
        boundary: Boundary,
        text: str,
        start_line: int,
        end_line: int,
        context: dict[str, Any] | None,
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
