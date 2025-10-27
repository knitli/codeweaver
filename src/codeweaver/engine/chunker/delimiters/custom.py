# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Language-specific delimiter patterns and customizations.

This module defines custom delimiter patterns for languages that have unique
syntax not covered by their family patterns, or require overrides.

Example:
    >>> CUSTOM_PATTERNS["bash"]
    [bash_while_pattern, bash_until_pattern, ...]
"""

from __future__ import annotations

import re

from functools import cache
from types import MappingProxyType

import textcase

from codeweaver.engine.chunker.delimiters.kind import DelimiterKind
from codeweaver.engine.chunker.delimiters.patterns import (
    EMPTY_PATTERN,
    LINEBREAK,
    NEWLINE_PATTERN,
    PARAGRAPH_BREAK,
    PARAGRAPH_PATTERN,
    WHITESPACE_PATTERN,
    DelimiterPattern,
)


# Bash-specific patterns (unique loop syntax with 'done')
BASH_WHILE_PATTERN = DelimiterPattern(
    starts=["while"],
    ends=["done"],
    kind=DelimiterKind.LOOP,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

BASH_UNTIL_PATTERN = DelimiterPattern(
    starts=["until"],
    ends=["done"],
    kind=DelimiterKind.LOOP,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

BASH_FOR_PATTERN = DelimiterPattern(
    starts=["for"],
    ends=["done"],
    kind=DelimiterKind.LOOP,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

BASH_DO_PATTERN = DelimiterPattern(
    starts=["do"],
    ends=["done"],
    kind=DelimiterKind.LOOP,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

BASH_IF_PATTERN = DelimiterPattern(
    starts=["if"],
    ends=["fi"],
    kind=DelimiterKind.CONDITIONAL,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

BASH_CASE_PATTERN = DelimiterPattern(
    starts=["case"],
    ends=["esac"],
    kind=DelimiterKind.CONDITIONAL,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

# Python-specific patterns (decorators, f-strings)
PYTHON_DECORATOR_AT_PATTERN = DelimiterPattern(
    starts=["@"],
    ends=LINEBREAK,
    kind=DelimiterKind.DECORATOR,
    inclusive=True,
    take_whole_lines=False,
    nestable=False,
)

# Rust-specific patterns (macros, attributes, impl blocks)
RUST_MACRO_PATTERN = DelimiterPattern(
    starts=["macro_rules!"],
    ends="ANY",
    kind=DelimiterKind.FUNCTION,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
)

RUST_ATTRIBUTE_PATTERN = DelimiterPattern(
    starts=["#["],
    ends=["]"],
    kind=DelimiterKind.ANNOTATION,
    inclusive=False,
    take_whole_lines=True,
    nestable=False,
)

RUST_IMPL_PATTERN = DelimiterPattern(
    starts=["impl"],
    ends="ANY",
    kind=DelimiterKind.IMPL_BLOCK,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

RUST_TYPE_PATTERN = DelimiterPattern(
    starts=["type"],
    ends="ANY",
    kind=DelimiterKind.TYPE_ALIAS,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
)

# Go-specific patterns
GO_DEFER_PATTERN = DelimiterPattern(
    starts=["defer"],
    ends="ANY",
    kind=DelimiterKind.FUNCTION,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
)

GO_GO_PATTERN = DelimiterPattern(
    starts=["go"],
    ends="ANY",
    kind=DelimiterKind.FUNCTION,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
)

GO_TYPE_PATTERN = DelimiterPattern(
    starts=["type"],
    ends="ANY",
    kind=DelimiterKind.TYPE_ALIAS,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
)

# Ruby-specific patterns (blocks with do/end)
RUBY_DO_END_PATTERN = DelimiterPattern(
    starts=["do"],
    ends=["end"],
    kind=DelimiterKind.BLOCK,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

# Elixir-specific patterns
ELIXIR_DO_END_PATTERN = DelimiterPattern(
    starts=["do"],
    ends=["end"],
    kind=DelimiterKind.BLOCK,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

ELIXIR_DEFMODULE_PATTERN = DelimiterPattern(
    starts=["defmodule"],
    ends=["end"],
    kind=DelimiterKind.MODULE,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

ELIXIR_DEFP_PATTERN = DelimiterPattern(
    starts=["defp"],
    ends=["end"],
    kind=DelimiterKind.FUNCTION,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

# Lua-specific patterns
LUA_FUNCTION_END_PATTERN = DelimiterPattern(
    starts=["function"],
    ends=["end"],
    kind=DelimiterKind.FUNCTION,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

LUA_DO_END_PATTERN = DelimiterPattern(
    starts=["do"],
    ends=["end"],
    kind=DelimiterKind.BLOCK,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

LUA_IF_END_PATTERN = DelimiterPattern(
    starts=["if"],
    ends=["end"],
    kind=DelimiterKind.CONDITIONAL,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

LUA_FOR_END_PATTERN = DelimiterPattern(
    starts=["for"],
    ends=["end"],
    kind=DelimiterKind.LOOP,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

LUA_WHILE_END_PATTERN = DelimiterPattern(
    starts=["while"],
    ends=["end"],
    kind=DelimiterKind.LOOP,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

LUA_REPEAT_UNTIL_PATTERN = DelimiterPattern(
    starts=["repeat"],
    ends=["until"],
    kind=DelimiterKind.LOOP,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

# Coq/proof language patterns
COQ_MATCH_END_PATTERN = DelimiterPattern(
    starts=["match"],
    ends=["end"],
    kind=DelimiterKind.CONDITIONAL,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

COQ_SECTION_END_PATTERN = DelimiterPattern(
    starts=["Section"],
    ends=["End"],
    kind=DelimiterKind.MODULE,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

PROTOBUF_HIERARCHY_PATTERN = DelimiterPattern(
    starts=["message ", "service ", "import ", "package "],
    ends=PARAGRAPH_BREAK,
    kind=DelimiterKind.MODULE_BOUNDARY,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
)

PROTOBUF_DEFINITION_PATTERN = DelimiterPattern(
    starts=["enum ", "rpc "],
    ends=PARAGRAPH_BREAK,
    kind=DelimiterKind.ENUM,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

PROTOBUF_DECLARATION_PATTERN = DelimiterPattern(
    starts=["optional ", "repeated ", "required ", "syntax "],
    ends=PARAGRAPH_BREAK,
    kind=DelimiterKind.ANNOTATION,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

# Assembly-specific (limited, mostly comments)
ASSEMBLY_SEMICOLON_COMMENT = DelimiterPattern(
    starts=[";"],
    ends=LINEBREAK,
    kind=DelimiterKind.COMMENT_LINE,
    inclusive=True,
    take_whole_lines=False,
    nestable=False,
)


def generate_rst_character_ranges(character: str) -> list[str]:
    """Generate a list of RST section underline characters based on a given character.

    Args:
        character: A single character to generate underline patterns for.

    Returns:
        A list of strings representing RST section underline patterns.

    Example:
        >>> generate_rst_character_ranges("=")
        ['=', '==', '===', '====', '=====']
    """
    return [f"\n{character * i}" for i in range(1, 6)]  # RST supports 1-5 character underlines


RST_SECTION_PATTERN = DelimiterPattern(
    starts=sorted(
        (
            c
            for char in ("=", "-", "*", "~", "^", '"', "+", "#", "<", ">")
            for c in generate_rst_character_ranges(char)
        ),
        key=len,
        reverse=True,
    ),
    ends=PARAGRAPH_BREAK,
    kind=DelimiterKind.BLOCK,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
)

RST_COMMENT_PATTERN = DelimiterPattern(
    starts=[".. "],
    ends=LINEBREAK,
    kind=DelimiterKind.COMMENT_LINE,
    inclusive=True,
    take_whole_lines=False,
    nestable=False,
)

HTML_TAGS_PATTERNS = [
    DelimiterPattern(
        starts=[f"<{tag}"],
        ends=[f"</{tag}>"],
        kind=DelimiterKind.BLOCK
        if tag in ["html", "body", "main", "section", "article"]
        else DelimiterKind.PARAGRAPH,
        inclusive=True,
        take_whole_lines=True,
        nestable=True,
    )
    for tag in [
        "html",
        "body",
        "main",
        "section",
        "article",
        "div",
        "p",
        "span",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "li",
        "table",
        "tr",
        "td",
        "th",
        "thead",
        "tbody",
        "footer",
        "header",
        "nav",
        "head",
        "script",
        "style",
        "meta",
        "title",
    ]
]

# COBOL-specific patterns
# COBOL has unique divisions and sections
# And while it's not something people code in often -- by choice -- it's still very much in use for legacy systems
COBOL_DIVISION_PATTERN = DelimiterPattern(
    starts=[
        "IDENTIFICATION DIVISION",
        "ENVIRONMENT DIVISION",
        "DATA DIVISION",
        "PROCEDURE DIVISION",
    ],
    ends=["."],
    kind=DelimiterKind.MODULE_BOUNDARY,
    priority_override=85,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
)

COBOL_SECTION_PATTERN = DelimiterPattern(
    starts=[
        "WORKING-STORAGE SECTION",
        "FILE SECTION",
        "LINKAGE SECTION",
        "LOCAL-STORAGE SECTION",
        "CONFIGURATION SECTION",
        "INPUT-OUTPUT SECTION",
    ],
    ends=["."],
    kind=DelimiterKind.MODULE,
    priority_override=80,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

COBOL_PERFORM_PATTERN = DelimiterPattern(
    starts=["PERFORM"],
    ends=["END-PERFORM"],
    kind=DelimiterKind.LOOP,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

COBOL_IF_PATTERN = DelimiterPattern(
    starts=["IF"],
    ends=["END-IF"],
    kind=DelimiterKind.CONDITIONAL,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

COBOL_EVALUATE_PATTERN = DelimiterPattern(
    starts=["EVALUATE"],
    ends=["END-EVALUATE"],
    kind=DelimiterKind.CONDITIONAL,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

COBOL_SEARCH_PATTERN = DelimiterPattern(
    starts=["SEARCH"],
    ends=["END-SEARCH"],
    kind=DelimiterKind.LOOP,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

COBOL_INLINE_COMMENT_PATTERN = DelimiterPattern(
    starts=["*>"],
    ends=LINEBREAK,
    kind=DelimiterKind.COMMENT_LINE,
    inclusive=True,
    take_whole_lines=False,
    nestable=False,
)

COBOL_ASTERISK_COMMENT_PATTERN = DelimiterPattern(
    starts=["*"],
    ends=LINEBREAK,
    kind=DelimiterKind.COMMENT_LINE,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
)

PKL_IMPORT_PATTERN = DelimiterPattern(
    starts=['amends "', 'extends "', 'import "'],
    ends=PARAGRAPH_BREAK,
    kind=DelimiterKind.MODULE_BOUNDARY,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
)

PKL_DOC_COMMENT_PATTERN = DelimiterPattern(
    starts=["/// "],
    ends=LINEBREAK,
    priority_override=70,
    kind=DelimiterKind.DOCSTRING,
    inclusive=True,
    take_whole_lines=False,
    nestable=False,
)

_rtf_markup_regex = re.compile(r"\\[a-z]+\s?")


def _rtf_formatter(text: str) -> str:
    """Formatter to strip RTF markup from text."""
    return _rtf_markup_regex.sub(" ", text.strip()).strip()


RTF_PARAGRAPH_PATTERN = PARAGRAPH_PATTERN._replace(formatter=_rtf_formatter)
RTF_LINE_PATTERN = NEWLINE_PATTERN._replace(formatter=_rtf_formatter)
RTF_WHITESPACE_PATTERN = WHITESPACE_PATTERN._replace(formatter=_rtf_formatter)
RTF_EMPTY_PATTERN = EMPTY_PATTERN._replace(formatter=_rtf_formatter)

POD_SECTION_PATTERN = DelimiterPattern(
    starts=["=pod", "=begin"],
    ends=["=cut", "=end"],
    kind=DelimiterKind.DOCSTRING,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
    formatter=lambda text: text.strip().replace("\n\n", "\n").strip(),  # type: ignore
)

POD_SUB_PATTERN = DelimiterPattern(
    starts=["=item", "=over", "=back", "=head1", "=head2", "=head3", "=head4", "=head5", "=head6"],
    ends=[
        "=cut",
        "=end",
        "=pod",
        "=begin",
        "=item",
        "=over",
        "=back",
        "=head1",
        "=head2",
        "=head3",
        "=head4",
        "=head5",
        "=head6",
    ],
    kind=DelimiterKind.DOCSTRING,
    inclusive=True,
    take_whole_lines=True,
    nestable=False,
)

TEXINFO_BLOCK_PATTERN = DelimiterPattern(
    starts=["@node", "@chapter", "@section", "@subsection", "@subsubsection", "@top", "@chapter"],
    ends=PARAGRAPH_BREAK,
    kind=DelimiterKind.BLOCK,
    inclusive=True,
    take_whole_lines=True,
    nestable=True,
)

CSV_PATTERN = DelimiterPattern(
    starts=[","],
    ends=LINEBREAK,
    kind=DelimiterKind.ARRAY,
    priority_override=30,
    inclusive=False,
    take_whole_lines=True,
    nestable=False,
)

TSV_PATTERN = DelimiterPattern(
    starts=["\t"],
    ends=LINEBREAK,
    kind=DelimiterKind.ARRAY,
    priority_override=30,
    inclusive=False,
    take_whole_lines=True,
    nestable=False,
)


# Language-specific pattern collections
CUSTOM_PATTERNS: MappingProxyType[str, list[DelimiterPattern]] = MappingProxyType({
    "csv": [CSV_PATTERN],
    "bash": [
        BASH_WHILE_PATTERN,
        BASH_UNTIL_PATTERN,
        BASH_FOR_PATTERN,
        BASH_DO_PATTERN,
        BASH_IF_PATTERN,
        BASH_CASE_PATTERN,
    ],
    "zsh": [
        BASH_WHILE_PATTERN,
        BASH_UNTIL_PATTERN,
        BASH_FOR_PATTERN,
        BASH_DO_PATTERN,
        BASH_IF_PATTERN,
        BASH_CASE_PATTERN,
    ],
    "fish": [
        # Fish uses different syntax, but similar concepts
        BASH_WHILE_PATTERN,
        BASH_FOR_PATTERN,
        BASH_IF_PATTERN,
    ],
    "sh": [
        BASH_WHILE_PATTERN,
        BASH_UNTIL_PATTERN,
        BASH_FOR_PATTERN,
        BASH_DO_PATTERN,
        BASH_IF_PATTERN,
        BASH_CASE_PATTERN,
    ],
    "html": HTML_TAGS_PATTERNS,
    "perl": [POD_SECTION_PATTERN, POD_SUB_PATTERN],
    "python": [PYTHON_DECORATOR_AT_PATTERN],
    "pkl": [PKL_IMPORT_PATTERN, PKL_DOC_COMMENT_PATTERN],
    "pod": [POD_SECTION_PATTERN, POD_SUB_PATTERN],
    "rust": [RUST_MACRO_PATTERN, RUST_ATTRIBUTE_PATTERN, RUST_IMPL_PATTERN, RUST_TYPE_PATTERN],
    "go": [GO_DEFER_PATTERN, GO_GO_PATTERN, GO_TYPE_PATTERN],
    "ruby": [RUBY_DO_END_PATTERN],
    "crystal": [RUBY_DO_END_PATTERN],
    "elixir": [ELIXIR_DO_END_PATTERN, ELIXIR_DEFMODULE_PATTERN, ELIXIR_DEFP_PATTERN],
    "lua": [
        LUA_FUNCTION_END_PATTERN,
        LUA_DO_END_PATTERN,
        LUA_IF_END_PATTERN,
        LUA_FOR_END_PATTERN,
        LUA_WHILE_END_PATTERN,
        LUA_REPEAT_UNTIL_PATTERN,
    ],
    "coq": [COQ_MATCH_END_PATTERN, COQ_SECTION_END_PATTERN],
    "assembly": [ASSEMBLY_SEMICOLON_COMMENT],
    "asm": [ASSEMBLY_SEMICOLON_COMMENT],
    "cobol": [
        COBOL_DIVISION_PATTERN,
        COBOL_SECTION_PATTERN,
        COBOL_PERFORM_PATTERN,
        COBOL_IF_PATTERN,
        COBOL_EVALUATE_PATTERN,
        COBOL_SEARCH_PATTERN,
        COBOL_INLINE_COMMENT_PATTERN,
        COBOL_ASTERISK_COMMENT_PATTERN,
    ],
    "protobuf": [
        PROTOBUF_HIERARCHY_PATTERN,
        PROTOBUF_DEFINITION_PATTERN,
        PROTOBUF_DECLARATION_PATTERN,
    ],
    "rtf": [RTF_PARAGRAPH_PATTERN, RTF_LINE_PATTERN, RTF_WHITESPACE_PATTERN, RTF_EMPTY_PATTERN],
    "rst": [RST_SECTION_PATTERN, RST_COMMENT_PATTERN],
    "texinfo": [TEXINFO_BLOCK_PATTERN],
    "tsv": [TSV_PATTERN],
})

_pattern_registry: dict[str, list[DelimiterPattern]] = {}


@cache
def get_custom_patterns(language: str) -> list[DelimiterPattern]:
    """Get custom delimiter patterns for a language.

    Args:
        language: Language name (normalized to lowercase)

    Returns:
        List of custom DelimiterPattern objects, or empty list if none

    Example:
        >>> patterns = get_custom_patterns("bash")
        >>> len(patterns)
        6
    """
    from codeweaver.config.settings import get_settings
    from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage

    language = textcase.snake(language)
    delimiters: list[DelimiterPattern] = []
    if custom_delimiters := get_settings().chunker.custom_delimiters:
        for delim in custom_delimiters:
            if (lang := delim.language) and language == textcase.snake(lang):
                delimiters.extend(delim.delimiters)
            if (extensions := delim.extensions) and any(
                ext
                for ext in extensions
                if textcase.snake(
                    ext.language.variable
                    if isinstance(ext.language, SemanticSearchLanguage | ConfigLanguage)
                    else str(ext.language)
                )
                == language
            ):
                delimiters.extend(delim.delimiters)
    if "_pattern_registry" not in globals():
        globals()["_pattern_registry"] = dict(CUSTOM_PATTERNS)
    global _pattern_registry
    if language not in _pattern_registry and delimiters:
        _pattern_registry[language] = delimiters
    else:
        _pattern_registry[language] = [*delimiters, *_pattern_registry[language]]
    return _pattern_registry.get(language, [])


__all__ = ("CUSTOM_PATTERNS", "get_custom_patterns")
