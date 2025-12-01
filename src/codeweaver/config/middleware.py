# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""McpMiddleware configuration settings for CodeWeaver.

NOTE: This module defines configurations for **mcp** middleware. It only applies to the mcp protocol server, and not CodeWeaver's http endpoints or services.
"""

from __future__ import annotations

import logging

from collections.abc import Callable
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from fastmcp.server.middleware.caching import (
    AsyncKeyValue,
    CallToolSettings,
    GetPromptSettings,
    ListPromptsSettings,
    ListResourcesSettings,
    ListToolsSettings,
    ReadResourceSettings,
)
from fastmcp.server.middleware.middleware import MiddlewareContext as McpMiddlewareContext
from pydantic import Field, PositiveInt

from codeweaver.mcp.middleware import (
    DetailedTimingMiddleware,
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    RateLimitingMiddleware,
    ResponseCachingMiddleware,
    RetryMiddleware,
    StructuredLoggingMiddleware,
)


# ===========================================================================
# *          TypedDict classes for McpMiddleware Settings
# ===========================================================================


AVAILABLE_MIDDLEWARE = (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    StructuredLoggingMiddleware,
    DetailedTimingMiddleware,
    RateLimitingMiddleware,
    ResponseCachingMiddleware,
    RetryMiddleware,
)


# ===========================
# *  Caching McpMiddleware
# ===========================


class ResponseCachingMiddlewareSettings(TypedDict, total=False):
    """Settings for response caching middleware."""

    cache_storage: NotRequired[AsyncKeyValue | None]
    list_tools_settings: NotRequired[ListToolsSettings | None]
    list_prompts_settings: NotRequired[ListPromptsSettings | None]
    list_resources_settings: NotRequired[ListResourcesSettings | None]
    read_resource_settings: NotRequired[ReadResourceSettings | None]
    get_prompt_settings: NotRequired[GetPromptSettings | None]
    call_tool_settings: NotRequired[CallToolSettings | None]
    max_item_size: NotRequired[int]


# ===========================
# * Other McpMiddleware
# ===========================


class ErrorHandlingMiddlewareSettings(TypedDict, total=False):
    """Settings for error handling middleware."""

    logger: NotRequired[logging.Logger | None]
    include_traceback: NotRequired[bool]
    error_callback: NotRequired[Callable[[Exception, McpMiddlewareContext[Any]], None] | None]
    transform_errors: NotRequired[bool]


class RetryMiddlewareSettings(TypedDict, total=False):
    """Settings for retry middleware."""

    max_retries: NotRequired[int]
    base_delay: NotRequired[float]
    max_delay: NotRequired[float]
    backoff_multiplier: NotRequired[float]
    retry_exceptions: NotRequired[tuple[type[Exception], ...]]
    logger: NotRequired[logging.Logger | None]


class LoggingMiddlewareSettings(TypedDict, total=False):
    """Settings for logging middleware (both structured and unstructured)."""

    logger: Annotated[NotRequired[logging.Logger | None], Field(exclude=True)]
    log_level: NotRequired[int]
    include_payloads: NotRequired[bool]
    max_payload_length: NotRequired[int]
    methods: NotRequired[list[str] | None]

    use_structured_logging: NotRequired[bool]


class RateLimitingMiddlewareSettings(TypedDict, total=False):
    """Settings for rate limiting middleware."""

    max_requests_per_second: NotRequired[PositiveInt]
    burst_capacity: NotRequired[PositiveInt | None]
    get_client_id: NotRequired[Callable[[McpMiddlewareContext[Any]], str] | None]
    global_limit: NotRequired[bool]


class MiddlewareOptions(TypedDict, total=False):
    """Settings for middleware."""

    caching: ResponseCachingMiddlewareSettings | None
    error_handling: ErrorHandlingMiddlewareSettings | None
    retry: RetryMiddlewareSettings | None
    logging: LoggingMiddlewareSettings | None
    rate_limiting: RateLimitingMiddlewareSettings | None


DefaultMiddlewareSettings = MiddlewareOptions(
    caching=ResponseCachingMiddlewareSettings(),  # we'll use defaults for now.
    error_handling=ErrorHandlingMiddlewareSettings(
        include_traceback=True, error_callback=None, transform_errors=False
    ),
    retry=RetryMiddlewareSettings(
        max_retries=5, base_delay=1.0, max_delay=60.0, backoff_multiplier=2.0
    ),
    logging=LoggingMiddlewareSettings(log_level=30, include_payloads=False),
    rate_limiting=RateLimitingMiddlewareSettings(
        max_requests_per_second=75, get_client_id=None, burst_capacity=150, global_limit=True
    ),
)


def default_for_transport(protocol: Literal["streamable-http", "stdio"]) -> MiddlewareOptions:
    """Get default mcp middleware settings for a given transport protocol."""
    settings = DefaultMiddlewareSettings.copy()
    if protocol == "stdio":
        return MiddlewareOptions(**{
            k: v for k, v in settings.items() if k not in ("rate_limiting", "retry")
        })
    return settings


__all__ = (
    "AVAILABLE_MIDDLEWARE",
    "DefaultMiddlewareSettings",
    "ErrorHandlingMiddlewareSettings",
    "LoggingMiddlewareSettings",
    "MiddlewareOptions",
    "RateLimitingMiddlewareSettings",
    "RetryMiddlewareSettings",
)
