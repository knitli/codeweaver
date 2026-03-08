# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""FastMCP middleware for CodeWeaver."""

from __future__ import annotations

from typing import Literal

from codeweaver.server.mcp.middleware.fastmcp import McpMiddleware


def default_middleware_for_transport(
    transport: Literal["streamable-http", "stdio"],
) -> list[type[McpMiddleware]]:
    """Get the default middleware for a given transport."""
    # Explicitly import middleware classes needed for this function
    from fastmcp.server.middleware.caching import ResponseCachingMiddleware
    from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware, RetryMiddleware
    from fastmcp.server.middleware.logging import LoggingMiddleware, StructuredLoggingMiddleware
    from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

    from codeweaver.server.mcp.middleware.statistics import StatisticsMiddleware

    base_middleware = [
        ResponseCachingMiddleware,
        ErrorHandlingMiddleware,
        RetryMiddleware,
        StatisticsMiddleware,
        RateLimitingMiddleware,
        LoggingMiddleware,
    ]
    if transport == "streamable-http":
        return [*base_middleware[:-1], StructuredLoggingMiddleware]
    return [
        mw
        for mw in base_middleware
        if mw.__name__ not in ("RetryMiddleware", "RateLimitingMiddleware")
    ]


# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.server.mcp.middleware.fastmcp import (
        DetailedTimingMiddleware,
        ErrorHandlingMiddleware,
        LoggingMiddleware,
        RateLimitingMiddleware,
        ResponseCachingMiddleware,
        RetryMiddleware,
        StructuredLoggingMiddleware,
    )
    from codeweaver.server.mcp.middleware.statistics import StatisticsMiddleware

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DetailedTimingMiddleware": (__spec__.parent, "fastmcp"),
    "ErrorHandlingMiddleware": (__spec__.parent, "fastmcp"),
    "LoggingMiddleware": (__spec__.parent, "fastmcp"),
    "RateLimitingMiddleware": (__spec__.parent, "fastmcp"),
    "ResponseCachingMiddleware": (__spec__.parent, "fastmcp"),
    "RetryMiddleware": (__spec__.parent, "fastmcp"),
    "StatisticsMiddleware": (__spec__.parent, "statistics"),
    "StructuredLoggingMiddleware": (__spec__.parent, "fastmcp"),
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
