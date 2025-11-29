# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""FastMCP Server Creation and Lifespan Management for CodeWeaver."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.common.utils.lazy_importer import create_lazy_getattr


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

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "McpMiddleware": (__spec__.parent, "middleware"),
    "ErrorHandlingMiddleware": (__spec__.parent, "middleware"),
    "LoggingMiddleware": (__spec__.parent, "middleware"),
    "RateLimitingMiddleware": (__spec__.parent, "middleware"),
    "ResponseCachingMiddleware": (__spec__.parent, "middleware"),
    "RetryMiddleware": (__spec__.parent, "middleware"),
    "StatisticsMiddleware": (__spec__.parent, "middleware"),
    "StructuredLoggingMiddleware": (__spec__.parent, "middleware"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
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
    """List available attributes for the middleware package."""
    return list(__all__)
