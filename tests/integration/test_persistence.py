# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 2 - Persistence across restarts.

From quickstart.md:108-148
Validates acceptance criteria spec.md:74
"""

from pathlib import Path
from uuid import uuid4

import pytest

from codeweaver.config.providers import QdrantConfig
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStore

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_persistence_across_restarts():
    """
    User Story: Previously indexed data persists across restarts.

    Given: I have previously indexed my codebase
    When: I restart CodeWeaver
    Then: System retrieves previously stored embeddings without re-embedding
    """
    collection_name = f"test_persist_{uuid4().hex[:8]}"
    config = {"url": "http://localhost:6333", "collection_name": collection_name}

    # Phase 1: Initial indexing
    provider1 = QdrantVectorStore(config=config)
    await provider1._initialize()

    chunk = CodeChunk(
        chunk_id=uuid4(),
        chunk_name="login.py:validate",
        file_path=Path("src/login.py"),
        language=Language.PYTHON,
        content="def validate(token): ...",
        embeddings={"dense": [0.5, 0.5, 0.5] * 256},
        line_start=20,
        line_end=25,
    )

    await provider1.upsert([chunk])
    original_chunk_id = chunk.chunk_id

    # Simulate restart: Create new provider instance
    provider2 = QdrantVectorStore(config=config)
    await provider2._initialize()

    # Verify: Previously stored chunk is retrievable
    results = await provider2.search(vector={"dense": [0.5, 0.5, 0.5] * 256})
    assert len(results) > 0, "Should find previously stored chunks"
    assert results[0].chunk.chunk_id == original_chunk_id
    assert results[0].chunk.chunk_name == "login.py:validate"

    # Cleanup
    try:
        await provider2._client.delete_collection(collection_name=collection_name)
    except Exception:
        pass

    print("✅ Scenario 2 PASSED: Embeddings persist across restarts")
