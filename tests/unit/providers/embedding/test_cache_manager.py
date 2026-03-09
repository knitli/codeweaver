# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Comprehensive unit tests for EmbeddingCacheManager.

Tests cover all cache manager functionality:
- Namespace isolation (dense/sparse, multiple providers)
- Async-safe locking and concurrent operations
- Deduplication logic with hash stores
- Batch storage and retrieval
- Registry integration (add, update, replace)
- Statistics tracking
- Namespace clearing
- Edge cases (empty lists, single chunk)
"""

import asyncio

from pathlib import Path
from typing import Any

import pytest

from codeweaver.core import CodeChunk, EmbeddingBatchInfo, uuid7
from codeweaver.core.spans import Span
from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager
from codeweaver.providers.embedding.registry import EmbeddingRegistry

# Rebuild models to resolve AstThing forward references
# This ensures CodeChunk and related models can be instantiated in tests
from codeweaver.semantic.ast_grep import rebuild_models_for_tests


rebuild_models_for_tests()

# Rebuild EmbeddingCacheManager to allow Any type for registry field during testing
# This lets us use Mock objects without Pydantic validation errors
try:
    EmbeddingCacheManager.model_rebuild(_types_namespace={"EmbeddingRegistry": Any})
except Exception:
    pass  # Ignore rebuild errors in tests


@pytest.fixture
def mock_embedding_registry():
    """Create a real embedding registry.

    Now that AstThing forward reference issues are resolved,
    we can use a real EmbeddingRegistry for testing.
    """
    return EmbeddingRegistry()


@pytest.fixture
def cache_manager(mock_embedding_registry) -> EmbeddingCacheManager:
    """Create fresh cache manager for each test with mock registry."""
    return EmbeddingCacheManager(registry=mock_embedding_registry)


@pytest.fixture
def sample_chunks() -> list[CodeChunk]:
    """Create sample CodeChunk objects for testing.

    All chunks have unique content for namespace isolation tests.
    For deduplication tests, use duplicate_chunks fixture instead.

    Uses model_construct() to bypass Pydantic validation and avoid
    AstThing forward reference issues during testing.
    """
    return [
        CodeChunk.model_construct(
            content="def hello():\n    print('Hello, World!')",
            file_path=Path("/test/sample1.py"),
            line_range=Span(1, 2, uuid7()),  # Span requires source_id
            language="python",
            _version="1.1.0",
            _embeddings={},
        ),
        CodeChunk.model_construct(
            content="function greet() { console.log('Hi!'); }",
            file_path=Path("/test/sample2.js"),
            line_range=Span(5, 5, uuid7()),  # Span requires source_id
            language="javascript",
            _version="1.1.0",
            _embeddings={},
        ),
        CodeChunk.model_construct(
            content="class Foo:\n    pass",  # Unique content (not a duplicate)
            file_path=Path("/test/sample3.py"),
            line_range=Span(10, 11, uuid7()),  # Span requires source_id
            language="python",
            _version="1.1.0",
            _embeddings={},
        ),
    ]


@pytest.fixture
def duplicate_chunks() -> list[CodeChunk]:
    """Create CodeChunk objects with duplicates for deduplication testing.

    Chunk 1 and chunk 3 have identical content to test deduplication logic.
    """
    return [
        CodeChunk.model_construct(
            content="def hello():\n    print('Hello, World!')",
            file_path=Path("/test/sample1.py"),
            line_range=Span(1, 2, uuid7()),
            language="python",
            _version="1.1.0",
            _embeddings={},
        ),
        CodeChunk.model_construct(
            content="function greet() { console.log('Hi!'); }",
            file_path=Path("/test/sample2.js"),
            line_range=Span(5, 5, uuid7()),
            language="javascript",
            _version="1.1.0",
            _embeddings={},
        ),
        CodeChunk.model_construct(
            content="def hello():\n    print('Hello, World!')",  # Duplicate of first
            file_path=Path("/test/sample3.py"),
            line_range=Span(10, 11, uuid7()),
            language="python",
            _version="1.1.0",
            _embeddings={},
        ),
    ]


@pytest.fixture
def sample_embeddings() -> list[list[float]]:
    """Create sample embedding vectors."""
    return [
        [0.1, 0.2, 0.3, 0.4, 0.5],
        [0.6, 0.7, 0.8, 0.9, 1.0],
        [0.11, 0.21, 0.31, 0.41, 0.51],  # Unique (for third unique chunk)
    ]


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestNamespaceIsolation:
    """Test namespace isolation between different providers and embedding kinds."""

    async def test_dense_and_sparse_isolation(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify dense and sparse embeddings use separate namespaces."""
        dense_namespace = cache_manager._get_namespace("voyage-code-2", "dense")
        sparse_namespace = cache_manager._get_namespace("voyage-code-2", "sparse")

        batch_id_dense = uuid7()
        batch_id_sparse = uuid7()

        # Deduplicate for dense
        unique_dense, hash_map_dense = await cache_manager.deduplicate(
            sample_chunks, dense_namespace, batch_id_dense
        )

        # Deduplicate for sparse (should not see dense hashes)
        unique_sparse, hash_map_sparse = await cache_manager.deduplicate(
            sample_chunks, sparse_namespace, batch_id_sparse
        )

        # Both should see all chunks as unique (no cross-namespace deduplication)
        assert len(unique_dense) == 3
        assert len(unique_sparse) == 3
        assert len(hash_map_dense) == 3
        assert len(hash_map_sparse) == 3

    async def test_provider_isolation(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify different providers use separate namespaces."""
        voyage_namespace = cache_manager._get_namespace("voyage-code-2", "dense")
        cohere_namespace = cache_manager._get_namespace("cohere-embed-v3", "dense")

        batch_id_voyage = uuid7()
        batch_id_cohere = uuid7()

        # Deduplicate for Voyage
        await cache_manager.deduplicate(sample_chunks, voyage_namespace, batch_id_voyage)

        # Deduplicate for Cohere (should not see Voyage hashes)
        unique_cohere, _ = await cache_manager.deduplicate(
            sample_chunks, cohere_namespace, batch_id_cohere
        )

        # Cohere should see all chunks as unique
        assert len(unique_cohere) == 3

    async def test_stats_per_namespace(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify statistics are tracked per namespace."""
        ns1 = cache_manager._get_namespace("provider1", "dense")
        ns2 = cache_manager._get_namespace("provider2", "dense")

        batch_id_1 = uuid7()
        batch_id_2 = uuid7()

        # Process chunks in namespace 1
        await cache_manager.deduplicate(sample_chunks[:2], ns1, batch_id_1)

        # Process chunks in namespace 2
        await cache_manager.deduplicate(sample_chunks, ns2, batch_id_2)

        # Check stats are separate
        stats = cache_manager.get_stats()
        assert ns1 in stats
        assert ns2 in stats
        assert stats[ns1]["total_chunks"] == 2
        assert stats[ns2]["total_chunks"] == 3


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestDeduplication:
    """Test deduplication logic with hash stores."""

    async def test_duplicate_detection(
        self, cache_manager: EmbeddingCacheManager, duplicate_chunks: list[CodeChunk]
    ):
        """Verify duplicate chunks are detected correctly."""
        namespace = cache_manager._get_namespace("test-provider", "dense")
        batch_id = uuid7()

        # First chunk and third chunk have same content (duplicates)
        unique_chunks, hash_mapping = await cache_manager.deduplicate(
            duplicate_chunks, namespace, batch_id
        )

        # Should have 2 unique chunks (first and second, third is duplicate of first)
        unique_list = list(unique_chunks)
        assert len(unique_list) == 2
        assert unique_list[0].content == duplicate_chunks[0].content
        assert unique_list[1].content == duplicate_chunks[1].content

        # Hash mapping should cover all 3 chunks
        assert len(hash_mapping) == 3

    async def test_second_batch_deduplication(
        self, cache_manager: EmbeddingCacheManager, duplicate_chunks: list[CodeChunk]
    ):
        """Verify second batch correctly identifies already-seen chunks."""
        namespace = cache_manager._get_namespace("test-provider", "dense")

        batch_id_1 = uuid7()
        batch_id_2 = uuid7()

        # First batch
        unique_1, _ = await cache_manager.deduplicate(duplicate_chunks, namespace, batch_id_1)
        assert len(list(unique_1)) == 2  # First and second chunks are unique

        # Second batch with same chunks
        unique_2, _ = await cache_manager.deduplicate(duplicate_chunks, namespace, batch_id_2)
        assert len(list(unique_2)) == 0  # All chunks already seen

    async def test_statistics_tracking(
        self, cache_manager: EmbeddingCacheManager, duplicate_chunks: list[CodeChunk]
    ):
        """Verify hit/miss statistics are tracked correctly."""
        namespace = cache_manager._get_namespace("test-provider", "dense")
        batch_id = uuid7()

        # First deduplication
        await cache_manager.deduplicate(duplicate_chunks, namespace, batch_id)

        stats = cache_manager.get_stats(namespace)
        assert namespace in stats
        assert stats[namespace]["hits"] == 1  # Third chunk is duplicate of first
        assert stats[namespace]["misses"] == 2  # First and second are new
        assert stats[namespace]["unique_chunks"] == 2
        assert stats[namespace]["total_chunks"] == 3


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestAsyncSafeLocking:
    """Test async-safe locking behavior during concurrent operations."""

    async def test_concurrent_deduplication(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify concurrent deduplication operations are properly locked."""
        namespace = cache_manager._get_namespace("test-provider", "dense")

        async def deduplicate_batch(batch_num: int):
            batch_id = uuid7()
            unique, _ = await cache_manager.deduplicate(sample_chunks, namespace, batch_id)
            return len(list(unique))

        # Run 10 concurrent deduplication operations
        results = await asyncio.gather(*[deduplicate_batch(i) for i in range(10)])

        # First operation should see 3 unique chunks (sample_chunks has 3 unique items)
        assert results[0] == 3  # First batch sees unique chunks
        assert all(r == 0 for r in results[1:])  # Subsequent batches see nothing new

    async def test_concurrent_batch_storage(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify concurrent batch storage operations don't corrupt data."""
        namespace = cache_manager._get_namespace("test-provider", "dense")

        async def store_batch(batch_num: int):
            batch_id = uuid7()
            await cache_manager.store_batch(sample_chunks[:2], batch_id, namespace)
            return batch_id

        # Store 10 batches concurrently
        batch_ids = await asyncio.gather(*[store_batch(i) for i in range(10)])

        # Verify all batches were stored correctly
        for batch_id in batch_ids:
            retrieved = cache_manager.get_batch(batch_id, namespace)
            assert retrieved is not None
            assert len(retrieved) == 2


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestBatchStorage:
    """Test batch storage and retrieval functionality."""

    async def test_store_and_retrieve_batch(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify batches can be stored and retrieved correctly."""
        namespace = cache_manager._get_namespace("test-provider", "dense")
        batch_id = uuid7()

        # Store batch
        await cache_manager.store_batch(sample_chunks, batch_id, namespace)

        # Retrieve batch
        retrieved = cache_manager.get_batch(batch_id, namespace)
        assert retrieved is not None
        assert len(retrieved) == len(sample_chunks)
        assert retrieved[0].content == sample_chunks[0].content

    async def test_get_nonexistent_batch(self, cache_manager: EmbeddingCacheManager):
        """Verify getting a non-existent batch returns None."""
        namespace = cache_manager._get_namespace("test-provider", "dense")
        batch_id = uuid7()

        retrieved = cache_manager.get_batch(batch_id, namespace)
        assert retrieved is None

    async def test_batch_namespace_isolation(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify batches are isolated per namespace."""
        ns1 = cache_manager._get_namespace("provider1", "dense")
        ns2 = cache_manager._get_namespace("provider2", "dense")
        batch_id = uuid7()

        # Store in namespace 1
        await cache_manager.store_batch(sample_chunks, batch_id, ns1)

        # Should not be retrievable from namespace 2
        retrieved_ns2 = cache_manager.get_batch(batch_id, ns2)
        assert retrieved_ns2 is None

        # Should be retrievable from namespace 1
        retrieved_ns1 = cache_manager.get_batch(batch_id, ns1)
        assert retrieved_ns1 is not None


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestRegistryIntegration:
    """Test integration with global embedding registry."""

    async def test_register_new_chunk(
        self,
        cache_manager: EmbeddingCacheManager,
        sample_chunks: list[CodeChunk],
        sample_embeddings: list[list[float]],
    ):
        """Verify new chunk embeddings are registered correctly."""
        chunk = sample_chunks[0]
        chunk_id = chunk.chunk_id  # Use the chunk's existing ID
        embedding = sample_embeddings[0]

        batch_id_for_info = uuid7()
        embedding_info = EmbeddingBatchInfo.create_dense(
            batch_id=batch_id_for_info,
            batch_index=0,
            chunk_id=chunk_id,
            model="test-model",
            embeddings=embedding,
            dimension=len(embedding),
            intent="indexing",
        )

        # Register embeddings
        await cache_manager.register_embeddings(chunk_id, embedding_info, chunk)

        # Verify in registry
        registered = cache_manager.registry.get(chunk_id)
        assert registered is not None
        assert registered.chunk == chunk
        assert "indexing" in registered.embeddings

    async def test_add_embedding_to_existing_chunk(
        self,
        cache_manager: EmbeddingCacheManager,
        sample_chunks: list[CodeChunk],
        sample_embeddings: list[list[float]],
    ):
        """Verify additional embeddings can be added to existing chunks."""
        chunk = sample_chunks[0]
        chunk_id = chunk.chunk_id  # Use the chunk's existing ID

        # Register first embedding (dense)
        dense_batch_id = uuid7()
        dense_info = EmbeddingBatchInfo.create_dense(
            batch_id=dense_batch_id,
            batch_index=0,
            chunk_id=chunk_id,
            model="dense-model",
            embeddings=sample_embeddings[0],
            dimension=len(sample_embeddings[0]),
            intent="indexing",
        )
        await cache_manager.register_embeddings(chunk_id, dense_info, chunk)

        # Register second embedding (sparse)
        from codeweaver.core.types.embeddings import CodeWeaverSparseEmbedding

        sparse_batch_id = uuid7()
        sparse_info = EmbeddingBatchInfo.create_sparse(
            batch_id=sparse_batch_id,
            batch_index=0,
            chunk_id=chunk_id,
            model="sparse-model",
            embeddings=CodeWeaverSparseEmbedding(indices=[1, 2, 3], values=[0.5, 0.6, 0.7]),
            intent="backup",
        )
        await cache_manager.register_embeddings(chunk_id, sparse_info, chunk)

        # Verify both embeddings exist
        registered = cache_manager.registry.get(chunk_id)
        assert registered is not None
        assert "indexing" in registered.embeddings
        assert "backup" in registered.embeddings

    async def test_replace_existing_embedding(
        self,
        cache_manager: EmbeddingCacheManager,
        sample_chunks: list[CodeChunk],
        sample_embeddings: list[list[float]],
    ):
        """Verify existing embeddings can be replaced."""
        chunk = sample_chunks[0]
        chunk_id = chunk.chunk_id  # Use the chunk's existing ID

        # Register first embedding
        first_batch_id = uuid7()
        first_info = EmbeddingBatchInfo.create_dense(
            batch_id=first_batch_id,
            batch_index=0,
            chunk_id=chunk_id,
            model="model-v1",
            embeddings=sample_embeddings[0],
            dimension=len(sample_embeddings[0]),
            intent="indexing",
        )
        await cache_manager.register_embeddings(chunk_id, first_info, chunk)

        # Replace with new embedding (same intent)
        second_batch_id = uuid7()
        second_info = EmbeddingBatchInfo.create_dense(
            batch_id=second_batch_id,
            batch_index=0,
            chunk_id=chunk_id,
            model="model-v2",
            embeddings=sample_embeddings[1],  # Different embedding
            dimension=len(sample_embeddings[1]),
            intent="indexing",  # Same intent
        )
        await cache_manager.register_embeddings(chunk_id, second_info, chunk)

        # Verify embedding was replaced
        registered = cache_manager.registry.get(chunk_id)
        assert registered is not None
        indexing_embedding = registered.embeddings.get("indexing")
        assert indexing_embedding is not None
        assert str(indexing_embedding.model) == "model-v2"
        assert indexing_embedding.embeddings == tuple(sample_embeddings[1])

    async def test_update_chunk_reference(
        self,
        cache_manager: EmbeddingCacheManager,
        sample_chunks: list[CodeChunk],
        sample_embeddings: list[list[float]],
    ):
        """Verify chunk references are updated when different instances provided."""
        old_chunk = sample_chunks[0]
        chunk_id = old_chunk.chunk_id  # Use the chunk's existing ID

        # Create a new chunk instance with same ID but different object
        new_chunk = CodeChunk.model_construct(
            content=old_chunk.content,
            file_path=old_chunk.file_path,
            line_range=old_chunk.line_range,
            language=old_chunk.language,
            chunk_id=chunk_id,  # Use same chunk_id
            _version="1.1.0",
            _embeddings={},
        )

        # Register with old chunk
        first_batch_id = uuid7()
        first_embedding_info = EmbeddingBatchInfo.create_dense(
            batch_id=first_batch_id,
            batch_index=0,
            chunk_id=chunk_id,
            model="test-model",
            embeddings=sample_embeddings[0],
            dimension=len(sample_embeddings[0]),
            intent="indexing",
        )
        await cache_manager.register_embeddings(chunk_id, first_embedding_info, old_chunk)

        # Register again with new chunk instance (same intent to trigger update path)
        second_batch_id = uuid7()
        second_embedding_info = EmbeddingBatchInfo.create_dense(
            batch_id=second_batch_id,
            batch_index=0,
            chunk_id=chunk_id,
            model="test-model-v2",  # Different model to ensure update
            embeddings=sample_embeddings[1],  # Different embeddings
            dimension=len(sample_embeddings[1]),
            intent="indexing",  # Same intent
        )
        await cache_manager.register_embeddings(chunk_id, second_embedding_info, new_chunk)

        # Verify chunk reference was updated
        registered = cache_manager.registry.get(chunk_id)
        assert registered is not None
        # Chunk should be equal to new_chunk (data-wise)
        assert registered.chunk == new_chunk
        # Model was updated so it should have new embedding
        assert str(registered.embeddings["indexing"].model) == "test-model-v2"


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestStatistics:
    """Test statistics tracking functionality."""

    async def test_get_all_stats(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify get_stats() returns all namespace statistics."""
        ns1 = cache_manager._get_namespace("provider1", "dense")
        ns2 = cache_manager._get_namespace("provider2", "sparse")

        # Process in both namespaces
        await cache_manager.deduplicate(sample_chunks[:2], ns1, uuid7())
        await cache_manager.deduplicate(sample_chunks, ns2, uuid7())

        # Get all stats
        all_stats = cache_manager.get_stats()
        assert ns1 in all_stats
        assert ns2 in all_stats

    async def test_get_specific_namespace_stats(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify get_stats(namespace) returns only specified namespace."""
        ns1 = cache_manager._get_namespace("provider1", "dense")
        ns2 = cache_manager._get_namespace("provider2", "dense")

        # Process in both namespaces
        await cache_manager.deduplicate(sample_chunks, ns1, uuid7())
        await cache_manager.deduplicate(sample_chunks, ns2, uuid7())

        # Get specific namespace stats
        ns1_stats = cache_manager.get_stats(ns1)
        assert ns1 in ns1_stats
        assert ns2 not in ns1_stats


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestNamespaceClearing:
    """Test clear_namespace functionality."""

    async def test_clear_namespace(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify clear_namespace removes all data for a namespace."""
        namespace = cache_manager._get_namespace("test-provider", "dense")
        batch_id = uuid7()

        # Add data to namespace
        await cache_manager.deduplicate(sample_chunks, namespace, batch_id)
        await cache_manager.store_batch(sample_chunks, batch_id, namespace)

        # Verify data exists
        assert namespace in cache_manager.get_stats()
        assert cache_manager.get_batch(batch_id, namespace) is not None

        # Clear namespace
        cache_manager.clear_namespace(namespace)

        # Verify data is gone
        assert namespace not in cache_manager.get_stats()
        assert cache_manager.get_batch(batch_id, namespace) is None

    async def test_clear_preserves_other_namespaces(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify clearing one namespace doesn't affect others."""
        ns1 = cache_manager._get_namespace("provider1", "dense")
        ns2 = cache_manager._get_namespace("provider2", "dense")

        batch_id_1 = uuid7()
        batch_id_2 = uuid7()

        # Add data to both namespaces
        await cache_manager.deduplicate(sample_chunks, ns1, batch_id_1)
        await cache_manager.store_batch(sample_chunks, batch_id_1, ns1)
        await cache_manager.deduplicate(sample_chunks, ns2, batch_id_2)
        await cache_manager.store_batch(sample_chunks, batch_id_2, ns2)

        # Clear namespace 1
        cache_manager.clear_namespace(ns1)

        # Verify ns1 is gone but ns2 remains
        assert ns1 not in cache_manager.get_stats()
        assert ns2 in cache_manager.get_stats()
        assert cache_manager.get_batch(batch_id_1, ns1) is None
        assert cache_manager.get_batch(batch_id_2, ns2) is not None


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error conditions."""

    async def test_empty_chunks_list(self, cache_manager: EmbeddingCacheManager):
        """Verify handling of empty chunks list."""
        namespace = cache_manager._get_namespace("test-provider", "dense")
        batch_id = uuid7()

        unique_chunks, hash_mapping = await cache_manager.deduplicate([], namespace, batch_id)

        assert len(list(unique_chunks)) == 0
        assert len(hash_mapping) == 0

    async def test_single_chunk(
        self, cache_manager: EmbeddingCacheManager, sample_chunks: list[CodeChunk]
    ):
        """Verify handling of single chunk."""
        namespace = cache_manager._get_namespace("test-provider", "dense")
        batch_id = uuid7()

        unique_chunks, hash_mapping = await cache_manager.deduplicate(
            sample_chunks[:1], namespace, batch_id
        )

        assert len(list(unique_chunks)) == 1
        assert len(hash_mapping) == 1
