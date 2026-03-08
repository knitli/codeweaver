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
    from codeweaver.server.mcp.middleware import default_middleware_for_transport
    from codeweaver.server.mcp.middleware.fastmcp import (
        DetailedTimingMiddleware,
        ErrorHandlingMiddleware,
        LoggingMiddleware,
        McpMiddleware,
        RateLimitingMiddleware,
        ResponseCachingMiddleware,
        RetryMiddleware,
        StructuredLoggingMiddleware,
    )
    from codeweaver.server.mcp.middleware.statistics import StatisticsMiddleware

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DetailedTimingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "ErrorHandlingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "LoggingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "McpMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "RateLimitingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "ResponseCachingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "RetryMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "StatisticsMiddleware": (__spec__.parent, "middleware.statistics"),
    "StructuredLoggingMiddleware": (__spec__.parent, "middleware.fastmcp"),
    "default_middleware_for_transport": (__spec__.parent, "middleware"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "DetailedTimingMiddleware",
    "ErrorHandlingMiddleware",
    "LoggingMiddleware",
    "McpMiddleware",
    "RateLimitingMiddleware",
    "ResponseCachingMiddleware",
    "RetryMiddleware",
    "StatisticsMiddleware",
    "StructuredLoggingMiddleware",
    "default_middleware_for_transport",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
