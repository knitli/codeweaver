# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Delimiter pattern definitions and expansion logic.

This module provides a DSL for defining reusable delimiter patterns that can be
expanded into concrete delimiter definitions. Patterns allow specifying multiple
start/end combinations with shared semantic properties.

Example:
    >>> function_pattern = DelimiterPattern(
    ...     starts=["def", "function", "fn"],
    ...     ends=[":", "{", "=>"],
    ...     kind=DelimiterKind.FUNCTION,
    ... )
    >>> delimiters = expand_pattern(function_pattern)
    >>> len(delimiters)
    9  # 3 starts * 3 ends
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from itertools import product
from typing import Annotated, Literal, NamedTuple, NotRequired, Required, TypedDict, overload

from pydantic import Field, PositiveInt

from codeweaver.services.chunker.delimiters.kind import DelimiterKind


class DelimiterDict(TypedDict, total=False):
    """A dictionary representation of a Delimiter.

    Just so we don't have to deal with forward refs.
    """

    start: Required[str]
    end: Required[str]
    kind: NotRequired[DelimiterKind]
    priority_override: NotRequired[PositiveInt]
    inclusive: NotRequired[bool]
    take_whole_lines: NotRequired[bool]
    nestable: NotRequired[bool]


class DelimiterPattern(NamedTuple):
    r"""A reusable delimiter pattern definition.

    Patterns specify a set of start and end delimiter strings along with their
    semantic classification. Multiple start/end combinations can be specified to
    reduce repetition when defining similar delimiters.

    Attributes:
        starts: List of possible start delimiter strings
        ends: List of possible end delimiter strings, or "ANY" for wildcard
        kind: Semantic classification of the delimiter
        priority_override: Optional priority override (None = use kind.default_priority)
        inclusive: Whether to include delimiters in chunk (None = infer from kind)
        take_whole_lines: Whether to expand to whole lines (None = infer from kind)
        nestable: Whether delimiter can nest (None = infer from kind)

    Special values:
        ends="ANY": Accepts any end delimiter (represented as empty string)

    Example:
        >>> # Function keywords with any end delimiter
        >>> DelimiterPattern(
        ...     starts=["def", "function", "fn"], ends="ANY", kind=DelimiterKind.FUNCTION
        ... )

        >>> # Paragraph delimiter with custom priority
        >>> DelimiterPattern(
        ...     starts=["\n\n", "\r\n\r\n"],
        ...     ends=["\n\n", "\r\n\r\n"],
        ...     kind=DelimiterKind.PARAGRAPH,
        ...     priority_override=40,
        ... )
    """

    starts: Annotated[list[str], Field(description="The start delimiters.")]

    ends: Annotated[list[str] | Literal["ANY"], Field(description="The end delimiters.")]

    kind: Annotated[DelimiterKind, Field(description="The kind of delimiter.")] = (
        DelimiterKind.UNKNOWN
    )
    priority_override: (
        Annotated[
            PositiveInt,
            Field(
                gt=0,
                lt=100,
                default_factory=lambda data: data["kind"].default_priority,
                description="The priority of the delimiter.",
            ),
        ]
        | None
    ) = None
    inclusive: Annotated[
        bool | None,
        Field(
            description="Whether to include the delimiters in the resulting chunk.",
            default_factory=lambda data: data["kind"].infer_inline_strategy().inclusive,
        ),
    ] = None
    take_whole_lines: Annotated[
        bool | None,
        Field(
            description="Whether to expand the chunk to include whole lines if matched within it.",
            default_factory=lambda data: data["kind"].infer_inline_strategy().take_whole_lines,
        ),
    ] = None
    nestable: Annotated[
        bool | None,
        Field(
            default_factory=lambda data: data["kind"].infer_nestable(),
            description="Whether the delimiter can be nested.",
        ),
    ] = None

    formatter: Annotated[
        Callable[[str], str] | None,
        Field(
            exclude=True, description="An optional formatter function to apply to the chunk text."
        ),
    ] = None

    @cached_property
    def as_dicts(self) -> tuple[DelimiterDict, ...]:
        """Return a dictionary representation of the pattern with lists converted to strings.

        Note that this does not expand the pattern into all combinations.
        Use `expand_pattern` for that purpose.
        """
        return tuple(
            DelimiterDict(
                start=start,
                end=end if self.ends != "ANY" else "",
                kind=self.kind,
                priority_override=self.priority_override or self.kind.default_priority,
                inclusive=self.inclusive or self.kind.infer_inline_strategy().inclusive,
                take_whole_lines=self.take_whole_lines
                or self.kind.infer_inline_strategy().take_whole_lines,
                nestable=self.nestable or self.kind.infer_nestable(),
            )
            for start, end in zip(
                self.starts,
                self.ends if self.ends != "ANY" else [""] * len(self.starts),
                strict=True,
            )
        )

    def format(self, text: str) -> str:
        """Apply the optional formatter function to the given text.

        If no formatter is defined, returns the text unchanged.

        Args:
            text: The text to format

        Returns:
            The formatted text, or the original text if no formatter is defined.
        """
        return self.formatter(text) if self.formatter else text


