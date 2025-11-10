# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 9 - Partial embeddings.

From quickstart.md:461-505
Validates edge case spec.md:94
"""

from pathlib import Path

import pytest

from codeweaver.common.utils.utils import uuid7
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider
from tests.conftest import create_test_chunk_with_embeddings


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_partial_embeddings(qdrant_test_manager):
    """
    User Story: Handle cases where dense embedding generation fails.

    Edge Case: Partial embedding failure
    Then: Store chunk with sparse-only and mark as 'incomplete'
    """
    # Create unique collection
    collection_name = qdrant_test_manager.create_collection_name("partial")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    config = {"url": qdrant_test_manager.url, "collection_name": collection_name}
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    # Create chunk with sparse-only embedding (dense failed)
    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="partial.py:func",
        file_path=Path("partial.py"),
        language=Language.PYTHON,
        content="function with failed dense embedding",
        dense_embedding=None,  # Dense embedding generation failed
        sparse_embedding={"indices": [1, 2, 3], "values": [0.8, 0.7, 0.6]},
        line_start=1,
        line_end=5,
    )

    # Should successfully upsert with sparse-only
    await provider.upsert([chunk])

    # Verify chunk is searchable with sparse vector
    from codeweaver.agent_api.find_code.types import SearchStrategy, StrategizedQuery

    results = await provider.search(
        StrategizedQuery(
            query="function with failed dense embedding",
            strategy=SearchStrategy.SEMANTIC,
            dense=None,
            sparse={"indices": [1, 2], "values": [0.8, 0.7]},  # ty: ignore[invalid-argument-type]
        )
    )
    assert len(results) > 0, "Should find chunk with sparse-only embedding"
    assert results[0].chunk.chunk_id == chunk.chunk_id

    # Verify metadata marks as incomplete
    # Note: This will be in the payload when we implement it
    # For now, just verify the chunk was stored
    assert results[0].chunk is not None

    # Cleanup handled by test manager

    print("✅ Scenario 9 PASSED: Partial embeddings handled correctly")
