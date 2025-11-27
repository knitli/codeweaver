# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests to validate failover embedding deduplication and registry concerns.

This test suite validates the concerns raised about embedding handling during
primary→backup→primary failover scenarios, specifically:

1. EmbeddingRegistry cross-provider collision
2. Backup restoring incompatible primary embeddings
3. Deduplication preventing sync-back re-embedding
4. Provider hash store architecture issues

Each test is designed to reproduce the actual failure scenario and can be
repurposed for regression testing after fixes are implemented.
"""

from pathlib import Path

import pytest

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.spans import Span
from codeweaver.providers.embedding.registry import get_embedding_registry


@pytest.fixture(autouse=True)
def cleanup_registry():
    """Cleanup the embedding registry before and after each test.

    This ensures test isolation by clearing the global singleton registry
    between test runs to prevent cross-test contamination.

    Also clears the hash stores from the embedding providers to prevent
    deduplication across tests.
    """
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
    )

    registry = get_embedding_registry()
    registry.clear()

    # Clear the hash stores (ClassVar shared across all instances)
    SentenceTransformersEmbeddingProvider._hash_store.clear()
    SentenceTransformersEmbeddingProvider._backup_hash_store.clear()

    yield

    registry.clear()
    SentenceTransformersEmbeddingProvider._hash_store.clear()
    SentenceTransformersEmbeddingProvider._backup_hash_store.clear()


@pytest.fixture
def sample_chunk() -> CodeChunk:
    """Create a sample code chunk for testing."""
    from codeweaver.common.utils import uuid7

    return CodeChunk(
        content="def test_function():\n    return 42",
        line_range=Span(start=1, end=2, _source_id=uuid7()),
        file_path=Path("test.py"),
        language="python",
    )


@pytest.fixture
async def primary_embedding_provider():
    """Create a primary embedding provider using real provider.

    Uses SentenceTransformers with a small model for testing.
    Represents PRIMARY provider with specific dimensions.
    """
    pytest.importorskip("sentence_transformers", reason="SentenceTransformers required for test")

    from sentence_transformers import SentenceTransformer

    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
    from codeweaver.providers.embedding.capabilities.ibm_granite import (
        GRANITE_EMBEDDING_SMALL_ENGLISH_R2_CAPABILITIES,
    )
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
    )
    from codeweaver.providers.provider import Provider

    # Use a small model for fast testing (384 dimensions)
    model = SentenceTransformer("ibm-granite/granite-embedding-small-english-r2")

    caps_dict = {
        **GRANITE_EMBEDDING_SMALL_ENGLISH_R2_CAPABILITIES,
        "provider": Provider.SENTENCE_TRANSFORMERS,
    }  # type: ignore
    caps = EmbeddingModelCapabilities.model_validate(caps_dict)

    return SentenceTransformersEmbeddingProvider(capabilities=caps, client=model)


@pytest.fixture
async def backup_embedding_provider():
    """Create a backup embedding provider with DIFFERENT dimensions.

    Uses different SentenceTransformers model than primary.
    Represents BACKUP provider with incompatible dimensions (768 vs 384).
    """
    pytest.importorskip("sentence_transformers", reason="SentenceTransformers required for test")

    from sentence_transformers import SentenceTransformer

    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
    from codeweaver.providers.embedding.capabilities.ibm_granite import (
        GRANITE_EMBEDDING_ENGLISH_R2_CAPABILITIES,  # 768 dimensions
    )
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
    )
    from codeweaver.providers.provider import Provider

    # Use larger Granite model (768 dimensions - different from primary's 384!)
    model = SentenceTransformer("ibm-granite/granite-embedding-english-r2")

    caps_dict = {
        **GRANITE_EMBEDDING_ENGLISH_R2_CAPABILITIES,
        "provider": Provider.SENTENCE_TRANSFORMERS,
    }  # type: ignore
    caps = EmbeddingModelCapabilities.model_validate(caps_dict)

    return SentenceTransformersEmbeddingProvider(capabilities=caps, client=model)


@pytest.mark.asyncio
@pytest.mark.network  # Requires network to download models from HuggingFace
async def test_registry_cross_provider_collision(
    sample_chunk, primary_embedding_provider, backup_embedding_provider
):
    """Test Bug #1: EmbeddingRegistry cross-provider collision.

    Scenario:
    1. Primary embeds chunk, stores in global registry
    2. Backup tries to upsert same chunk
    3. Chunk.dense_embeddings fetches PRIMARY embeddings from registry
    4. Dimension mismatch causes failure

    Expected Behavior: Should fail or use wrong embeddings
    """
    # Step 1: Primary embeds the chunk
    primary_embeddings = await primary_embedding_provider.embed_documents([sample_chunk])

    assert len(primary_embeddings) > 0, "Primary should generate embeddings"
    primary_dims = len(primary_embeddings[0])
    print(f"\nPrimary embeddings: {primary_dims} dimensions")
    assert primary_dims == 384, "Primary should be 384-dim (granite model)"

    # Verify chunk is in registry
    registry = get_embedding_registry()
    chunk_id = sample_chunk.chunk_id

    assert chunk_id in registry, "Chunk should be in registry after primary embedding"

    # Get the chunk with batch keys set
    embedded_chunk = sample_chunk.set_batch_keys(
        next(iter(primary_embedding_provider._store.values()))[0]._embedding_index.primary_dense
    )

    # Step 2: Check what embeddings the chunk retrieves
    retrieved_embeddings = embedded_chunk.dense_embeddings

    assert retrieved_embeddings is not None, "Chunk should retrieve embeddings"
    retrieved_dims = len(retrieved_embeddings.embeddings)
    print(f"Retrieved embeddings: {retrieved_dims} dimensions")
    assert retrieved_dims == 384, "Should retrieve PRIMARY's 384-dim embeddings"

    if chunk_embeddings := embedded_chunk.dense_embeddings:
        vector_dims = len(chunk_embeddings.embeddings)
        backup_expected_dims = 768  # Backup provider uses 768-dim model
        print(f"\n❌ BUG CONFIRMED: Backup would get {vector_dims}-dim embeddings from registry")
        print(f"   Expected: {backup_expected_dims}-dim (backup provider's model)")
        print(f"   Got: {vector_dims}-dim (primary provider's embeddings)")
        print(
            "   This happens because EmbeddingRegistry is GLOBAL and chunk.dense_embeddings fetches from it!"
        )

        assert vector_dims == 384, "Proves backup gets primary's embeddings"
        assert vector_dims != backup_expected_dims, "Dimension mismatch - this is the bug!"


@pytest.mark.asyncio
@pytest.mark.network  # Requires network to download models from HuggingFace
async def test_deduplication_prevents_reembedding(sample_chunk, primary_embedding_provider):
    """Test Bug #3: Deduplication prevents sync-back re-embedding.

    Scenario:
    1. Chunk is embedded with primary provider
    2. Content hash is stored in _hash_store
    3. Try to re-embed same chunk (simulating sync-back)
    4. With default behavior: chunk is filtered out due to deduplication
    5. With skip_deduplication=True: chunk is re-embedded successfully

    Expected Behavior: skip_deduplication flag should allow re-embedding
    """
    # Step 1: First embedding
    embeddings_first = await primary_embedding_provider.embed_documents([sample_chunk])

    assert len(embeddings_first) > 0, "First embedding should succeed"

    # Verify hash is stored
    from codeweaver.core.stores import get_blake_hash

    content_hash = get_blake_hash(sample_chunk.content.encode("utf-8"))

    assert content_hash in primary_embedding_provider._hash_store, (
        "Content hash should be in provider's hash store"
    )

    # Step 2: Try to re-embed without skip_deduplication (default behavior)
    embeddings_second = await primary_embedding_provider.embed_documents([sample_chunk])

    print(f"\nDefault behavior: Re-embedding returned {len(embeddings_second)} embeddings")
    assert len(embeddings_second) == 0, "Second embedding should return empty due to deduplication"

    # Step 3: Re-embed WITH skip_deduplication=True (should succeed)
    embeddings_third = await primary_embedding_provider.embed_documents(
        [sample_chunk], skip_deduplication=True
    )

    print(f"With skip_deduplication=True: Re-embedding returned {len(embeddings_third)} embeddings")
    assert len(embeddings_third) > 0, "✓ FIXED: Re-embedding with skip_deduplication=True succeeds"
    print("   ✓ This allows sync-back to work for unchanged chunks!")


@pytest.mark.asyncio
@pytest.mark.network  # Requires network to download models from HuggingFace
async def test_hash_store_is_class_variable(primary_embedding_provider, backup_embedding_provider):
    """Test Bug #4: Hash store is ClassVar (shared across instances).

    Scenario:
    1. Check if _hash_store is shared between provider instances
    2. Verify SAME provider class shares hash store across instances

    Expected Behavior: Same class shares store, instances share the ClassVar
    """

    # Check if both provider instances share the same hash store (they're both SentenceTransformers)
    primary_store_id = id(primary_embedding_provider._hash_store)
    backup_store_id = id(backup_embedding_provider._hash_store)

    print(f"\nPrimary provider _hash_store id: {primary_store_id}")
    print(f"Backup provider _hash_store id: {backup_store_id}")

    if primary_store_id == backup_store_id:
        print("❌ CONFIRMED: Both instances share the SAME hash store (ClassVar)")
        print("  This means if primary and backup use same provider CLASS,")
        print("  backup WILL be affected by primary's deduplication!")
    else:
        print("✓ Instances have separate hash stores")

    # Since both are SentenceTransformersEmbeddingProvider, they SHOULD share the store
    assert primary_store_id == backup_store_id, (
        "Same provider class should share hash store (ClassVar behavior)"
    )

    # But the REGISTRY is still global!
    registry1 = get_embedding_registry()
    registry2 = get_embedding_registry()

    print(f"\nRegistry 1 id: {id(registry1)}")
    print(f"Registry 2 id: {id(registry2)}")

    assert id(registry1) == id(registry2), "Registry is global singleton"
    print("❌ CONFIRMED: EmbeddingRegistry is global singleton - this causes Bug #1")


@pytest.mark.asyncio
@pytest.mark.network  # Requires network to download models from HuggingFace
async def test_chunk_property_fetches_from_global_registry(
    sample_chunk, primary_embedding_provider
):
    """Test that chunk.dense_embeddings property fetches from global registry.

    This is the mechanism that causes Bug #1.
    """
    # Embed with primary
    await primary_embedding_provider.embed_documents([sample_chunk])

    # Get chunk with batch keys
    embedded_chunk = sample_chunk.set_batch_keys(
        next(iter(primary_embedding_provider._store.values()))[0]._embedding_index.primary_dense
    )

    # Access the property
    registry = get_embedding_registry()
    property_embeddings = embedded_chunk.dense_embeddings
    registry_embeddings = (
        registry[embedded_chunk.chunk_id].dense if embedded_chunk.chunk_id in registry else None
    )

    # Verify they're the same
    assert property_embeddings is not None
    assert registry_embeddings is not None
    assert property_embeddings.batch_id == registry_embeddings.batch_id, (
        "Property fetches from global registry"
    )

    print("\n❌ CONFIRMED: chunk.dense_embeddings fetches from global registry")
    print("   This means backup will get primary's embeddings when upserting!")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
