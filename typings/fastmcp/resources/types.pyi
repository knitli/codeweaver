# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from pathlib import Path

from fastmcp.resources.resource import Resource
from pydantic import ValidationInfo

"""Concrete resource implementations."""
logger = ...

class TextResource(Resource):


    text: str = ...
    async def read(self) -> str:
        ...

class BinaryResource(Resource):


    data: bytes = ...
    async def read(self) -> bytes:
        ...

class FileResource(Resource):


    path: Path = ...
    is_binary: bool = ...
    mime_type: str = ...
    @pydantic.field_validator("path")
    @classmethod
    def validate_absolute_path(cls, path: Path) -> Path:
        ...

    @pydantic.field_validator("is_binary")
    @classmethod
    def set_binary_from_mime_type(cls, is_binary: bool, info: ValidationInfo) -> bool:
        ...

    async def read(self) -> str | bytes:
        ...

class HttpResource(Resource):


    url: str = ...
    mime_type: str = ...
    async def read(self) -> str | bytes:
        ...

class DirectoryResource(Resource):


    path: Path = ...
    recursive: bool = ...
    pattern: str | None = ...
    mime_type: str = ...
    @pydantic.field_validator("path")
    @classmethod
    def validate_absolute_path(cls, path: Path) -> Path:
        ...

    def list_files(self) -> list[Path]:
        ...

    async def read(self) -> str:
        ...
