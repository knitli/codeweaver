# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 5 - Incremental updates.

From quickstart.md:286-340
Validates acceptance criteria spec.md:86
"""

from pathlib import Path
from uuid import uuid4

import pytest

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStore


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_incremental_updates():
    """
    User Story: File updates only re-index changed chunks.

    Given: I update a file in my codebase
    When: File is re-indexed
    Then: System updates only affected embeddings in both sparse and dense indexes
    """
    config = {
        "url": "http://localhost:6333",
        "collection_name": f"test_incremental_{uuid4().hex[:8]}",
    }
    provider = QdrantVectorStore(config=config)
    await provider._initialize()

    file_path = Path("src/updated_file.py")

    # Initial indexing
    chunk_v1 = CodeChunk(
        chunk_id=uuid4(),
        chunk_name=f"{file_path}:func_v1",
        file_path=file_path,
        language=Language.PYTHON,
        content="def func(): return 1",
        embeddings={"dense": [0.1] * 768},
        line_start=1,
        line_end=1,
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
        embeddings={"dense": [0.9] * 768},
        line_start=1,
        line_end=1,
    )

    await provider.upsert([chunk_v2])

    # Verify: Old chunk gone, new chunk present
    results = await provider.search(vector={"dense": [0.9] * 768})
    assert len(results) > 0, "Should find updated chunk"
    assert results[0].chunk.chunk_name == f"{file_path}:func_v2"
    assert "func_v1" not in [r.chunk.chunk_name for r in results]

    # Cleanup
    try:
        await provider._client.delete_collection(collection_name=config["collection_name"])
    except Exception:
        pass

    print("✅ Scenario 5 PASSED: Incremental updates work correctly")
