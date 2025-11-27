<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Quickstart: Vector Storage Provider System

**Feature**: Vector Storage Provider System
**Branch**: 002-we-re-completing
**Date**: 2025-10-25

## Overview

This quickstart guide provides executable test scenarios that validate the vector storage provider system implementation. Each scenario corresponds to acceptance criteria from the feature specification.

## Prerequisites

```bash
# Install dependencies
uv sync --all-groups

# Start local Qdrant instance (for Qdrant provider tests)
docker run -p 6333:6333 qdrant/qdrant:latest

# Or use docker-compose
docker-compose up -d qdrant
```

## Scenario 1: Store Hybrid Embeddings with Default Settings

**User Story**: As a CodeWeaver user, I want the system to store both dense and sparse embeddings when I initialize with default settings.

**Acceptance Criteria** (spec.md:72): Given embeddings have been generated for my codebase, When I initialize CodeWeaver with default settings, Then the system stores both dense and sparse embeddings in the configured vector store provider.

**Test Scenario**:
```python
import asyncio
from pathlib import Path
from uuid import uuid4
from codeweaver.providers.vector_stores import QdrantVectorStoreProvider
from codeweaver.config.providers import QdrantConfig
from codeweaver.core.chunks import CodeChunk, ChunkEmbeddings
from codeweaver.core.language import Language

async def test_store_hybrid_embeddings():
    # Setup
    config = QdrantConfig(
        url="http://localhost:6333",
        collection_name="test_hybrid"
    )
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    # Create chunk with both dense and sparse embeddings
    chunk = CodeChunk(
        chunk_id=uuid4(),
        chunk_name="auth.py:authenticate",
        file_path=Path("src/auth.py"),
        language=Language.PYTHON,
        content="def authenticate(user, password):\n    ...",
        embeddings=ChunkEmbeddings(
            dense=[0.1, 0.2, 0.3] * 256,  # 768-dim vector
            sparse={"indices": [1, 5, 10, 23], "values": [0.8, 0.6, 0.9, 0.4]}
        ),
        line_start=10,
        line_end=15
    )

    # Execute: Upsert chunk
    await provider.upsert([chunk])

    # Verify: Search with dense vector returns result
    dense_results = await provider.search(
        vector={"dense": [0.1, 0.2, 0.3] * 256}
    )
    assert len(dense_results) > 0
    assert dense_results[0].chunk.chunk_id == chunk.chunk_id

    # Verify: Search with sparse vector returns result
    sparse_results = await provider.search(
        vector={"sparse": {"indices": [1, 5, 10], "values": [0.8, 0.6, 0.9]}}
    )
    assert len(sparse_results) > 0

    # Verify: Hybrid search returns result
    hybrid_results = await provider.search(
        vector={
            "dense": [0.1, 0.2, 0.3] * 256,
            "sparse": {"indices": [1, 5, 10], "values": [0.8, 0.6, 0.9]}
        }
    )
    assert len(hybrid_results) > 0
    assert hybrid_results[0].chunk.chunk_id == chunk.chunk_id

    print("✅ Scenario 1 PASSED: Hybrid embeddings stored and searchable")

asyncio.run(test_store_hybrid_embeddings())
```

**Expected Output**:
```
✅ Scenario 1 PASSED: Hybrid embeddings stored and searchable
```

## Scenario 2: Retrieve Previously Stored Embeddings

**User Story**: As a CodeWeaver user, I want previously indexed data to persist across restarts.

**Acceptance Criteria** (spec.md:74): Given I have previously indexed my codebase, When I restart CodeWeaver, Then the system retrieves previously stored embeddings without needing to re-embed files.

**Test Scenario**:
```python
async def test_persistence_across_restarts():
    # Phase 1: Initial indexing
    config = QdrantConfig(url="http://localhost:6333", collection_name="test_persist")
    provider1 = QdrantVectorStoreProvider(config=config)
    await provider1._initialize()

    chunk = CodeChunk(
        chunk_id=uuid4(),
        chunk_name="login.py:validate",
        file_path=Path("src/login.py"),
        language=Language.PYTHON,
        content="def validate(token): ...",
        embeddings=ChunkEmbeddings(dense=[0.5, 0.5, 0.5] * 256),
        line_start=20,
        line_end=25
    )

    await provider1.upsert([chunk])
    original_chunk_id = chunk.chunk_id

    # Simulate restart: Create new provider instance
    provider2 = QdrantVectorStoreProvider(config=config)
    await provider2._initialize()

    # Verify: Previously stored chunk is retrievable
    results = await provider2.search(vector={"dense": [0.5, 0.5, 0.5] * 256})
    assert len(results) > 0
    assert results[0].chunk.chunk_id == original_chunk_id
    assert results[0].chunk.chunk_name == "login.py:validate"

    print("✅ Scenario 2 PASSED: Embeddings persist across restarts")

asyncio.run(test_persistence_across_restarts())
```

