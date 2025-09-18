# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from pathlib import Path
from typing import Any

from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthMetadata
from mcp.shared.auth import OAuthToken as OAuthToken

__all__ = ["OAuth"]
logger = ...

def default_cache_dir() -> Path: ...

class FileTokenStorage(TokenStorage):

    def __init__(self, server_url: str, cache_dir: Path | None = ...) -> None:
        ...

    @staticmethod
    def get_base_url(url: str) -> str:
        ...

    def get_cache_key(self) -> str:
        ...

    async def get_tokens(self) -> OAuthToken | None:
        ...

    async def set_tokens(self, tokens: OAuthToken) -> None:
        ...

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        ...

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        ...

    def clear(self) -> None:
        ...

    @classmethod
    def clear_all(cls, cache_dir: Path | None = ...) -> None:
        ...

async def discover_oauth_metadata(
    server_base_url: str, httpx_kwargs: dict[str, Any] | None = ...
) -> OAuthMetadata | None:
    ...

async def check_if_auth_required(mcp_url: str, httpx_kwargs: dict[str, Any] | None = ...) -> bool:
    ...

def OAuth(
    mcp_url: str,
    scopes: str | list[str] | None = ...,
    client_name: str = ...,
    token_storage_cache_dir: Path | None = ...,
    additional_client_metadata: dict[str, Any] | None = ...,
) -> OAuthClientProvider:
    ...
