# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Centralized cache manager for embedding providers with namespace isolation.

This module provides the EmbeddingCacheManager class which replaces per-instance
stores with a centralized, namespace-isolated caching system. This enables true
cross-instance deduplication while maintaining async safety.

Architecture:
- Namespace isolation: {provider_id}.{embedding_kind} prevents collisions
- Async-safe locking: Uses asyncio.Lock instead of threading.Lock
- Centralized storage: Replaces ClassVar registries with singleton pattern
- DI integration: Singleton via FastAPI lifespan and dependency injection

Example:
    >>> cache_manager = EmbeddingCacheManager(registry=get_embedding_registry())
    >>> namespace = cache_manager._get_namespace("voyage-code-2", "dense")
    >>> chunks, hash_map = await cache_manager.deduplicate(chunks, namespace, batch_id)
"""

from __future__ import annotations

import asyncio

from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from pydantic import UUID7, ConfigDict, Field, PrivateAttr

from codeweaver.core import BlakeHashKey, CodeChunk
from codeweaver.core.constants import ONE_MEGABYTE
from codeweaver.core.stores import BlakeStore, UUIDStore, make_blake_store, make_uuid_store
from codeweaver.core.types import BasedModel
from codeweaver.core.utils import get_blake_hash
from codeweaver.providers.embedding.registry import EmbeddingRegistry


if TYPE_CHECKING:
    from codeweaver.core.types import AnonymityConversion, EmbeddingBatchInfo, FilteredKeyT


class EmbeddingCacheManager(BasedModel):
    """Centralized cache manager with namespace isolation for embedding providers.

    Replaces per-instance _store and _hash_store ClassVar registries with a
    singleton pattern that provides:
    - True cross-instance deduplication
    - Namespace isolation (dense vs sparse, different providers)
    - Async-safe locking per namespace
    - Statistics tracking per namespace

    The cache manager is designed to be injected as a singleton dependency into
    all embedding provider instances via FastAPI's lifespan and DI system.

    Attributes:
        registry: Global embedding registry for cross-provider coordination
        _batch_stores: Namespace-isolated UUID stores for batches
        _hash_stores: Namespace-isolated Blake hash stores for deduplication
        _locks: Async locks per namespace for thread-safe operations
        _stats: Statistics per namespace (hits, misses, unique chunks)
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=False,
        # Allow mock objects during testing by skipping strict type validation
        validate_assignment=False,
    )

    registry: EmbeddingRegistry = Field(..., description="Global embedding registry instance")

    # Namespace-isolated stores (namespace = "{provider_id}.{embedding_kind}")
    # Use PrivateAttr for internal state that shouldn't be part of the model
    _batch_stores: dict[str, UUIDStore[list]] = PrivateAttr(default_factory=dict)
    _hash_stores: dict[str, BlakeStore[UUID7]] = PrivateAttr(default_factory=dict)
    _locks: dict[str, asyncio.Lock] = PrivateAttr(default_factory=dict)
    _stats: dict[str, dict[str, int]] = PrivateAttr(default_factory=dict)

    def _get_namespace(self, provider_id: str, embedding_kind: str) -> str:
        """Generate namespace key for store isolation.

        Namespace format: "{provider_id}.{embedding_kind}"
        Examples:
            - "voyage-code-2.dense"
            - "voyage-code-2.sparse"
            - "cohere-embed-v3.dense"

        Args:
            provider_id: Unique provider identifier (e.g., "voyage-code-2")
            embedding_kind: Type of embedding ("dense" or "sparse")

        Returns:
            Namespace key for store lookup
        """
        return f"{provider_id}.{embedding_kind}"

    def _get_lock(self, namespace: str) -> asyncio.Lock:
        """Get or create async lock for namespace.

        Lazy initialization of locks to avoid creating locks for unused namespaces.

        Args:
            namespace: Namespace key

        Returns:
            Async lock for namespace
        """
        if namespace not in self._locks:
            self._locks[namespace] = asyncio.Lock()
        return self._locks[namespace]

    def _get_batch_store(self, namespace: str) -> UUIDStore[list]:
        """Get or create batch store for namespace.

        Args:
            namespace: Namespace key

        Returns:
            UUID store for batches
        """
        if namespace not in self._batch_stores:
            # 3MB limit per namespace (same as original per-instance limit)
            self._batch_stores[namespace] = make_uuid_store(
                value_type=list, size_limit=ONE_MEGABYTE * 10
            )
        return self._batch_stores[namespace]

    def _get_hash_store(self, namespace: str) -> BlakeStore[UUID7]:
        """Get or create hash store for namespace.

        Args:
            namespace: Namespace key

        Returns:
            Blake hash store for deduplication
        """
        if namespace not in self._hash_stores:
            # 10MB limit per namespace (same as original per-instance limit)
            self._hash_stores[namespace] = make_blake_store(
                value_type=UUID, size_limit=ONE_MEGABYTE * 10
            )
        return self._hash_stores[namespace]

    def _init_stats(self, namespace: str) -> None:
        """Initialize statistics for namespace if not exists."""
        if namespace not in self._stats:
            self._stats[namespace] = {"hits": 0, "misses": 0, "unique_chunks": 0, "total_chunks": 0}

    async def deduplicate(
        self, chunks: list[CodeChunk], namespace: str, batch_id: UUID7
    ) -> tuple[list[CodeChunk], dict[int, BlakeHashKey]]:
        """Deduplicate chunks using namespace-isolated hash store.

        This method identifies chunks that have already been processed in this
        namespace and returns only the unique chunks that need embedding.

        Args:
            chunks: List of code chunks to deduplicate
            namespace: Namespace key (e.g., "voyage-code-2.dense")
            batch_id: UUID for this batch (used for tracking)

        Returns:
            Tuple of (unique_chunks, hash_mapping) where:
                - unique_chunks: Chunks not seen before in this namespace
                - hash_mapping: Dict mapping chunk index to its Blake hash

        Thread Safety:
            Uses async lock per namespace to ensure thread-safe deduplication
        """
        async with self._get_lock(namespace):
            hash_store = self._get_hash_store(namespace)
            self._init_stats(namespace)

            unique_chunks: list[CodeChunk] = []
            hash_mapping: dict[int, BlakeHashKey] = {}

            # Compute hashes for all chunks
            chunk_hashes = [get_blake_hash(chunk.content.encode("utf-8")) for chunk in chunks]

            # Check each chunk for duplicates
            for idx, (chunk, chunk_hash) in enumerate(zip(chunks, chunk_hashes, strict=False)):
                hash_mapping[idx] = chunk_hash

                # Check if we've seen this chunk before
                if chunk_hash in hash_store:
                    # Duplicate - already processed
                    self._stats[namespace]["hits"] += 1
                else:
                    # New chunk - needs embedding
                    unique_chunks.append(chunk)
                    hash_store[chunk_hash] = batch_id
                    self._stats[namespace]["misses"] += 1
                    self._stats[namespace]["unique_chunks"] += 1

            self._stats[namespace]["total_chunks"] += len(chunks)
            return unique_chunks, hash_mapping

    async def store_batch(self, chunks: list[CodeChunk], batch_id: UUID7, namespace: str) -> None:
        """Store batch for potential reprocessing.

        Stores the final chunk list (after deduplication) for this batch.
        This enables reprocessing or retrieval of batches later.

        Args:
            chunks: Final list of chunks to store
            batch_id: UUID for this batch
            namespace: Namespace key

        Thread Safety:
            Uses async lock per namespace to ensure thread-safe storage
        """
        async with self._get_lock(namespace):
            batch_store = self._get_batch_store(namespace)
            batch_store[batch_id] = chunks

    async def register_embeddings(
        self, chunk_id: UUID7, embedding_info: EmbeddingBatchInfo, chunk: CodeChunk
    ) -> None:
        """Register embeddings in global registry.

        Handles updating existing entries or creating new ones in the registry.
        This is NOT namespace-isolated - the registry maintains embeddings for all
        chunks regardless of which provider created them.

        Args:
            chunk_id: UUID of the chunk
            embedding_info: Batch information with embeddings
            chunk: The CodeChunk object to store
        """
        from codeweaver.core.types.embeddings import ChunkEmbeddings

        # Registry is dict-like, handles its own locking
        if (registered := self.registry.get(chunk_id)) is not None:
            # Check if we already have an embedding with this intent
            has_existing = embedding_info.intent in registered.embeddings

            if has_existing:
                # Replace existing embedding (e.g., during re-embedding with skip_deduplication=True)
                self.registry[chunk_id] = registered.update(embedding_info)
            else:
                # Add new embedding kind to existing entry
                self.registry[chunk_id] = registered.add(embedding_info)

            if registered.chunk != chunk:
                # because we create new CodeChunk instances during processing, we need to update the chunk reference
                self.registry[chunk_id] = self.registry[chunk_id].model_copy(
                    update={"chunk": chunk}
                )
        else:
            # Create new ChunkEmbeddings with the chunk, then add the embedding
            self.registry[chunk_id] = ChunkEmbeddings(chunk=chunk).add(embedding_info)

    def get_batch(self, batch_id: UUID7, namespace: str) -> list[CodeChunk] | None:
        """Get batch by ID from namespace-isolated store.

        Args:
            batch_id: UUID of the batch
            namespace: Namespace key

        Returns:
            List of chunks if batch exists, None otherwise
        """
        batch_store = self._get_batch_store(namespace)
        return batch_store.get(batch_id)

    def get_stats(self, namespace: str | None = None) -> dict[str, dict[str, int]]:
        """Get deduplication statistics.

        Args:
            namespace: Specific namespace, or None for all namespaces

        Returns:
            Statistics dict for namespace(s)
        """
        if namespace is not None:
            return {namespace: self._stats.get(namespace, {})}
        return self._stats.copy()

    def clear_namespace(self, namespace: str) -> None:
        """Clear all data for a specific namespace.

        Useful for testing or resetting provider state.

        Args:
            namespace: Namespace to clear

        Warning:
            This is a destructive operation - all cached data will be lost
        """
        if namespace in self._batch_stores:
            del self._batch_stores[namespace]
        if namespace in self._hash_stores:
            del self._hash_stores[namespace]
        if namespace in self._stats:
            del self._stats[namespace]
        if namespace in self._locks:
            del self._locks[namespace]

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Define telemetry anonymization for EmbeddingCacheManager fields.

        Returns:
            None - registry field handles its own telemetry, private attrs excluded automatically
        """
        # registry field will handle its own telemetry via its _telemetry_keys method
        # Private attributes (_batch_stores, _hash_stores, etc.) are automatically excluded
        return None


__all__ = ("EmbeddingCacheManager",)