def expand_pattern(pattern: DelimiterPattern) -> list[DelimiterDict]:
    """Expand a DelimiterPattern into concrete DelimiterDict entries.

    Generates all combinations of start/end delimiters specified in the pattern,
    with consistent semantic properties across all combinations.

    Args:
        pattern: The delimiter pattern to expand

    Returns:
        List of DelimiterDict entries, one per start/end combination

    Example:
        >>> pattern = DelimiterPattern(
        ...     starts=["if", "while"], ends=[":", "then"], kind=DelimiterKind.CONDITIONAL
        ... )
        >>> delims = expand_pattern(pattern)
        >>> len(delims)
        4  # 2 starts * 2 ends
        >>> delims[0]["start"]
        'if'
        >>> delims[0]["end"]
        ':'
    """
    results: list[DelimiterDict] = []

    # Handle "ANY" end wildcard as empty string
    pattern = pattern if pattern.ends != "ANY" else pattern._replace(ends=[""])
    results.extend(
        DelimiterDict(
            start=start,
            end=end,
            kind=pattern.kind,
            priority_override=pattern.priority_override or pattern.kind.default_priority,
            inclusive=pattern.inclusive or pattern.kind.infer_inline_strategy().inclusive,
            take_whole_lines=pattern.take_whole_lines
            or pattern.kind.infer_inline_strategy().take_whole_lines,
            nestable=pattern.nestable or pattern.kind.infer_nestable(),
        )
        for start, end in product(pattern.starts, pattern.ends)
    )
    return results


def matches_pattern(start: str, end: str, pattern: DelimiterPattern) -> bool:
    """Test if delimiter matches a pattern.

    Case-insensitive matching of delimiter strings against pattern specifications.
    Useful for classifying unknown delimiters or validating delimiter definitions.

    Args:
        start: Start delimiter string to test
        end: End delimiter string to test
        pattern: Pattern to match against

    Returns:
        True if delimiter matches pattern, False otherwise

    Example:
        >>> pattern = DelimiterPattern(
        ...     starts=["def", "function"], ends="ANY", kind=DelimiterKind.FUNCTION
        ... )
        >>> matches_pattern("def", ":", pattern)
        True
        >>> matches_pattern("DEF", "end", pattern)  # case-insensitive
        True
        >>> matches_pattern("class", ":", pattern)
        False
    """
    # Case-insensitive start matching
    start_match = start.lower() in (s.lower() for s in pattern.starts)

    # Handle "ANY" end wildcard or specific end matching
    end_match = True if pattern.ends == "ANY" else end.lower() in (e.lower() for e in pattern.ends)

    return start_match and end_match


# Core patterns extracted from inference methods
# These represent the canonical delimiter patterns used across languages

# Code element patterns
FUNCTION_PATTERN = DelimiterPattern(
    starts=[
        "def",
        "function",
        "fn",
        "fun",
        "method",
        "sub",
        "proc",
        "procedure",
        "func",
        "lambda",
        "subroutine",
        "macro",
        "init",
        "main",
        "entry",
        "constructor",
        "destructor",
        "ctor",
        "dtor",
        "define",
        "functor",
    ],
    ends="ANY",
    kind=DelimiterKind.FUNCTION,
)

CLASS_PATTERN = DelimiterPattern(starts=["class"], ends="ANY", kind=DelimiterKind.CLASS)

STRUCT_PATTERN = DelimiterPattern(starts=["struct", "type"], ends="ANY", kind=DelimiterKind.STRUCT)

