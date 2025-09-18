# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fastmcp.server.server import MountedServer
from fastmcp.settings import DuplicateBehavior
from fastmcp.tools.tool import Tool, ToolResult
from mcp.types import ToolAnnotations

if TYPE_CHECKING: ...
logger = ...

class ToolManager:

    def __init__(
        self,
        duplicate_behavior: DuplicateBehavior | None = ...,
        mask_error_details: bool | None = ...,
    ) -> None: ...
    def mount(self, server: MountedServer) -> None:
        ...

    async def has_tool(self, key: str) -> bool:
        ...

    async def get_tool(self, key: str) -> Tool:
        ...

    async def get_tools(self) -> dict[str, Tool]:
        ...

    async def list_tools(self) -> list[Tool]:
        ...

    def add_tool_from_fn(
        self,
        fn: Callable[..., Any],
        name: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
        annotations: ToolAnnotations | None = ...,
        serializer: Callable[[Any], str] | None = ...,
        exclude_args: list[str] | None = ...,
    ) -> Tool:
        ...

    def add_tool(self, tool: Tool) -> Tool:
        ...

    def remove_tool(self, key: str) -> None:
        ...

    async def call_tool(self, key: str, arguments: dict[str, Any]) -> ToolResult:
        ...
