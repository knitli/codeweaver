# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Contract tests for MemoryVectorStore provider.

These tests verify that MemoryVectorStore correctly implements the
VectorStoreProvider interface and provides in-memory storage with persistence.
"""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from codeweaver.config.providers import MemoryConfig
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.core.spans import Span
from codeweaver.providers.vector_stores.inmemory import MemoryVectorStore

pytestmark = pytest.mark.unit


@pytest.fixture
def temp_persist_path():
    """Provide temporary persistence path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_memory.json"


@pytest.fixture
async def memory_config(temp_persist_path):
    """Provide test Memory configuration."""
    return {
        "persist_path": str(temp_persist_path),
        "auto_persist": True,
        "persist_interval": None,  # Disable periodic persistence for tests
        "collection_name": f"test_memory_{uuid4().hex[:8]}",
    }


@pytest.fixture
async def memory_provider(memory_config):
    """Create a MemoryVectorStore instance for testing."""
    provider = MemoryVectorStore(config=memory_config)
    await provider._initialize()
    yield provider
    # Cleanup handled by temp directory


@pytest.fixture
def sample_chunk():
    """Create a sample CodeChunk for testing."""
    # Use model_construct to bypass Pydantic validation and avoid AstThing forward reference issues
    return CodeChunk.model_construct(
        chunk_name="memory_test.py:test_func",
        file_path=Path("memory_test.py"),
        language=Language.PYTHON,
        content="def test_func():\n    return True",
        embeddings={"dense": [0.5, 0.5, 0.5] * 256},
        line_range=Span(start=1, end=2),
    )


class TestMemoryProviderContract:
    """Contract tests for MemoryVectorStore implementation."""

    async def test_implements_vector_store_provider(self):
        """Verify MemoryVectorStore implements VectorStoreProvider interface."""
        from codeweaver.providers.vector_stores.base import VectorStoreProvider

        assert issubclass(MemoryVectorStore, VectorStoreProvider)

    async def test_list_collections(self, memory_provider):
        """Test list_collections returns list or None."""
        collections = await memory_provider.list_collections()

        assert collections is None or isinstance(collections, list)
        if isinstance(collections, list):
            assert all(isinstance(name, str) for name in collections)

    async def test_search(self, memory_provider, sample_chunk):
        """Test search functionality."""
        await memory_provider.upsert([sample_chunk])

        results = await memory_provider.search(vector={"dense": [0.5, 0.5, 0.5] * 256})

        assert isinstance(results, list)
        if results:
            assert all(hasattr(r, "chunk") and hasattr(r, "score") for r in results)

    async def test_upsert(self, memory_provider, sample_chunk):
        """Test upsert stores chunks."""
        await memory_provider.upsert([sample_chunk])

        # Verify chunk can be retrieved
        results = await memory_provider.search(vector={"dense": [0.5, 0.5, 0.5] * 256})
        assert len(results) > 0

    async def test_delete_by_file(self, memory_provider, sample_chunk):
        """Test delete_by_file removes chunks."""
        await memory_provider.upsert([sample_chunk])
        await memory_provider.delete_by_file(sample_chunk.file_path)

        results = await memory_provider.search(vector={"dense": [0.5, 0.5, 0.5] * 256})
        assert len(results) == 0 or all(r.chunk.file_path != sample_chunk.file_path for r in results)

    async def test_delete_by_id(self, memory_provider, sample_chunk):
        """Test delete_by_id removes chunks."""
        await memory_provider.upsert([sample_chunk])
        await memory_provider.delete_by_id([sample_chunk.chunk_id])

        results = await memory_provider.search(vector={"dense": [0.5, 0.5, 0.5] * 256})
        assert len(results) == 0 or all(r.chunk.chunk_id != sample_chunk.chunk_id for r in results)

    async def test_delete_by_name(self, memory_provider, sample_chunk):
        """Test delete_by_name removes chunks."""
        await memory_provider.upsert([sample_chunk])
        await memory_provider.delete_by_name([sample_chunk.chunk_name])

        results = await memory_provider.search(vector={"dense": [0.5, 0.5, 0.5] * 256})
        assert len(results) == 0 or all(r.chunk.chunk_name != sample_chunk.chunk_name for r in results)

    async def test_persist_to_disk(self, memory_provider, memory_config, sample_chunk):
        """Test _persist_to_disk creates JSON file."""
        await memory_provider.upsert([sample_chunk])
        await memory_provider._persist_to_disk()

        persist_path = Path(memory_config["persist_path"])
        assert persist_path.exists(), "Persistence file should be created"
        assert persist_path.stat().st_size > 0, "Persistence file should not be empty"

    async def test_restore_from_disk(self, memory_config, sample_chunk, temp_persist_path):
        """Test _restore_from_disk loads data from JSON."""
        # Create and persist data
        provider1 = MemoryVectorStore(config=memory_config)
        await provider1._initialize()
        await provider1.upsert([sample_chunk])
        await provider1._persist_to_disk()

        # Create new provider and restore
        provider2 = MemoryVectorStore(config=memory_config)
        await provider2._initialize()

        # Verify data was restored
        results = await provider2.search(vector={"dense": [0.5, 0.5, 0.5] * 256})
        assert len(results) > 0
        assert any(r.chunk.chunk_id == sample_chunk.chunk_id for r in results)

    async def test_persistence_file_format(self, memory_provider, memory_config, sample_chunk):
        """Test persistence file has correct JSON structure."""
        import json

        await memory_provider.upsert([sample_chunk])
        await memory_provider._persist_to_disk()

        with open(memory_config["persist_path"]) as f:
            data = json.load(f)

        # Verify top-level structure
        assert "version" in data
        assert "collections" in data or "metadata" in data
        assert data["version"] == "1.0"

    async def test_auto_persist_on_upsert(self, memory_config, sample_chunk, temp_persist_path):
        """Test auto_persist triggers persistence on upsert."""
        config_with_auto = memory_config.copy()
        config_with_auto["auto_persist"] = True

        provider = MemoryVectorStore(config=config_with_auto)
        await provider._initialize()
        await provider.upsert([sample_chunk])

        # Auto-persist should have created the file
        assert temp_persist_path.exists()

    async def test_collection_property(self, memory_provider, memory_config):
        """Test collection property returns configured collection name."""
        assert memory_provider.collection == memory_config["collection_name"]
