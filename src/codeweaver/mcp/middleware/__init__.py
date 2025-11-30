# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""FastMCP middleware for CodeWeaver."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from fastmcp.server.middleware.middleware import Middleware as McpMiddleware

from codeweaver.common.utils.lazy_importer import create_lazy_getattr


if TYPE_CHECKING:
    # we lazily re-export FastMCP middleware for convenience
    from fastmcp.server.middleware.caching import ResponseCachingMiddleware
    from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware, RetryMiddleware
    from fastmcp.server.middleware.logging import LoggingMiddleware, StructuredLoggingMiddleware
    from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
    from fastmcp.server.middleware.timing import DetailedTimingMiddleware

    from codeweaver.mcp.middleware.statistics import StatisticsMiddleware

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ResponseCachingMiddleware": ("fastmcp.server.middleware.caching", "caching"),
    "ErrorHandlingMiddleware": ("fastmcp.server.middleware.error_handling", "error_handling"),
    "DetailedTimingMiddleware": ("fastmcp.server.middleware.timing", "timing"),
    "LoggingMiddleware": ("fastmcp.server.middleware.logging", "logging"),
    "RateLimitingMiddleware": ("fastmcp.server.middleware.rate_limiting", "rate_limiting"),
    "RetryMiddleware": ("fastmcp.server.middleware.error_handling", "error_handling"),
    "StatisticsMiddleware": (__spec__.parent, "statistics"),
    "StructuredLoggingMiddleware": ("fastmcp.server.middleware.logging", "logging"),
})


def default_middleware_for_transport(
    transport: Literal["streamable-http", "stdio"],
) -> list[type[McpMiddleware]]:
    """Get the default middleware for a given transport."""
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


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


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
    """List available attributes for the middleware package."""
    return list(__all__)