INTERFACE_PATTERN = DelimiterPattern(
    starts=["interface", "trait", "protocol", "sig"], ends="ANY", kind=DelimiterKind.INTERFACE
)

MODULE_PATTERN = DelimiterPattern(
    starts=["module", "namespace", "package", "mod", "extension"],
    ends="ANY",
    kind=DelimiterKind.MODULE,
)

ENUM_PATTERN = DelimiterPattern(starts=["enum", "enumeration"], ends="ANY", kind=DelimiterKind.ENUM)

TYPE_ALIAS_PATTERN = DelimiterPattern(
    starts=["type", "typedef", "typealias"], ends="ANY", kind=DelimiterKind.TYPE_ALIAS
)

IMPL_PATTERN = DelimiterPattern(starts=["impl"], ends="ANY", kind=DelimiterKind.IMPL_BLOCK)

EXTENSION_PATTERN = DelimiterPattern(
    starts=["extension", "extend"], ends="ANY", kind=DelimiterKind.EXTENSION
)

MODULE_BOUNDARY_PATTERN = DelimiterPattern(
    starts=["import", "from", "export", "require", "using", "include", "load", "open", "use"],
    ends="ANY",
    kind=DelimiterKind.MODULE_BOUNDARY,
)

# Control flow patterns
CONDITIONAL_PATTERN = DelimiterPattern(
    starts=[
        "if",
        "else",
        "elif",
        "unless",
        "switch",
        "case",
        "select",
        "when",
        "match",
        "where",
        "select case",
        "ifelse",
    ],
    ends="ANY",
    kind=DelimiterKind.CONDITIONAL,
)

CONDITIONAL_TEX_PATTERN = DelimiterPattern(
    starts=[r"\if", r"\\if"], ends=[r"\fi", r"\\fi"], kind=DelimiterKind.CONDITIONAL
)

LOOP_PATTERN = DelimiterPattern(
    starts=["for", "while", "do", "until", "loop", "foreach", "pareach", "parfor"],
    ends="ANY",
    kind=DelimiterKind.LOOP,
)

TRY_CATCH_PATTERN = DelimiterPattern(
    starts=["try", "catch", "except", "finally", "receive"],
    ends="ANY",
    kind=DelimiterKind.TRY_CATCH,
)

CONTEXT_MANAGER_PATTERN = DelimiterPattern(
    starts=["with", "async with"], ends="ANY", kind=DelimiterKind.CONTEXT_MANAGER
)

# Commentary patterns with cross-platform line ending support
HASH_COMMENT_PATTERN = DelimiterPattern(
    starts=["#"], ends=["\n", "\r\n", "\r"], kind=DelimiterKind.COMMENT_LINE
)

SLASH_COMMENT_PATTERN = DelimiterPattern(
    starts=["//"], ends=["\n", "\r\n", "\r"], kind=DelimiterKind.COMMENT_LINE
)

DASH_COMMENT_PATTERN = DelimiterPattern(
    starts=["--"], ends=["\n", "\r\n", "\r"], kind=DelimiterKind.COMMENT_LINE
)

SEMICOLON_COMMENT_PATTERN = DelimiterPattern(
    starts=[";"], ends=["\n", "\r\n", "\r"], kind=DelimiterKind.COMMENT_LINE
)

PERCENT_COMMENT_PATTERN = DelimiterPattern(
    starts=["%"], ends=["\n", "\r\n", "\r"], kind=DelimiterKind.COMMENT_LINE
)

EXCLAMATION_COMMENT_PATTERN = DelimiterPattern(
    starts=["!"], ends=["\n", "\r\n", "\r"], kind=DelimiterKind.COMMENT_LINE
)

STAR_COMMENT_PATTERN = DelimiterPattern(starts=["*"], ends=[";\n"], kind=DelimiterKind.COMMENT_LINE)

# Docstring patterns
DOCSTRING_SLASH_PATTERN = DelimiterPattern(
    starts=["///", "/**"], ends=["\n", "\r\n", "\r"], kind=DelimiterKind.DOCSTRING
)

DOCSTRING_SEMICOLON_PATTERN = DelimiterPattern(
    starts=[";;;", ";;"], ends=["\n", "\r\n", "\r"], kind=DelimiterKind.DOCSTRING
)

