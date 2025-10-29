# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 6 - Custom configuration.

From quickstart.md:342-373
Validates acceptance criteria spec.md:88
"""

import pytest

from codeweaver.providers.vector_stores.qdrant import QdrantVectorStore


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


async def test_custom_configuration():
    """
    User Story: Customize provider settings like collection names.

    Given: I configure provider-specific settings
    When: Vector store is initialized
    Then: Provider respects my custom configuration
    """
    # Test custom collection name
    config = {
        "url": "http://localhost:6333",
        "collection_name": "my_custom_collection",
        "batch_size": 128,
        "prefer_grpc": False,
    }

    provider = QdrantVectorStore(config=config)
    await provider._initialize()

    # Verify custom collection name
    assert provider.collection == "my_custom_collection"

    # Verify collection exists
    collections = await provider.list_collections()
    assert "my_custom_collection" in collections

    # Cleanup
    try:
        await provider._client.delete_collection(collection_name="my_custom_collection")
    except Exception:
        pass

    print("✅ Scenario 6 PASSED: Custom configuration respected")
