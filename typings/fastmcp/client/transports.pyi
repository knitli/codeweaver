# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import abc
import contextlib
import datetime

from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, Literal, TypeVar, Unpack, overload

import httpx
import mcp.types

from fastmcp.mcp_config import MCPConfig
from fastmcp.server.server import FastMCP
from mcp import ClientSession
from mcp.client.session import (
    ElicitationFnT,
    ListRootsFnT,
    LoggingFnT,
    MessageHandlerFnT,
    SamplingFnT,
)
from mcp.server.fastmcp import FastMCP as FastMCP1Server
from pydantic import AnyUrl
from typing_extensions import TypedDict

logger = ...
ClientTransportT = TypeVar("ClientTransportT", bound=ClientTransport)
__all__ = [
    "ClientTransport",
    "FastMCPStdioTransport",
    "FastMCPTransport",
    "NodeStdioTransport",
    "NpxStdioTransport",
    "PythonStdioTransport",
    "SSETransport",
    "StdioTransport",
    "StreamableHttpTransport",
    "UvxStdioTransport",
    "infer_transport",
]

class SessionKwargs(TypedDict, total=False):


    read_timeout_seconds: datetime.timedelta | None
    sampling_callback: SamplingFnT | None
    list_roots_callback: ListRootsFnT | None
    logging_callback: LoggingFnT | None
    elicitation_callback: ElicitationFnT | None
    message_handler: MessageHandlerFnT | None
    client_info: mcp.types.Implementation | None

class ClientTransport(abc.ABC):

    @abc.abstractmethod
    @contextlib.asynccontextmanager
    async def connect_session(
        self, **session_kwargs: Unpack[SessionKwargs]
    ) -> AsyncIterator[ClientSession]:

        ...

    async def close(self):  # -> None:
        ...

class WSTransport(ClientTransport):

    def __init__(self, url: str | AnyUrl) -> None: ...
    @contextlib.asynccontextmanager
    async def connect_session(
        self, **session_kwargs: Unpack[SessionKwargs]
    ) -> AsyncIterator[ClientSession]: ...

class SSETransport(ClientTransport):

    def __init__(
        self,
        url: str | AnyUrl,
        headers: dict[str, str] | None = ...,
        auth: httpx.Auth | Literal["oauth"] | str | None = ...,
        sse_read_timeout: datetime.timedelta | float | None = ...,
        httpx_client_factory: Callable[[], httpx.AsyncClient] | None = ...,
    ) -> None: ...
    @contextlib.asynccontextmanager
    async def connect_session(
        self, **session_kwargs: Unpack[SessionKwargs]
    ) -> AsyncIterator[ClientSession]: ...

class StreamableHttpTransport(ClientTransport):

    def __init__(
        self,
        url: str | AnyUrl,
        headers: dict[str, str] | None = ...,
        auth: httpx.Auth | Literal["oauth"] | str | None = ...,
        sse_read_timeout: datetime.timedelta | float | None = ...,
        httpx_client_factory: Callable[[], httpx.AsyncClient] | None = ...,
    ) -> None: ...
    @contextlib.asynccontextmanager
    async def connect_session(
        self, **session_kwargs: Unpack[SessionKwargs]
    ) -> AsyncIterator[ClientSession]: ...

class StdioTransport(ClientTransport):

    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str] | None = ...,
        cwd: str | None = ...,
        keep_alive: bool | None = ...,
    ) -> None:
        ...

    @contextlib.asynccontextmanager
    async def connect_session(
        self, **session_kwargs: Unpack[SessionKwargs]
    ) -> AsyncIterator[ClientSession]: ...
    async def connect(self, **session_kwargs: Unpack[SessionKwargs]) -> ClientSession | None: ...
    async def disconnect(self):  # -> None:
        ...
    async def close(self):  # -> None:
        ...

class PythonStdioTransport(StdioTransport):

    def __init__(
        self,
        script_path: str | Path,
        args: list[str] | None = ...,
        env: dict[str, str] | None = ...,
        cwd: str | None = ...,
        python_cmd: str = ...,
        keep_alive: bool | None = ...,
    ) -> None:
        ...

class FastMCPStdioTransport(StdioTransport):

    def __init__(
        self,
        script_path: str | Path,
        args: list[str] | None = ...,
        env: dict[str, str] | None = ...,
        cwd: str | None = ...,
        keep_alive: bool | None = ...,
    ) -> None: ...

class NodeStdioTransport(StdioTransport):

    def __init__(
        self,
        script_path: str | Path,
        args: list[str] | None = ...,
        env: dict[str, str] | None = ...,
        cwd: str | None = ...,
        node_cmd: str = ...,
        keep_alive: bool | None = ...,
    ) -> None:
        ...

class UvxStdioTransport(StdioTransport):

    def __init__(
        self,
        tool_name: str,
        tool_args: list[str] | None = ...,
        project_directory: str | None = ...,
        python_version: str | None = ...,
        with_packages: list[str] | None = ...,
        from_package: str | None = ...,
        env_vars: dict[str, str] | None = ...,
        keep_alive: bool | None = ...,
    ) -> None:
        ...

class NpxStdioTransport(StdioTransport):

    def __init__(
        self,
        package: str,
        args: list[str] | None = ...,
        project_directory: str | None = ...,
        env_vars: dict[str, str] | None = ...,
        use_package_lock: bool = ...,
        keep_alive: bool | None = ...,
    ) -> None:
        ...

class FastMCPTransport(ClientTransport):

    def __init__(self, mcp: FastMCP | FastMCP1Server, raise_exceptions: bool = ...) -> None:
        ...

    @contextlib.asynccontextmanager
    async def connect_session(
        self, **session_kwargs: Unpack[SessionKwargs]
    ) -> AsyncIterator[ClientSession]: ...

class MCPConfigTransport(ClientTransport):

    def __init__(self, config: MCPConfig | dict) -> None: ...
    @contextlib.asynccontextmanager
    async def connect_session(
        self, **session_kwargs: Unpack[SessionKwargs]
    ) -> AsyncIterator[ClientSession]: ...

@overload
def infer_transport[ClientTransportT: ClientTransport](transport: ClientTransportT) -> ClientTransportT: ...
@overload
def infer_transport(transport: FastMCP) -> FastMCPTransport: ...
@overload
def infer_transport(transport: FastMCP1Server) -> FastMCPTransport: ...
@overload
def infer_transport(transport: MCPConfig) -> MCPConfigTransport: ...
@overload
def infer_transport(transport: dict[str, Any]) -> MCPConfigTransport: ...
@overload
def infer_transport(transport: AnyUrl) -> SSETransport | StreamableHttpTransport: ...
@overload
def infer_transport(
    transport: str,
) -> PythonStdioTransport | NodeStdioTransport | SSETransport | StreamableHttpTransport: ...
@overload
def infer_transport(transport: Path) -> PythonStdioTransport | NodeStdioTransport: ...
def infer_transport(
    transport: ClientTransport
    | FastMCP
    | FastMCP1Server
    | AnyUrl
    | Path
    | MCPConfig
    | dict[str, Any]
    | str,
) -> ClientTransport:
    ...
