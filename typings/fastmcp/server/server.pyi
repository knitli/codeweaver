# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, Literal, overload

import httpx

from fastmcp.client import Client
from fastmcp.client.transports import ClientTransport, ClientTransportT
from fastmcp.mcp_config import MCPConfig
from fastmcp.prompts import Prompt
from fastmcp.prompts.prompt import FunctionPrompt
from fastmcp.resources import Resource
from fastmcp.resources.template import ResourceTemplate
from fastmcp.server.auth.auth import OAuthProvider
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.server.middleware import Middleware
from fastmcp.server.openapi import ComponentFn as OpenAPIComponentFn
from fastmcp.server.openapi import FastMCPOpenAPI, RouteMap
from fastmcp.server.openapi import RouteMapFn as OpenAPIRouteMapFn
from fastmcp.server.proxy import FastMCPProxy
from fastmcp.settings import Settings
from fastmcp.tools.tool import FunctionTool, Tool
from fastmcp.utilities.types import NotSetT
from mcp.server.lowlevel.server import LifespanResultT
from mcp.types import AnyFunction, ToolAnnotations
from pydantic import AnyUrl
from starlette.middleware import Middleware as ASGIMiddleware

"""FastMCP - A more ergonomic interface for MCP servers."""
if TYPE_CHECKING: ...
logger = ...
type DuplicateBehavior = Literal["warn", "error", "replace", "ignore"]
type Transport = Literal["stdio", "http", "sse", "streamable-http"]
URI_PATTERN = ...

@asynccontextmanager
async def default_lifespan(server: FastMCP[LifespanResultT]) -> AsyncIterator[Any]:
    ...

