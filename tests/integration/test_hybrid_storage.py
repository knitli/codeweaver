# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 1 - Hybrid embeddings storage.

From quickstart.md:31-106
Validates acceptance criteria spec.md:72
"""

from pathlib import Path
from uuid import uuid4

import pytest

from codeweaver.config.providers import QdrantConfig
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStore

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


@pytest.fixture
async def qdrant_provider():
    """Create Qdrant provider for testing."""
    config = {
        "url": "http://localhost:6333",
        "collection_name": f"test_hybrid_{uuid4().hex[:8]}",
    }
    provider = QdrantVectorStore(config=config)
    await provider._initialize()
    yield provider
    # Cleanup
    try:
        await provider._client.delete_collection(collection_name=config["collection_name"])
    except Exception:
        pass


async def test_store_hybrid_embeddings(qdrant_provider):
    """
    User Story: Store both dense and sparse embeddings with default settings.

    Given: Embeddings have been generated for my codebase
    When: I initialize CodeWeaver with default settings
    Then: System stores both dense and sparse embeddings in the vector store
    """
    # Create chunk with both dense and sparse embeddings
    chunk = CodeChunk(
        chunk_id=uuid4(),
        chunk_name="auth.py:authenticate",
        file_path=Path("src/auth.py"),
        language=Language.PYTHON,
        content="def authenticate(user, password):\n    ...",
        embeddings={
            "dense": [0.1, 0.2, 0.3] * 256,  # 768-dim vector
            "sparse": {"indices": [1, 5, 10, 23], "values": [0.8, 0.6, 0.9, 0.4]},
        },
        line_start=10,
        line_end=15,
    )

    # Execute: Upsert chunk
    await qdrant_provider.upsert([chunk])

    # Verify: Search with dense vector returns result
    dense_results = await qdrant_provider.search(vector={"dense": [0.1, 0.2, 0.3] * 256})
    assert len(dense_results) > 0, "Dense vector search should return results"
    assert dense_results[0].chunk.chunk_id == chunk.chunk_id

    # Verify: Search with sparse vector returns result
    sparse_results = await qdrant_provider.search(
        vector={"sparse": {"indices": [1, 5, 10], "values": [0.8, 0.6, 0.9]}}
    )
    assert len(sparse_results) > 0, "Sparse vector search should return results"

    # Verify: Hybrid search returns result
    hybrid_results = await qdrant_provider.search(
        vector={
            "dense": [0.1, 0.2, 0.3] * 256,
            "sparse": {"indices": [1, 5, 10], "values": [0.8, 0.6, 0.9]},
        }
    )
    assert len(hybrid_results) > 0, "Hybrid search should return results"
    assert hybrid_results[0].chunk.chunk_id == chunk.chunk_id

    print("✅ Scenario 1 PASSED: Hybrid embeddings stored and searchable")
