# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Search-related types and classes for provider systems.

The primary type defined here is `SearchPackage`, which encapsulates the components necessary for performing a search operation, including the embedding models, reranking models, and vector stores.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from pydantic_ai import Agent


if TYPE_CHECKING:
    from codeweaver.core.types import ModelName, ModelNameT
    from codeweaver.providers.embedding.capabilities.base import (
        EmbeddingModelCapabilities,
        SparseEmbeddingModelCapabilities,
    )
    from codeweaver.providers.embedding.providers.base import (
        EmbeddingProvider,
        SparseEmbeddingProvider,
    )
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
    from codeweaver.providers.reranking.providers.base import RerankingProvider
    from codeweaver.providers.types.embedding import EmbeddingCapabilityGroup
    from codeweaver.providers.vector_stores.base import VectorStoreProvider


class ModelNameDict(TypedDict, total=False):
    """Dictionary of model names used in a search package."""

    dense: ModelNameT | None
    sparse: ModelNameT | None
    reranking: tuple[ModelNameT, ...] | None


class ModelCapDict(TypedDict, total=False):
    """Dictionary of model capabilities used in a search package."""

    dense: EmbeddingModelCapabilities | None
    sparse: SparseEmbeddingModelCapabilities | None
    reranking: tuple[RerankingModelCapabilities, ...] | None


class SearchPackage:
    """Represents a complete package of CodeWeaver providers."""

    embedding: EmbeddingProvider

    sparse_embedding: SparseEmbeddingProvider

    reranking: tuple[RerankingProvider, ...]

    vector_store: VectorStoreProvider

    capabilities: EmbeddingCapabilityGroup

    agent: Agent | None = None

    def __init__(
        self,
        embedding: EmbeddingProvider,
        sparse_embedding: SparseEmbeddingProvider,
        reranking: tuple[RerankingProvider, ...],
        vector_store: VectorStoreProvider,
        capabilities: EmbeddingCapabilityGroup,
        agent: Agent | None = None,
    ):
        """Initializes a SearchPackage with the given providers and capabilities."""
        self.embedding = embedding
        self.sparse_embedding = sparse_embedding
        self.reranking = reranking
        self.vector_store = vector_store
        self.capabilities = capabilities
        self.agent = agent

    @property
    def model_names(self) -> ModelNameDict:
        """Get the names of the models used in this search package."""
        return ModelNameDict(
            dense=self.capabilities.dense_model,
            sparse=self.capabilities.sparse_model or self.capabilities.idf_model,
            reranking=tuple(ModelName(model.model_name) for model in self.reranking),
        )

    @property
    def caps(self) -> ModelCapDict:
        """Get the capabilities of the models used in this search package."""
        return ModelCapDict(
            dense=self.capabilities.dense.capability if self.capabilities.dense else None,
            sparse=self.capabilities.sparse.capability if self.capabilities.sparse else None,
            reranking=tuple(model.capabilities for model in self.reranking)
            if self.reranking
            else None,
        )


__all__ = ("ModelCapDict", "ModelNameDict", "SearchPackage")
