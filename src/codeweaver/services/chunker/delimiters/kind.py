# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""The DelimiterKind enum defines the semantic kinds of code delimiters."""

from __future__ import annotations

from typing import NamedTuple

from pydantic import PositiveInt

from codeweaver._common import BaseEnum


class LineStrategy(NamedTuple):
    """A strategy for how to handle lines when chunking."""

    inclusive: bool
    take_whole_lines: bool


class DelimiterKind(str, BaseEnum):
    """Delimiter metadata that provide semantic information on the resulting chunk. Used to provide semantic metadata and meaning to the chunk, approximating its role in the code."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    TYPE_ALIAS = "type_alias"
    IMPL_BLOCK = "impl_block"
    EXTENSION = "extension"
    NAMESPACE = "namespace"
    MODULE = "module"
    MODULE_BOUNDARY = "module_boundary"  # imports, exports, requires, etc.

    CONDITIONAL = "conditional"
    LOOP = "loop"
    TRY_CATCH = "try_catch"
    CONTEXT_MANAGER = "context_manager"

    COMMENT_LINE = "comment_line"
    COMMENT_BLOCK = "comment_block"
    DOCSTRING = "docstring"

    BLOCK = "block"
    ARRAY = "array"
    TUPLE = "tuple"

    STRING = "string"
    TEMPLATE_STRING = "template_string"

    ANNOTATION = "annotation"
    DECORATOR = "decorator"
    PROPERTY = "property"
    PRAGMA = "pragma"

    PARAGRAPH = "paragraph"  # double newlines, semantic section boundaries
    WHITESPACE = "whitespace"
    UNKNOWN = "unknown"

    __slots__ = ()

    @property
    def is_code_element(self) -> bool:
        """Whether the delimiter represents a code element in the code."""
        return self in {
            DelimiterKind.FUNCTION,
            DelimiterKind.CLASS,
            DelimiterKind.METHOD,
            DelimiterKind.INTERFACE,
            DelimiterKind.STRUCT,
            DelimiterKind.ENUM,
            DelimiterKind.TYPE_ALIAS,
            DelimiterKind.IMPL_BLOCK,
            DelimiterKind.EXTENSION,
            DelimiterKind.NAMESPACE,
            DelimiterKind.MODULE,
            DelimiterKind.MODULE_BOUNDARY,
        }

    @property
    def is_structure(self) -> bool:
        """Whether the delimiter represents a structural element in the code.

        I recognize that `array`, `object`, and `tuple` are data structures, but they have less semantic meaning on their own than a type, function, class, etc. For our purposes, they're more structural than data.
        """
        return self in {DelimiterKind.BLOCK, DelimiterKind.ARRAY, DelimiterKind.TUPLE}

    @property
    def is_control_flow(self) -> bool:
        """Whether the delimiter represents a control flow element in the code."""
        return self in {
            DelimiterKind.CONDITIONAL,
            DelimiterKind.LOOP,
            DelimiterKind.TRY_CATCH,
            DelimiterKind.CONTEXT_MANAGER,
        }

    @property
    def is_commentary(self) -> bool:
        """Whether the delimiter represents a commentary element in the code."""
        return self in {
            DelimiterKind.COMMENT_LINE,
            DelimiterKind.COMMENT_BLOCK,
            DelimiterKind.DOCSTRING,
        }

    @property
    def is_data(self) -> bool:
        """Whether the delimiter represents a data element in the code."""
        return self in {DelimiterKind.STRING, DelimiterKind.TEMPLATE_STRING}

    @property
    def is_meta(self) -> bool:
        """Whether the delimiter represents a meta element in the code."""
        return self in {
            DelimiterKind.ANNOTATION,
            DelimiterKind.DECORATOR,
            DelimiterKind.PROPERTY,
            DelimiterKind.PRAGMA,
            DelimiterKind.WHITESPACE,
        }

    @property
    def default_priority(self) -> PositiveInt:
        """Return the default priority for the delimiter kind."""
        return {
            DelimiterKind.MODULE_BOUNDARY: 90,
            DelimiterKind.CLASS: 85,
            DelimiterKind.INTERFACE: 80,
            DelimiterKind.TYPE_ALIAS: 75,
            DelimiterKind.IMPL_BLOCK: 75,
            DelimiterKind.STRUCT: 75,
            DelimiterKind.EXTENSION: 70,
            DelimiterKind.FUNCTION: 70,
            DelimiterKind.PROPERTY: 65,
            DelimiterKind.METHOD: 65,
            DelimiterKind.ENUM: 65,
            DelimiterKind.CONTEXT_MANAGER: 60,
            DelimiterKind.MODULE: 60,
            DelimiterKind.DOCSTRING: 60,
            DelimiterKind.DECORATOR: 55,
            DelimiterKind.NAMESPACE: 55,
            DelimiterKind.COMMENT_BLOCK: 55,
            DelimiterKind.TRY_CATCH: 50,
            DelimiterKind.LOOP: 50,
            DelimiterKind.CONDITIONAL: 50,
            DelimiterKind.PARAGRAPH: 40,
            DelimiterKind.BLOCK: 30,
            DelimiterKind.ANNOTATION: 30,
            DelimiterKind.ARRAY: 25,
            DelimiterKind.TUPLE: 20,
            DelimiterKind.COMMENT_LINE: 20,
            DelimiterKind.TEMPLATE_STRING: 15,
            DelimiterKind.STRING: 10,
            DelimiterKind.PRAGMA: 5,
            DelimiterKind.WHITESPACE: 1,
            DelimiterKind.UNKNOWN: 1,
        }[self]

    def infer_nestable(self) -> bool:
        """Infer a kind is nestable. Returns True if the kind is nestable."""
        return self in {
            DelimiterKind.FUNCTION,
            DelimiterKind.CLASS,
            DelimiterKind.INTERFACE,
            DelimiterKind.STRUCT,
            DelimiterKind.ENUM,
            DelimiterKind.IMPL_BLOCK,
            DelimiterKind.EXTENSION,
            DelimiterKind.NAMESPACE,
            DelimiterKind.CONDITIONAL,
            DelimiterKind.LOOP,
            DelimiterKind.TRY_CATCH,
            DelimiterKind.CONTEXT_MANAGER,
            DelimiterKind.BLOCK,
            DelimiterKind.ARRAY,
            DelimiterKind.TUPLE,
            DelimiterKind.STRING,
            DelimiterKind.TEMPLATE_STRING,
        }

    def infer_inline_strategy(self) -> LineStrategy:
        """Infer inline strategy based on delimiter kind if not explicitly set. Returns a tuple of (inclusive, take_whole_lines)."""
        if self.is_code_element or self.is_control_flow:
            return LineStrategy(inclusive=True, take_whole_lines=True)
        if self.is_structure or self.is_data or self.is_meta:
            return LineStrategy(inclusive=False, take_whole_lines=True)
        if self.is_commentary:
            return (
                LineStrategy(inclusive=True, take_whole_lines=False)
                if self == DelimiterKind.COMMENT_LINE
                else LineStrategy(inclusive=False, take_whole_lines=True)
            )
        return LineStrategy(inclusive=False, take_whole_lines=False)
