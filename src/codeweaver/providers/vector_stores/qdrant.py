# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Qdrant provider for vector and hybrid search/store."""

from __future__ import annotations

import logging

from typing import Any

from pydantic import SecretStr

from codeweaver.config.providers import QdrantConfig
from codeweaver.exceptions import ProviderError
from codeweaver.providers.provider import Provider
from codeweaver.providers.vector_stores.qdrant_base import QdrantBaseProvider


logger = logging.getLogger(__name__)

QdrantClient = None
try:
    from qdrant_client import AsyncQdrantClient
except ImportError as e:
    raise ProviderError(
        "Qdrant client is required for QdrantVectorStoreProvider. Install it with: pip install qdrant-client"
    ) from e


class QdrantVectorStoreProvider(QdrantBaseProvider):
    """Qdrant vector store provider supporting local and remote deployments.

    Supports hybrid search with dense and sparse embeddings via named vectors.
    """

    _client: AsyncQdrantClient | None = None
    config: QdrantConfig = QdrantConfig()
    _metadata: dict[str, Any] | None = None
    _provider: Provider = Provider.QDRANT  # type: ignore

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the Qdrant instance from config."""
        return self.config.get("url", "http://localhost:6333")

    async def _build_client(self) -> AsyncQdrantClient:
        """Build Qdrant client based on configuration."""
        url = self.config.get("url", "http://localhost:6333")
        api_key = None

        # DEBUG: Print self.config state
        print(f"[DEBUG _build_client] self.config type: {type(self.config)}")
        print(f"[DEBUG _build_client] self.config keys: {list(self.config.keys()) if self.config else 'None'}")
        print(f"[DEBUG _build_client] url from self.config: {url}")

        # Try to get API key from config first
        if config_api_key := self.config.get("api_key") or self.config.get("client_options", {}).get("api_key"):
            api_key = config_api_key.get_secret_value() if isinstance(config_api_key, SecretStr) else config_api_key
            print(f"[DEBUG _build_client] Got api_key from config: {api_key[:8]}..." if api_key else "[DEBUG _build_client] api_key from config is empty")

        # Fall back to environment variable if not in config
        if not api_key:
            print(f"[DEBUG _build_client] self._provider = {self._provider}, type = {type(self._provider)}")
            print(f"[DEBUG _build_client] Provider.QDRANT = {Provider.QDRANT}")
            print(f"[DEBUG _build_client] api_key_env_vars = {self._provider.api_key_env_vars if hasattr(self._provider, 'api_key_env_vars') else 'N/A'}")
            api_key = self._provider.get_env_api_key()
            print(f"[DEBUG _build_client] Got api_key from env: {api_key[:8]}..." if api_key else "[DEBUG _build_client] api_key from env is None")

        # Build client kwargs based on connection type
        client_kwargs: dict[str, Any] = {"url": url, "api_key": api_key}
        print(f"[DEBUG _build_client] Final client_kwargs: url={url}, api_key={'set' if api_key else 'None'}")

        client = AsyncQdrantClient(**client_kwargs)
        # Store client before calling _ensure_collection (which needs self._client)
        self._client = client
        if collection_name := self.collection:
            await self._ensure_collection(collection_name)
        return client

    async def _init_provider(self) -> None:
        """We don't use this method at the moment for the main Qdrant provider."""


__all__ = ("QdrantVectorStoreProvider",)

# for debugging purposes
if __name__ == "__main__":
    store = QdrantVectorStoreProvider()
    import asyncio

    asyncio.run(store._initialize())
