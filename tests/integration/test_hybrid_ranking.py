# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 3 - Hybrid search ranking.

From quickstart.md:150-226
Validates acceptance criteria spec.md:76
"""

from pathlib import Path

import pytest

from codeweaver.agent_api.find_code.types import SearchStrategy, StrategizedQuery
from codeweaver.common.utils.utils import uuid7
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider

# sourcery skip: dont-import-test-modules
from tests.conftest import create_test_chunk_with_embeddings


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_hybrid_search_ranking(qdrant_test_manager):
    """
    User Story: Hybrid search combines sparse and dense for better relevance.

    Given: I perform a semantic code search
    When: Query is processed
    Then: System returns hybrid search results ranked by relevance
    """
    # Create unique collection
    collection_name = qdrant_test_manager.create_collection_name("ranking")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    config = {"url": qdrant_test_manager.url, "collection_name": collection_name}
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    # Insert chunks with varying similarity - using helper to create valid chunks
    chunk_id_1 = uuid7()
    chunk_id_2 = uuid7()
    chunk_id_3 = uuid7()

    chunks = [
        create_test_chunk_with_embeddings(
            chunk_id=chunk_id_1,
            chunk_name="exact_match.py:func",
            file_path=Path("exact_match.py"),
            language=Language.PYTHON,
            content="authentication function",
            dense_embedding=[1.0, 0.0, 0.0] * 256,  # Very similar
            sparse_embedding={"indices": [1, 2, 3], "values": [1.0, 0.9, 0.8]},
            line_start=1,
            line_end=5,
        ),
        create_test_chunk_with_embeddings(
            chunk_id=chunk_id_2,
            chunk_name="partial_match.py:func",
            file_path=Path("partial_match.py"),
            language=Language.PYTHON,
            content="auth helper",
            dense_embedding=[0.5, 0.5, 0.0] * 256,  # Somewhat similar
            sparse_embedding={"indices": [1, 4], "values": [0.6, 0.5]},
            line_start=10,
            line_end=15,
        ),
        create_test_chunk_with_embeddings(
            chunk_id=chunk_id_3,
            chunk_name="no_match.py:func",
            file_path=Path("no_match.py"),
            language=Language.PYTHON,
            content="unrelated function",
            dense_embedding=[0.0, 0.0, 1.0] * 256,  # Not similar
            sparse_embedding={"indices": [10, 11], "values": [0.3, 0.2]},
            line_start=20,
            line_end=25,
        ),
    ]

    await provider.upsert(chunks)

    # Execute hybrid search
    results = await provider.search(
        StrategizedQuery(
            query="authentication function",
            strategy=SearchStrategy.HYBRID,
            dense=[1.0, 0.0, 0.0] * 256,
            sparse={"indices": [1, 2], "values": [1.0, 0.9]},
        )
    )

    # Verify results are ranked by relevance
    assert len(results) >= 2, "Should return multiple results"
    assert results[0].chunk.chunk_name == "exact_match.py:func", (
        "Highest score should be exact match"
    )
    assert results[0].score > results[1].score, "Results should be in descending score order"
    assert "partial_match.py:func" in [r.chunk.chunk_name for r in results]

    # Cleanup handled by test manager

    print(f"✅ Scenario 3 PASSED: Hybrid search ranked {len(results)} results correctly")
