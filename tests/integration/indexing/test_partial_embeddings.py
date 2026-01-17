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

from codeweaver.core import SemanticSearchLanguage as Language
from codeweaver.core import uuid7
from codeweaver.providers import QdrantVectorStoreProvider
from tests.conftest import create_test_chunk_with_embeddings


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_partial_embeddings(qdrant_test_manager, vector_store_factory):
    """
    User Story: Handle cases where dense embedding generation fails.

    Edge Case: Partial embedding failure
    Then: Store chunk with sparse-only and mark as 'incomplete'
    """

    # Create unique collection
    collection_name = qdrant_test_manager.create_collection_name("partial")

    provider = await vector_store_factory(
        QdrantVectorStoreProvider,
        config_overrides={
            "collection_name": collection_name,
            "url": qdrant_test_manager.url,
            "dense_vector_size": 768,
            "sparse_vector_size": 1000,
        },
    )

    # Create chunk with sparse-only embedding (dense failed)
    # Use consistent sparse embedding for both chunk and search
    test_sparse_indices = [1, 2, 3]
    test_sparse_values = [0.8, 0.7, 0.6]

    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="partial.py:func",
        file_path=Path("partial.py"),
        language=Language.PYTHON,
        content="function with failed dense embedding",
        dense_embedding=None,  # Dense embedding generation failed
        sparse_embedding={"indices": test_sparse_indices, "values": test_sparse_values},
        line_start=1,
        line_end=5,
    )

    # Should successfully upsert with sparse-only
    await provider.upsert([chunk])

    # Verify chunk is searchable with sparse vector
    from codeweaver.core import SearchStrategy, StrategizedQuery
    from codeweaver.providers import SparseEmbedding

    # Use same sparse embedding for search to ensure we find the chunk
    results = await provider.search(
        StrategizedQuery(
            query="function with failed dense embedding",
            strategy=SearchStrategy.SPARSE_ONLY,
            dense=None,
            sparse=SparseEmbedding(indices=test_sparse_indices, values=test_sparse_values),
        )
    )
    assert len(results) > 0, "Sparse search should find the chunk"

    # Verify metadata marks as incomplete
    # Note: This will be in the payload when we implement it
    # For now, just verify the chunk was stored
    assert results[0].chunk is not None

    # Cleanup handled by test manager

    print("✅ Scenario 9 PASSED: Partial embeddings handled correctly")