class FastMCP(Generic[LifespanResultT]):
    def __init__(
        self,
        name: str | None = ...,
        instructions: str | None = ...,
        *,
        version: str | None = ...,
        auth: OAuthProvider | None = ...,
        middleware: list[Middleware] | None = ...,
        lifespan: Callable[[FastMCP[LifespanResultT]], AbstractAsyncContextManager[LifespanResultT]]
        | None = ...,
        tool_serializer: Callable[[Any], str] | None = ...,
        cache_expiration_seconds: float | None = ...,
        on_duplicate_tools: DuplicateBehavior | None = ...,
        on_duplicate_resources: DuplicateBehavior | None = ...,
        on_duplicate_prompts: DuplicateBehavior | None = ...,
        resource_prefix_format: Literal["protocol", "path"] | None = ...,
        mask_error_details: bool | None = ...,
        tools: list[Tool | Callable[..., Any]] | None = ...,
        dependencies: list[str] | None = ...,
        include_tags: set[str] | None = ...,
        exclude_tags: set[str] | None = ...,
        log_level: str | None = ...,
        debug: bool | None = ...,
        host: str | None = ...,
        port: int | None = ...,
        sse_path: str | None = ...,
        message_path: str | None = ...,
        streamable_http_path: str | None = ...,
        json_response: bool | None = ...,
        stateless_http: bool | None = ...,
    ) -> None: ...
    @property
    def settings(self) -> Settings: ...
    @property
    def name(self) -> str: ...
    @property
    def instructions(self) -> str | None: ...
    async def run_async(
        self, transport: Transport | None = ..., show_banner: bool = ..., **transport_kwargs: Any
    ) -> None:
        ...

    def run(
        self, transport: Transport | None = ..., show_banner: bool = ..., **transport_kwargs: Any
    ) -> None:
        ...

    def add_middleware(self, middleware: Middleware) -> None: ...
    async def get_tools(self) -> dict[str, Tool]:
        ...

    async def get_tool(self, key: str) -> Tool: ...
    async def get_resources(self) -> dict[str, Resource]:
        ...

    async def get_resource(self, key: str) -> Resource: ...
    async def get_resource_templates(self) -> dict[str, ResourceTemplate]:
        ...

    async def get_resource_template(self, key: str) -> ResourceTemplate:
        ...

    async def get_prompts(self) -> dict[str, Prompt]:
        ...

    async def get_prompt(self, key: str) -> Prompt: ...
    def custom_route(
        self, path: str, methods: list[str], name: str | None = ..., include_in_schema: bool = ...
    ):  # -> Callable[..., Callable[[Request], Awaitable[Response]]]:
        ...

    def add_tool(self, tool: Tool) -> Tool:
        ...

    def remove_tool(self, name: str) -> None:
        ...

    @overload
    def tool(
        self,
        name_or_fn: AnyFunction,
        *,
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
        output_schema: dict[str, Any] | None | NotSetT = ...,
        annotations: ToolAnnotations | dict[str, Any] | None = ...,
        exclude_args: list[str] | None = ...,
        enabled: bool | None = ...,
    ) -> FunctionTool: ...
    @overload
    def tool(
        self,
        name_or_fn: str | None = ...,
        *,
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
        output_schema: dict[str, Any] | None | NotSetT = ...,
        annotations: ToolAnnotations | dict[str, Any] | None = ...,
        exclude_args: list[str] | None = ...,
        enabled: bool | None = ...,
    ) -> Callable[[AnyFunction], FunctionTool]: ...
    def tool(
        self,
        name_or_fn: str | AnyFunction | None = ...,
        *,
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
        output_schema: dict[str, Any] | None | NotSetT = ...,
        annotations: ToolAnnotations | dict[str, Any] | None = ...,
        exclude_args: list[str] | None = ...,
        enabled: bool | None = ...,
    ) -> Callable[[AnyFunction], FunctionTool] | FunctionTool:
        ...

    def add_resource(self, resource: Resource) -> Resource:
        ...

    def add_template(self, template: ResourceTemplate) -> ResourceTemplate:
        ...

    def add_resource_fn(
        self,
        fn: AnyFunction,
        uri: str,
        name: str | None = ...,
        description: str | None = ...,
        mime_type: str | None = ...,
        tags: set[str] | None = ...,
    ) -> None:
        ...

    def resource(
        self,
        uri: str,
        *,
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        mime_type: str | None = ...,
        tags: set[str] | None = ...,
        enabled: bool | None = ...,
    ) -> Callable[[AnyFunction], Resource | ResourceTemplate]:
        ...

    def add_prompt(self, prompt: Prompt) -> Prompt:
        ...

    @overload
    def prompt(
        self,
        name_or_fn: AnyFunction,
        *,
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
        enabled: bool | None = ...,
    ) -> FunctionPrompt: ...
    @overload
    def prompt(
        self,
        name_or_fn: str | None = ...,
        *,
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
        enabled: bool | None = ...,
    ) -> Callable[[AnyFunction], FunctionPrompt]: ...
    def prompt(
        self,
        name_or_fn: str | AnyFunction | None = ...,
        *,
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
        enabled: bool | None = ...,
    ) -> Callable[[AnyFunction], FunctionPrompt] | FunctionPrompt:
        ...

    async def run_stdio_async(self, show_banner: bool = ...) -> None:
        ...

    async def run_http_async(
        self,
        show_banner: bool = ...,
        transport: Literal["http", "streamable-http", "sse"] = ...,
        host: str | None = ...,
        port: int | None = ...,
        log_level: str | None = ...,
        path: str | None = ...,
        uvicorn_config: dict[str, Any] | None = ...,
        middleware: list[ASGIMiddleware] | None = ...,
        stateless_http: bool | None = ...,
    ) -> None:
        ...

    async def run_sse_async(
        self,
        host: str | None = ...,
        port: int | None = ...,
        log_level: str | None = ...,
        path: str | None = ...,
        uvicorn_config: dict[str, Any] | None = ...,
    ) -> None:
        ...

    def sse_app(
        self,
        path: str | None = ...,
        message_path: str | None = ...,
        middleware: list[ASGIMiddleware] | None = ...,
    ) -> StarletteWithLifespan:
        ...

    def streamable_http_app(
        self, path: str | None = ..., middleware: list[ASGIMiddleware] | None = ...
    ) -> StarletteWithLifespan:
        ...

    def http_app(
        self,
        path: str | None = ...,
        middleware: list[ASGIMiddleware] | None = ...,
        json_response: bool | None = ...,
        stateless_http: bool | None = ...,
        transport: Literal["http", "streamable-http", "sse"] = ...,
    ) -> StarletteWithLifespan:
        ...

    async def run_streamable_http_async(
        self,
        host: str | None = ...,
        port: int | None = ...,
        log_level: str | None = ...,
        path: str | None = ...,
        uvicorn_config: dict[str, Any] | None = ...,
    ) -> None: ...
    def mount(
        self,
        server: FastMCP[LifespanResultT],
        prefix: str | None = ...,
        as_proxy: bool | None = ...,
        *,
        tool_separator: str | None = ...,
        resource_separator: str | None = ...,
        prompt_separator: str | None = ...,
    ) -> None:
        ...

    async def import_server(
        self,
        server: FastMCP[LifespanResultT],
        prefix: str | None = ...,
        tool_separator: str | None = ...,
        resource_separator: str | None = ...,
        prompt_separator: str | None = ...,
    ) -> None:
        ...

    @classmethod
    def from_openapi(
        cls,
        openapi_spec: dict[str, Any],
        client: httpx.AsyncClient,
        route_maps: list[RouteMap] | None = ...,
        route_map_fn: OpenAPIRouteMapFn | None = ...,
        mcp_component_fn: OpenAPIComponentFn | None = ...,
        mcp_names: dict[str, str] | None = ...,
        tags: set[str] | None = ...,
        **settings: Any,
    ) -> FastMCPOpenAPI:
        ...

    @classmethod
    def from_fastapi(
        cls,
        app: Any,
        name: str | None = ...,
        route_maps: list[RouteMap] | None = ...,
        route_map_fn: OpenAPIRouteMapFn | None = ...,
        mcp_component_fn: OpenAPIComponentFn | None = ...,
        mcp_names: dict[str, str] | None = ...,
        httpx_client_kwargs: dict[str, Any] | None = ...,
        tags: set[str] | None = ...,
        **settings: Any,
    ) -> FastMCPOpenAPI:
        ...

    @classmethod
    def as_proxy(
        cls,
        backend: Client[ClientTransportT]
        | ClientTransport
        | FastMCP[Any]
        | AnyUrl
        | Path
        | MCPConfig
        | dict[str, Any]
        | str,
        **settings: Any,
    ) -> FastMCPProxy:
        ...

    @classmethod
    def from_client(cls, client: Client[ClientTransportT], **settings: Any) -> FastMCPProxy:
        ...

@dataclass
class MountedServer:
    prefix: str | None
    server: FastMCP[Any]
    resource_prefix_format: Literal["protocol", "path"] | None = ...

def add_resource_prefix(
    uri: str, prefix: str, prefix_format: Literal["protocol", "path"] | None = ...
) -> str:
    ...

def remove_resource_prefix(
    uri: str, prefix: str, prefix_format: Literal["protocol", "path"] | None = ...
) -> str:
    ...

def has_resource_prefix(
    uri: str, prefix: str, prefix_format: Literal["protocol", "path"] | None = ...
) -> bool:
    ...
