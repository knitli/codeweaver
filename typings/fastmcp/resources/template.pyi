# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import re

from collections.abc import Callable
from typing import Any

from fastmcp.resources.resource import Resource
from fastmcp.utilities.components import FastMCPComponent
from mcp.types import ResourceTemplate as MCPResourceTemplate
from pydantic import field_validator

"""Resource template functionality."""

def build_regex(template: str) -> re.Pattern: ...
def match_uri_template(uri: str, uri_template: str) -> dict[str, str] | None: ...

class ResourceTemplate(FastMCPComponent):


    uri_template: str = ...
    mime_type: str = ...
    parameters: dict[str, Any] = ...
    def enable(self) -> None: ...
    def disable(self) -> None: ...
    @staticmethod
    def from_function(
        fn: Callable[..., Any],
        uri_template: str,
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        mime_type: str | None = ...,
        tags: set[str] | None = ...,
        enabled: bool | None = ...,
    ) -> FunctionResourceTemplate: ...
    @field_validator("mime_type", mode="before")
    @classmethod
    def set_default_mime_type(cls, mime_type: str | None) -> str:
        ...

    def matches(self, uri: str) -> dict[str, Any] | None:
        ...

    async def read(self, arguments: dict[str, Any]) -> str | bytes:
        ...

    async def create_resource(self, uri: str, params: dict[str, Any]) -> Resource:
        ...

    def to_mcp_template(self, **overrides: Any) -> MCPResourceTemplate:
        ...

    @classmethod
    def from_mcp_template(cls, mcp_template: MCPResourceTemplate) -> ResourceTemplate:
        ...

    @property
    def key(self) -> str:
        ...

class FunctionResourceTemplate(ResourceTemplate):


    fn: Callable[..., Any]
    async def read(self, arguments: dict[str, Any]) -> str | bytes:
        ...

    @classmethod
    def from_function(
        cls,
        fn: Callable[..., Any],
        uri_template: str,
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        mime_type: str | None = ...,
        tags: set[str] | None = ...,
        enabled: bool | None = ...,
    ) -> FunctionResourceTemplate:
        ...
