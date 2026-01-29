# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

"""Dependency injection type aliases and factories for semantic package."""

# sourcery skip: docstrings-for-modules
from __future__ import annotations

import asyncio

from typing import TYPE_CHECKING, Annotated

from codeweaver.core.di.depends import depends
from codeweaver.core.exceptions import NodeParsingFailureError


if TYPE_CHECKING:
    from codeweaver.semantic.node_type_parser import NodeTypeParser
    from codeweaver.semantic.registry import ThingRegistry


async def _create_thing_registry() -> ThingRegistry:  # Use string forward reference
    from codeweaver.semantic.registry import ThingRegistry

    return ThingRegistry()


# Use string forward reference to avoid circular import at runtime
ThingRegistryDep = Annotated["ThingRegistry", depends(_create_thing_registry, scope="singleton")]


async def _create_node_parser() -> NodeTypeParser:  # Use string forward reference
    from codeweaver.semantic.node_type_parser import NodeTypeParser

    parser = await asyncio.to_thread(NodeTypeParser)
    if parser and parser._initialized():
        return parser
    try:
        # this forces the parser to populate from files if available
        await asyncio.to_thread(lambda: parser.nodes)
    except (OSError, ValueError) as e:
        raise NodeParsingFailureError from e
    else:
        return parser


# Use string forward reference to avoid circular import at runtime
NodeParserDep = Annotated["NodeTypeParser", depends(_create_node_parser, scope="singleton")]


__all__ = ("NodeParserDep", "ThingRegistryDep")
