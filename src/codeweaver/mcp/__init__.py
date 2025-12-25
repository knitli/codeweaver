# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""FastMCP Server Creation and Lifespan Management for CodeWeaver.

## Which Find_Code Tool?

There are *three* symbols named "find_code" in CodeWeaver, two in this package:
- `find_code_tool`: The actual implementation function of the tool. This version is really a wrapper around the real `find_code` function defined in `codeweaver.agent_api.find_code`. `find_code_tool` is defined here in `codeweaver.mcp.user_agent` because it's the part exposed as an MCP tool for user's agents to call.
- `find_code_tool_definition`: The MCP `Tool` definition for the `find_code` tool. This is defined in `codeweaver.mcp.tools` as part of the `TOOL_DEFINITIONS` dictionary. This is what gets registered with the MCP server.
- `find_code`: The actual implementation function of the `find_code` logic, defined in `codeweaver.agent_api.find_code`. This is the core logic that does the code searching. If a user uses the `search` command in CodeWeaver's CLI, this `find_code` function is what gets called under the hood.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.mcp.middleware import (
        ErrorHandlingMiddleware,
        LoggingMiddleware,
        McpMiddleware,
        RateLimitingMiddleware,
        ResponseCachingMiddleware,
        RetryMiddleware,
        StatisticsMiddleware,
        StructuredLoggingMiddleware,
    )
    from codeweaver.mcp.server import create_http_server, create_stdio_server
    from codeweaver.mcp.state import CwMcpHttpState
    from codeweaver.mcp.tools import (
        TOOL_DEFINITIONS,
        find_code_tool_definition,
        get_bulk_tool,
        register_tool,
    )
    from codeweaver.mcp.types import ToolAnnotationsDict, ToolRegistrationDict
    from codeweaver.mcp.user_agent import find_code_tool


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CwMcpHttpState": (__spec__.parent, "state"),
    "ErrorHandlingMiddleware": (__spec__.parent, "middleware"),
    "LoggingMiddleware": (__spec__.parent, "middleware"),
    "McpMiddleware": (__spec__.parent, "middleware"),
    "RateLimitingMiddleware": (__spec__.parent, "middleware"),
    "ResponseCachingMiddleware": (__spec__.parent, "middleware"),
    "RetryMiddleware": (__spec__.parent, "middleware"),
    "StatisticsMiddleware": (__spec__.parent, "middleware"),
    "StructuredLoggingMiddleware": (__spec__.parent, "middleware"),
    "TOOL_DEFINITIONS": (__spec__.parent, "tools"),
    "ToolAnnotationsDict": (__spec__.parent, "types"),
    "ToolRegistrationDict": (__spec__.parent, "types"),
    "create_http_server": (__spec__.parent, "server"),
    "create_stdio_server": (__spec__.parent, "server"),
    "find_code_tool": (__spec__.parent, "user_agent"),
    "find_code_tool_definition": (__spec__.parent, "tools"),
    "get_bulk_tool": (__spec__.parent, "tools"),
    "register_tool": (__spec__.parent, "tools"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "TOOL_DEFINITIONS",
    "CwMcpHttpState",
    "ErrorHandlingMiddleware",
    "LoggingMiddleware",
    "McpMiddleware",
    "RateLimitingMiddleware",
    "ResponseCachingMiddleware",
    "RetryMiddleware",
    "StatisticsMiddleware",
    "StructuredLoggingMiddleware",
    "ToolAnnotationsDict",
    "ToolRegistrationDict",
    "create_http_server",
    "create_stdio_server",
    "find_code_tool",
    "find_code_tool_definition",
    "get_bulk_tool",
    "register_tool",
)


def __dir__() -> list[str]:
    """List available attributes for the middleware package."""
    return list(__all__)
