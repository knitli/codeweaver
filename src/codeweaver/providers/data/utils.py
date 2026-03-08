# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Utility functions for data providers."""

from __future__ import annotations

import logging

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast, overload

from fastmcp.tools import Tool
from pydantic import TypeAdapter

from codeweaver.core import (
    LiteralProviderCategoryType,
    ProviderCategory,
    ProviderLiteralString,
    has_package,
)


if TYPE_CHECKING:
    from codeweaver.server.mcp.server import CwMcpHttpState
    from codeweaver.server.mcp.types import ToolRegistrationDict


logger = logging.getLogger(__name__)


async def _get_state() -> CwMcpHttpState | None:
    """Get the current MCP HTTP state."""
    if not has_package("codeweaver.server"):
        return None
    from codeweaver.core.di.container import get_container
    from codeweaver.server.mcp.state import CwMcpHttpState

    container = get_container()
    return await container.resolve(CwMcpHttpState)


async def register_data_tool(tool: Tool[Any], state: CwMcpHttpState | None = None) -> None:
    """Register a data tool with the given MCP HTTP state."""
    if state is None:
        state = await _get_state()
    if state is None:
        logger.warning(
            "MCP HTTP state is not available. Data tool registration skipped for %s.", tool.name
        )
        return
    app = state.app
    app.add_tool(tool)


async def build_data_tool(config: ToolRegistrationDict) -> Tool[Any]:
    """Build a data tool from the given configuration."""
    return Tool.from_function(**config)


def get_type_adapter[T: Any](type_: type[T], module: str) -> TypeAdapter[T]:
    """Get an adapter of the given type from the specified module."""
    return TypeAdapter(type_, module=module)


@overload
def get_schema_for_type[T](
    type_: None = None, module: None = None, *, adapter: TypeAdapter[T]
) -> dict[str, Any]: ...
@overload
def get_schema_for_type[T](type_: type[T], module: str) -> dict[str, Any]: ...
def get_schema_for_type[T](
    type_: type[T] | None = None,
    module: str | None = None,
    *,
    adapter: TypeAdapter[T] | None = None,
) -> dict[str, Any]:
    """Get the schema for the given type from the specified module. Or from a provided adapter."""
    if not type_ and not adapter:
        raise ValueError("Either type_ and module or adapter must be provided")
    if adapter is None:
        adapter = get_type_adapter(cast(type[T], type_), module=cast(str, module))
    return adapter.json_schema(mode="serialization")


@overload
def get_serializer_for_type[T](
    type_: None = None, module: str | None = None, *, adapter: TypeAdapter[T]
) -> Callable[[T], str]: ...
@overload
def get_serializer_for_type[T](type_: type[T], module: str) -> Callable[[T], str]: ...
def get_serializer_for_type[T](
    type_: type[T] | None = None, module: str | None = None, adapter: TypeAdapter[T] | None = None
) -> Callable[[T], str]:
    """Get a serializer for the given type from the specified module. Or from a provided adapter."""
    if adapter is None:
        if type_ is None or module is None:
            raise ValueError("Either adapter or both type_ and module must be provided")
        adapter = get_type_adapter(type_, module=module)
    return lambda data: adapter.dump_json(data, round_trip=True)


def get_provider_names_for_category(
    category: LiteralProviderCategoryType,
) -> set[ProviderLiteralString]:
    """Get the set of provider literal strings for the given provider category."""
    category: ProviderCategory = (
        category
        if isinstance(category, ProviderCategory)
        else ProviderCategory.from_string(category)
    )
    return cast(set[ProviderLiteralString], {provider.variable for provider in category.providers})


__all__ = (
    "build_data_tool",
    "get_provider_names_for_category",
    "get_schema_for_type",
    "get_serializer_for_type",
    "get_type_adapter",
    "register_data_tool",
)
