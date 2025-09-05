# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal

from fastmcp.tools.tool import Tool, ToolResult
from fastmcp.utilities.types import NotSetT
from mcp.types import ToolAnnotations

logger = ...
_current_tool: ContextVar[TransformedTool | None] = ...

async def forward(**kwargs) -> ToolResult:
    ...

async def forward_raw(**kwargs) -> ToolResult:
    ...

@dataclass(kw_only=True)
class ArgTransform:


    name: str | NotSetT = ...
    description: str | NotSetT = ...
    default: Any | NotSetT = ...
    default_factory: Callable[[], Any] | NotSetT = ...
    type: Any | NotSetT = ...
    hide: bool = ...
    required: Literal[True] | NotSetT = ...
    examples: Any | NotSetT = ...
    def __post_init__(self):  # -> None:
        ...

class TransformedTool(Tool):


    model_config = ...
    parent_tool: Tool
    fn: Callable[..., Any]
    forwarding_fn: Callable[..., Any]
    transform_args: dict[str, ArgTransform]
    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        ...

    @classmethod
    def from_tool(
        cls,
        tool: Tool,
        name: str | None = ...,
        title: str | None | NotSetT = ...,
        description: str | None | NotSetT = ...,
        tags: set[str] | None = ...,
        transform_fn: Callable[..., Any] | None = ...,
        transform_args: dict[str, ArgTransform] | None = ...,
        annotations: ToolAnnotations | None = ...,
        output_schema: dict[str, Any] | None | Literal[False] = ...,
        serializer: Callable[[Any], str] | None = ...,
        enabled: bool | None = ...,
    ) -> TransformedTool:
        ...
