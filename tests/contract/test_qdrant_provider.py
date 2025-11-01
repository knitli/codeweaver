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

from pathlib import Path

import pytest

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import SemanticSearchLanguage as Language
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
    mock_embedder = MagicMock()

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
        config=config, _embedder=mock_embedder, _reranking=None, _client=None, _metadata=None
    )
    await provider._initialize()

    yield provider  # noqa: PT022  # The fixture is an async context manager, so it cleans up after yield

    # Cleanup handled by test manager


@pytest.fixture
def sample_chunk():
    """Create a sample CodeChunk for testing."""
    from codeweaver.common.utils.utils import uuid7

    # Use model_construct to bypass Pydantic validation and avoid AstThing forward reference issues
    return CodeChunk.model_construct(
        chunk_name="test.py:test_function",
        file_path=Path("test.py"),
        language=Language.PYTHON,
        content="def test_function():\n    pass",
        embeddings={
            "dense": [0.1, 0.2, 0.3] * 256,  # 768-dim vector
            "sparse": {"indices": [1, 5, 10], "values": [0.8, 0.6, 0.4]},
        },
        line_range=Span(start=1, end=2, _source_id=uuid7()),
    )


class TestQdrantProviderContract:
    """Contract tests for QdrantVectorStoreProvider implementation."""

    async def test_implements_vector_store_provider(self):
        """Verify QdrantVectorStoreProvider implements VectorStoreProvider interface."""
        from codeweaver.providers.vector_stores.base import VectorStoreProvider

        assert issubclass(QdrantVectorStoreProvider, VectorStoreProvider)

    async def test_list_collections(self, qdrant_provider):
        """Test list_collections returns list or None."""
        collections = await qdrant_provider.list_collections()

        assert collections is None or isinstance(collections, list)
        if isinstance(collections, list):
            assert all(isinstance(name, str) for name in collections)

    async def test_search_with_dense_vector(self, qdrant_provider, sample_chunk):
        """Test search with dense vector only."""
        # First upsert a chunk
        await qdrant_provider.upsert([sample_chunk])

        # Search with dense vector
        results = await qdrant_provider.search(vector={"dense": [0.1, 0.2, 0.3] * 256})

        assert isinstance(results, list)
        if results:
            assert all(hasattr(r, "chunk") and hasattr(r, "score") for r in results)
            assert all(0.0 <= r.score <= 1.0 for r in results)

    async def test_search_with_sparse_vector(self, qdrant_provider, sample_chunk):
        """Test search with sparse vector only."""
        await qdrant_provider.upsert([sample_chunk])

        # Search with sparse vector
        results = await qdrant_provider.search(
            vector={"sparse": {"indices": [1, 5, 10], "values": [0.8, 0.6, 0.4]}}
        )

        assert isinstance(results, list)

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

    async def test_upsert_batch_of_chunks(self, qdrant_provider):
        """Test upsert with multiple chunks."""
        from uuid import uuid4

        from codeweaver.common.utils.utils import uuid7

        chunks = [
            CodeChunk.model_construct(
                chunk_id=uuid4(),
                chunk_name=f"test_{i}.py:func",
                file_path=Path(f"test_{i}.py"),
                language=Language.PYTHON,
                content=f"def func_{i}(): pass",
                embeddings={"dense": [float(i)] * 768},
                line_range=Span(start=1, end=1, _source_id=uuid7()),
            )
            for i in range(10)
        ]

        # Should not raise
        await qdrant_provider.upsert(chunks)

        # Verify chunks were stored
        results = await qdrant_provider.search(vector={"dense": [5.0] * 768})
        assert len(results) > 0

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

    async def test_collection_property(self, qdrant_provider):
        """Test collection property returns configured collection name."""
        # Collection name should start with "contract-"
        assert qdrant_provider.collection.startswith("contract-")

    async def test_base_url_property(self, qdrant_provider, qdrant_test_manager):
        """Test base_url property returns Qdrant URL."""
        assert qdrant_provider.base_url == qdrant_test_manager.url
