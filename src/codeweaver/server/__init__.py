# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver server package initialization."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
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
    "DetailedTimingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "ErrorHandlingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "LoggingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "McpMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "RateLimitingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "ResponseCachingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "RetryMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "StatisticsMiddleware": (__spec__.parent, "mcp.middleware.statistics"),
    "StructuredLoggingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
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
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
