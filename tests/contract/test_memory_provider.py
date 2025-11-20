# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Contract tests for MemoryVectorStoreProvider provider.

These tests verify that MemoryVectorStoreProvider correctly implements the
VectorStoreProvider interface and provides in-memory storage with persistence.
"""

import tempfile

from pathlib import Path
from uuid import uuid4

import pytest

from codeweaver.agent_api.find_code.types import StrategizedQuery
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.core.spans import Span
from codeweaver.providers.provider import Provider
from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider


pytestmark = [pytest.mark.validation]



pytestmark = pytest.mark.unit


@pytest.fixture
def temp_persist_path():
    """Provide temporary persistence directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
async def memory_config(temp_persist_path):
    """Provide test Memory configuration."""
    return {
        "persist_path": str(temp_persist_path / "vector_store.json"),  # Full file path
        "auto_persist": True,
        "persist_interval": None,  # Disable periodic persistence for tests
        "collection_name": f"test_memory_{uuid4().hex[:8]}",
    }


@pytest.fixture
async def test_embedding_caps():
    """Provide test embedding capabilities with 768 dimensions."""
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    dense_caps = EmbeddingModelCapabilities(
        name="test-dense-model",
        default_dimension=768,
        default_dtype="float32",
        preferred_metrics=("cosine", "dot"),
    )

    return {"dense": dense_caps, "sparse": None}


@pytest.fixture
async def memory_provider(memory_config, test_embedding_caps):
    """Create a MemoryVectorStoreProvider instance for testing."""
    from codeweaver.providers.provider import Provider

    provider = MemoryVectorStoreProvider(
        _provider=Provider.MEMORY, config=memory_config, embedding_caps=test_embedding_caps
    )
    await provider._initialize()
    return provider
    # Cleanup handled by temp directory


@pytest.fixture
def sample_chunk():
    """Create a sample CodeChunk for testing."""
    from codeweaver.common.utils.utils import uuid7
    from codeweaver.core.chunks import BatchKeys
    from codeweaver.core.metadata import ChunkKind, ExtKind
    from codeweaver.providers.embedding.registry import get_embedding_registry
    from codeweaver.providers.embedding.types import ChunkEmbeddings, EmbeddingBatchInfo

    chunk_id = uuid7()

    # Create the base chunk
    chunk = CodeChunk(
        chunk_id=chunk_id,
        chunk_name="memory_test.py:test_func",
        file_path=Path("memory_test.py"),
        language=Language.PYTHON,
        ext_kind=ExtKind.from_language(Language.PYTHON, ChunkKind.CODE),
        content="def test_func():\n    return True",
        line_range=Span(start=1, end=2, _source_id=chunk_id),
    )

    # Register embeddings in the registry
    registry = get_embedding_registry()

    # Create dense embeddings (768 dimensions to match default)
    dense_batch_id = uuid7()
    dense_info = EmbeddingBatchInfo.create_dense(
        batch_id=dense_batch_id,
        batch_index=0,
        chunk_id=chunk_id,
        model="test-dense-model",
        embeddings=[0.5] * 768,  # 768 dimensions
        dimension=768,
    )

    # Set batch key on chunk
    dense_batch_key = BatchKeys(id=dense_batch_id, idx=0, sparse=False)
    chunk = chunk.set_batch_keys(dense_batch_key)

    # Register in the embedding registry
    registry[chunk_id] = ChunkEmbeddings(sparse=None, dense=dense_info, chunk=chunk)

    return chunk


