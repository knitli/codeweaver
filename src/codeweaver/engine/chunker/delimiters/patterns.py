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

from itertools import product
from typing import overload

from codeweaver.core.types.delimiter import DelimiterDict, DelimiterKind, DelimiterPattern


PARAGRAPH_BREAK = ["\n\n", "\r\n\r\n", "\r\r"]  # Cross-platform paragraph breaks
LINEBREAK = ["\n", "\r\n", "\r"]  # Cross-platform line endings


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
    starts=["#"], ends=LINEBREAK, kind=DelimiterKind.COMMENT_LINE
)

SLASH_COMMENT_PATTERN = DelimiterPattern(
    starts=["//"], ends=LINEBREAK, kind=DelimiterKind.COMMENT_LINE
)

DASH_COMMENT_PATTERN = DelimiterPattern(
    starts=["--"], ends=LINEBREAK, kind=DelimiterKind.COMMENT_LINE
)

SEMICOLON_COMMENT_PATTERN = DelimiterPattern(
    starts=[";"], ends=LINEBREAK, kind=DelimiterKind.COMMENT_LINE
)

PERCENT_COMMENT_PATTERN = DelimiterPattern(
    starts=["%"], ends=LINEBREAK, kind=DelimiterKind.COMMENT_LINE
)

EXCLAMATION_COMMENT_PATTERN = DelimiterPattern(
    starts=["!"], ends=LINEBREAK, kind=DelimiterKind.COMMENT_LINE
)

STAR_COMMENT_PATTERN = DelimiterPattern(starts=["*"], ends=[";\n"], kind=DelimiterKind.COMMENT_LINE)

# Docstring patterns
DOCSTRING_SLASH_PATTERN = DelimiterPattern(
    starts=["///", "/**"], ends=LINEBREAK, kind=DelimiterKind.DOCSTRING
)

DOCSTRING_SEMICOLON_PATTERN = DelimiterPattern(
    starts=[";;;", ";;"], ends=LINEBREAK, kind=DelimiterKind.DOCSTRING
)

