# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import enum

from collections.abc import Callable
from dataclasses import dataclass
from re import Pattern
from typing import TYPE_CHECKING, Any, Literal

import httpx

from fastmcp.resources import Resource, ResourceTemplate
from fastmcp.server import Context
from fastmcp.server.server import FastMCP
from fastmcp.tools.tool import Tool, ToolResult
from fastmcp.utilities import openapi
from fastmcp.utilities.openapi import HTTPRoute
from mcp.types import ToolAnnotations

"""FastMCP server implementation for OpenAPI integration."""
if TYPE_CHECKING: ...
logger = ...
type HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
type RouteMapFn = Callable[[HTTPRoute, MCPType], MCPType | None]
type ComponentFn = Callable[[HTTPRoute, OpenAPITool | OpenAPIResource | OpenAPIResourceTemplate], None]

class MCPType(enum.Enum):


    TOOL = ...
    RESOURCE = ...
    RESOURCE_TEMPLATE = ...
    EXCLUDE = ...

class RouteType(enum.Enum):


    TOOL = ...
    RESOURCE = ...
    RESOURCE_TEMPLATE = ...
    IGNORE = ...

@dataclass(kw_only=True)
class RouteMap:


    methods: list[HttpMethod] | Literal["*"] = ...
    pattern: Pattern[str] | str = ...
    route_type: RouteType | MCPType | None = ...
    tags: set[str] = ...
    mcp_type: MCPType | None = ...
    mcp_tags: set[str] = ...
    def __post_init__(self):  # -> None:
        ...

DEFAULT_ROUTE_MAPPINGS = ...

class OpenAPITool(Tool):

    def __init__(
        self,
        client: httpx.AsyncClient,
        route: openapi.HTTPRoute,
        name: str,
        description: str,
        parameters: dict[str, Any],
        output_schema: dict[str, Any] | None = ...,
        tags: set[str] | None = ...,
        timeout: float | None = ...,
        annotations: ToolAnnotations | None = ...,
        serializer: Callable[[Any], str] | None = ...,
    ) -> None: ...

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        ...

class OpenAPIResource(Resource):

    def __init__(
        self,
        client: httpx.AsyncClient,
        route: openapi.HTTPRoute,
        uri: str,
        name: str,
        description: str,
        mime_type: str = ...,
        tags: set[str] = ...,
        timeout: float | None = ...,
    ) -> None: ...

    async def read(self) -> str | bytes:
        ...

class OpenAPIResourceTemplate(ResourceTemplate):

    def __init__(
        self,
        client: httpx.AsyncClient,
        route: openapi.HTTPRoute,
        uri_template: str,
        name: str,
        description: str,
        parameters: dict[str, Any],
        tags: set[str] = ...,
        timeout: float | None = ...,
    ) -> None: ...

    async def create_resource(
        self, uri: str, params: dict[str, Any], context: Context | None = ...
    ) -> Resource:
        ...

class FastMCPOpenAPI(FastMCP):

    def __init__(
        self,
        openapi_spec: dict[str, Any],
        client: httpx.AsyncClient,
        name: str | None = ...,
        route_maps: list[RouteMap] | None = ...,
        route_map_fn: RouteMapFn | None = ...,
        mcp_component_fn: ComponentFn | None = ...,
        mcp_names: dict[str, str] | None = ...,
        tags: set[str] | None = ...,
        timeout: float | None = ...,
        **settings: Any,
    ) -> None:
        ...
