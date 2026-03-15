# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Re-export of FastMCP middleware for CodeWeaver."""

from __future__ import annotations

from fastmcp.server.middleware.caching import ResponseCachingMiddleware as ResponseCachingMiddleware
from fastmcp.server.middleware.error_handling import (
    ErrorHandlingMiddleware as ErrorHandlingMiddleware,
)
from fastmcp.server.middleware.error_handling import RetryMiddleware as RetryMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware as LoggingMiddleware
from fastmcp.server.middleware.logging import (
    StructuredLoggingMiddleware as StructuredLoggingMiddleware,
)
from fastmcp.server.middleware.middleware import Middleware as McpMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware as RateLimitingMiddleware
from fastmcp.server.middleware.timing import DetailedTimingMiddleware as DetailedTimingMiddleware


__all__ = (
    "DetailedTimingMiddleware",
    "ErrorHandlingMiddleware",
    "LoggingMiddleware",
    "McpMiddleware",
    "RateLimitingMiddleware",
    "ResponseCachingMiddleware",
    "RetryMiddleware",
    "StructuredLoggingMiddleware",
)
