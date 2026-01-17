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

from voyageai.client_async import AsyncClient

from codeweaver.providers import (
    QdrantVectorStoreProvider,
    VoyageEmbeddingProvider,
    get_voyage_embedding_capabilities,
)


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
async def test_custom_configuration(qdrant_test_manager, vector_store_factory):
    """
    User Story: Customize provider settings like collection names.

    Given: I configure provider-specific settings
    When: Vector store is initialized
    Then: Provider respects my custom configuration
    """
    # Get configuration from qdrant_test_manager
    qdrant_url = qdrant_test_manager.url

    # Cleanup any existing collection first
    with contextlib.suppress(Exception):
        await qdrant_test_manager.delete_collection("my_custom_collection")

    # Use factory to create provider with custom config
    provider = await vector_store_factory(
        QdrantVectorStoreProvider,
        config_overrides={
            "collection_name": "my_custom_collection",
            "url": qdrant_url,
            "batch_size": 128,
            # api_key is handled by qdrant_client creation in factory if we passed it,
            # but factory currently only takes url.
            # qdrant_test_manager.url typically embeds api key or we might need to enhance factory.
            # However, standard test setup usually doesn't use API key for local Qdrant.
            # If qdrant_test_manager has api_key, we should pass it.
        },
    )
    # Note: factory uses qdrant_test_manager.url default if not provided, but we provide it.
    # If API key is separate, factory might need update.
    # Current factory implementation:
    # client_options=QdrantClientOptions(url=AnyUrl(url)),
    # It doesn't pass api_key explicitly to ClientOptions.
    # If qdrant_test_manager.url is full URL, it might be fine.
    # But let's check factory implementation again.

    # Factory:
    # url = config_overrides.get("url", qdrant_test_manager.url)
    # settings = QdrantVectorStoreProviderSettings(..., client_options=QdrantClientOptions(url=AnyUrl(url)), ...)
    # client = AsyncQdrantClient(url=url)

    # If api_key is needed, AsyncQdrantClient needs it.
    # The factory as implemented in previous turn *does not* take api_key from config_overrides for client creation.
    # It just uses `AsyncQdrantClient(url=url)`.
    # This might be a limitation if tests require auth.
    # But for now, I will proceed.

    # Verify collection name behavior
    # When collection_name is provided in config, it should be used instead of auto-generation
    assert provider.collection is not None
    assert provider.collection == "my_custom_collection"

    # Verify the collection that was actually created exists in the list
    collections = await provider.list_collections()
    assert provider.collection in collections  # type: ignore

    # Cleanup
    with contextlib.suppress(Exception):
        await qdrant_test_manager.delete_collection("my_custom_collection")
    print("✅ Scenario 6 PASSED: Custom configuration respected")
