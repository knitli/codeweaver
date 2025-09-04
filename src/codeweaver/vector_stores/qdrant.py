# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Qdrant provider for vector and hybrid search/store."""

from mistralai import Any

from codeweaver.embedding.providers import EmbeddingProvider
from codeweaver.exceptions import ProviderError
from codeweaver.reranking import RerankingProvider
from codeweaver.vector_stores.base import VectorStoreProvider


QdrantClient = None

try:
    from qdrant_client import AsyncQdrantClient

except ImportError as e:
    raise ProviderError(
        "Qdrant client is required for QdrantVectorStore. Install it with: pip install qdrant-client"
    ) from e


class QdrantVectorStore(VectorStoreProvider[AsyncQdrantClient]):
    """Qdrant vector store provider."""

    _client: AsyncQdrantClient
    _embedder: EmbeddingProvider[Any]
    _reranker: RerankingProvider[Any] | None = None