DOCSTRING_HASH_PATTERN = DelimiterPattern(
    starts=["###"], ends=["\n", "\r\n", "\r"], kind=DelimiterKind.DOCSTRING
)

DOCSTRING_QUOTE_PATTERN = DelimiterPattern(
    starts=["'''", '"""'], ends=["'''", '"""'], kind=DelimiterKind.DOCSTRING
)

DOCSTRING_RUBY_PATTERN = DelimiterPattern(
    starts=["=begin"], ends=["=end"], kind=DelimiterKind.DOCSTRING
)

DOCSTRING_ELIXIR_PATTERN = DelimiterPattern(
    starts=["@doc"], ends=["@enddoc", "@doc"], kind=DelimiterKind.DOCSTRING
)

DOCSTRING_MATLAB_PATTERN = DelimiterPattern(
    starts=["%{"], ends=["%}"], kind=DelimiterKind.DOCSTRING
)

# Comment block patterns
C_BLOCK_COMMENT_PATTERN = DelimiterPattern(
    starts=["/*", "/**"], ends=["*/"], kind=DelimiterKind.COMMENT_BLOCK
)

ML_BLOCK_COMMENT_PATTERN = DelimiterPattern(
    starts=["(*"], ends=["*)"], kind=DelimiterKind.COMMENT_BLOCK
)

HASKELL_BLOCK_COMMENT_PATTERN = DelimiterPattern(
    starts=["{-"], ends=["-}"], kind=DelimiterKind.COMMENT_BLOCK
)

LISP_BLOCK_COMMENT_PATTERN = DelimiterPattern(
    starts=["#|"], ends=["|#"], kind=DelimiterKind.COMMENT_BLOCK
)

JULIA_BLOCK_COMMENT_PATTERN = DelimiterPattern(
    starts=["#="], ends=["=#"], kind=DelimiterKind.COMMENT_BLOCK
)

NIM_BLOCK_COMMENT_PATTERN = DelimiterPattern(
    starts=["#["], ends=["]#"], kind=DelimiterKind.COMMENT_BLOCK
)

HTML_COMMENT_PATTERN = DelimiterPattern(
    starts=["<!--", "<!---"], ends=["-->", "--->"], kind=DelimiterKind.COMMENT_BLOCK
)

RUST_RAW_STRING_COMMENT_PATTERN = DelimiterPattern(
    starts=["r#", "r##", "r###", "r####", "r#####", "r######", "r#######"],
    ends=["#", "##", "###", "####", "#####", "######", "#######"],
    kind=DelimiterKind.COMMENT_BLOCK,
)

# Structural patterns
BRACE_BLOCK_PATTERN = DelimiterPattern(
    starts=["{", "{|"], ends=["}", "|}"], kind=DelimiterKind.BLOCK
)

LET_END_BLOCK_PATTERN = DelimiterPattern(
    starts=["let"], ends=["end", "in", "then"], kind=DelimiterKind.BLOCK
)

BEGIN_END_BLOCK_PATTERN = DelimiterPattern(starts=["begin"], ends=["end"], kind=DelimiterKind.BLOCK)

PROOF_BLOCK_PATTERN = DelimiterPattern(
    starts=["proof"], ends=["qed", "defined", "admitted"], kind=DelimiterKind.BLOCK
)

LATEX_BLOCK_PATTERN = DelimiterPattern(
    starts=[r"\begin{"], ends=[r"\end{"], kind=DelimiterKind.BLOCK
)

ARRAY_PATTERN = DelimiterPattern(starts=["["], ends=["]"], kind=DelimiterKind.ARRAY)

TUPLE_PATTERN = DelimiterPattern(starts=["("], ends=[")"], kind=DelimiterKind.BLOCK)

# Data patterns
PRAGMA_PATTERN = DelimiterPattern(
    starts=["pragma", "#pragma"], ends=[";", "", "\n"], kind=DelimiterKind.ANNOTATION
)

DECORATOR_PATTERN = DelimiterPattern(
    starts=["@@", "@", "decorator"], ends=["\n"], kind=DelimiterKind.DECORATOR
)

PROPERTY_PATTERN = DelimiterPattern(
    starts=["@property", "@classmethod", "@staticmethod"],
    ends=["\n"],
    kind=DelimiterKind.PROPERTY,
    priority_override=65,
)

