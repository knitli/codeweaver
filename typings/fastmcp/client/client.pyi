# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import asyncio
import datetime

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar, overload

import anyio
import httpx
import mcp.types

from fastmcp.client.elicitation import ElicitationHandler
from fastmcp.client.logging import LogHandler
from fastmcp.client.messages import MessageHandler, MessageHandlerT
from fastmcp.client.progress import ProgressHandler
from fastmcp.client.roots import RootsHandler, RootsList
from fastmcp.client.sampling import SamplingHandler
from fastmcp.mcp_config import MCPConfig
from fastmcp.server import FastMCP
from mcp import ClientSession
from pydantic import AnyUrl

from .transports import (
    ClientTransport,
    ClientTransportT,
    FastMCP1Server,
    FastMCPTransport,
    MCPConfigTransport,
    NodeStdioTransport,
    PythonStdioTransport,
    SSETransport,
    StreamableHttpTransport,
)

__all__ = [
    "Client",
    "ElicitationHandler",
    "LogHandler",
    "MessageHandler",
    "ProgressHandler",
    "RootsHandler",
    "RootsList",
    "SamplingHandler",
    "SessionKwargs",
]
logger = ...
T = TypeVar("T", bound=ClientTransport)

@dataclass
class ClientSessionState:


    session: ClientSession | None = ...
    nesting_counter: int = ...
    lock: anyio.Lock = ...
    session_task: asyncio.Task | None = ...
    ready_event: anyio.Event = ...
    stop_event: anyio.Event = ...
    initialize_result: mcp.types.InitializeResult | None = ...

class Client(Generic[ClientTransportT]):

    @overload
    def __init__(self: Client[T], transport: T, *args, **kwargs) -> None: ...
    @overload
    def __init__(
        self: Client[SSETransport | StreamableHttpTransport], transport: AnyUrl, *args, **kwargs
    ) -> None: ...
    @overload
    def __init__(
        self: Client[FastMCPTransport], transport: FastMCP | FastMCP1Server, *args, **kwargs
    ) -> None: ...
    @overload
    def __init__(
        self: Client[PythonStdioTransport | NodeStdioTransport], transport: Path, *args, **kwargs
    ) -> None: ...
    @overload
    def __init__(
        self: Client[MCPConfigTransport], transport: MCPConfig | dict[str, Any], *args, **kwargs
    ) -> None: ...
    @overload
    def __init__(
        self: Client[
            PythonStdioTransport | NodeStdioTransport | SSETransport | StreamableHttpTransport
        ],
        transport: str,
        *args,
        **kwargs,
    ) -> None: ...
    def __init__(
        self,
        transport: ClientTransportT
        | FastMCP
        | FastMCP1Server
        | AnyUrl
        | Path
        | MCPConfig
        | dict[str, Any]
        | str,
        roots: RootsList | RootsHandler | None = ...,
        sampling_handler: SamplingHandler | None = ...,
        elicitation_handler: ElicitationHandler | None = ...,
        log_handler: LogHandler | None = ...,
        message_handler: MessageHandlerT | MessageHandler | None = ...,
        progress_handler: ProgressHandler | None = ...,
        timeout: datetime.timedelta | float | None = ...,
        init_timeout: datetime.timedelta | float | None = ...,
        client_info: mcp.types.Implementation | None = ...,
        auth: httpx.Auth | Literal["oauth"] | str | None = ...,
    ) -> None: ...
    @property
    def session(self) -> ClientSession:
        ...

    @property
    def initialize_result(self) -> mcp.types.InitializeResult:
        ...

    def set_roots(self, roots: RootsList | RootsHandler) -> None:
        ...

    def set_sampling_callback(self, sampling_callback: SamplingHandler) -> None:
        ...

    def set_elicitation_callback(self, elicitation_callback: ElicitationHandler) -> None:
        ...

    def is_connected(self) -> bool:
        ...

    def new(self) -> Client[ClientTransportT]:
        ...

    async def __aenter__(self):  # -> Self:
        ...
    async def __aexit__(self, exc_type, exc_val, exc_tb):  # -> None:
        ...
    async def close(self):  # -> None:
        ...
    async def ping(self) -> bool:
        ...

    async def cancel(self, request_id: str | int, reason: str | None = ...) -> None:
        ...

    async def progress(
        self,
        progress_token: str | int,
        progress: float,
        total: float | None = ...,
        message: str | None = ...,
    ) -> None:
        ...

    async def set_logging_level(self, level: mcp.types.LoggingLevel) -> None:
        ...

    async def send_roots_list_changed(self) -> None:
        ...

    async def list_resources_mcp(self) -> mcp.types.ListResourcesResult:
        ...

    async def list_resources(self) -> list[mcp.types.Resource]:
        ...

    async def list_resource_templates_mcp(self) -> mcp.types.ListResourceTemplatesResult:
        ...

    async def list_resource_templates(self) -> list[mcp.types.ResourceTemplate]:
        ...

    async def read_resource_mcp(self, uri: AnyUrl | str) -> mcp.types.ReadResourceResult:
        ...

    async def read_resource(
        self, uri: AnyUrl | str
    ) -> list[mcp.types.TextResourceContents | mcp.types.BlobResourceContents]:
        ...

    async def list_prompts_mcp(self) -> mcp.types.ListPromptsResult:
        ...

    async def list_prompts(self) -> list[mcp.types.Prompt]:
        ...

    async def get_prompt_mcp(
        self, name: str, arguments: dict[str, Any] | None = ...
    ) -> mcp.types.GetPromptResult:
        ...

    async def get_prompt(
        self, name: str, arguments: dict[str, Any] | None = ...
    ) -> mcp.types.GetPromptResult:
        ...

    async def complete_mcp(
        self, ref: mcp.types.ResourceReference | mcp.types.PromptReference, argument: dict[str, str]
    ) -> mcp.types.CompleteResult:
        ...

    async def complete(
        self, ref: mcp.types.ResourceReference | mcp.types.PromptReference, argument: dict[str, str]
    ) -> mcp.types.Completion:
        ...

    async def list_tools_mcp(self) -> mcp.types.ListToolsResult:
        ...

    async def list_tools(self) -> list[mcp.types.Tool]:
        ...

    async def call_tool_mcp(
        self,
        name: str,
        arguments: dict[str, Any],
        progress_handler: ProgressHandler | None = ...,
        timeout: datetime.timedelta | float | None = ...,
    ) -> mcp.types.CallToolResult:
        ...

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = ...,
        timeout: datetime.timedelta | float | None = ...,
        progress_handler: ProgressHandler | None = ...,
        raise_on_error: bool = ...,
    ) -> CallToolResult:
        ...

@dataclass
class CallToolResult:
    content: list[mcp.types.ContentBlock]
    structured_content: dict[str, Any] | None
    data: Any = ...
    is_error: bool = ...
