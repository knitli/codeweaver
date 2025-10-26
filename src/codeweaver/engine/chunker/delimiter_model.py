# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Delimiter model and supporting classes for pattern-based chunking.

This module provides the core data structures for delimiter-based code chunking:

- Delimiter: Concrete delimiter definition with semantic metadata
- DelimiterMatch: A matched delimiter occurrence in source code
- Boundary: A complete delimiter boundary (start + end matched)

These classes work together to implement pattern-based chunking across 170+ languages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from pydantic import Field, PositiveInt

from codeweaver.core.types.models import BasedModel
from codeweaver.engine.chunker.delimiters.kind import DelimiterKind


if TYPE_CHECKING:
    from codeweaver.engine.chunker.delimiters.patterns import DelimiterPattern


class Delimiter(BasedModel):
    """Concrete delimiter definition with semantic metadata.

    Represents a specific delimiter pattern that can be used for code chunking.
    Delimiters define start/end patterns along with semantic classification and
    processing rules.

    Attributes:
        start: Start delimiter pattern
        end: End delimiter pattern
        kind: Semantic classification of the delimiter
        priority: Processing priority (higher values processed first)
        inclusive: Whether to include delimiters in chunk content
        take_whole_lines: Whether to expand chunks to line boundaries
        nestable: Whether this delimiter can nest within itself

    Example:
        >>> delimiter = Delimiter(
        ...     start="def ",
        ...     end=":",
        ...     kind=DelimiterKind.FUNCTION,
        ...     priority=70,
        ...     inclusive=True,
        ...     take_whole_lines=True,
        ...     nestable=True,
        ... )
    """

    start: Annotated[str, Field(description="Start delimiter pattern")]
    end: Annotated[str, Field(description="End delimiter pattern")]
    kind: Annotated[DelimiterKind, Field(description="Semantic type of delimiter")]
    priority: Annotated[PositiveInt, Field(description="Processing priority (higher first)")]
    inclusive: Annotated[bool, Field(default=True, description="Include delimiters in chunk")]
    take_whole_lines: Annotated[bool, Field(default=True, description="Expand to line boundaries")]
    nestable: Annotated[bool, Field(default=True, description="Can nest within itself")]

    def _telemetry_keys(self) -> None:
        """Get telemetry keys for the delimiter model."""
        return

    @property
    def is_keyword_delimiter(self) -> bool:
        """Check if this delimiter uses keyword matching (empty end).
        
        Returns:
            True if this delimiter has an empty end string, indicating it needs
            keyword-to-structure binding rather than explicit end matching.
        """
        return self.end == ""

    @classmethod
    def from_pattern(cls, pattern: DelimiterPattern) -> list[Delimiter]:
        """Expand pattern to concrete delimiters.

        Converts a DelimiterPattern (which may specify multiple start/end combinations)
        into a list of concrete Delimiter instances.

        Args:
            pattern: The delimiter pattern to expand

        Returns:
            List of Delimiter instances, one per start/end combination

        Example:
            >>> from codeweaver.engine.chunker.delimiters import DelimiterPattern
            >>> pattern = DelimiterPattern(
            ...     starts=["if", "while"], ends=[":", "then"], kind=DelimiterKind.CONDITIONAL
            ... )
            >>> delimiters = Delimiter.from_pattern(pattern)
            >>> len(delimiters)
            4  # 2 starts * 2 ends
        """
        from codeweaver.engine.chunker.delimiters.patterns import expand_pattern

        expanded = expand_pattern(pattern)
        return [
            cls(
                start=d["start"],
                end=d["end"],
                kind=d.get("kind", DelimiterKind.UNKNOWN),
                priority=d.get("priority_override", pattern.kind.default_priority),
                inclusive=d.get("inclusive", pattern.kind.infer_inline_strategy().inclusive),
                take_whole_lines=d.get(
                    "take_whole_lines", pattern.kind.infer_inline_strategy().take_whole_lines
                ),
                nestable=d.get("nestable", pattern.kind.infer_nestable()),
            )
            for d in expanded
        ]


@dataclass
class DelimiterMatch:
    """A matched delimiter occurrence in source code.

    Represents a single delimiter match found during scanning, tracking its
    position and nesting context. Matches are paired during boundary extraction
    to form complete Boundary objects.

    Attributes:
        delimiter: The delimiter that was matched
        start_pos: Character position of the match start
        end_pos: Character position of the match end (None for start delimiters)
        nesting_level: Depth of nesting at this match (0 = top level)

    Example:
        >>> match = DelimiterMatch(
        ...     delimiter=my_delimiter, start_pos=42, end_pos=None, nesting_level=0
        ... )
        >>> match.is_start
        True
    """

    delimiter: Delimiter
    start_pos: int
    end_pos: int | None = None
    nesting_level: int = 0

    @property
    def is_start(self) -> bool:
        """Check if this is a start delimiter match.

        Returns:
            True if this match represents a start delimiter (no end_pos set)
        """
        return self.end_pos is None


@dataclass
class Boundary:
    """A complete delimiter boundary (start + end matched).

    Represents a fully matched delimiter pair, defining a chunk boundary with
    both start and end positions. Boundaries are used to extract chunk content
    and metadata.

    Attributes:
        start: Character position of boundary start
        end: Character position of boundary end
        delimiter: The delimiter that defines this boundary
        nesting_level: Depth of nesting for this boundary (0 = top level)

    Raises:
        ValueError: If start >= end (invalid boundary)

    Example:
        >>> boundary = Boundary(start=0, end=100, delimiter=my_delimiter, nesting_level=0)
        >>> boundary.length
        100
    """

    start: int
    end: int
    delimiter: Delimiter
    nesting_level: int

    def __post_init__(self) -> None:
        """Validate boundary positions after initialization.

        Raises:
            ValueError: If start position is >= end position
        """
        if self.start >= self.end:
            msg = f"Invalid boundary: start {self.start} >= end {self.end}"
            raise ValueError(msg)

    @property
    def length(self) -> int:
        """Calculate the length of this boundary.

        Returns:
            Number of characters between start and end positions
        """
        return self.end - self.start


__all__ = ("Boundary", "Delimiter", "DelimiterMatch")
