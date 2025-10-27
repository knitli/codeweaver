# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 8 - Provider switch detection.

From quickstart.md:415-459
Validates edge case spec.md:93
"""

from pathlib import Path
from uuid import uuid4

import pytest

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import SemanticSearchLanguage as Language
from codeweaver.exceptions import ProviderSwitchError
from codeweaver.providers.vector_stores.inmemory import MemoryVectorStore
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStore


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_provider_switch_detection():
    """
    User Story: Warn when switching providers to prevent data loss.

    Edge Case: Provider switching
    Then: System detects provider changes and blocks startup with clear error
    """
    collection_name = f"test_provider_switch_{uuid4().hex[:8]}"

    # Phase 1: Create collection with Qdrant
    qdrant_config = {"url": "http://localhost:6333", "collection_name": collection_name}
    qdrant_provider = QdrantVectorStore(config=qdrant_config)
    await qdrant_provider._initialize()

    chunk = CodeChunk(
        chunk_id=uuid4(),
        chunk_name="test.py:func",
        file_path=Path("test.py"),
        language=Language.PYTHON,
        content="test",
        embeddings={"dense": [0.5] * 768},
        line_start=1,
        line_end=1,
    )
    await qdrant_provider.upsert([chunk])

    # Phase 2: Try to use same collection with Memory provider
    memory_config = {"collection_name": collection_name}
    memory_provider = MemoryVectorStore(config=memory_config)

    # Should raise ProviderSwitchError
    with pytest.raises(ProviderSwitchError) as exc_info:
        await memory_provider._initialize()

    error_msg = str(exc_info.value).lower()
    assert "different provider" in error_msg or "provider" in error_msg
    assert "re-index" in error_msg or "revert" in error_msg

    # Cleanup
    try:
        await qdrant_provider._client.delete_collection(collection_name=collection_name)
    except Exception:
        pass

    print("✅ Scenario 8 PASSED: Provider switch detected with error")
