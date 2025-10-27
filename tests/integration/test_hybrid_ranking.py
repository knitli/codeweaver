# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 3 - Hybrid search ranking.

From quickstart.md:150-226
Validates acceptance criteria spec.md:76
"""

from pathlib import Path
from uuid import uuid4

import pytest

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStore


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_hybrid_search_ranking():
    """
    User Story: Hybrid search combines sparse and dense for better relevance.

    Given: I perform a semantic code search
    When: Query is processed
    Then: System returns hybrid search results ranked by relevance
    """
    config = {"url": "http://localhost:6333", "collection_name": f"test_ranking_{uuid4().hex[:8]}"}
    provider = QdrantVectorStore(config=config)
    await provider._initialize()

    # Insert chunks with varying similarity
    chunks = [
        CodeChunk(
            chunk_id=uuid4(),
            chunk_name="exact_match.py:func",
            file_path=Path("exact_match.py"),
            language=Language.PYTHON,
            content="authentication function",
            embeddings={
                "dense": [1.0, 0.0, 0.0] * 256,  # Very similar
                "sparse": {"indices": [1, 2, 3], "values": [1.0, 0.9, 0.8]},
            },
            line_start=1,
            line_end=5,
        ),
        CodeChunk(
            chunk_id=uuid4(),
            chunk_name="partial_match.py:func",
            file_path=Path("partial_match.py"),
            language=Language.PYTHON,
            content="auth helper",
            embeddings={
                "dense": [0.5, 0.5, 0.0] * 256,  # Somewhat similar
                "sparse": {"indices": [1, 4], "values": [0.6, 0.5]},
            },
            line_start=10,
            line_end=15,
        ),
        CodeChunk(
            chunk_id=uuid4(),
            chunk_name="no_match.py:func",
            file_path=Path("no_match.py"),
            language=Language.PYTHON,
            content="unrelated function",
            embeddings={
                "dense": [0.0, 0.0, 1.0] * 256,  # Not similar
                "sparse": {"indices": [10, 11], "values": [0.3, 0.2]},
            },
            line_start=20,
            line_end=25,
        ),
    ]

    await provider.upsert(chunks)

    # Execute hybrid search
    results = await provider.search(
        vector={
            "dense": [1.0, 0.0, 0.0] * 256,
            "sparse": {"indices": [1, 2], "values": [1.0, 0.9]},
        },
        limit=10,
    )

    # Verify results are ranked by relevance
    assert len(results) >= 2, "Should return multiple results"
    assert results[0].chunk.chunk_name == "exact_match.py:func", (
        "Highest score should be exact match"
    )
    assert results[0].score > results[1].score, "Results should be in descending score order"
    assert "partial_match.py:func" in [r.chunk.chunk_name for r in results]

    # Cleanup
    try:
        await provider._client.delete_collection(collection_name=config["collection_name"])
    except Exception:
        pass

    print(f"✅ Scenario 3 PASSED: Hybrid search ranked {len(results)} results correctly")
