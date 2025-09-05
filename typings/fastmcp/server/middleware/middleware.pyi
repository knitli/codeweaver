# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeVar, runtime_checkable

import mcp.types as mt

from fastmcp.prompts.prompt import Prompt
from fastmcp.resources.resource import Resource
from fastmcp.resources.template import ResourceTemplate
from fastmcp.server.context import Context
from fastmcp.tools.tool import Tool

if TYPE_CHECKING: ...
__all__ = ["CallNext", "Middleware", "MiddlewareContext"]
logger = ...
T = TypeVar("T")
R = TypeVar("R", covariant=True)

@runtime_checkable
class CallNext(Protocol[T, R]):
    def __call__(self, context: MiddlewareContext[T]) -> Awaitable[R]: ...

ServerResultT = TypeVar(
    "ServerResultT",
    bound=mt.EmptyResult
    | mt.InitializeResult
    | mt.CompleteResult
    | mt.GetPromptResult
    | mt.ListPromptsResult
    | mt.ListResourcesResult
    | mt.ListResourceTemplatesResult
    | mt.ReadResourceResult
    | mt.CallToolResult
    | mt.ListToolsResult,
)

@runtime_checkable
class ServerResultProtocol(Protocol[ServerResultT]):
    root: ServerResultT

@dataclass(kw_only=True, frozen=True)
class MiddlewareContext[T]:


    message: T
    fastmcp_context: Context | None = ...
    source: Literal["client", "server"] = ...
    type: Literal["request", "notification"] = ...
    method: str | None = ...
    timestamp: datetime = ...
    def copy(self, **kwargs: Any) -> MiddlewareContext[T]: ...

def make_middleware_wrapper[T, R](middleware: Middleware, call_next: CallNext[T, R]) -> CallNext[T, R]:
    ...

class Middleware:

    async def __call__(self, context: MiddlewareContext[T], call_next: CallNext[T, Any]) -> Any:
        ...

    async def on_message(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any: ...
    async def on_request(
        self, context: MiddlewareContext[mt.Request], call_next: CallNext[mt.Request, Any]
    ) -> Any: ...
    async def on_notification(
        self, context: MiddlewareContext[mt.Notification], call_next: CallNext[mt.Notification, Any]
    ) -> Any: ...
    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, mt.CallToolResult],
    ) -> mt.CallToolResult: ...
    async def on_read_resource(
        self,
        context: MiddlewareContext[mt.ReadResourceRequestParams],
        call_next: CallNext[mt.ReadResourceRequestParams, mt.ReadResourceResult],
    ) -> mt.ReadResourceResult: ...
    async def on_get_prompt(
        self,
        context: MiddlewareContext[mt.GetPromptRequestParams],
        call_next: CallNext[mt.GetPromptRequestParams, mt.GetPromptResult],
    ) -> mt.GetPromptResult: ...
    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, list[Tool]],
    ) -> list[Tool]: ...
    async def on_list_resources(
        self,
        context: MiddlewareContext[mt.ListResourcesRequest],
        call_next: CallNext[mt.ListResourcesRequest, list[Resource]],
    ) -> list[Resource]: ...
    async def on_list_resource_templates(
        self,
        context: MiddlewareContext[mt.ListResourceTemplatesRequest],
        call_next: CallNext[mt.ListResourceTemplatesRequest, list[ResourceTemplate]],
    ) -> list[ResourceTemplate]: ...
    async def on_list_prompts(
        self,
        context: MiddlewareContext[mt.ListPromptsRequest],
        call_next: CallNext[mt.ListPromptsRequest, list[Prompt]],
    ) -> list[Prompt]: ...