# Template string patterns
TEMPLATE_ANGLE_PATTERN = DelimiterPattern(
    starts=["<", "<<", "<<<"], ends=[">", ">>", ">>>"], kind=DelimiterKind.TEMPLATE_STRING
)

TEMPLATE_PIPE_PATTERN = DelimiterPattern(
    starts=["<|", "<||", "<|||"], ends=["|>", "||>", "|||>"], kind=DelimiterKind.TEMPLATE_STRING
)

TEMPLATE_PERCENT_PATTERN = DelimiterPattern(
    starts=["<%", "<%="], ends=["%>"], kind=DelimiterKind.TEMPLATE_STRING
)

TEMPLATE_BRACE_PATTERN = DelimiterPattern(
    starts=["{{", "{%"], ends=["}}", "%}"], kind=DelimiterKind.TEMPLATE_STRING
)

TEMPLATE_BRACKET_PATTERN = DelimiterPattern(
    starts=["[|", "[||", "[|||", "[[", "[[["],
    ends=["|]", "||]", "|||]", "]]", "]]]"],
    kind=DelimiterKind.TEMPLATE_STRING,
)

TEMPLATE_TILDE_PATTERN = DelimiterPattern(
    starts=["<~", "<~~", "<~~~"], ends=["~>", "~~>", "~~~>"], kind=DelimiterKind.TEMPLATE_STRING
)

TEMPLATE_BACKTICK_PATTERN = DelimiterPattern(
    starts=["`"], ends=["`"], kind=DelimiterKind.TEMPLATE_STRING
)

# String patterns
STRING_QUOTE_PATTERN = DelimiterPattern(
    starts=["''", "'", '"', "`"], ends=["''", "'", '"', "`"], kind=DelimiterKind.STRING
)

STRING_RAW_PATTERN = DelimiterPattern(
    starts=["r'", 'r"', "r`"], ends=["'", '"', "`"], kind=DelimiterKind.STRING
)

STRING_FORMATTED_PATTERN = DelimiterPattern(
    starts=["f'", 'f"', "f`"], ends=["'", '"', "`"], kind=DelimiterKind.STRING
)

STRING_RAW_FORMATTED_PATTERN = DelimiterPattern(
    starts=["fr'", 'fr"', "fr`", "rf'", 'rf"', "rf`"],
    ends=["'", '"', "`"],
    kind=DelimiterKind.STRING,
)

STRING_BYTES_PATTERN = DelimiterPattern(
    starts=["b'", 'b"', "b`"], ends=["'", '"', "`"], kind=DelimiterKind.STRING
)

STRING_RAW_BYTES_PATTERN = DelimiterPattern(
    starts=["br'", 'br"', "br`", "rb'", 'rb"', "rb`"],
    ends=["'", '"', "`"],
    kind=DelimiterKind.STRING,
)

STRING_HASH_PATTERN = DelimiterPattern(
    starts=["#'", '#"', "#`"], ends=["'", '"', "`"], kind=DelimiterKind.STRING
)

STRING_BACKTICK_QUOTE_PATTERN = DelimiterPattern(
    starts=['"`', "'`", "#`"], ends=['"`', "'`", "`#"], kind=DelimiterKind.STRING
)

STRING_ANGLE_PATTERN = DelimiterPattern(starts=["<"], ends=[">"], kind=DelimiterKind.STRING)

STRING_STAR_PATTERN = DelimiterPattern(starts=["*"], ends=[";"], kind=DelimiterKind.STRING)

# Special case: Paragraph delimiter with custom priority
PARAGRAPH_PATTERN = DelimiterPattern(
    starts=["\n\n", "\r\n\r\n"],
    ends=["\n\n", "\r\n\r\n"],
    kind=DelimiterKind.PARAGRAPH,
    priority_override=40,  # Between COMMENT_BLOCK:45 and BLOCK:30
    inclusive=False,
    take_whole_lines=False,
    nestable=False,
)

# Whitespace patterns
NEWLINE_PATTERN = DelimiterPattern(
    starts=["\n", "\r\n", "\r"], ends=["\n", "\r\n", "\r"], kind=DelimiterKind.WHITESPACE
)

WHITESPACE_PATTERN = DelimiterPattern(
    starts=[" ", "\t", "    ", "  "], ends=[" ", "\t", "   ", "  "], kind=DelimiterKind.WHITESPACE
)