## Scenario 3: Hybrid Search Returns Ranked Results

**User Story**: As a CodeWeaver user, I want hybrid search to combine both sparse and dense embeddings for better relevance.

**Acceptance Criteria** (spec.md:76): Given I perform a semantic code search, When the query is processed, Then the system searches both sparse and dense indexes and returns hybrid search results ranked by relevance.

**Test Scenario**:
```python
async def test_hybrid_search_ranking():
    config = QdrantConfig(url="http://localhost:6333", collection_name="test_ranking")
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    # Insert multiple chunks with varying similarity
    chunks = [
        CodeChunk(
            chunk_id=uuid4(),
            chunk_name="exact_match.py:func",
            file_path=Path("exact_match.py"),
            language=Language.PYTHON,
            content="authentication function",
            embeddings=ChunkEmbeddings(
                dense=[1.0, 0.0, 0.0] * 256,  # Very similar
                sparse={"indices": [1, 2, 3], "values": [1.0, 0.9, 0.8]}
            ),
            line_start=1,
            line_end=5
        ),
        CodeChunk(
            chunk_id=uuid4(),
            chunk_name="partial_match.py:func",
            file_path=Path("partial_match.py"),
            language=Language.PYTHON,
            content="auth helper",
            embeddings=ChunkEmbeddings(
                dense=[0.5, 0.5, 0.0] * 256,  # Somewhat similar
                sparse={"indices": [1, 4], "values": [0.6, 0.5]}
            ),
            line_start=10,
            line_end=15
        ),
        CodeChunk(
            chunk_id=uuid4(),
            chunk_name="no_match.py:func",
            file_path=Path("no_match.py"),
            language=Language.PYTHON,
            content="unrelated function",
            embeddings=ChunkEmbeddings(
                dense=[0.0, 0.0, 1.0] * 256,  # Not similar
                sparse={"indices": [10, 11], "values": [0.3, 0.2]}
            ),
            line_start=20,
            line_end=25
        )
    ]

    await provider.upsert(chunks)

    # Execute hybrid search
    results = await provider.search(
        vector={
            "dense": [1.0, 0.0, 0.0] * 256,
            "sparse": {"indices": [1, 2], "values": [1.0, 0.9]}
        },
        limit=10
    )

    # Verify results are ranked by relevance
    assert len(results) >= 2
    assert results[0].chunk.chunk_name == "exact_match.py:func"  # Highest score
    assert results[0].score > results[1].score  # Descending order
    assert "partial_match.py:func" in [r.chunk.chunk_name for r in results]

    print(f"✅ Scenario 3 PASSED: Hybrid search ranked {len(results)} results correctly")

asyncio.run(test_hybrid_search_ranking())
```

## Scenario 4: In-Memory Provider with Disk Persistence

**User Story**: As a developer, I want to use in-memory storage for testing with automatic persistence.

**Acceptance Criteria** (spec.md:78): Given I want to use in-memory storage for testing, When I configure the in-memory provider in settings, Then the system stores embeddings in memory and persists them to disk on shutdown.

**Test Scenario**:
```python
from codeweaver.providers.vector_stores import MemoryVectorStoreProvider
from codeweaver.config.providers import MemoryConfig
import tempfile

async def test_inmemory_persistence():
    # Setup with temporary persistence path
    temp_path = Path(tempfile.mkdtemp()) / "test_memory.json"
    config = MemoryConfig(
        persist_path=temp_path,
        auto_persist=True,
        collection_name="test_memory"
    )

    # Phase 1: Create and populate
    provider1 = MemoryVectorStoreProvider(config=config)
    await provider1._initialize()

    chunk = CodeChunk(
        chunk_id=uuid4(),
        chunk_name="memory_test.py:func",
        file_path=Path("memory_test.py"),
        language=Language.PYTHON,
        content="test function",
        embeddings=ChunkEmbeddings(dense=[0.7, 0.7, 0.7] * 256),
        line_start=1,
        line_end=5
    )

    await provider1.upsert([chunk])

    # Trigger persistence
    await provider1._persist_to_disk()

    # Verify persistence file exists
    assert temp_path.exists()

    # Phase 2: Restore from disk
    provider2 = MemoryVectorStoreProvider(config=config)
    await provider2._initialize()

    # Verify: Chunk restored from disk
    results = await provider2.search(vector={"dense": [0.7, 0.7, 0.7] * 256})
    assert len(results) > 0
    assert results[0].chunk.chunk_name == "memory_test.py:func"

    print("✅ Scenario 4 PASSED: In-memory provider persists to disk")

asyncio.run(test_inmemory_persistence())
```

