# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from fastmcp.utilities.components import FastMCPComponent
from fastmcp.utilities.types import FastMCPBaseModel
from mcp.types import ContentBlock, PromptMessage, Role
from mcp.types import Prompt as MCPPrompt

"""Base classes for FastMCP prompts."""
logger = ...

def Message(content: str | ContentBlock, role: Role | None = ..., **kwargs: Any) -> PromptMessage:
    ...

message_validator = ...
type SyncPromptResult = (
    str | PromptMessage | dict[str, Any] | Sequence[str | PromptMessage | dict[str, Any]]
)
type PromptResult = SyncPromptResult | Awaitable[SyncPromptResult]

class PromptArgument(FastMCPBaseModel):


    name: str = ...
    description: str | None = ...
    required: bool = ...

class Prompt(FastMCPComponent, ABC):


    arguments: list[PromptArgument] | None = ...
    def enable(self) -> None: ...
    def disable(self) -> None: ...
    def to_mcp_prompt(self, **overrides: Any) -> MCPPrompt:
        ...

    @staticmethod
    def from_function(
        fn: Callable[..., PromptResult | Awaitable[PromptResult]],
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
        enabled: bool | None = ...,
    ) -> FunctionPrompt:
        ...

    @abstractmethod
    async def render(self, arguments: dict[str, Any] | None = ...) -> list[PromptMessage]:

        ...

class FunctionPrompt(Prompt):


    fn: Callable[..., PromptResult | Awaitable[PromptResult]]
    @classmethod
    def from_function(
        cls,
        fn: Callable[..., PromptResult | Awaitable[PromptResult]],
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
        enabled: bool | None = ...,
    ) -> FunctionPrompt:
        ...

    async def render(self, arguments: dict[str, Any] | None = ...) -> list[PromptMessage]:
        ...
