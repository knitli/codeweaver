# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Callable
from typing import Any

from mcp import McpError

from .middleware import CallNext, Middleware, MiddlewareContext

"""Rate limiting middleware for protecting FastMCP servers from abuse."""

class RateLimitError(McpError):

    def __init__(self, message: str = ...) -> None: ...

class TokenBucketRateLimiter:

    def __init__(self, capacity: int, refill_rate: float) -> None:
        ...

    async def consume(self, tokens: int = ...) -> bool:
        ...

class SlidingWindowRateLimiter:

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        ...

    async def is_allowed(self) -> bool:
        ...

class RateLimitingMiddleware(Middleware):

    def __init__(
        self,
        max_requests_per_second: float = ...,
        burst_capacity: int | None = ...,
        get_client_id: Callable[[MiddlewareContext], str] | None = ...,
        global_limit: bool = ...,
    ) -> None:
        ...

    async def on_request(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...

class SlidingWindowRateLimitingMiddleware(Middleware):

    def __init__(
        self,
        max_requests: int,
        window_minutes: int = ...,
        get_client_id: Callable[[MiddlewareContext], str] | None = ...,
    ) -> None:
        ...

    async def on_request(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...
