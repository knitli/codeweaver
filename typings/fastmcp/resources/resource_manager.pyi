# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fastmcp.resources.resource import Resource
from fastmcp.resources.template import ResourceTemplate
from fastmcp.server.server import MountedServer
from fastmcp.settings import DuplicateBehavior
from pydantic import AnyUrl

"""Resource manager functionality."""
if TYPE_CHECKING: ...
logger = ...

class ResourceManager:

    def __init__(
        self,
        duplicate_behavior: DuplicateBehavior | None = ...,
        mask_error_details: bool | None = ...,
    ) -> None:
        ...

    def mount(self, server: MountedServer) -> None:
        ...

    async def get_resources(self) -> dict[str, Resource]:
        ...

    async def get_resource_templates(self) -> dict[str, ResourceTemplate]:
        ...

    async def list_resources(self) -> list[Resource]:
        ...

    async def list_resource_templates(self) -> list[ResourceTemplate]:
        ...

    def add_resource_or_template_from_fn(
        self,
        fn: Callable[..., Any],
        uri: str,
        name: str | None = ...,
        description: str | None = ...,
        mime_type: str | None = ...,
        tags: set[str] | None = ...,
    ) -> Resource | ResourceTemplate:
        ...

    def add_resource_from_fn(
        self,
        fn: Callable[..., Any],
        uri: str,
        name: str | None = ...,
        description: str | None = ...,
        mime_type: str | None = ...,
        tags: set[str] | None = ...,
    ) -> Resource:
        ...

    def add_resource(self, resource: Resource) -> Resource:
        ...

    def add_template_from_fn(
        self,
        fn: Callable[..., Any],
        uri_template: str,
        name: str | None = ...,
        description: str | None = ...,
        mime_type: str | None = ...,
        tags: set[str] | None = ...,
    ) -> ResourceTemplate:
        ...

    def add_template(self, template: ResourceTemplate) -> ResourceTemplate:
        ...

    async def has_resource(self, uri: AnyUrl | str) -> bool:
        ...

    async def get_resource(self, uri: AnyUrl | str) -> Resource:
        ...

    async def read_resource(self, uri: AnyUrl | str) -> str | bytes:
        ...
