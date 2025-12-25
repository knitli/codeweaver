# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 5 - Incremental updates.

From quickstart.md:286-340
Validates acceptance criteria spec.md:86
"""

from pathlib import Path

import pytest

from codeweaver.common.utils.utils import uuid7
from codeweaver.config.providers import QdrantConfig
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider

# sourcery skip: dont-import-test-modules
from tests.conftest import create_test_chunk_with_embeddings


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_incremental_updates(qdrant_test_manager):
    """
    User Story: File updates only re-index changed chunks.

    Given: I update a file in my codebase
    When: File is re-indexed
    Then: System updates only affected embeddings in both sparse and dense indexes
    """
    # Create unique collection with sparse vector support (needed for BM25)
    collection_name = qdrant_test_manager.create_collection_name("incremental")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    config = QdrantConfig(url=qdrant_test_manager.url, collection_name=collection_name)
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    file_path = Path("src/updated_file.py")

    # Initial indexing
    chunk_v1 = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name=f"{file_path}:func_v1",
        file_path=file_path,
        language=Language.PYTHON,
        content="def func(): return 1",
        dense_embedding=[0.1] * 768,
        line_start=1,
        line_end=1,
    )

    await provider.upsert([chunk_v1])

    # File updated: Delete old chunks, insert new chunks
    await provider.delete_by_file(file_path)

    chunk_v2 = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name=f"{file_path}:func_v2",
        file_path=file_path,
        language=Language.PYTHON,
        content="def func(): return 2",
        dense_embedding=[0.9] * 768,
        line_start=1,
        line_end=1,
    )

    await provider.upsert([chunk_v2])

    # Verify: Old chunk gone, new chunk present
    from codeweaver.core.types.search import SearchStrategy, StrategizedQuery

    results = await provider.search(
        StrategizedQuery(
            query="def func(): return 2",
            strategy=SearchStrategy.DENSE_ONLY,
            dense=[0.9] * 768,
            sparse=None,
        )
    )
    assert len(results) > 0, "Should find updated chunk"
    assert results[0].chunk.chunk_name == f"{file_path}:func_v2"
    assert "func_v1" not in [r.chunk.chunk_name for r in results]

    # Cleanup handled by test manager

    print("✅ Scenario 5 PASSED: Incremental updates work correctly")
