# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Text processing utilities for code snippets."""

# TODO: Once we have better code parsing implementations, we need to define a pipeline for processing.
from __future__ import annotations

import re
import textwrap

import textcase


REMOVE_ID = re.compile(r"(?P<trailing_id>(?!^)_id$)|(?P<lone_id>\b_id$|(?<=\b)_id(?=\b))")
"""Matches trailing and lone _id patterns. Only matches _id at the end of a string or surrounded by word boundaries."""

BOUNDARY = re.compile(r"(\W+)")

LOWLY_WORDS = {  # Don't confuse with lowly worms 🪱🎩
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
    "into",
    "is",
    "nor",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "without",
    "vs",
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


# ===========================================================================
# *                 Formatting Functions for Elements
# ===========================================================================


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


__all__ = (
    "format_descriptor",
    "format_docstring",
    "format_signature",
    "format_snippet_name",
    "humanize",
    "to_lowly_lowercase",
    "to_tokens",
)
