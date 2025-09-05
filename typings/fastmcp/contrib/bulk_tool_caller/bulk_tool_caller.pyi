# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from typing import Any

from fastmcp import FastMCP
from fastmcp.contrib.mcp_mixin.mcp_mixin import MCPMixin, mcp_tool
from mcp.types import CallToolResult
from pydantic import BaseModel

class CallToolRequest(BaseModel):


    tool: str = ...
    arguments: dict[str, Any] = ...

class CallToolRequestResult(CallToolResult):


    tool: str = ...
    arguments: dict[str, Any] = ...
    @classmethod
    def from_call_tool_result(
        cls, result: CallToolResult, tool: str, arguments: dict[str, Any]
    ) -> CallToolRequestResult:
        ...

class BulkToolCaller(MCPMixin):

    def register_tools(
        self, mcp_server: FastMCP, prefix: str | None = ..., separator: str = ...
    ) -> None:
        ...

    @mcp_tool()
    async def call_tools_bulk(
        self, tool_calls: list[CallToolRequest], continue_on_error: bool = ...
    ) -> list[CallToolRequestResult]:
        ...

    @mcp_tool()
    async def call_tool_bulk(
        self,
        tool: str,
        tool_arguments: list[dict[str, str | int | float | bool | None]],
        continue_on_error: bool = ...,
    ) -> list[CallToolRequestResult]:
        ...
