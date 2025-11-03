# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Vector store interfaces and implementations for CodeWeaver."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from codeweaver.config.providers import VectorStoreProviderSettings
    from codeweaver.providers.embedding.providers import EmbeddingProvider
    from codeweaver.providers.reranking import RerankingProvider
    from codeweaver.providers.vector_stores.base import VectorStoreProvider


def get_vector_store_provider(settings: VectorStoreProviderSettings) -> VectorStoreProvider[Any]:
    """Create vector store provider from settings.

    Args:
        settings: Vector store configuration with provider selection and config.
        embedder: Optional embedding provider for dimension validation (required for Qdrant).
        reranking: Optional reranking provider for search result optimization.

    Returns:
        Configured vector store provider instance (QdrantVectorStoreProvider or MemoryVectorStoreProvider).

    Raises:
        ValueError: If provider type is not recognized or required config is missing.
        ImportError: If required dependencies for selected provider are not installed.

    Examples:
        >>> from codeweaver.config.providers import VectorStoreProviderSettings
        >>> settings = VectorStoreProviderSettings(provider=Provider.MEMORY)
        >>> provider = get_vector_store_provider(settings)
        >>> isinstance(provider, MemoryVectorStoreProvider)
        True

        >>> from unittest.mock import MagicMock
        >>> qdrant_settings = VectorStoreProviderSettings(
        ...     provider="qdrant",
        ...     qdrant={"url": "http://localhost:6333", "collection_name": "test"},
        ... )
        >>> mock_embedder = MagicMock()
        >>> provider = get_vector_store_provider(qdrant_settings)
        >>> isinstance(provider, QdrantVectorStoreProvider)
        True
    """
    from codeweaver.providers.provider import Provider
    from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider
    from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider

    provider_type = settings.get("provider", Provider.MEMORY)

    if provider_type == Provider.QDRANT:
        if qdrant_config := settings.get("qdrant", {}):
            return QdrantVectorStoreProvider.model_construct(
                config=qdrant_config, _client=None, _metadata=None
            )

        raise ValueError("Qdrant provider selected but no qdrant config provided")
    if provider_type == Provider.MEMORY:
        memory_config = settings.get("memory", {})
        return MemoryVectorStoreProvider.model_construct(config=memory_config, _client=None)

    raise ValueError(
        f"Unknown vector store provider: {provider_type}. Supported providers: 'qdrant', 'memory'"
    )


__all__ = ("VectorStoreProvider", "get_vector_store_provider")
