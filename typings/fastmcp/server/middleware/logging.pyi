# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import logging

from typing import Any

from .middleware import CallNext, Middleware, MiddlewareContext

"""Comprehensive logging middleware for FastMCP servers."""

class LoggingMiddleware(Middleware):

    def __init__(
        self,
        logger: logging.Logger | None = ...,
        log_level: int = ...,
        include_payloads: bool = ...,
        max_payload_length: int = ...,
        methods: list[str] | None = ...,
    ) -> None:
        ...

    async def on_message(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...

class StructuredLoggingMiddleware(Middleware):

    def __init__(
        self,
        logger: logging.Logger | None = ...,
        log_level: int = ...,
        include_payloads: bool = ...,
        methods: list[str] | None = ...,
    ) -> None:
        ...

    async def on_message(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...
