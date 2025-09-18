# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fastmcp.server import FastMCP
from mcp.types import ToolAnnotations

"""Provides a base mixin class and decorators for easy registration of class methods with FastMCP."""
if TYPE_CHECKING: ...
_MCP_REGISTRATION_TOOL_ATTR = ...
_MCP_REGISTRATION_RESOURCE_ATTR = ...
_MCP_REGISTRATION_PROMPT_ATTR = ...
_DEFAULT_SEPARATOR_TOOL = ...
_DEFAULT_SEPARATOR_RESOURCE = ...
_DEFAULT_SEPARATOR_PROMPT = ...

def mcp_tool(
    name: str | None = ...,
    description: str | None = ...,
    tags: set[str] | None = ...,
    annotations: ToolAnnotations | dict[str, Any] | None = ...,
    exclude_args: list[str] | None = ...,
    serializer: Callable[[Any], str] | None = ...,
    enabled: bool | None = ...,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    ...

def mcp_resource(
    uri: str,
    *,
    name: str | None = ...,
    description: str | None = ...,
    mime_type: str | None = ...,
    tags: set[str] | None = ...,
    enabled: bool | None = ...,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    ...

def mcp_prompt(
    name: str | None = ...,
    description: str | None = ...,
    tags: set[str] | None = ...,
    enabled: bool | None = ...,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    ...

class MCPMixin:

    def register_tools(
        self, mcp_server: FastMCP, prefix: str | None = ..., separator: str = ...
    ) -> None:
        ...

    def register_resources(
        self, mcp_server: FastMCP, prefix: str | None = ..., separator: str = ...
    ) -> None:
        ...

    def register_prompts(
        self, mcp_server: FastMCP, prefix: str | None = ..., separator: str = ...
    ) -> None:
        ...

    def register_all(
        self,
        mcp_server: FastMCP,
        prefix: str | None = ...,
        tool_separator: str = ...,
        resource_separator: str = ...,
        prompt_separator: str = ...,
    ) -> None:
        ...
