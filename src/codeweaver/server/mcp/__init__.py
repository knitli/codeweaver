# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""FastMCP Server Creation and Lifespan Management for CodeWeaver.

## Which Find_Code Tool?

There are *three* symbols named "find_code" in CodeWeaver, two in this package:
- `find_code_tool`: The actual implementation function of the tool. This version is really a wrapper around the real `find_code` function defined in `codeweaver.agent_api`. `find_code_tool` is defined here in `codeweaver.server.mcp.user_agent` because it's the part exposed as an MCP tool for user's agents to call.
- `find_code_tool_definition`: The MCP `Tool` definition for the `find_code` tool. This is defined in `codeweaver.server.mcp.tools` as part of the `TOOL_DEFINITIONS` dictionary. This is what gets registered with the MCP server.
- `find_code`: The actual implementation function of the `find_code` logic, defined in `codeweaver.agent_api`. This is the core logic that does the code searching. If a user uses the `search` command in CodeWeaver's CLI, this `find_code` function is what gets called under the hood.
"""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.server.mcp.middleware import MappingProxyType, default_middleware_for_transport
    from codeweaver.server.mcp.middleware.fastmcp import (
        DetailedTimingMiddleware,
        ErrorHandlingMiddleware,
        LoggingMiddleware,
        RateLimitingMiddleware,
        ResponseCachingMiddleware,
        RetryMiddleware,
        StructuredLoggingMiddleware,
    )
    from codeweaver.server.mcp.middleware.statistics import McpMiddlewareContext, ProviderError
    from codeweaver.server.mcp.server import (
        TOOLS_TO_REGISTER,
        McpMiddleware,
        SettingsMapDep,
        StatisticsDep,
        StatisticsMiddleware,
        StdioClientLifespan,
        configure_uvicorn_logging,
        create_http_server,
        create_stdio_server,
        get_statistics_middleware,
        register_middleware,
        register_tools,
        setup_middleware,
        setup_runargs,
    )
    from codeweaver.server.mcp.state import (
        CodeWeaverSettingsType,
        CwMcpHttpState,
        FastMCPServerSettings,
    )
    from codeweaver.server.mcp.tools import (
        TOOL_DEFINITIONS,
        ContextAgentToolkit,
        ToolCollectionDict,
        get_bulk_tool,
        register_tool,
    )
    from codeweaver.server.mcp.types import ToolAnnotationsDict, ToolRegistrationDict
    from codeweaver.server.mcp.user_agent import CodeWeaverStateDep, IntentType, find_code_tool

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "TOOL_DEFINITIONS": (__spec__.parent, "tools"),
    "TOOLS_TO_REGISTER": (__spec__.parent, "server"),
    "CodeWeaverSettingsType": (__spec__.parent, "state"),
    "CodeWeaverStateDep": (__spec__.parent, "user_agent"),
    "ContextAgentToolkit": (__spec__.parent, "tools"),
    "CwMcpHttpState": (__spec__.parent, "state"),
    "DetailedTimingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "ErrorHandlingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "IntentType": (__spec__.parent, "user_agent"),
    "LoggingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "MappingProxyType": (__spec__.parent, "middleware"),
    "McpMiddleware": (__spec__.parent, "server"),
    "McpMiddlewareContext": (__spec__.parent, "middleware.statistics"),
    "ProviderError": (__spec__.parent, "middleware.statistics"),
    "RateLimitingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "ResponseCachingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "RetryMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "SettingsMapDep": (__spec__.parent, "server"),
    "StatisticsDep": (__spec__.parent, "server"),
    "StatisticsMiddleware": (__spec__.parent, "server"),
    "StructuredLoggingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "ToolAnnotationsDict": (__spec__.parent, "types"),
    "ToolCollectionDict": (__spec__.parent, "tools"),
    "ToolRegistrationDict": (__spec__.parent, "types"),
    "configure_uvicorn_logging": (__spec__.parent, "server"),
    "create_http_server": (__spec__.parent, "server"),
    "create_stdio_server": (__spec__.parent, "server"),
    "default_middleware_for_transport": (__spec__.parent, "middleware"),
    "find_code_tool": (__spec__.parent, "user_agent"),
    "get_bulk_tool": (__spec__.parent, "tools"),
    "get_statistics_middleware": (__spec__.parent, "server"),
    "register_middleware": (__spec__.parent, "server"),
    "register_tool": (__spec__.parent, "tools"),
    "register_tools": (__spec__.parent, "server"),
    "setup_middleware": (__spec__.parent, "server"),
    "setup_runargs": (__spec__.parent, "server"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "TOOLS_TO_REGISTER",
    "TOOL_DEFINITIONS",
    "CodeWeaverSettingsType",
    "CodeWeaverStateDep",
    "ContextAgentToolkit",
    "CwMcpHttpState",
    "DetailedTimingMiddleware",
    "ErrorHandlingMiddleware",
    "FastMCPServerSettings",
    "IntentType",
    "LoggingMiddleware",
    "MappingProxyType",
    "McpMiddleware",
    "McpMiddlewareContext",
    "ProviderError",
    "RateLimitingMiddleware",
    "ResponseCachingMiddleware",
    "RetryMiddleware",
    "SettingsMapDep",
    "StatisticsDep",
    "StatisticsMiddleware",
    "StdioClientLifespan",
    "StructuredLoggingMiddleware",
    "ToolAnnotationsDict",
    "ToolCollectionDict",
    "ToolRegistrationDict",
    "configure_uvicorn_logging",
    "create_http_server",
    "create_stdio_server",
    "default_middleware_for_transport",
    "find_code_tool",
    "get_bulk_tool",
    "get_statistics_middleware",
    "register_middleware",
    "register_tool",
    "register_tools",
    "setup_middleware",
    "setup_runargs",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
