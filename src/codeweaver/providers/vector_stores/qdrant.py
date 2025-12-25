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
from codeweaver.core.types.provider import Provider
from codeweaver.exceptions import ProviderError
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

        # Try to get API key from config first
        if config_api_key := self.config.get("api_key") or self.config.get(
            "client_options", {}
        ).get("api_key"):
            api_key = (
                config_api_key.get_secret_value()
                if isinstance(config_api_key, SecretStr)
                else config_api_key
            )

        # Fall back to environment variable if not in config
        if not api_key:
            api_key = self._provider.get_env_api_key()
        from urllib.parse import urlparse

        # Check if API key is required for cloud instances
        is_cloud_url = (
            url and isinstance(url, str) and urlparse(url).hostname.endswith(".cloud.qdrant.io")
        )
        if is_cloud_url and not api_key:
            raise ProviderError(
                f"API key required for Qdrant Cloud connection to {url}. "
                "Please set the QDRANT__SERVICE__API_KEY environment variable or "
                "add api_key to provider_settings in your configuration file."
            )

        # Build client kwargs based on connection type
        # Use longer timeout for large batch operations (default httpx is 5s which is too short)
        timeout = self.config.get("timeout", 120)  # 2 minutes default
        client_kwargs: dict[str, Any] = {"url": url, "api_key": api_key, "timeout": timeout}

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
