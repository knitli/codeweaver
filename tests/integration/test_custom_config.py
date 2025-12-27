# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Scenario 6 - Custom configuration.

From quickstart.md:342-373
Validates acceptance criteria spec.md:88
"""

import contextlib
import os

import pytest

from qdrant_client import AsyncQdrantClient
from voyageai.client_async import AsyncClient

from codeweaver.config.providers import QdrantConfig
from codeweaver.providers.embedding.capabilities.voyage import get_voyage_embedding_capabilities
from codeweaver.providers.embedding.providers.voyage import VoyageEmbeddingProvider
from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider


embedding_caps = next(
    cap for cap in get_voyage_embedding_capabilities() if cap.name == "voyage-code-3"
)

# Only create the provider if the API key is available
# This prevents collection errors when the environment variable is not set
embedding_provider = None
if os.environ.get("VOYAGE_API_KEY"):
    embedding_provider = VoyageEmbeddingProvider(
        client=AsyncClient(api_key=os.environ["VOYAGE_API_KEY"]),  # type: ignore
        caps=embedding_caps,  # type: ignore
        kwargs=None,  # type: ignore
    )


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


@pytest.mark.skipif(
    not os.environ.get("VOYAGE_API_KEY"), reason="VOYAGE_API_KEY environment variable required"
)
async def test_custom_configuration(qdrant_test_manager):
    """
    User Story: Customize provider settings like collection names.

    Given: I configure provider-specific settings
    When: Vector store is initialized
    Then: Provider respects my custom configuration
    """
    # Get configuration from qdrant_test_manager
    qdrant_url = qdrant_test_manager.url
    qdrant_api_key = qdrant_test_manager.api_key

    # Get base test config with proper authentication
    base_config = {"url": qdrant_url, "api_key": qdrant_api_key, "prefer_grpc": False}

    # Test custom collection name
    config = QdrantConfig(**{
        **base_config,
        "collection_name": "my_custom_collection",
        "batch_size": 128,
    })
    # AsyncQdrantClient doesn't accept collection_name - filter it out
    client_config = {k: v for k, v in config.items() if k not in ["collection_name", "batch_size"]}
    client = AsyncQdrantClient(**client_config)  # ty: ignore[invalid-argument-type]

    # Cleanup any existing collection first
    with contextlib.suppress(Exception):
        _ = await client.delete_collection(collection_name="my_custom_collection")
    provider = QdrantVectorStoreProvider(client=client, config=config)
    await provider._initialize()

    # Verify collection name behavior
    # When collection_name is provided in config, it should be used instead of auto-generation
    assert provider.collection is not None
    assert provider.collection == "my_custom_collection"

    # Verify the collection that was actually created exists in the list
    collections = await provider.list_collections()
    assert provider.collection in collections  # type: ignore

    # Cleanup
    with contextlib.suppress(Exception):
        _ = await provider.client.delete_collection(collection_name="my_custom_collection")
    print("✅ Scenario 6 PASSED: Custom configuration respected")
