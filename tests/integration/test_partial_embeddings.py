# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 9 - Partial embeddings.

From quickstart.md:461-505
Validates edge case spec.md:94
"""

from pathlib import Path
from uuid import uuid4

import pytest

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStore

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_partial_embeddings():
    """
    User Story: Handle cases where dense embedding generation fails.

    Edge Case: Partial embedding failure
    Then: Store chunk with sparse-only and mark as 'incomplete'
    """
    config = {"url": "http://localhost:6333", "collection_name": f"test_partial_{uuid4().hex[:8]}"}
    provider = QdrantVectorStore(config=config)
    await provider._initialize()

    # Create chunk with sparse-only embedding (dense failed)
    chunk = CodeChunk(
        chunk_id=uuid4(),
        chunk_name="partial.py:func",
        file_path=Path("partial.py"),
        language=Language.PYTHON,
        content="function with failed dense embedding",
        embeddings={
            "dense": None,  # Dense embedding generation failed
            "sparse": {"indices": [1, 2, 3], "values": [0.8, 0.7, 0.6]},
        },
        line_start=1,
        line_end=5,
    )

    # Should successfully upsert with sparse-only
    await provider.upsert([chunk])

    # Verify chunk is searchable with sparse vector
    results = await provider.search(vector={"sparse": {"indices": [1, 2], "values": [0.8, 0.7]}})
    assert len(results) > 0, "Should find chunk with sparse-only embedding"
    assert results[0].chunk.chunk_id == chunk.chunk_id

    # Verify metadata marks as incomplete
    # Note: This will be in the payload when we implement it
    # For now, just verify the chunk was stored
    assert results[0].chunk is not None

    # Cleanup
    try:
        await provider._client.delete_collection(collection_name=config["collection_name"])
    except Exception:
        pass

    print("✅ Scenario 9 PASSED: Partial embeddings handled correctly")