@pytest.mark.async_test
class TestMemoryProviderContract:
    """Contract tests for MemoryVectorStoreProvider implementation."""

    async def test_implements_vector_store_provider(self):
        """Verify MemoryVectorStoreProvider implements VectorStoreProvider interface."""
        from codeweaver.providers.vector_stores.base import VectorStoreProvider

        assert issubclass(MemoryVectorStoreProvider, VectorStoreProvider)

    async def test_list_collections(self, memory_provider):
        """Test list_collections returns list or None."""
        collections = await memory_provider.list_collections()

        assert collections is None or isinstance(collections, list)
        if isinstance(collections, list):
            assert all(isinstance(name, str) for name in collections)

    async def test_search(self, memory_provider, sample_chunk):
        """Test search functionality."""
        await memory_provider.upsert([sample_chunk])

        results = await memory_provider.search(vector={"dense": [0.5] * 768})

        assert isinstance(results, list)
        if results:
            assert all(hasattr(r, "chunk") and hasattr(r, "score") for r in results)

    async def test_upsert(self, memory_provider, sample_chunk):
        """Test upsert stores chunks."""
        await memory_provider.upsert([sample_chunk])

        # Verify chunk can be retrieved
        results = await memory_provider.search(vector={"dense": [0.5] * 768})
        assert len(results) > 0

    async def test_delete_by_file(self, memory_provider, sample_chunk):
        """Test delete_by_file removes chunks."""
        await memory_provider.upsert([sample_chunk])
        await memory_provider.delete_by_file(sample_chunk.file_path)

        results = await memory_provider.search(vector={"dense": [0.5] * 768})
        assert len(results) == 0 or all(
            r.chunk.file_path != sample_chunk.file_path for r in results
        )

    async def test_delete_by_id(self, memory_provider, sample_chunk):
        """Test delete_by_id removes chunks."""
        await memory_provider.upsert([sample_chunk])
        await memory_provider.delete_by_id([sample_chunk.chunk_id])

        results = await memory_provider.search(vector={"dense": [0.5] * 768})
        assert len(results) == 0 or all(r.chunk.chunk_id != sample_chunk.chunk_id for r in results)

    async def test_delete_by_name(self, memory_provider, sample_chunk):
        """Test delete_by_name removes chunks."""
        await memory_provider.upsert([sample_chunk])
        await memory_provider.delete_by_name([sample_chunk.chunk_name])

        results = await memory_provider.search(vector={"dense": [0.5] * 768})
        assert len(results) == 0 or all(
            r.chunk.chunk_name != sample_chunk.chunk_name for r in results
        )

    async def test_persist_to_disk(self, memory_provider, memory_config, sample_chunk):
        """Test _persist_to_disk creates JSON file."""
        await memory_provider.upsert([sample_chunk])
        await memory_provider._persist_to_disk()

        persist_path = Path(memory_config["persist_path"])
        assert persist_path.exists(), "Persistence file should be created"
        assert persist_path.stat().st_size > 0, "Persistence file should not be empty"

    async def test_restore_from_disk(
        self, memory_config, sample_chunk, temp_persist_path, test_embedding_caps
    ):
        """Test _restore_from_disk loads data from JSON."""
        from codeweaver.providers.provider import Provider

        # Create and persist data
        provider1 = MemoryVectorStoreProvider(
            _provider=Provider.MEMORY, config=memory_config, embedding_caps=test_embedding_caps
        )
        await provider1._initialize()
        await provider1.upsert([sample_chunk])
        await provider1._persist_to_disk()

        # Create new provider and restore
        provider2 = MemoryVectorStoreProvider(
            _provider=Provider.MEMORY, config=memory_config, embedding_caps=test_embedding_caps
        )
        await provider2._initialize()

        # Verify data was restored
        from codeweaver.agent_api.find_code.types import SearchStrategy

        results = await provider2.search(
            StrategizedQuery(
                query="what is the word?",
                dense=[0.5] * 768,
                sparse=None,
                strategy=SearchStrategy.DENSE_ONLY,
            )
        )
        assert len(results) > 0
        assert any(
            r.chunk.chunk_id == sample_chunk.chunk_id
            if isinstance(r.chunk, CodeChunk)
            else r.chunk == sample_chunk.chunk_id
            for r in results
        )

    async def test_persistence_file_format(self, memory_provider, memory_config, sample_chunk):
        """Test persistence file has correct JSON structure."""
        import json

        await memory_provider.upsert([sample_chunk])
        await memory_provider._persist_to_disk()

        persist_path = Path(memory_config["persist_path"])
        data = json.loads(persist_path.read_text())
        # Verify top-level structure
        assert "version" in data
        assert "collections" in data or "metadata" in data
        assert data["version"] == "1.0"

    async def test_auto_persist_on_upsert(
        self, memory_config, sample_chunk, temp_persist_path, test_embedding_caps
    ):
        """Test auto_persist triggers persistence on upsert."""
        config_with_auto = memory_config.copy()
        config_with_auto["auto_persist"] = True

        provider = MemoryVectorStoreProvider(
            _provider=Provider.MEMORY, config=config_with_auto, embedding_caps=test_embedding_caps
        )
        await provider._initialize()
        await provider.upsert([sample_chunk])

        # Auto-persist should have created the file
        persist_file = Path(memory_config["persist_path"])
        assert persist_file.exists()

    async def test_collection_property(self, memory_provider, memory_config):
        """Test collection property returns configured collection name."""
        assert memory_provider.collection == memory_config["collection_name"]
