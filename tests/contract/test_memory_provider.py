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

from qdrant_client import AsyncQdrantClient

from codeweaver.core import CodeChunk, SemanticSearchLanguage, Span
from codeweaver.core.types import Provider, SearchStrategy, StrategizedQuery
from codeweaver.providers import (
    ConfiguredCapability,
    EmbeddingCapabilityGroup,
    EmbeddingModelCapabilities,
    EmbeddingProviderSettings,
    MemoryVectorStoreProvider,
    MemoryVectorStoreProviderSettings,
)


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
    return MemoryVectorStoreProviderSettings(
        provider=Provider.MEMORY,
        in_memory_config={
            "persist_path": str(temp_persist_path / "vector_store"),
            "auto_persist": True,
            "persist_interval": None,
            "collection_name": f"test_memory_{uuid4().hex[:8]}",
        },
    )


@pytest.fixture
async def test_embedding_caps():
    """Provide test embedding capabilities with 768 dimensions."""

    dense_caps = EmbeddingModelCapabilities(
        name="test-dense-model",
        default_dimension=768,
        default_dtype="float32",
        preferred_metrics=("cosine", "dot"),
    )

    # We need a ConfiguredCapability for the group
    # Mocking the settings to satisfy ConfiguredCapability
    mock_settings = EmbeddingProviderSettings(
        provider=Provider.OPENAI,  # Dummy provider
        model_name="test-dense-model",
        embedding_config=EmbeddingProviderSettings(model_name="test-dense-model"),
    )

    configured_dense = ConfiguredCapability(capability=dense_caps, config=mock_settings)

    return EmbeddingCapabilityGroup(dense=configured_dense, sparse=None)


@pytest.fixture
async def memory_provider(memory_config, test_embedding_caps):
    """Create a MemoryVectorStoreProvider instance for testing."""
    client = AsyncQdrantClient(location=":memory:")

    provider = MemoryVectorStoreProvider(
        client=client, config=memory_config, caps=test_embedding_caps
    )
    await provider._initialize()
    return provider
    # Cleanup handled by temp directory


@pytest.fixture
def sample_chunk():
    """Create a sample CodeChunk for testing."""
    from codeweaver.core import BatchKeys, ChunkKind, ExtKind, uuid7
    from codeweaver.providers import ChunkEmbeddings, EmbeddingBatchInfo, get_embedding_registry

    chunk_id = uuid7()

    # Create the base chunk
    chunk = CodeChunk(
        chunk_id=chunk_id,
        chunk_name="memory_test.py:test_func",
        file_path=Path("memory_test.py"),
        language=SemanticSearchLanguage.PYTHON,
        ext_kind=ExtKind.from_language(SemanticSearchLanguage.PYTHON, ChunkKind.CODE),
        content="def test_func():\n    return True",
        line_range=Span(start=1, end=2, source_id=chunk_id),
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
    registry[chunk_id] = ChunkEmbeddings(chunk=chunk).add(dense_info)

    return chunk


@pytest.mark.async_test
@pytest.mark.external_api
@pytest.mark.qdrant
class TestMemoryProviderContract:
    """Contract tests for MemoryVectorStoreProvider implementation."""

    async def test_implements_vector_store_provider(self):
        """Verify MemoryVectorStoreProvider implements VectorStoreProvider interface."""
        from codeweaver.providers import VectorStoreProvider

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
        """Test _persist_to_disk creates persistence directory."""
        await memory_provider.upsert([sample_chunk])
        await memory_provider._persist_to_disk()

        persist_path = Path(memory_config.in_memory_config["persist_path"])
        assert persist_path.exists(), "Persistence directory should be created"
        assert persist_path.is_dir(), "Persistence path should be a directory"
        # Check if Qdrant files exist inside (simple check)
        assert any(persist_path.iterdir()), "Persistence directory should not be empty"

    async def test_restore_from_disk(
        self, memory_config, sample_chunk, temp_persist_path, test_embedding_caps
    ):
        """Test _restore_from_disk loads data from JSON."""
        # Create and persist data
        client1 = AsyncQdrantClient(location=":memory:")
        provider1 = MemoryVectorStoreProvider(
            client=client1, config=memory_config, caps=test_embedding_caps
        )
        await provider1._initialize()
        await provider1.upsert([sample_chunk])
        await provider1._persist_to_disk()

        # Create new provider and restore
        client2 = AsyncQdrantClient(location=":memory:")
        provider2 = MemoryVectorStoreProvider(
            client=client2, config=memory_config, caps=test_embedding_caps
        )
        await provider2._initialize()

        # Verify data was restored

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

    async def test_auto_persist_on_upsert(
        self, memory_config, sample_chunk, temp_persist_path, test_embedding_caps
    ):
        """Test auto_persist triggers persistence on upsert."""
        # Config is already a settings object, we need to create a new one with modified inner config
        # or just modify the dict used to create it if we were doing that.
        # Since memory_config is a Pydantic model, we should use model_copy with update if possible,
        # but in_memory_config is a dict inside.

        # Easiest way is to create a new settings object
        new_config = memory_config.in_memory_config.copy()
        new_config["auto_persist"] = True

        config_with_auto = MemoryVectorStoreProviderSettings(
            provider=Provider.MEMORY, in_memory_config=new_config
        )

        client = AsyncQdrantClient(location=":memory:")
        provider = MemoryVectorStoreProvider(
            client=client, config=config_with_auto, caps=test_embedding_caps
        )
        await provider._initialize()
        await provider.upsert([sample_chunk])

        # Auto-persist should have created the file
        persist_file = Path(memory_config.in_memory_config["persist_path"])
        assert persist_file.exists()
        assert persist_file.is_dir()

    async def test_collection_property(self, memory_provider, memory_config):
        """Test collection property returns configured collection name."""
        # Collection name can be either:
        # 1. Custom name from config (e.g., test_memory_{8_char_hex})
        # 2. Generated name: project_name-{8_char_hash} (e.g., codeweaver-test-751748d4)
        assert memory_provider.collection is not None
        # Either format should have an 8-character hex suffix
        collection_name = memory_provider.collection
        # Check the last segment (after last underscore or hyphen) is 8-char hex
        parts = collection_name.replace("-", "_").split("_")
        last_part = parts[-1]
        assert len(last_part) == 8, f"Expected 8-char hex suffix, got '{last_part}'"
        assert all(c in "0123456789abcdef" for c in last_part), (
            f"Expected hex characters, got '{last_part}'"
        )
