# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Text processing utilities for code snippets."""

# TODO: Once we have better code parsing implementations, we need to define a pipeline for processing.
from __future__ import annotations

import re
import textwrap

from functools import cache

import textcase

from langchain_text_splitters import Language

from codeweaver._common import BaseEnum
from codeweaver._constants import DOC_FILES_EXTENSIONS, get_ext_lang_pairs
from codeweaver.language import SemanticSearchLanguage


class SplitterKind(BaseEnum):
    """Kinds of text splitters."""

    MARKDOWN = "markdown"
    LATEX = "latex"
    SEMANTIC = "semantic"
    CHARACTER = "character"

    LANG_C = "c"
    LANG_COBOL = "cobol"
    LANG_CPP = "cpp"
    LANG_CSHARP = "csharp"
    LANG_ELIXIR = "elixir"
    LANG_GO = "go"
    LANG_HASKELL = "haskell"
    LANG_HTML = "html"
    LANG_JAVA = "java"
    LANG_JS = "javascript"
    LANG_KOTLIN = "kotlin"
    LANG_LATEX = "latex"
    LANG_LUA = "lua"
    LANG_MARKDOWN = "markdown"
    LANG_PERL = "perl"
    LANG_PHP = "php"
    LANG_POWERSHELL = "powershell"
    LANG_PROTOCOL_BUFFERS = "protocol_buffers"
    LANG_PYTHON = "python"
    LANG_RUBY = "ruby"
    LANG_RUST = "rust"
    LANG_RST = "restructuredtext"
    LANG_SCALA = "scala"
    LANG_SOLIDITY = "solidity"
    LANG_SWIFT = "swift"
    LANG_TS = "typescript"
    LANG_VISUALBASIC6 = "visualbasic6"

    @property
    def alias(self) -> tuple[str, ...]:
        """Get other names for this kind."""
        additional_akas = {
            SplitterKind.LANG_JS: ("js", "node", "nodejs"),
            SplitterKind.LANG_TS: ("ts"),
            SplitterKind.LANG_CSHARP: ("c#", "c-sharp", "dotnet"),
            SplitterKind.LANG_PROTOCOL_BUFFERS: ("protobuf", "proto"),
            SplitterKind.LANG_VISUALBASIC6: ("vb6", "vb-6"),
            SplitterKind.LANG_SOLIDITY: ("sol",),
            SplitterKind.LANG_RST: ("rst",),
        }
        return self.aka + additional_akas.get(self, ())  # type: ignore


REMOVE_ID = re.compile(r"(?P<trailing_id>(?!^)_id$)|(?P<lone_id>\b_id$|(?<=\b)_id(?=\b))")
"""Matches trailing and lone _id patterns. Only matches _id at the end of a string or surrounded by word boundaries."""

BOUNDARY = re.compile(r"(\W+)")

LOWLY_WORDS = {  # Not lowly worms 🪱🎩
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "from",
    "if",
    "in",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def to_lowly_lowercase(word: str) -> str:
    """Ensure insignificant words are lowercase."""
    return word.lower() if word in LOWLY_WORDS else word


def humanize(word: str) -> str:
    """
    Capitalize the first word and turn underscores into spaces and strip a
    trailing ``"_id"``, if any. Creates a nicer looking string.

    Examples:
        >>> humanize("employee_salary")
        'Employee salary'
        >>> humanize("author_id")
        'Author'

    """
    word = REMOVE_ID.sub(lambda m: "ID" if m.group("lone_id") else "", word)
    return to_lowly_lowercase(textcase.sentence(word))


def format_docstring(docstring: str) -> str:
    """Format a docstring for display."""
    lines = docstring.strip().splitlines()
    return textwrap.dedent("\n".join([to_lowly_lowercase(textcase.title(lines[0])), *lines[1:]]))


def format_snippet_name(name: str) -> str:
    """Format a snippet name for display."""
    return to_lowly_lowercase(textcase.title(humanize(textcase.snake(name.strip()))))


def format_signature(signature: str) -> str:
    """Format a function signature for display."""
    return textcase.title(humanize(textcase.snake(signature.strip())))


def format_descriptor(
    module: str, file_name: str, code_kind: str, snippet_name: str | None = None
) -> str:
    """Format a code descriptor for display."""
    return f"module {module} | file {file_name} | {code_kind} {format_snippet_name(snippet_name) if snippet_name else ''}".strip()


def to_tokens(text: str) -> str:
    """Convert a text string into a list of tokens."""
    tokens = BOUNDARY.split(text)
    tokens = (x for x in tokens if x)
    return " ".join(tokens)


@cache
def get_splitterkind_for_file(suffix: str) -> SplitterKind:
    """Get the appropriate text splitter for a given file type."""
    if suffix in SemanticSearchLanguage.all_extensions():
        return SplitterKind.SEMANTIC
    if suffix in (pair.ext for pair in DOC_FILES_EXTENSIONS if pair.language == "markdown"):
        return SplitterKind.MARKDOWN
    if suffix in (pair.ext for pair in DOC_FILES_EXTENSIONS if pair.language == "latex"):
        return SplitterKind.LATEX

    if (
        (
            matched_suffix := (
                next((pair for pair in get_ext_lang_pairs() if pair.ext == suffix), None)
            )
        )
        and (matched_lang := SplitterKind.from_string(matched_suffix.language))
        and any(a for a in matched_lang.alias if a in Language._value2member_map_)
    ):
        return matched_lang
    return SplitterKind.CHARACTER


__all__ = (
    "format_descriptor",
    "format_docstring",
    "format_signature",
    "format_snippet_name",
    "humanize",
    "to_lowly_lowercase",
    "to_tokens",
)
