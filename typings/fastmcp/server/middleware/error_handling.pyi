# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import logging

from collections.abc import Callable
from typing import Any

from .middleware import CallNext, Middleware, MiddlewareContext

"""Error handling middleware for consistent error responses and tracking."""

class ErrorHandlingMiddleware(Middleware):

    def __init__(
        self,
        logger: logging.Logger | None = ...,
        include_traceback: bool = ...,
        error_callback: Callable[[Exception, MiddlewareContext], None] | None = ...,
        transform_errors: bool = ...,
    ) -> None:
        ...

    async def on_message(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...

    def get_error_stats(self) -> dict[str, int]:
        ...

class RetryMiddleware(Middleware):

    def __init__(
        self,
        max_retries: int = ...,
        base_delay: float = ...,
        max_delay: float = ...,
        backoff_multiplier: float = ...,
        retry_exceptions: tuple[type[Exception], ...] = ...,
        logger: logging.Logger | None = ...,
    ) -> None:
        ...

    async def on_request(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...