## Scenario 5: Incremental File Updates

**User Story**: As a CodeWeaver user, I want file updates to only re-index changed chunks.

**Acceptance Criteria** (spec.md:86): Given I update a file in my codebase, When the file is re-indexed, Then the system updates only the affected embeddings in both sparse and dense indexes.

**Test Scenario**:
```python
async def test_incremental_updates():
    config = QdrantConfig(url="http://localhost:6333", collection_name="test_incremental")
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    file_path = Path("src/updated_file.py")

    # Initial indexing
    chunk_v1 = CodeChunk(
        chunk_id=uuid4(),
        chunk_name=f"{file_path}:func_v1",
        file_path=file_path,
        language=Language.PYTHON,
        content="def func(): return 1",
        embeddings=ChunkEmbeddings(dense=[0.1] * 768),
        line_start=1,
        line_end=1
    )

    await provider.upsert([chunk_v1])

    # File updated: Delete old chunks, insert new chunks
    await provider.delete_by_file(file_path)

    chunk_v2 = CodeChunk(
        chunk_id=uuid4(),
        chunk_name=f"{file_path}:func_v2",
        file_path=file_path,
        language=Language.PYTHON,
        content="def func(): return 2",
        embeddings=ChunkEmbeddings(dense=[0.9] * 768),
        line_start=1,
        line_end=1
    )

    await provider.upsert([chunk_v2])

    # Verify: Old chunk gone, new chunk present
    results = await provider.search(vector={"dense": [0.9] * 768})
    assert len(results) > 0
    assert results[0].chunk.chunk_name == f"{file_path}:func_v2"
    assert "func_v1" not in [r.chunk.chunk_name for r in results]

    print("✅ Scenario 5 PASSED: Incremental updates work correctly")

asyncio.run(test_incremental_updates())
```

## Scenario 6: Provider-Specific Configuration

**User Story**: As a CodeWeaver user, I want to customize provider settings like collection names.

**Acceptance Criteria** (spec.md:88): Given I configure provider-specific settings, When the vector store is initialized, Then the provider respects my custom configuration.

**Test Scenario**:
```python
async def test_custom_configuration():
    # Test custom collection name
    config = QdrantConfig(
        url="http://localhost:6333",
        collection_name="my_custom_collection",
        batch_size=128,
        prefer_grpc=False
    )

    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    # Verify custom collection name
    assert provider.collection == "my_custom_collection"

    # Verify collection exists
    collections = await provider.list_collections()
    assert "my_custom_collection" in collections

    print("✅ Scenario 6 PASSED: Custom configuration respected")

asyncio.run(test_custom_configuration())
```

## Scenario 7: Remote Qdrant Connection

**User Story**: As a production user, I want to connect to Qdrant Cloud for remote storage.

**Acceptance Criteria** (spec.md:82-84): Given I want to use Qdrant Cloud, When I configure URL and API key, Then the system connects to the remote instance.

**Test Scenario**:
```python
import os

async def test_remote_connection():
    # Requires CODEWEAVER_QDRANT_URL and CODEWEAVER_QDRANT_API_KEY env vars
    remote_url = os.getenv("CODEWEAVER_QDRANT_URL")
    api_key = os.getenv("CODEWEAVER_QDRANT_API_KEY")

    if not remote_url or not api_key:
        print("⏭️  Scenario 7 SKIPPED: Remote Qdrant credentials not configured")
        return

    config = QdrantConfig(
        url=remote_url,
        api_key=api_key,
        collection_name="test_remote"
    )

    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    # Verify connection
    collections = await provider.list_collections()
    assert isinstance(collections, list)

    print("✅ Scenario 7 PASSED: Remote Qdrant connection successful")

# Note: This test requires actual remote Qdrant instance
# asyncio.run(test_remote_connection())
```

## Scenario 8: Provider Switch Detection

**User Story**: As a CodeWeaver user, I should be warned when switching providers to prevent data loss.

