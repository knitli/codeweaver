# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeVar

from fastmcp.tools.tool_transform import ArgTransform, TransformedTool
from fastmcp.utilities.components import FastMCPComponent
from fastmcp.utilities.types import NotSetT
from mcp.types import ContentBlock, ToolAnnotations
from mcp.types import Tool as MCPTool
from pydantic import Field

if TYPE_CHECKING: ...
logger = ...
T = TypeVar("T")

@dataclass
class _WrappedResult[T]:


    result: T

class _UnserializableType: ...

def default_serializer(data: Any) -> str: ...

class ToolResult:
    def __init__(
        self,
        content: list[ContentBlock] | Any | None = ...,
        structured_content: dict[str, Any] | Any | None = ...,
    ) -> None: ...
    def to_mcp_result(self) -> list[ContentBlock] | tuple[list[ContentBlock], dict[str, Any]]: ...

class Tool(FastMCPComponent):


    parameters: Annotated[dict[str, Any], Field(description="JSON schema for tool parameters")]
    output_schema: Annotated[
        dict[str, Any] | None, Field(description="JSON schema for tool output")
    ] = ...
    annotations: Annotated[
        ToolAnnotations | None, Field(description="Additional annotations about the tool")
    ] = ...
    serializer: Annotated[
        Callable[[Any], str] | None,
        Field(description="Optional custom serializer for tool results"),
    ] = ...
    def enable(self) -> None: ...
    def disable(self) -> None: ...
    def to_mcp_tool(self, **overrides: Any) -> MCPTool: ...
    @staticmethod
    def from_function(
        fn: Callable[..., Any],
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
        annotations: ToolAnnotations | None = ...,
        exclude_args: list[str] | None = ...,
        output_schema: dict[str, Any] | None | NotSetT | Literal[False] = ...,
        serializer: Callable[[Any], str] | None = ...,
        enabled: bool | None = ...,
    ) -> FunctionTool:
        ...

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        ...

    @classmethod
    def from_tool(
        cls,
        tool: Tool,
        transform_fn: Callable[..., Any] | None = ...,
        name: str | None = ...,
        title: str | None | NotSetT = ...,
        transform_args: dict[str, ArgTransform] | None = ...,
        description: str | None | NotSetT = ...,
        tags: set[str] | None = ...,
        annotations: ToolAnnotations | None = ...,
        output_schema: dict[str, Any] | None | Literal[False] = ...,
        serializer: Callable[[Any], str] | None = ...,
        enabled: bool | None = ...,
    ) -> TransformedTool: ...

class FunctionTool(Tool):
    fn: Callable[..., Any]
    @classmethod
    def from_function(
        cls,
        fn: Callable[..., Any],
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
        annotations: ToolAnnotations | None = ...,
        exclude_args: list[str] | None = ...,
        output_schema: dict[str, Any] | None | NotSetT | Literal[False] = ...,
        serializer: Callable[[Any], str] | None = ...,
        enabled: bool | None = ...,
    ) -> FunctionTool:
        ...

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        ...

@dataclass
class ParsedFunction:
    fn: Callable[..., Any]
    name: str
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    @classmethod
    def from_function(
        cls,
        fn: Callable[..., Any],
        exclude_args: list[str] | None = ...,
        validate: bool = ...,
        wrap_non_object_output_schema: bool = ...,
    ) -> ParsedFunction: ...