EMPTY_PATTERN = DelimiterPattern(starts=["", "\n"], ends=["\n", ""], kind=DelimiterKind.WHITESPACE)

# Collection of all patterns for iteration and lookup
ALL_PATTERNS: list[DelimiterPattern] = [
    # Code elements
    FUNCTION_PATTERN,
    CLASS_PATTERN,
    STRUCT_PATTERN,
    INTERFACE_PATTERN,
    MODULE_PATTERN,
    ENUM_PATTERN,
    TYPE_ALIAS_PATTERN,
    IMPL_PATTERN,
    EXTENSION_PATTERN,
    MODULE_BOUNDARY_PATTERN,
    # Control flow
    CONDITIONAL_PATTERN,
    CONDITIONAL_TEX_PATTERN,
    LOOP_PATTERN,
    TRY_CATCH_PATTERN,
    CONTEXT_MANAGER_PATTERN,
    # Commentary
    HASH_COMMENT_PATTERN,
    SLASH_COMMENT_PATTERN,
    DASH_COMMENT_PATTERN,
    SEMICOLON_COMMENT_PATTERN,
    PERCENT_COMMENT_PATTERN,
    EXCLAMATION_COMMENT_PATTERN,
    STAR_COMMENT_PATTERN,
    # Docstrings
    DOCSTRING_SLASH_PATTERN,
    DOCSTRING_SEMICOLON_PATTERN,
    DOCSTRING_HASH_PATTERN,
    DOCSTRING_QUOTE_PATTERN,
    DOCSTRING_RUBY_PATTERN,
    DOCSTRING_ELIXIR_PATTERN,
    DOCSTRING_MATLAB_PATTERN,
    # Comment blocks
    C_BLOCK_COMMENT_PATTERN,
    ML_BLOCK_COMMENT_PATTERN,
    HASKELL_BLOCK_COMMENT_PATTERN,
    LISP_BLOCK_COMMENT_PATTERN,
    JULIA_BLOCK_COMMENT_PATTERN,
    NIM_BLOCK_COMMENT_PATTERN,
    HTML_COMMENT_PATTERN,
    RUST_RAW_STRING_COMMENT_PATTERN,
    # Structural
    BRACE_BLOCK_PATTERN,
    LET_END_BLOCK_PATTERN,
    BEGIN_END_BLOCK_PATTERN,
    PROOF_BLOCK_PATTERN,
    LATEX_BLOCK_PATTERN,
    ARRAY_PATTERN,
    TUPLE_PATTERN,
    # Data
    PRAGMA_PATTERN,
    DECORATOR_PATTERN,
    PROPERTY_PATTERN,
    # Template strings
    TEMPLATE_ANGLE_PATTERN,
    TEMPLATE_PIPE_PATTERN,
    TEMPLATE_PERCENT_PATTERN,
    TEMPLATE_BRACE_PATTERN,
    TEMPLATE_BRACKET_PATTERN,
    TEMPLATE_TILDE_PATTERN,
    TEMPLATE_BACKTICK_PATTERN,
    # Strings
    STRING_QUOTE_PATTERN,
    STRING_RAW_PATTERN,
    STRING_FORMATTED_PATTERN,
    STRING_RAW_FORMATTED_PATTERN,
    STRING_BYTES_PATTERN,
    STRING_RAW_BYTES_PATTERN,
    STRING_HASH_PATTERN,
    STRING_BACKTICK_QUOTE_PATTERN,
    STRING_ANGLE_PATTERN,
    STRING_STAR_PATTERN,
    # Special cases
    PARAGRAPH_PATTERN,
    # Whitespace
    NEWLINE_PATTERN,
    WHITESPACE_PATTERN,
    EMPTY_PATTERN,
]


