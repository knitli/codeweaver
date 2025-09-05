# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Self, TypeVar, overload

from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)
from fastmcp.server.server import FastMCP
from mcp import LoggingLevel, ServerSession
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.shared.context import RequestContext
from mcp.types import ContentBlock, IncludeContext, ModelPreferences, Root, SamplingMessage
from pydantic.networks import AnyUrl
from starlette.requests import Request

logger = ...
T = TypeVar("T")
_current_context: ContextVar[Context | None] = ...
_flush_lock = ...

@contextmanager
def set_context(context: Context) -> Generator[Context, None, None]: ...

@dataclass
class Context:

    def __init__(self, fastmcp: FastMCP) -> None: ...
    async def __aenter__(self) -> Self:
        ...

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        ...

    @property
    def request_context(self) -> RequestContext:
        ...

    async def report_progress(
        self, progress: float, total: float | None = ..., message: str | None = ...
    ) -> None:
        ...

    async def read_resource(self, uri: str | AnyUrl) -> list[ReadResourceContents]:
        ...

    async def log(
        self, message: str, level: LoggingLevel | None = ..., logger_name: str | None = ...
    ) -> None:
        ...

    @property
    def client_id(self) -> str | None:
        ...

    @property
    def request_id(self) -> str:
        ...

    @property
    def session_id(self) -> str | None:
        ...

    @property
    def session(self) -> ServerSession:
        ...

    async def debug(self, message: str, logger_name: str | None = ...) -> None:
        ...

    async def info(self, message: str, logger_name: str | None = ...) -> None:
        ...

    async def warning(self, message: str, logger_name: str | None = ...) -> None:
        ...

    async def error(self, message: str, logger_name: str | None = ...) -> None:
        ...

    async def list_roots(self) -> list[Root]:
        ...

    async def send_tool_list_changed(self) -> None:
        ...

    async def send_resource_list_changed(self) -> None:
        ...

    async def send_prompt_list_changed(self) -> None:
        ...

    async def sample(
        self,
        messages: str | list[str | SamplingMessage],
        system_prompt: str | None = ...,
        include_context: IncludeContext | None = ...,
        temperature: float | None = ...,
        max_tokens: int | None = ...,
        model_preferences: ModelPreferences | str | list[str] | None = ...,
    ) -> ContentBlock:
        ...

    @overload
    async def elicit(
        self, message: str, response_type: None
    ) -> AcceptedElicitation[dict[str, Any]] | DeclinedElicitation | CancelledElicitation: ...
    @overload
    async def elicit(
        self, message: str, response_type: type[T]
    ) -> AcceptedElicitation[T] | DeclinedElicitation | CancelledElicitation: ...
    @overload
    async def elicit(
        self, message: str, response_type: list[str]
    ) -> AcceptedElicitation[str] | DeclinedElicitation | CancelledElicitation: ...
    async def elicit(
        self, message: str, response_type: type[T] | list[str] | None = ...
    ) -> (
        AcceptedElicitation[T]
        | AcceptedElicitation[dict[str, Any]]
        | AcceptedElicitation[str]
        | DeclinedElicitation
        | CancelledElicitation
    ):
        ...

    def get_http_request(self) -> Request:
        ...
