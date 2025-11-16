# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Contract tests for QdrantVectorStoreProvider provider.

These tests verify that QdrantVectorStoreProvider correctly implements the
VectorStoreProvider interface and provides Qdrant-specific functionality.

Uses QdrantTestManager for reliable test instance management with:
- Automatic port detection (won't interfere with existing instances)
- Unique collections per test
- Automatic cleanup after tests
- Optional authentication support
"""

import asyncio

from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from codeweaver.agent_api.find_code.types import StrategizedQuery
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.spans import Span
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


@pytest.fixture
async def qdrant_provider(qdrant_test_manager):
    """Create a QdrantVectorStoreProvider instance using test manager."""
    from unittest.mock import MagicMock

    # Create test collection with both dense and sparse vectors
    collection_name = qdrant_test_manager.create_collection_name("contract")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    # Create mock embedder (not used in contract tests, but required by field definition)
    MagicMock()

    # Create config for provider
    config = {
        "url": qdrant_test_manager.url,
        "collection_name": collection_name,
        "batch_size": 64,
        "dense_vector_name": "dense",
        "sparse_vector_name": "sparse",
    }

    # Use model_construct to bypass validation and create instance
    provider = QdrantVectorStoreProvider.model_construct(
        config=config, _client=None, _metadata=None
    )
    await provider._initialize()

    yield provider  # noqa: PT022  # The fixture is an async context manager, so it cleans up after yield

    # Cleanup handled by test manager


def _register_chunk_embeddings(chunk, dense=None, sparse=None):
    """Helper to register embeddings for a test chunk in the global registry."""
    from codeweaver.common.utils.utils import uuid7
    from codeweaver.providers.embedding.registry import get_embedding_registry
    from codeweaver.providers.embedding.types import ChunkEmbeddings, EmbeddingBatchInfo

    registry = get_embedding_registry()

    # Create batch IDs for this chunk - separate for dense and sparse
    dense_batch_id = cast(UUID, uuid7()) if dense is not None else None
    sparse_batch_id = cast(UUID, uuid7()) if sparse is not None else None
    batch_index = 0

    # Create EmbeddingBatchInfo objects for dense/sparse embeddings
    dense_info = None
    if dense is not None:
        dense_info = EmbeddingBatchInfo.create_dense(
            batch_id=cast(UUID, dense_batch_id),
            batch_index=batch_index,
            chunk_id=chunk.chunk_id,
            model="test-dense-model",
            embeddings=dense,
        )

    sparse_info = None
    if sparse is not None:
        from codeweaver.providers.embedding.types import SparseEmbedding

        sparse_emb = SparseEmbedding(indices=sparse["indices"], values=sparse["values"])
        sparse_info = EmbeddingBatchInfo.create_sparse(
            batch_id=cast(UUID, sparse_batch_id),
            batch_index=batch_index,
            chunk_id=chunk.chunk_id,
            model="test-sparse-model",
            embeddings=sparse_emb,
        )

    # Register the embeddings - ChunkEmbeddings is a NamedTuple (sparse, dense, chunk)
    registry[chunk.chunk_id] = ChunkEmbeddings(sparse=sparse_info, dense=dense_info, chunk=chunk)

    # Update chunk with batch keys - need to add both dense and sparse keys
    from codeweaver.core.chunks import BatchKeys

    # Start with the chunk
    result_chunk = chunk

    # Add dense batch key if we have dense embeddings
    if dense is not None:
        dense_batch_keys = BatchKeys(id=cast(UUID, dense_batch_id), idx=batch_index, sparse=False)
        result_chunk = result_chunk.set_batch_keys(dense_batch_keys)

    # Add sparse batch key if we have sparse embeddings
    if sparse is not None:
        sparse_batch_keys = BatchKeys(id=cast(UUID, sparse_batch_id), idx=batch_index, sparse=True)
        result_chunk = result_chunk.set_batch_keys(sparse_batch_keys)

    return result_chunk


@pytest.fixture
def sample_chunk():
    """Create a sample CodeChunk for testing with proper embedding registration."""
    from codeweaver.common.utils.utils import uuid7

    chunk = CodeChunk.model_construct(
        chunk_name="test.py:test_function",
        file_path=Path("test.py"),
        content="def test_function():\n    pass",
        line_range=Span(start=1, end=2, _source_id=uuid7()),
    )

    # Register embeddings properly in the registry
    return _register_chunk_embeddings(
        chunk,
        dense=[0.1, 0.2, 0.3] * 256,  # 768-dim vector
        sparse={"indices": [1, 5, 10], "values": [0.8, 0.6, 0.4]},
    )


class TestQdrantProviderContract:
    """Contract tests for QdrantVectorStoreProvider implementation."""

    async def test_implements_vector_store_provider(self):
        """Verify QdrantVectorStoreProvider implements VectorStoreProvider interface."""
        from codeweaver.providers.vector_stores.base import VectorStoreProvider

        assert issubclass(QdrantVectorStoreProvider, VectorStoreProvider)

    @pytest.mark.qdrant
    @pytest.mark.asyncio
    async def test_list_collections(self, qdrant_provider):
        """Test list_collections returns list or None."""
        collections = await qdrant_provider.list_collections()

        assert collections is None or isinstance(collections, list)
        if isinstance(collections, list):
            assert all(isinstance(name, str) for name in collections)

    @pytest.mark.qdrant
    @pytest.mark.asyncio
    @pytest.mark.search
    async def test_search_with_dense_vector(self, qdrant_provider, sample_chunk):
        """Test search with dense vector only."""
        # First upsert a chunk
        await qdrant_provider.upsert([sample_chunk])

        # Search with dense vector
        results = await qdrant_provider.search(vector={"dense": [0.1, 0.2, 0.3] * 256})

        assert isinstance(results, list)
        assert len(results) > 0, (
            "Search returned no results after upserting chunk with dense embeddings"
        )
        assert all(hasattr(r, "chunk") and hasattr(r, "score") for r in results), (
            "Search results missing chunk or score attributes"
        )
        assert all(0.0 <= r.score <= 1.0 for r in results), (
            "Search result scores out of valid range [0.0, 1.0]"
        )

    @pytest.mark.qdrant
    @pytest.mark.asyncio
    @pytest.mark.search
    async def test_search_with_sparse_vector(self, qdrant_provider, sample_chunk):
        """Test search with sparse vector only."""
        await qdrant_provider.upsert([sample_chunk])

        # Search with sparse vector
        results = await qdrant_provider.search(
            vector={"sparse": {"indices": [1, 5, 10], "values": [0.8, 0.6, 0.4]}}
        )

        assert isinstance(results, list)
        assert len(results) > 0, (
            "Search returned no results after upserting chunk with sparse embeddings"
        )
        assert all(hasattr(r, "chunk") and hasattr(r, "score") for r in results), (
            "Search results missing chunk or score attributes"
        )
        # Sparse vector scores can be unbounded (SPLADE/BM25), so we just check they're valid numbers
        assert all(
            isinstance(r.score, (int, float)) and not isinstance(r.score, bool) for r in results
        ), "Search result scores should be numeric"

    @pytest.mark.qdrant
    @pytest.mark.asyncio
    @pytest.mark.search
    async def test_search_with_hybrid_vectors(self, qdrant_provider, sample_chunk):
        """Test search with both dense and sparse vectors."""
        await qdrant_provider.upsert([sample_chunk])

        # Hybrid search
        results = await qdrant_provider.search(
            vector={
                "dense": [0.1, 0.2, 0.3] * 256,
                "sparse": {"indices": [1, 5, 10], "values": [0.8, 0.6, 0.4]},
            }
        )

        assert isinstance(results, list)
        assert len(results) > 0, (
            "Hybrid search returned no results after upserting chunk with both dense and sparse embeddings"
        )
        assert all(hasattr(r, "chunk") and hasattr(r, "score") for r in results), (
            "Search results missing chunk or score attributes"
        )
        # Hybrid scores combine dense and sparse, so can be unbounded
        assert all(
            isinstance(r.score, (int, float)) and not isinstance(r.score, bool) for r in results
        ), "Search result scores should be numeric"

    @pytest.mark.qdrant
    @pytest.mark.asyncio
    async def test_upsert_batch_of_chunks(self, qdrant_provider: QdrantVectorStoreProvider):
        """Test upserting a batch of chunks and verify they can be retrieved via search."""
        from pathlib import Path

        from codeweaver.common.utils.utils import uuid7
        from codeweaver.core.chunks import CodeChunk, Span

        chunks = []
        for i in range(10):
            chunk = CodeChunk.model_construct(
                chunk_id=uuid7(),  # Use uuid7 instead of uuid4
                chunk_name=f"test_{i}.py:func",
                file_path=Path(f"test_{i}.py"),
                content=f"def func_{i}(): pass",
                line_range=Span(start=1, end=1, _source_id=uuid7()),
            )
            # Register embeddings properly
            chunk_with_emb = _register_chunk_embeddings(chunk, dense=[float(i)] * 768)
            chunks.append(chunk_with_emb)

        # Should not raise
        await qdrant_provider.upsert(chunks)

        # Wait for indexing
        await asyncio.sleep(1.0)

        # Verify chunks were stored
        from codeweaver.agent_api.find_code.types import SearchStrategy

        results = await qdrant_provider.search(
            StrategizedQuery(
                query="test", dense=[0.5] * 768, sparse=None, strategy=SearchStrategy.DENSE_ONLY
            )
        )
        assert len(results) > 0

    @pytest.mark.qdrant
    @pytest.mark.asyncio
    async def test_delete_by_file(self, qdrant_provider, sample_chunk):
        """Test delete_by_file removes chunks for specific file."""
        await qdrant_provider.upsert([sample_chunk])

        # Delete by file path
        await qdrant_provider.delete_by_file(sample_chunk.file_path)

        # Verify chunk is gone
        results = await qdrant_provider.search(vector={"dense": [0.1, 0.2, 0.3] * 256})
        assert len(results) == 0 or all(
            r.chunk.file_path != sample_chunk.file_path for r in results
        )

    @pytest.mark.qdrant
    @pytest.mark.asyncio
    async def test_delete_by_file_idempotent(self, qdrant_provider):
        """Test delete_by_file doesn't error on non-existent file."""
        # Should not raise even if file has no chunks
        await qdrant_provider.delete_by_file(Path("nonexistent.py"))

    async def test_delete_by_id(self, qdrant_provider, sample_chunk):
        """Test delete_by_id removes specific chunks."""
        await qdrant_provider.upsert([sample_chunk])

        # Delete by ID
        await qdrant_provider.delete_by_id([sample_chunk.chunk_id])

        # Verify chunk is gone
        results = await qdrant_provider.search(vector={"dense": [0.1, 0.2, 0.3] * 256})
        assert len(results) == 0 or all(r.chunk.chunk_id != sample_chunk.chunk_id for r in results)

    @pytest.mark.qdrant
    @pytest.mark.asyncio
    async def test_delete_by_name(self, qdrant_provider, sample_chunk):
        """Test delete_by_name removes chunks by name."""
        await qdrant_provider.upsert([sample_chunk])

        # Delete by chunk name
        await qdrant_provider.delete_by_name([sample_chunk.chunk_name])

        # Verify chunk is gone
        results = await qdrant_provider.search(vector={"dense": [0.1, 0.2, 0.3] * 256})
        assert len(results) == 0 or all(
            r.chunk.chunk_name != sample_chunk.chunk_name for r in results
        )

    @pytest.mark.qdrant
    @pytest.mark.asyncio
    async def test_collection_property(self, qdrant_provider):
        """Test collection property returns configured collection name."""
        # Collection name should start with "contract-"
        assert qdrant_provider.collection.startswith("contract-")

    @pytest.mark.qdrant
    @pytest.mark.asyncio
    async def test_base_url_property(self, qdrant_provider, qdrant_test_manager):
        """Test base_url property returns Qdrant URL."""
        assert qdrant_provider.base_url == qdrant_test_manager.url
