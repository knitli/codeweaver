# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 2 - Persistence across restarts.

From quickstart.md:108-148
Validates acceptance criteria spec.md:74
"""

from pathlib import Path

import pytest

from codeweaver.agent_api.find_code.types import SearchStrategy, StrategizedQuery
from codeweaver.common.utils.utils import uuid7
from codeweaver.config.providers import QdrantConfig
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider

# sourcery skip: dont-import-test-modules
from tests.conftest import create_test_chunk_with_embeddings


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_persistence_across_restarts(qdrant_test_manager):
    """
    User Story: Previously indexed data persists across restarts.

    Given: I have previously indexed my codebase
    When: I restart CodeWeaver
    Then: System retrieves previously stored embeddings without re-embedding
    """
    # Create unique collection with sparse vector support (needed for BM25)
    collection_name = qdrant_test_manager.create_collection_name("persist")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    config = QdrantConfig(url=qdrant_test_manager.url, collection_name=collection_name)

    # Phase 1: Initial indexing
    provider1 = QdrantVectorStoreProvider(config=config)
    await provider1._initialize()

    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="login.py:validate",
        file_path=Path("src/login.py"),
        language=Language.PYTHON,
        content="def validate(token): ...",
        dense_embedding=[0.5, 0.5, 0.5] * 256,
        line_start=20,
        line_end=25,
    )

    await provider1.upsert([chunk])
    original_chunk_id = chunk.chunk_id

    # Simulate restart: Create new provider instance
    provider2 = QdrantVectorStoreProvider(config=config)
    await provider2._initialize()

    # Verify: Previously stored chunk is retrievable
    results = await provider2.search(
        StrategizedQuery(
            query="validate token",
            strategy=SearchStrategy.DENSE_ONLY,
            dense=[0.5, 0.5, 0.5] * 256,
            sparse=None,
        )
    )
    assert len(results) > 0, "Should find previously stored chunks"
    assert results[0].chunk.chunk_id == original_chunk_id
    assert results[0].chunk.chunk_name == "login.py:validate"

    # Cleanup handled by test manager

    print("✅ Scenario 2 PASSED: Embeddings persist across restarts")