DOCSTRING_HASH_PATTERN = DelimiterPattern(
    starts=["###"], ends=LINEBREAK, kind=DelimiterKind.DOCSTRING
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


def generate_latex_patterns(
    starts: list[str], kind: DelimiterKind, override: int
) -> list[DelimiterPattern]:
    """Generate LaTeX delimiter patterns for given starts and ends.

    Args:
        starts: List of LaTeX start commands
        ends: List of LaTeX end commands
        kind: DelimiterKind for the patterns

    Returns:
        List of DelimiterPattern instances

    """
    ends = [word.replace("begin", "end") for word in starts]
    patterns = zip(starts, ends, strict=True)
    return [
        DelimiterPattern(
            starts=[start],
            ends=[end],
            kind=kind,
            priority_override=override,
            inclusive=True,
            take_whole_lines=True,
        )
        for start, end in patterns
    ]


LATEX_SECTION_PATTERN = DelimiterPattern(
    starts=[r"\\chapter{", r"\\section{", r"\\subsection{", r"\\subsubsection{"],
    ends=["}"],
    inclusive=True,
    take_whole_lines=True,
    kind=DelimiterKind.BLOCK,
    priority_override=70,
)

LATEX_BLOCK_PATTERNS = generate_latex_patterns(
    starts=[
        r"\\begin{enumerate}",
        r"\\begin{itemize}",
        r"\\begin{description}",
        r"\\begin{figure}",
    ],
    kind=DelimiterKind.BLOCK,
    override=60,
)

LATEX_ARRAY_PATTERNS = generate_latex_patterns(
    starts=[
        r"\\begin{list}",
        r"\\begin{array}",
        r"\\begin{bmatrix}",
        r"\\begin{pmatrix}",
        r"\\begin{vmatrix}",
        r"\\begin{Vmatrix}",
    ],
    kind=DelimiterKind.ARRAY,
    override=40,
)

LATEX_ALIGN_PATTERNS = generate_latex_patterns(
    starts=[r"\\begin{align}"], kind=DelimiterKind.PARAGRAPH, override=30
)

LATEX_LITERALS_PATTERNS = generate_latex_patterns(
    starts=[
        r"\\begin{quote}",
        r"\\begin{quotation}",
        r"\\begin{verse}",
        r"\\begin{verbatim}",
        r"\\begin{lstlisting}",
        r"\\begin{minted}",
    ],
    kind=DelimiterKind.STRING,
    override=20,
)

LATEX_ENV_PATTERN = DelimiterPattern(
    starts=["$$", "$"],
    ends=["$$", "$"],
    inclusive=True,
    take_whole_lines=True,
    kind=DelimiterKind.PARAGRAPH,
    priority_override=30,
)

LATEX_STRING_PATTERN = DelimiterPattern(
    starts=[r"\\text{", r"\\mathrm{", r"\\mathbf{", r"\\mathbb{"],
    ends=["}"],
    inclusive=False,
    take_whole_lines=False,
    kind=DelimiterKind.STRING,
    priority_override=20,
)

ARRAY_PATTERN = DelimiterPattern(starts=["["], ends=["]"], kind=DelimiterKind.ARRAY)

TUPLE_PATTERN = DelimiterPattern(starts=["("], ends=[")"], kind=DelimiterKind.BLOCK)

# Data patterns
PRAGMA_PATTERN = DelimiterPattern(
    starts=["pragma", "#pragma"], ends=[";", "", *LINEBREAK], kind=DelimiterKind.ANNOTATION
)

DECORATOR_PATTERN = DelimiterPattern(
    starts=["@@", "@", "decorator"], ends=LINEBREAK, kind=DelimiterKind.DECORATOR
)

PROPERTY_PATTERN = DelimiterPattern(
    starts=["@property", "@classmethod", "@staticmethod"],
    ends=LINEBREAK,
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
    starts=PARAGRAPH_BREAK,
    ends=PARAGRAPH_BREAK,
    kind=DelimiterKind.PARAGRAPH,
    priority_override=40,  # Between COMMENT_BLOCK:45 and BLOCK:30
    inclusive=False,
    take_whole_lines=False,
    nestable=False,
)

# Whitespace patterns
NEWLINE_PATTERN = DelimiterPattern(starts=LINEBREAK, ends=LINEBREAK, kind=DelimiterKind.WHITESPACE)

WHITESPACE_PATTERN = DelimiterPattern(
    starts=[" ", "\t", "    ", "  "], ends=[" ", "\t", "   ", "  "], kind=DelimiterKind.WHITESPACE
)

EMPTY_PATTERN = DelimiterPattern(
    starts=["", *LINEBREAK], ends=[*LINEBREAK, ""], kind=DelimiterKind.WHITESPACE
)

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
    LATEX_SECTION_PATTERN,
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
    *LATEX_ALIGN_PATTERNS,
    LATEX_SECTION_PATTERN,
    *LATEX_BLOCK_PATTERNS,
    *LATEX_ARRAY_PATTERNS,
    *LATEX_ALIGN_PATTERNS,
    LATEX_ENV_PATTERN,
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
    *LATEX_LITERALS_PATTERNS,
    LATEX_STRING_PATTERN,
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
    "FUNCTION_PATTERN",
    "HASH_COMMENT_PATTERN",
    "HASKELL_BLOCK_COMMENT_PATTERN",
    "HTML_COMMENT_PATTERN",
    "IMPL_PATTERN",
    "INTERFACE_PATTERN",
    "JULIA_BLOCK_COMMENT_PATTERN",
    "LATEX_ALIGN_PATTERNS",
    "LATEX_ARRAY_PATTERNS",
    "LATEX_BLOCK_PATTERNS",
    "LATEX_ENV_PATTERN",
    "LATEX_LITERALS_PATTERNS",
    "LATEX_SECTION_PATTERN",
    "LATEX_STRING_PATTERN",
    "LET_END_BLOCK_PATTERN",
    "LINEBREAK",
    "LISP_BLOCK_COMMENT_PATTERN",
    "LOOP_PATTERN",
    "ML_BLOCK_COMMENT_PATTERN",
    "MODULE_BOUNDARY_PATTERN",
    "MODULE_PATTERN",
    "NEWLINE_PATTERN",
    "NIM_BLOCK_COMMENT_PATTERN",
    "PARAGRAPH_BREAK",
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
