# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""FastMCP middleware for CodeWeaver."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fastmcp.server.middleware.middleware import Middleware as McpMiddleware


if TYPE_CHECKING:
    from fastmcp.server.middleware.caching import ResponseCachingMiddleware
    from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware, RetryMiddleware
    from fastmcp.server.middleware.logging import LoggingMiddleware, StructuredLoggingMiddleware
    from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
    from fastmcp.server.middleware.timing import DetailedTimingMiddleware

    from codeweaver.mcp.middleware.statistics import StatisticsMiddleware


def __getattr__(name: str) -> object:
    """Dynamically import middleware classes."""
    # External FastMCP middleware - direct imports
    if name == "ResponseCachingMiddleware":
        from fastmcp.server.middleware.caching import ResponseCachingMiddleware

        return ResponseCachingMiddleware
    if name == "ErrorHandlingMiddleware":
        from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware

        return ErrorHandlingMiddleware
    if name == "RetryMiddleware":
        from fastmcp.server.middleware.error_handling import RetryMiddleware

        return RetryMiddleware
    if name == "LoggingMiddleware":
        from fastmcp.server.middleware.logging import LoggingMiddleware

        return LoggingMiddleware
    if name == "StructuredLoggingMiddleware":
        from fastmcp.server.middleware.logging import StructuredLoggingMiddleware

        return StructuredLoggingMiddleware
    if name == "RateLimitingMiddleware":
        from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

        return RateLimitingMiddleware
    if name == "DetailedTimingMiddleware":
        from fastmcp.server.middleware.timing import DetailedTimingMiddleware

        return DetailedTimingMiddleware
    # Internal CodeWeaver middleware
    if name == "StatisticsMiddleware":
        from codeweaver.mcp.middleware.statistics import StatisticsMiddleware

        return StatisticsMiddleware

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def default_middleware_for_transport(
    transport: Literal["streamable-http", "stdio"],
) -> list[type[McpMiddleware]]:
    """Get the default middleware for a given transport."""
    # Explicitly import middleware classes needed for this function
    from fastmcp.server.middleware.caching import ResponseCachingMiddleware
    from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware, RetryMiddleware
    from fastmcp.server.middleware.logging import LoggingMiddleware, StructuredLoggingMiddleware
    from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

    from codeweaver.mcp.middleware.statistics import StatisticsMiddleware

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
