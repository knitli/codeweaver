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

from codeweaver.core import CodeChunk, Metadata, Span, get_blake_hash, uuid7
from codeweaver.engine.chunker.base import AdaptiveChunkBehavior, BaseChunker, ChunkGovernor
from codeweaver.engine.chunker.delimiter_model import Boundary, Delimiter, DelimiterMatch
from codeweaver.engine.chunker.exceptions import (
    BinaryFileError,
    ChunkingError,
    ChunkLimitExceededError,
    ParseError,
)


if TYPE_CHECKING:
    from codeweaver.core import DiscoveredFile


PERFORMANCE_THRESHOLD_MS = 1000.0  # 1 second

# Token estimation: ~4 chars per token for code (conservative)
# This is a heuristic; actual tokenization varies by model
CHARS_PER_TOKEN = 4

# Sliding window overlap for force splits (as fraction of window)
SLIDING_WINDOW_OVERLAP = 0.1

# Minimum lines for paragraph-based splitting
MIN_LINES_FOR_PARAGRAPH_SPLIT = 3

# Lazy-loaded semantic boundaries set to avoid import cycles
_SEMANTIC_BOUNDARIES: set | None = None


def _get_semantic_boundaries():
    """Get the set of semantic boundary delimiter kinds.

    Lazily loads to avoid import cycles at module level.
    """
    global _SEMANTIC_BOUNDARIES
    if _SEMANTIC_BOUNDARIES is None:
        from codeweaver.core.types.delimiter import DelimiterKind

        _SEMANTIC_BOUNDARIES = {
            DelimiterKind.FUNCTION,
            DelimiterKind.CLASS,
            DelimiterKind.METHOD,
            DelimiterKind.INTERFACE,
            DelimiterKind.STRUCT,
            DelimiterKind.ENUM,
            DelimiterKind.PARAGRAPH,
            DelimiterKind.MODULE,
            DelimiterKind.NAMESPACE,
        }
    return _SEMANTIC_BOUNDARIES


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

        from codeweaver.core import UUID7Hex
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
                    chunks, boundaries = self._process_matches_to_chunks(
                        matches, content, file_path, source_id, context, governor
                    )

                    # Phase 4: Apply adaptive sizing
                    governor.check_timeout()
                    chunks = self._apply_adaptive_sizing(
                        chunks, content, boundaries, file_path, source_id, context
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

        from codeweaver.engine.config import PerformanceSettings

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
    ) -> tuple[list[CodeChunk], list[Boundary]]:
        """Process delimiter matches into code chunks.

        Args:
            matches: Delimiter matches to process
            content: Source code content
            file_path: Optional file path
            source_id: Source identifier
            context: Optional context
            governor: Resource governor for tracking

        Returns:
            Tuple of (list of code chunks, list of resolved boundaries)
        """
        # Phase 2: Extract boundaries from matches
        governor.check_timeout()
        boundaries = self._extract_boundaries(matches)

        if not boundaries:
            return [], []

        # Phase 3: Resolve overlapping boundaries
        governor.check_timeout()
        resolved = self._resolve_overlaps(boundaries)

        # Convert boundaries to chunks
        chunks = self._boundaries_to_chunks(resolved, content, file_path, source_id, context)

        # Register each chunk with the governor for resource tracking
        for _ in chunks:
            governor.register_chunk()

        return chunks, resolved

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
                    content, struct_start, struct_char or "", structural_pairs.get(struct_char, "")
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
                return pos, cast(str, struct)
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
            delimiter: Delimiter = match.delimiter
            # Keyword delimiters with empty ends that have been matched already have both positions
            # Also treat matches with both start and end positions as complete
            if (delimiter.is_keyword_delimiter and match.end_pos is not None) or (
                match.end_pos is not None and delimiter.start == "" and delimiter.end == ""
            ):
                keyword_matches.append(match)
            else:
                explicit_matches.append(match)

        # Handle keyword delimiter matches - they're already complete
        for match in keyword_matches:
            delimiter: Delimiter = match.delimiter
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
            delimiter: Delimiter = match.delimiter
            delimiter_key: str = f"{delimiter.start}_{delimiter.end}"

            if delimiter_key not in delimiter_stacks:
                delimiter_stacks[delimiter_key] = []

            if match.is_start:
                # Start delimiter - push to stack
                current_level: int = (
                    len(delimiter_stacks[delimiter_key]) if delimiter.nestable else 0
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
            key=lambda b: (-cast(int, b.delimiter.priority), -(b.end - b.start), b.start),
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

                    # Only allow nesting if priorities are equal (same category of structure)
                    same_priority = boundary.delimiter.priority == selected.delimiter.priority

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
        from codeweaver.core import ExtCategory

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
                ext_category=ExtCategory.from_file(file_path) if file_path else None,
                line_range=Span(
                    start_line, end_line, source_id
                ),  # All spans from same file share source_id
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
        delimiter: Delimiter = boundary.delimiter

        # Build context dict with proper types
        chunk_context: dict[str, Any] = {
            "chunker_type": "delimiter",
            "content_hash": str(get_blake_hash(text)),
            "delimiter_kind": delimiter.kind.name,
            "delimiter_start": delimiter.start,
            "delimiter_end": delimiter.end,
            "priority": int(delimiter.priority),
            "nesting_level": boundary.nesting_level,
        }

        # Merge with provided context
        if context:
            chunk_context |= context

        metadata: Metadata = {
            "chunk_id": uuid7(),
            "created_at": datetime.now(UTC).timestamp(),
            "name": f"{delimiter.kind.name.title()} at line {start_line}",
            "kind": delimiter.kind,  # Add kind at top level for test compatibility
            "nesting_level": boundary.nesting_level,  # Add nesting_level at top level too
            "priority": int(delimiter.priority),  # Add priority at top level
            "line_start": start_line,  # Add line_start for test compatibility
            "line_end": end_line,  # Add line_end for test compatibility
            "context": chunk_context,
        }

        # Add fallback indicator at top level if present in context
        if context and context.get("fallback_to_generic"):
            metadata["fallback_to_generic"] = True

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

        # Initialize delimiters list
        delimiters: list[Delimiter] = []

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
                    for pattern in custom_delim.delimiters:
                        delimiters.extend(Delimiter.from_pattern(pattern))

        # Load from delimiter families system
        family = LanguageFamily.from_known_language(language)
        patterns = get_family_patterns(family)

        # Convert patterns to delimiters
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

    # =========================================================================
    # Adaptive Chunk Sizing Methods
    # =========================================================================

    def _estimate_tokens(self, content: str) -> int:
        """Estimate token count for content.

        Uses a simple character-based heuristic. For code, ~4 characters per
        token is a reasonable approximation across most tokenizers.

        Args:
            content: Text content to estimate

        Returns:
            Estimated token count
        """
        return len(content) // CHARS_PER_TOKEN

    def _apply_adaptive_sizing(
        self,
        chunks: list[CodeChunk],
        content: str,
        boundaries: list[Boundary],
        file_path: Path | None,
        source_id: Any,
        context: dict[str, Any] | None,
    ) -> list[CodeChunk]:
        """Post-process chunks with adaptive size enforcement.

        Iterates through chunks and applies size-based actions:
        - MERGE: Combine undersized chunks with neighbors
        - KEEP: Leave chunk as-is
        - TRY_CHILDREN: Attempt semantic split using child boundaries
        - FORCE_SPLIT: Mechanically split oversized chunks

        Args:
            chunks: Initial chunks from boundary extraction
            content: Full source content
            boundaries: Resolved boundaries that created the chunks
            file_path: Optional source file path
            source_id: Source identifier for spans
            context: Optional additional context

        Returns:
            List of adaptively-sized chunks
        """
        if not chunks:
            return chunks

        from codeweaver.core.types.delimiter import DelimiterKind

        semantic_boundaries = _get_semantic_boundaries()
        result: list[CodeChunk] = []
        i = 0

        while i < len(chunks):
            chunk = chunks[i]
            tokens = self._estimate_tokens(chunk.content)
            action = self.governor.classify_chunk_size(tokens)

            # Don't merge semantic boundaries (functions, classes, paragraphs)
            # even if they're undersized
            chunk_kind = chunk.metadata.get("kind")
            if isinstance(chunk_kind, DelimiterKind) and chunk_kind in semantic_boundaries:
                result.append(chunk)
                i += 1
                continue

            if action == AdaptiveChunkBehavior.MERGE:
                # Try to merge with next chunk if available and compatible
                merged_chunk, next_idx = self._try_merge_forward(
                    chunks, i, content, file_path, source_id, context
                )
                result.append(merged_chunk)
                i = next_idx

            elif action == AdaptiveChunkBehavior.TRY_CHILDREN:
                if boundary := self._find_boundary_for_chunk(chunk, boundaries):
                    if children := self._rediscover_children(chunk.content, boundary):
                        split_chunks = self._split_at_children(
                            chunk, children, file_path, source_id, context
                        )
                        result.extend(split_chunks)
                    else:
                        # No semantic children, try paragraphs
                        para_chunks = self._split_at_paragraphs(
                            chunk, file_path, source_id, context
                        )
                        result.extend(para_chunks)
                else:
                    # Can't find boundary, try paragraph split
                    para_chunks = self._split_at_paragraphs(chunk, file_path, source_id, context)
                    result.extend(para_chunks)
                i += 1

            elif action == AdaptiveChunkBehavior.FORCE_SPLIT:
                # Must split - exceeds context window
                split_chunks = self._sliding_window_split(chunk, file_path, source_id, context)
                result.extend(split_chunks)
                i += 1

            else:  # KEEP
                result.append(chunk)
                i += 1

        return result

    def _try_merge_forward(
        self,
        chunks: list[CodeChunk],
        start_idx: int,
        content: str,
        file_path: Path | None,
        source_id: Any,
        context: dict[str, Any] | None,
    ) -> tuple[CodeChunk, int]:
        """Attempt to merge undersized chunk with following chunks.

        Merges chunks until the combined size reaches the floor threshold or
        we run out of mergeable chunks. Only merges chunks that are truly
        adjacent in the source content (no blank lines between them).

        Note: Semantic boundaries (functions, classes, paragraphs) are filtered
        out before reaching this function, so we only merge non-semantic chunks.
        """
        from codeweaver.core import ExtCategory

        current = chunks[start_idx]
        merged_content = current.content
        merged_start_line = current.line_range.start if current.line_range else 1
        merged_end_line = current.line_range.end if current.line_range else 1
        next_idx = start_idx + 1
        content_lines: list[str] | None = None

        while (
            next_idx < len(chunks)
            and self._estimate_tokens(merged_content) < self.governor.floor_tokens
        ):
            next_chunk = chunks[next_idx]

            # Adjacency check using line numbers - only merge truly adjacent chunks
            if current.line_range and next_chunk.line_range:
                gap = next_chunk.line_range.start - merged_end_line
                if gap != 1:  # Only merge adjacent chunks (no blank lines, no overlap)
                    break

                # Handle gap padding from source content if necessary
                gap_content = ""
                if gap > 1:
                    if content_lines is None:
                        content_lines = content.splitlines(keepends=True)
                    gap_content = "".join(
                        content_lines[merged_end_line : next_chunk.line_range.start - 1]
                    )
                merged_content = f"{merged_content.rstrip('\n')}\n{gap_content}{next_chunk.content}"
            else:
                # Merge anyway if line info is missing (fallback behavior)
                merged_content = f"{merged_content.rstrip('\n')}\n{next_chunk.content}"

            if next_chunk.line_range:
                merged_end_line = next_chunk.line_range.end
            next_idx += 1

        # Create merged chunk
        merged_metadata = self._build_merge_metadata(
            merged_content, merged_start_line, merged_end_line, context, content
        )

        merged_chunk = CodeChunk(
            content=merged_content,
            ext_category=ExtCategory.from_file(file_path) if file_path else None,
            line_range=Span(merged_start_line, merged_end_line, source_id),
            file_path=file_path,
            metadata=merged_metadata,
        )

        return merged_chunk, next_idx

    def _build_merge_metadata(
        self,
        content: str,
        start_line: int,
        end_line: int,
        context: dict[str, Any] | None,
        full_content: str | None = None,
    ) -> Metadata:
        """Build metadata for a merged chunk.

        Args:
            content: Merged chunk content
            start_line: Starting line number
            end_line: Ending line number
            context: Optional additional context
            full_content: Full source content for calculating nesting level

        Returns:
            Metadata dictionary
        """
        from codeweaver.engine.chunker.delimiter_model import DelimiterKind

        chunk_context: dict[str, Any] = {
            "chunker_type": "delimiter",
            "content_hash": str(get_blake_hash(content)),
            "delimiter_kind": DelimiterKind.GENERIC.name,
            "adaptive_action": "merged",
        }

        if context:
            chunk_context |= context

        # Calculate nesting level from full content if available
        nesting_level = 0
        if full_content is not None:
            # Find position of start_line in full content
            lines = full_content.splitlines(keepends=True)
            if 0 < start_line <= len(lines):
                pos = sum(len(line) for line in lines[: start_line - 1])
                nesting_level = self._calculate_nesting_level(full_content, pos)

        metadata: Metadata = {
            "chunk_id": uuid7(),
            "created_at": datetime.now(UTC).timestamp(),
            "name": f"Merged block at line {start_line}",
            "kind": DelimiterKind.GENERIC,
            "nesting_level": nesting_level,
            "priority": DelimiterKind.GENERIC.default_priority,
            "line_start": start_line,
            "line_end": end_line,
            "context": chunk_context,
        }

        # Add fallback indicator at top level if present in context (same logic as _build_metadata)
        if context and context.get("fallback_to_generic"):
            metadata["fallback_to_generic"] = True

        return metadata

    def _find_boundary_for_chunk(
        self, chunk: CodeChunk, boundaries: list[Boundary]
    ) -> Boundary | None:
        """Find the boundary that created a given chunk.

        Args:
            chunk: The chunk to find the boundary for
            boundaries: List of boundaries from extraction

        Returns:
            The matching Boundary, or None if not found
        """
        if not chunk.line_range:
            return None

        chunk_start = chunk.line_range.start
        chunk_end = chunk.line_range.end

        return next(
            (
                boundary
                for boundary in boundaries
                if (
                    chunk.metadata
                    and chunk.metadata.get("line_start") == chunk_start
                    and chunk.metadata.get("line_end") == chunk_end
                )
            ),
            None,
        )

    # spellchecker:off
    def _rediscover_children(self, content: str, parent: Boundary) -> list[Boundary]:
        """Re-run delimiter matching to find child boundaries for splitting.

        Only finds delimiters with LOWER priority than parent (more specific
        structural elements). For example, if the parent is a CLASS(85), this
        will find FUNCTIONs(70), METHODs(65), etc. within it.

        Args:
            content: The chunk content to search within
            parent: The boundary that defined the oversized chunk

        Returns:
            List of child boundaries sorted by position, or empty if none found
        """
        # spellchecker:on
        # Run delimiter matching on this content
        matches = self._find_delimiter_matches(content)
        if not matches:
            return []

        # Extract boundaries
        boundaries = self._extract_boundaries(matches)
        if not boundaries:
            return []

        # Filter to lower priority than parent (more specific elements)
        parent_priority = parent.delimiter.priority
        children = [b for b in boundaries if b.delimiter.priority < parent_priority]

        # Also require minimum size to avoid fragmenting into tiny pieces
        min_child_chars = self.governor.floor_tokens * CHARS_PER_TOKEN
        children = [b for b in children if (b.end - b.start) >= min_child_chars]

        # Sort by position
        return sorted(children, key=lambda b: b.start)

    def _split_at_children(
        self,
        chunk: CodeChunk,
        children: list[Boundary],
        file_path: Path | None,
        source_id: Any,
        context: dict[str, Any] | None,
    ) -> list[CodeChunk]:
        """Split a chunk at child boundary positions.

        Creates new chunks from each child boundary, plus chunks for any
        content between children (preamble, interludes, postamble).

        Args:
            chunk: The oversized chunk to split
            children: Child boundaries within the chunk
            file_path: Optional source file path
            source_id: Source identifier
            context: Optional additional context

        Returns:
            List of split chunks
        """
        result: list[CodeChunk] = []
        content = chunk.content
        lines = content.splitlines(keepends=True)
        base_line = chunk.line_range.start if chunk.line_range else 1

        current_pos = 0

        for child in children:
            # Add any content before this child (preamble/interlude)
            if child.start > current_pos:
                preamble = content[current_pos : child.start]
                if preamble.strip():  # Only if non-empty
                    preamble_start, preamble_end = self._expand_to_lines(
                        current_pos, child.start, lines
                    )
                    preamble_chunk = self._create_split_chunk(
                        preamble,
                        base_line + preamble_start - 1,
                        base_line + preamble_end - 1,
                        file_path,
                        source_id,
                        context,
                        "preamble",
                    )
                    result.append(preamble_chunk)

            # Add the child boundary as a chunk
            child_content = content[child.start : child.end]
            child_start, child_end = self._expand_to_lines(child.start, child.end, lines)
            child_chunk = self._create_split_chunk(
                child_content,
                base_line + child_start - 1,
                base_line + child_end - 1,
                file_path,
                source_id,
                context,
                "child",
                child.delimiter,
            )
            result.append(child_chunk)

            current_pos = child.end

        # Add any remaining content (postamble)
        if current_pos < len(content):
            postamble = content[current_pos:]
            if postamble.strip():
                postamble_start, postamble_end = self._expand_to_lines(
                    current_pos, len(content), lines
                )
                postamble_chunk = self._create_split_chunk(
                    postamble,
                    base_line + postamble_start - 1,
                    base_line + postamble_end - 1,
                    file_path,
                    source_id,
                    context,
                    "postamble",
                )
                result.append(postamble_chunk)

        return result or [chunk]  # Return original if split failed

    def _create_split_chunk(
        self,
        content: str,
        start_line: int,
        end_line: int,
        file_path: Path | None,
        source_id: Any,
        context: dict[str, Any] | None,
        split_type: str,
        delimiter: Delimiter | None = None,
    ) -> CodeChunk:
        """Create a chunk from split content.

        Args:
            content: Chunk content
            start_line: Starting line number
            end_line: Ending line number
            file_path: Optional source file path
            source_id: Source identifier
            context: Optional additional context
            split_type: Type of split ("child", "preamble", "postamble", etc.)
            delimiter: Optional delimiter that defined this chunk

        Returns:
            A new CodeChunk
        """
        from codeweaver.core import ExtCategory
        from codeweaver.engine.chunker.delimiter_model import DelimiterKind

        kind = delimiter.kind if delimiter else DelimiterKind.GENERIC
        priority = delimiter.priority if delimiter else DelimiterKind.GENERIC.default_priority

        chunk_context: dict[str, Any] = {
            "chunker_type": "delimiter",
            "content_hash": str(get_blake_hash(content)),
            "delimiter_kind": kind.name,
            "adaptive_action": f"split_{split_type}",
        }

        if context:
            chunk_context |= context

        metadata: Metadata = {
            "chunk_id": uuid7(),
            "created_at": datetime.now(UTC).timestamp(),
            "name": f"{kind.name.title()} at line {start_line}",
            "kind": kind,
            "nesting_level": 0,
            "priority": int(priority),
            "line_start": start_line,
            "line_end": end_line,
            "context": chunk_context,
        }

        return CodeChunk(
            content=content,
            ext_category=ExtCategory.from_file(file_path) if file_path else None,
            line_range=Span(start_line, end_line, source_id),
            file_path=file_path,
            metadata=metadata,
        )

    def _split_at_paragraphs(
        self,
        chunk: CodeChunk,
        file_path: Path | None,
        source_id: Any,
        context: dict[str, Any] | None,
    ) -> list[CodeChunk]:
        """Split chunk at paragraph boundaries (blank lines).

        Fallback when no semantic children are found. Accumulates paragraphs
        until reaching optimal size, then starts a new chunk.

        Args:
            chunk: The oversized chunk to split
            file_path: Optional source file path
            source_id: Source identifier
            context: Optional additional context

        Returns:
            List of paragraph-based chunks
        """
        import re

        content = chunk.content
        base_line = chunk.line_range.start if chunk.line_range else 1

        # Split by double newlines (paragraph boundaries)
        paragraphs = re.split(r"\n\n+", content)

        if len(paragraphs) < MIN_LINES_FOR_PARAGRAPH_SPLIT:
            # Not enough paragraphs, fall back to sliding window
            return self._sliding_window_split(chunk, file_path, source_id, context)

        result: list[CodeChunk] = []
        current_content = ""
        current_start_line = base_line
        line_offset = 0

        for para in paragraphs:
            if not para.strip():
                line_offset += para.count("\n") + 2  # Account for split
                continue

            # Check if adding this paragraph would exceed optimal
            test_content = current_content + ("\n\n" if current_content else "") + para
            test_tokens = self._estimate_tokens(test_content)

            if test_tokens > self.governor.acceptable_max_tokens and current_content:
                # Emit current chunk, start new one
                current_lines = current_content.count("\n") + 1
                split_chunk = self._create_split_chunk(
                    current_content,
                    current_start_line,
                    current_start_line + current_lines - 1,
                    file_path,
                    source_id,
                    context,
                    "paragraph",
                )
                result.append(split_chunk)

                current_content = para
                current_start_line = base_line + line_offset
            else:
                current_content = test_content

            line_offset += para.count("\n") + 2  # +2 for the split "\n\n"

        # Emit final chunk
        if current_content.strip():
            current_lines = current_content.count("\n") + 1
            split_chunk = self._create_split_chunk(
                current_content,
                current_start_line,
                current_start_line + current_lines - 1,
                file_path,
                source_id,
                context,
                "paragraph",
            )
            result.append(split_chunk)

        return result or [chunk]

    def _sliding_window_split(
        self,
        chunk: CodeChunk,
        file_path: Path | None,
        source_id: Any,
        context: dict[str, Any] | None,
    ) -> list[CodeChunk]:
        """Split chunk using sliding window with overlap.

        Last resort mechanical splitting when semantic and paragraph
        approaches fail. Respects line boundaries to avoid mid-line splits.

        Args:
            chunk: The oversized chunk to split
            file_path: Optional source file path
            source_id: Source identifier
            context: Optional additional context

        Returns:
            List of window-based chunks
        """
        content = chunk.content
        lines = content.splitlines(keepends=True)
        base_line = chunk.line_range.start if chunk.line_range else 1

        # Calculate window size in characters (based on optimal tokens)
        window_chars = self.governor.optimal_chunk_tokens * CHARS_PER_TOKEN
        overlap_chars = int(window_chars * SLIDING_WINDOW_OVERLAP)

        result: list[CodeChunk] = []
        current_pos = 0
        current_line = 0

        while current_pos < len(content):
            # Adjust to line boundary
            end_pos = current_pos
            end_line = current_line
            chars_so_far = 0

            for i in range(current_line, len(lines)):
                line_len = len(lines[i])
                if chars_so_far + line_len >= window_chars:
                    # Include this line if it doesn't push us too far over
                    if chars_so_far + line_len <= window_chars * 1.2:  # 20% tolerance
                        end_pos = current_pos + chars_so_far + line_len
                        end_line = i + 1
                    else:
                        end_pos = current_pos + chars_so_far
                        end_line = i
                    break
                chars_so_far += line_len
                end_pos = current_pos + chars_so_far
                end_line = i + 1
            else:
                # Reached end of content
                end_pos = len(content)
                end_line = len(lines)

            # Ensure we make progress
            if end_pos <= current_pos:
                end_pos = min(current_pos + window_chars, len(content))
                end_line = min(current_line + 1, len(lines))

            # Extract window content
            window_content = content[current_pos:end_pos]

            if window_content.strip():
                window_chunk = self._create_split_chunk(
                    window_content,
                    base_line + current_line,
                    base_line + end_line - 1,
                    file_path,
                    source_id,
                    context,
                    "window",
                )
                result.append(window_chunk)

            # Move forward with overlap
            overlap_start = max(current_pos, end_pos - overlap_chars)

            # Find line boundary for overlap start
            chars_counted = 0
            for i in range(current_line, end_line):
                line_len = len(lines[i])
                if current_pos + chars_counted + line_len > overlap_start:
                    current_line = i
                    current_pos = current_pos + chars_counted
                    break
                chars_counted += line_len
            else:
                current_pos = end_pos
                current_line = end_line

            # Prevent infinite loop
            if current_pos >= len(content) - 1:
                break

        return result or [chunk]


from codeweaver.core.types.delimiter import DelimiterDict, DelimiterKind, DelimiterPattern
from codeweaver.engine.chunker.delimiters.families import (
    LanguageFamily,
    detect_family_characteristics,
    detect_language_family,
)
from codeweaver.engine.chunker.delimiters.patterns import (
    ALL_PATTERNS,
    CONDITIONAL_PATTERN,
    FUNCTION_PATTERN,
    HASH_COMMENT_PATTERN,
    PARAGRAPH_PATTERN,
    STRING_QUOTE_PATTERN,
    expand_pattern,
    matches_pattern,
)


__all__ = (
    "ALL_PATTERNS",
    "CHARS_PER_TOKEN",
    "CONDITIONAL_PATTERN",
    "FUNCTION_PATTERN",
    "HASH_COMMENT_PATTERN",
    "MIN_LINES_FOR_PARAGRAPH_SPLIT",
    "PARAGRAPH_PATTERN",
    "PERFORMANCE_THRESHOLD_MS",
    "SLIDING_WINDOW_OVERLAP",
    "STRING_QUOTE_PATTERN",
    "DelimiterChunker",
    "DelimiterDict",
    "DelimiterKind",
    "DelimiterPattern",
    "LanguageFamily",
    "StringParseState",
    "detect_family_characteristics",
    "detect_language_family",
    "expand_pattern",
    "matches_pattern",
)
