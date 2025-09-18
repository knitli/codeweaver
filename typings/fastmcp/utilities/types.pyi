# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from types import EllipsisType
from typing import TypeVar

import mcp.types

from mcp.types import Annotations
from pydantic import BaseModel, TypeAdapter

"""Common types used across FastMCP."""
T = TypeVar("T")
NotSet = ...
type NotSetT = EllipsisType

class FastMCPBaseModel(BaseModel):


    model_config = ...

@lru_cache(maxsize=5000)
def get_cached_typeadapter[T](cls: T) -> TypeAdapter[T]:
    ...

def issubclass_safe(cls: type, base: type) -> bool:
    ...

def is_class_member_of_type(cls: type, base: type) -> bool:
    ...

def find_kwarg_by_type(fn: Callable, kwarg_type: type) -> str | None:
    ...

class Image:

    def __init__(
        self,
        path: str | Path | None = ...,
        data: bytes | None = ...,
        format: str | None = ...,
        annotations: Annotations | None = ...,
    ) -> None: ...
    def to_image_content(
        self, mime_type: str | None = ..., annotations: Annotations | None = ...
    ) -> mcp.types.ImageContent:
        ...

class Audio:

    def __init__(
        self,
        path: str | Path | None = ...,
        data: bytes | None = ...,
        format: str | None = ...,
        annotations: Annotations | None = ...,
    ) -> None: ...
    def to_audio_content(
        self, mime_type: str | None = ..., annotations: Annotations | None = ...
    ) -> mcp.types.AudioContent: ...

class File:

    def __init__(
        self,
        path: str | Path | None = ...,
        data: bytes | None = ...,
        format: str | None = ...,
        name: str | None = ...,
        annotations: Annotations | None = ...,
    ) -> None: ...
    def to_resource_content(
        self, mime_type: str | None = ..., annotations: Annotations | None = ...
    ) -> mcp.types.EmbeddedResource: ...

def replace_type(type_, type_map: dict[type, type]):  # -> type | UnionType | Any:
    ...