@overload
def kind_from_delimiter_tuple(
    start: None, end: None, delimiter: tuple[str, str]
) -> DelimiterKind: ...  # sourcery skip: docstrings-for-functions
@overload
def kind_from_delimiter_tuple(
    start: str, end: str
) -> DelimiterKind: ...  # sourcery skip: docstrings-for-functions
def kind_from_delimiter_tuple(
    start: str | None = None, end: str | None = None, delimiter: tuple[str, str] | None = None
) -> DelimiterKind:
    """Infer DelimiterKind from delimiter strings using patterns.

    Matches the provided start/end strings against known patterns to determine
    the most specific DelimiterKind classification.

    Args:
        start: Start delimiter string (optional if `delimiter` provided)
        end: End delimiter string (optional if `delimiter` provided)
        delimiter: tuple of (start, end) strings (optional if `start` and `end` provided)
    """
    if delimiter:
        start, end = delimiter
    if start is None or end is None:
        raise ValueError("Both start and end must be provided")
    return next(
        (
            pattern.kind
            for pattern in ALL_PATTERNS
            if (start, end) == (pattern.starts, pattern.ends)
        ),
        DelimiterKind.UNKNOWN,
    )


__all__ = (
    "ALL_PATTERNS",
    "ALL_PATTERNS",
    "ARRAY_PATTERN",
    "BEGIN_END_BLOCK_PATTERN",
    "BRACE_BLOCK_PATTERN",
    "CLASS_PATTERN",
    "CONDITIONAL_PATTERN",
    "CONDITIONAL_TEX_PATTERN",
    "CONTEXT_MANAGER_PATTERN",
    "C_BLOCK_COMMENT_PATTERN",
    "DASH_COMMENT_PATTERN",
    "DECORATOR_PATTERN",
    "DOCSTRING_ELIXIR_PATTERN",
    "DOCSTRING_HASH_PATTERN",
    "DOCSTRING_MATLAB_PATTERN",
    "DOCSTRING_QUOTE_PATTERN",
    "DOCSTRING_RUBY_PATTERN",
    "DOCSTRING_SEMICOLON_PATTERN",
    "DOCSTRING_SLASH_PATTERN",
    "EMPTY_PATTERN",
    "ENUM_PATTERN",
    "EXCLAMATION_COMMENT_PATTERN",
    "EXTENSION_PATTERN",
    # Core patterns
    "FUNCTION_PATTERN",
    "HASH_COMMENT_PATTERN",
    "HASKELL_BLOCK_COMMENT_PATTERN",
    "HTML_COMMENT_PATTERN",
    "IMPL_PATTERN",
    "INTERFACE_PATTERN",
    "JULIA_BLOCK_COMMENT_PATTERN",
    "LATEX_BLOCK_PATTERN",
    "LET_END_BLOCK_PATTERN",
    "LISP_BLOCK_COMMENT_PATTERN",
    "LOOP_PATTERN",
    "ML_BLOCK_COMMENT_PATTERN",
    "MODULE_BOUNDARY_PATTERN",
    "MODULE_PATTERN",
    "NEWLINE_PATTERN",
    "NIM_BLOCK_COMMENT_PATTERN",
    "PARAGRAPH_PATTERN",
    "PERCENT_COMMENT_PATTERN",
    "PRAGMA_PATTERN",
    "PROOF_BLOCK_PATTERN",
    "PROPERTY_PATTERN",
    "RUST_RAW_STRING_COMMENT_PATTERN",
    "SEMICOLON_COMMENT_PATTERN",
    "SLASH_COMMENT_PATTERN",
    "STAR_COMMENT_PATTERN",
    "STRING_ANGLE_PATTERN",
    "STRING_BACKTICK_QUOTE_PATTERN",
    "STRING_BYTES_PATTERN",
    "STRING_FORMATTED_PATTERN",
    "STRING_HASH_PATTERN",
    "STRING_QUOTE_PATTERN",
    "STRING_RAW_BYTES_PATTERN",
    "STRING_RAW_FORMATTED_PATTERN",
    "STRING_RAW_PATTERN",
    "STRING_STAR_PATTERN",
    "STRUCT_PATTERN",
    "TEMPLATE_ANGLE_PATTERN",
    "TEMPLATE_BACKTICK_PATTERN",
    "TEMPLATE_BRACE_PATTERN",
    "TEMPLATE_BRACKET_PATTERN",
    "TEMPLATE_PERCENT_PATTERN",
    "TEMPLATE_PIPE_PATTERN",
    "TEMPLATE_TILDE_PATTERN",
    "TRY_CATCH_PATTERN",
    "TUPLE_PATTERN",
    "TYPE_ALIAS_PATTERN",
    "WHITESPACE_PATTERN",
    "DelimiterPattern",
    "expand_pattern",
    "kind_from_delimiter_tuple",
    "matches_pattern",
)
