# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import logging

from typing import Any

from .middleware import CallNext, Middleware, MiddlewareContext

"""Timing middleware for measuring and logging request performance."""

class TimingMiddleware(Middleware):

    def __init__(self, logger: logging.Logger | None = ..., log_level: int = ...) -> None:
        ...

    async def on_request(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...

class DetailedTimingMiddleware(Middleware):

    def __init__(self, logger: logging.Logger | None = ..., log_level: int = ...) -> None:
        ...

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...

    async def on_read_resource(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...

    async def on_get_prompt(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...

    async def on_list_tools(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...

    async def on_list_resources(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...

    async def on_list_resource_templates(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        ...

    async def on_list_prompts(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        ...
