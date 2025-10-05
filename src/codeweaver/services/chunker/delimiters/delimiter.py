# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""The Delimiter tuple and related types for defining code delimiters."""

from __future__ import annotations

from typing import Annotated, NamedTuple

from pydantic import Field, PositiveInt

from codeweaver.services.chunker.delimiters.kind import DelimiterKind


class Delimiter(NamedTuple):
    r"""Delimiter defines a pair of start end strings, along with metadata about how to treat the resulting chunk.

    Delimiter provides a powerful way to glean semantic information from code chunks for languages that CodeWeaver doesn't support for AST-based parsing.
    It can help provide context to the model about the chunk's purpose, and how it relates to other chunks, which improves retrieval and generation.

    Example:
        >>> from codeweaver._constants import DelimiterKind
        >>> from codeweaver.delimiters import Delimiter
        >>> function_delimiter = Delimiter(
        ...     start="def ",
        ...     end=":\n",
        ...     kind=DelimiterKind.FUNCTION,
        ...     priority=80,
        ...     nestable=False,
        ...     inclusive=True,
        ...     take_whole_lines=True,
        ... )

    This would define a delimiter for Python function definitions, which could be used to chunk Python code into individual functions, extracting the function signature as context.
    You could similarly define a delimiter for the entire function by using the end delimiter of `"\n\n"` (two newlines) to capture the whole function body.
    """

    start: Annotated[str, Field(description="The start delimiter.")]

    end: Annotated[str, Field(description="The end delimiter.")]

    kind: Annotated[DelimiterKind, Field(description="The kind of delimiter.")] = (
        DelimiterKind.UNKNOWN
    )

    nestable: Annotated[
        bool,
        Field(
            default_factory=lambda data: data["kind"].infer_nestable(),
            description="Whether the delimiter can be nested.",
        ),
    ] = False

    priority: Annotated[
        PositiveInt,
        Field(
            gt=0,
            lt=100,
            default_factory=lambda data: data["kind"].default_priority,
            description="The priority of the delimiter.",
        ),
    ] = 10

    inclusive: Annotated[
        bool,
        Field(
            description="Whether to include the delimiters in the resulting chunk.",
            default_factory=lambda data: data["kind"].infer_inline_strategy().inclusive,
        ),
    ] = True

    take_whole_lines: Annotated[
        bool,
        Field(
            description="Whether to expand the chunk to include whole lines if matched within it.",
            default_factory=lambda data: data["kind"].infer_inline_strategy().take_whole_lines,
        ),
    ] = True
