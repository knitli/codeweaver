# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""SDK settings for vector store providers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from pydantic import Field, PrivateAttr
from qdrant_client.models import (
    BinaryQuantization,
    CollectionParams,
    HnswConfig,
    OptimizersConfig,
    ProductQuantization,
    ScalarQuantization,
    SparseVectorParams,
    VectorParams,
    WalConfig,
)
from qdrant_client.models import CollectionConfig as QdrantCollectionConfig

from codeweaver.core import INJECTED
from codeweaver.core.types import AnonymityConversion, BasedModel, FilteredKey, FilteredKeyT
from codeweaver.core.utils import deep_merge_dicts
from codeweaver.providers.dependencies import EmbeddingCapabilityGroupDep
from codeweaver.providers.types.embedding import EmbeddingCapabilityGroup
from codeweaver.providers.types.vector_store import CollectionMetadata


def get_embedding_group(group: EmbeddingCapabilityGroupDep = INJECTED) -> EmbeddingCapabilityGroup:
    """Get the embedding capability group, using dependency injection."""
    return group


class CollectionConfig(BasedModel):
    """Collection configuration for Qdrant and in-memory vector stores.

    NOTE: The vector configurations share many of the same properties as these collection parameters. If vector configurations exist, such as for hnsw_config or quantization_config, they will override the corresponding collection parameters.
    """

    collection_name: str | None = None
    "Collection name override. Defaults to a unique name based on the project name."
    vectors_config: Mapping[str, VectorParams] | None = None
    "Configuration for individual vector types in the collection."
    quantization_config: ScalarQuantization | ProductQuantization | BinaryQuantization | None = None
    "Configuration for quantization used in the collection."
    sparse_vectors_config: Mapping[str, SparseVectorParams] | None = None
    "Configuration for individual sparse vector types in the collection."
    wal_config: WalConfig | None = None
    "Configuration for the write-ahead log (WAL) used in the collection. We have no default configuration for the WAL at this time. Qdrant's defaults are good for nearly all cases, but you can customize it for performance tuning, resource, or durability requirements."
    optimizer_config: OptimizersConfig | None = None
    "Configuration for optimizers used in the collection. No default configuration. Optimizing segments can increase throughput/concurrency at the cost of additional memory usage.  See https://qdrant.tech/documentation/concepts/optimizer/"
    hnsw_config: HnswConfig | None = Field(
        default_factory=lambda: HnswConfig(
            m=24, ef_construct=130, payload_m=120, full_scan_threshold=10000
        )
    )
    "Configuration for HNSW (Hierarchical Navigable Small World) index used for approximate nearest neighbor search. We generally recommend you keep our defaults here, which we will tweak and fine-tune over time to get optimal performance for code search."
    _vectors_initialized: bool = PrivateAttr(default=False)

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Return telemetry keys for privacy-first data collection."""
        from codeweaver.core.types import AnonymityConversion

        return {FilteredKey("collection_name"): AnonymityConversion.HASH}

    async def params(self) -> CollectionParams:
        """Return the Qdrant collection parameters for this configuration."""
        if not self._vectors_initialized:
            await self.set_vector_params()
        return CollectionParams.model_construct(
            vectors=self.vectors_config, sparse_vectors=self.sparse_vectors_config
        )

    async def set_vector_params(
        self, embedding_group: EmbeddingCapabilityGroup | None = None
    ) -> None:
        """Assemble the vector parameters for the collection."""
        embedding_group = embedding_group or get_embedding_group()
        params = await embedding_group.as_vector_params()
        vectors = params.vectors
        if vectors is not None:
            if isinstance(vectors, dict):
                assembled_vectors = cast(dict[str, VectorParams], vectors)
            else:
                assembled_vectors = cast(dict[str, VectorParams], vectors.model_dump())
        else:
            assembled_vectors = {}
        self.vectors_config = deep_merge_dicts(dict(self.vectors_config or {}), assembled_vectors)  # type: ignore
        self.sparse_vectors_config = deep_merge_dicts(  # type: ignore
            dict(self.sparse_vectors_config or {}),  # type: ignore
            cast(dict[str, SparseVectorParams], params.sparse_vectors or {}),  # ty:ignore[invalid-argument-type]
        )
        self._vectors_initialized = True

    async def as_qdrant_config(self, metadata: CollectionMetadata) -> QdrantCollectionConfig:
        """Convert the collection configuration to a QdrantCollectionConfig object."""
        return QdrantCollectionConfig.model_construct(
            params=await self.params(),
            hnsw_config=self.hnsw_config,
            optimizer_config=self.optimizer_config,
            wal_config=self.wal_config,
            metadata=metadata.model_dump(),
        )


__all__ = ("CollectionConfig", "QdrantCollectionConfig", "get_embedding_group")
