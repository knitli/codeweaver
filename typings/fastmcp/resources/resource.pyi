# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import abc

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any, Self

from fastmcp.utilities.components import FastMCPComponent
from mcp.types import Resource as MCPResource
from pydantic import AnyUrl, UrlConstraints, field_validator, model_validator

"""Base classes and interfaces for FastMCP resources."""
if TYPE_CHECKING: ...

class Resource(FastMCPComponent, abc.ABC):


    model_config = ...
    uri: Annotated[AnyUrl, UrlConstraints(host_required=False)] = ...
    name: str = ...
    mime_type: str = ...
    def enable(self) -> None: ...
    def disable(self) -> None: ...
    @staticmethod
    def from_function(
        fn: Callable[..., Any],
        uri: str | AnyUrl,
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        mime_type: str | None = ...,
        tags: set[str] | None = ...,
        enabled: bool | None = ...,
    ) -> FunctionResource: ...
    @field_validator("mime_type", mode="before")
    @classmethod
    def set_default_mime_type(cls, mime_type: str | None) -> str:
        ...

    @model_validator(mode="after")
    def set_default_name(self) -> Self:
        ...

    @abc.abstractmethod
    async def read(self) -> str | bytes:

        ...

    def to_mcp_resource(self, **overrides: Any) -> MCPResource:
        ...

    @property
    def key(self) -> str:
        ...

class FunctionResource(Resource):


    fn: Callable[..., Any]
    @classmethod
    def from_function(
        cls,
        fn: Callable[..., Any],
        uri: str | AnyUrl,
        name: str | None = ...,
        title: str | None = ...,
        description: str | None = ...,
        mime_type: str | None = ...,
        tags: set[str] | None = ...,
        enabled: bool | None = ...,
    ) -> FunctionResource:
        ...

    async def read(self) -> str | bytes:
        ...
