# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import mcp.types

from fastmcp.client.client import Client, FastMCP1Server
from fastmcp.client.elicitation import ElicitResult
from fastmcp.client.logging import LogMessage
from fastmcp.client.roots import RootsList
from fastmcp.client.transports import ClientTransportT
from fastmcp.mcp_config import MCPConfig
from fastmcp.prompts import Prompt, PromptMessage
from fastmcp.prompts.prompt_manager import PromptManager
from fastmcp.resources import Resource, ResourceTemplate
from fastmcp.resources.resource_manager import ResourceManager
from fastmcp.server import Context
from fastmcp.server.context import Context
from fastmcp.server.server import FastMCP
from fastmcp.tools.tool import Tool, ToolResult
from fastmcp.tools.tool_manager import ToolManager
from fastmcp.utilities.components import MirroredComponent
from mcp.client.session import ClientSession
from mcp.shared.context import LifespanContextT, RequestContext
from mcp.types import GetPromptResult
from pydantic.networks import AnyUrl

if TYPE_CHECKING: ...
logger = ...

class ProxyToolManager(ToolManager):

    def __init__(self, client_factory: Callable[[], Client], **kwargs) -> None: ...
    async def get_tools(self) -> dict[str, Tool]:
        ...

    async def list_tools(self) -> list[Tool]:
        ...

    async def call_tool(self, key: str, arguments: dict[str, Any]) -> ToolResult:
        ...

class ProxyResourceManager(ResourceManager):

    def __init__(self, client_factory: Callable[[], Client], **kwargs) -> None: ...
    async def get_resources(self) -> dict[str, Resource]:
        ...

    async def get_resource_templates(self) -> dict[str, ResourceTemplate]:
        ...

    async def list_resources(self) -> list[Resource]:
        ...

    async def list_resource_templates(self) -> list[ResourceTemplate]:
        ...

    async def read_resource(self, uri: AnyUrl | str) -> str | bytes:
        ...

class ProxyPromptManager(PromptManager):

    def __init__(self, client_factory: Callable[[], Client], **kwargs) -> None: ...
    async def get_prompts(self) -> dict[str, Prompt]:
        ...

    async def list_prompts(self) -> list[Prompt]:
        ...

    async def render_prompt(
        self, name: str, arguments: dict[str, Any] | None = ...
    ) -> GetPromptResult:
        ...

class ProxyTool(Tool, MirroredComponent):

    def __init__(self, client: Client, **kwargs) -> None: ...
    @classmethod
    def from_mcp_tool(cls, client: Client, mcp_tool: mcp.types.Tool) -> ProxyTool:
        ...

    async def run(self, arguments: dict[str, Any], context: Context | None = ...) -> ToolResult:
        ...

class ProxyResource(Resource, MirroredComponent):


    _client: Client
    _value: str | bytes | None = ...
    def __init__(self, client: Client, *, _value: str | bytes | None = ..., **kwargs) -> None: ...
    @classmethod
    def from_mcp_resource(cls, client: Client, mcp_resource: mcp.types.Resource) -> ProxyResource:
        ...

    async def read(self) -> str | bytes:
        ...

class ProxyTemplate(ResourceTemplate, MirroredComponent):

    def __init__(self, client: Client, **kwargs) -> None: ...
    @classmethod
    def from_mcp_template(
        cls, client: Client, mcp_template: mcp.types.ResourceTemplate
    ) -> ProxyTemplate:
        ...

    async def create_resource(
        self, uri: str, params: dict[str, Any], context: Context | None = ...
    ) -> ProxyResource:
        ...

class ProxyPrompt(Prompt, MirroredComponent):


    _client: Client
    def __init__(self, client: Client, **kwargs) -> None: ...
    @classmethod
    def from_mcp_prompt(cls, client: Client, mcp_prompt: mcp.types.Prompt) -> ProxyPrompt:
        ...

    async def render(self, arguments: dict[str, Any]) -> list[PromptMessage]:
        ...

class FastMCPProxy(FastMCP):

    def __init__(
        self,
        client: Client | None = ...,
        *,
        client_factory: Callable[[], Client] | None = ...,
        **kwargs,
    ) -> None:
        ...

async def default_proxy_roots_handler(
    context: RequestContext[ClientSession, LifespanContextT],
) -> RootsList:
    ...

class ProxyClient(Client[ClientTransportT]):

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
        **kwargs,
    ) -> None: ...
    @classmethod
    async def default_sampling_handler(
        cls,
        messages: list[mcp.types.SamplingMessage],
        params: mcp.types.CreateMessageRequestParams,
        context: RequestContext[ClientSession, LifespanContextT],
    ) -> mcp.types.CreateMessageResult:
        ...

    @classmethod
    async def default_elicitation_handler(
        cls,
        message: str,
        response_type: type,
        params: mcp.types.ElicitRequestParams,
        context: RequestContext[ClientSession, LifespanContextT],
    ) -> ElicitResult:
        ...

    @classmethod
    async def default_log_handler(cls, message: LogMessage) -> None:
        ...

    @classmethod
    async def default_progress_handler(
        cls, progress: float, total: float | None, message: str | None
    ) -> None:
        ...

class StatefulProxyClient(ProxyClient[ClientTransportT]):

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        ...

    def new_stateful(self) -> Client[ClientTransportT]:
        ...
