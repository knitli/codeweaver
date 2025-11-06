# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 8 - Provider switch detection.

From quickstart.md:415-459
Validates edge case spec.md:93
"""

from pathlib import Path

import pytest

from codeweaver.common.utils.utils import uuid7
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.exceptions import ProviderSwitchError
from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider
from tests.conftest import create_test_chunk_with_embeddings


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_provider_switch_detection(qdrant_test_manager):
    """
    User Story: Warn when switching providers to prevent data loss.

    Edge Case: Provider switching
    Then: System detects provider changes and blocks startup with clear error
    """
    # Create unique collection
    collection_name = qdrant_test_manager.create_collection_name("provider_switch")
    await qdrant_test_manager.create_collection(collection_name, dense_vector_size=768)

    # Phase 1: Create collection with Qdrant
    qdrant_config = {"url": qdrant_test_manager.url, "collection_name": collection_name}
    qdrant_provider = QdrantVectorStoreProvider(config=qdrant_config)
    await qdrant_provider._initialize()

    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="test.py:func",
        file_path=Path("test.py"),
        language=Language.PYTHON,
        content="test",
        dense_embedding=[0.5] * 768,
        line_start=1,
        line_end=1,
    )
    await qdrant_provider.upsert([chunk])

    # Phase 2: Try to use same collection with Memory provider
    memory_config = {"collection_name": collection_name}
    memory_provider = MemoryVectorStoreProvider(config=memory_config)

    # Should raise ProviderSwitchError
    with pytest.raises(ProviderSwitchError) as exc_info:
        await memory_provider._initialize()

    error_msg = str(exc_info.value).lower()
    assert "different provider" in error_msg or "provider" in error_msg
    assert "re-index" in error_msg or "revert" in error_msg

    # Cleanup handled by test manager

    print("✅ Scenario 8 PASSED: Provider switch detected with error")