**Edge Case** (spec.md:93): Provider switching - System detects provider changes and blocks startup with clear error message.

**Test Scenario**:
```python
from codeweaver.exceptions import ProviderSwitchError

async def test_provider_switch_detection():
    collection_name = "test_provider_switch"

    # Phase 1: Create collection with Qdrant
    qdrant_config = QdrantConfig(
        url="http://localhost:6333",
        collection_name=collection_name
    )
    qdrant_provider = QdrantVectorStoreProvider(config=qdrant_config)
    await qdrant_provider._initialize()

    chunk = CodeChunk(
        chunk_id=uuid4(),
        chunk_name="test.py:func",
        file_path=Path("test.py"),
        language=Language.PYTHON,
        content="test",
        embeddings=ChunkEmbeddings(dense=[0.5] * 768),
        line_start=1,
        line_end=1
    )
    await qdrant_provider.upsert([chunk])

    # Phase 2: Try to use same collection with Memory provider
    memory_config = MemoryConfig(collection_name=collection_name)
    memory_provider = MemoryVectorStoreProvider(config=memory_config)

    # Should raise ProviderSwitchError
    try:
        await memory_provider._initialize()
        assert False, "Expected ProviderSwitchError"
    except ProviderSwitchError as e:
        assert "different provider" in str(e).lower()
        assert "re-index" in str(e).lower() or "revert" in str(e).lower()
        print(f"✅ Scenario 8 PASSED: Provider switch detected with error: {e}")

asyncio.run(test_provider_switch_detection())
```

## Scenario 9: Partial Embedding Handling

**User Story**: As a system, I should handle cases where dense embedding generation fails.

**Edge Case** (spec.md:94): Partial embedding failure - Store chunk with sparse-only and mark as "incomplete".

**Test Scenario**:
```python
async def test_partial_embeddings():
    config = QdrantConfig(url="http://localhost:6333", collection_name="test_partial")
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    # Create chunk with sparse-only embedding (dense failed)
    chunk = CodeChunk(
        chunk_id=uuid4(),
        chunk_name="partial.py:func",
        file_path=Path("partial.py"),
        language=Language.PYTHON,
        content="function with failed dense embedding",
        embeddings=ChunkEmbeddings(
            dense=None,  # Dense embedding generation failed
            sparse={"indices": [1, 2, 3], "values": [0.8, 0.7, 0.6]}
        ),
        line_start=1,
        line_end=5
    )

    # Should successfully upsert with sparse-only
    await provider.upsert([chunk])

    # Verify chunk is searchable with sparse vector
    results = await provider.search(
        vector={"sparse": {"indices": [1, 2], "values": [0.8, 0.7]}}
    )
    assert len(results) > 0
    assert results[0].chunk.chunk_id == chunk.chunk_id

    # Verify metadata marks as incomplete
    assert results[0].chunk.metadata.get("embedding_complete") == False

    print("✅ Scenario 9 PASSED: Partial embeddings handled correctly")

asyncio.run(test_partial_embeddings())
```

## Run All Scenarios

```python
async def run_all_scenarios():
    scenarios = [
        ("Scenario 1: Hybrid Embeddings", test_store_hybrid_embeddings),
        ("Scenario 2: Persistence", test_persistence_across_restarts),
        ("Scenario 3: Hybrid Search Ranking", test_hybrid_search_ranking),
        ("Scenario 4: In-Memory Persistence", test_inmemory_persistence),
        ("Scenario 5: Incremental Updates", test_incremental_updates),
        ("Scenario 6: Custom Configuration", test_custom_configuration),
        ("Scenario 8: Provider Switch Detection", test_provider_switch_detection),
        ("Scenario 9: Partial Embeddings", test_partial_embeddings),
    ]

    print("\n" + "="*60)
    print("Running Vector Storage Provider Quickstart Scenarios")
    print("="*60 + "\n")

    for name, test_func in scenarios:
        print(f"\n{name}")
        print("-" * 60)
        try:
            await test_func()
        except Exception as e:
            print(f"❌ {name} FAILED: {e}")

    print("\n" + "="*60)
    print("All Scenarios Complete")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(run_all_scenarios())
```

## Next Steps

1. **Run Quickstart**: Execute scenarios to validate implementation
2. **Contract Tests**: Generate contract tests from YAML specifications
3. **Integration Tests**: Build comprehensive test suite
4. **Performance Testing**: Validate performance characteristics
5. **Documentation**: Update user-facing docs with examples

---

**Quickstart Status**: ✅ READY - Executable validation scenarios defined
