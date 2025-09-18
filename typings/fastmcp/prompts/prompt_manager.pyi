# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastmcp.prompts.prompt import FunctionPrompt, Prompt, PromptResult
from fastmcp.server.server import MountedServer
from fastmcp.settings import DuplicateBehavior
from mcp import GetPromptResult

if TYPE_CHECKING: ...
logger = ...

class PromptManager:

    def __init__(
        self,
        duplicate_behavior: DuplicateBehavior | None = ...,
        mask_error_details: bool | None = ...,
    ) -> None: ...
    def mount(self, server: MountedServer) -> None:
        ...

    async def has_prompt(self, key: str) -> bool:
        ...

    async def get_prompt(self, key: str) -> Prompt:
        ...

    async def get_prompts(self) -> dict[str, Prompt]:
        ...

    async def list_prompts(self) -> list[Prompt]:
        ...

    def add_prompt_from_fn(
        self,
        fn: Callable[..., PromptResult | Awaitable[PromptResult]],
        name: str | None = ...,
        description: str | None = ...,
        tags: set[str] | None = ...,
    ) -> FunctionPrompt:
        ...

    def add_prompt(self, prompt: Prompt) -> Prompt:
        ...

    async def render_prompt(
        self, name: str, arguments: dict[str, Any] | None = ...
    ) -> GetPromptResult:
        ...
