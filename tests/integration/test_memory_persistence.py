# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 4 - In-memory persistence.

From quickstart.md:228-284
Validates acceptance criteria spec.md:78
"""

import tempfile  # noqa: I001

from pathlib import Path

import pytest

from codeweaver.common.utils.utils import uuid7
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider

# sourcery skip: dont-import-test-modules
from tests.conftest import create_test_chunk_with_embeddings
from codeweaver.providers.provider import Provider


pytestmark = pytest.mark.integration


async def test_inmemory_persistence():
    """
    User Story: Use in-memory storage with automatic persistence.

    Given: I want to use in-memory storage for testing
    When: I configure the in-memory provider
    Then: System stores embeddings in memory and persists to disk on shutdown
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "test_memory.json"
        config = {
            "persist_path": str(temp_path),
            "auto_persist": True,
            "collection_name": "test_memory",
        }

        # Phase 1: Create and populate
        provider1 = MemoryVectorStoreProvider(_provider=Provider.MEMORY, config=config)
        await provider1._initialize()

        chunk = create_test_chunk_with_embeddings(
            chunk_id=uuid7(),
            chunk_name="memory_test.py:func",
            file_path=Path("memory_test.py"),
            language=Language.PYTHON,
            content="test function",
            dense_embedding=[0.7, 0.7, 0.7] * 256,
            line_start=1,
            line_end=5,
        )

        await provider1.upsert([chunk])

        # Trigger persistence
        await provider1._persist_to_disk()

        # Verify persistence file exists
        assert temp_path.exists(), "Persistence file should be created"

        # Phase 2: Restore from disk
        provider2 = MemoryVectorStoreProvider(_provider=Provider.MEMORY, config=config)
        await provider2._initialize()

        # Verify: Chunk restored from disk
        from codeweaver.agent_api.find_code.types import SearchStrategy, StrategizedQuery

        results = await provider2.search(
            StrategizedQuery(
                query="test function",
                strategy=SearchStrategy.DENSE_ONLY,
                dense=[0.7, 0.7, 0.7] * 256,
                sparse=None,
            )
        )
        assert len(results) > 0, "Should restore chunks from persistence file"
        assert results[0].chunk.chunk_name == "memory_test.py:func"

        print("✅ Scenario 4 PASSED: In-memory provider persists to disk")
