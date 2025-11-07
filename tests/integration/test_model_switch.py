# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test: Model switch detection and provider switch warnings.

Validates that:
1. Switching embedding models raises ModelSwitchError (prevents search corruption)
2. Switching providers logs warning (suggests reindex but doesn't block)
"""

from datetime import UTC, datetime

import pytest

from codeweaver.exceptions import ModelSwitchError
from codeweaver.providers.vector_stores.metadata import CollectionMetadata


pytestmark = [pytest.mark.integration]


def test_model_switch_detection():
    """
    User Story: Prevent using different embedding models with same collection.

    Given: Collection created with voyage-code-3 model
    When: User switches to text-embedding-ada-002 model
    Then: System raises ModelSwitchError with clear remediation steps
    """
    metadata_original = CollectionMetadata(
        provider="qdrant",
        project_name="test-project",
        embedding_model="voyage-code-3",
        embedding_dim_dense=1536,
        vector_config={},
        created_at=datetime.now(UTC),
    )

    metadata_switched = CollectionMetadata(
        provider="qdrant",  # Same provider is OK
        project_name="test-project",
        embedding_model="text-embedding-ada-002",  # Different model is NOT OK
        embedding_dim_dense=1536,
        vector_config={},
        created_at=datetime.now(UTC),
    )

    # Should raise ModelSwitchError
    with pytest.raises(ModelSwitchError) as exc_info:
        metadata_switched.validate_compatibility(metadata_original)

    error = exc_info.value
    error_msg = str(error).lower()

    # Verify error message contains key information
    assert "voyage-code-3" in error_msg
    assert "text-embedding-ada-002" in error_msg

    # Verify error includes suggestions with reindex guidance
    assert error.suggestions
    assert len(error.suggestions) >= 3
    suggestions_text = " ".join(error.suggestions).lower()
    assert "re-index" in suggestions_text or "reindex" in suggestions_text

    # Verify error includes details
    assert error.details
    assert error.details["collection_model"] == "voyage-code-3"
    assert error.details["current_model"] == "text-embedding-ada-002"

    print("✅ Model switch detected with clear error message and remediation steps")


def test_provider_switch_warning(caplog):
    """
    User Story: Warn when switching providers to suggest reindexing.

    Given: Collection created with Qdrant provider
    When: User switches to different provider with same model
    Then: System logs warning suggesting reindex but continues
    """
    import logging

    caplog.set_level(logging.WARNING)

    metadata_original = CollectionMetadata(
        provider="qdrant",
        project_name="test-project",
        embedding_model="voyage-code-3",
        embedding_dim_dense=1536,
        vector_config={},
        created_at=datetime.now(UTC),
    )

    metadata_switched = CollectionMetadata(
        provider="pinecone",  # Different provider
        project_name="test-project",
        embedding_model="voyage-code-3",  # Same model is OK
        embedding_dim_dense=1536,
        vector_config={},
        created_at=datetime.now(UTC),
    )

    # Should NOT raise error, just log warning
    metadata_switched.validate_compatibility(metadata_original)

    # Verify warning was logged
    assert len(caplog.records) > 0
    warning_msg = caplog.records[0].message.lower()

    assert "provider switch detected" in warning_msg or "provider" in warning_msg
    assert "qdrant" in warning_msg
    assert "pinecone" in warning_msg
    assert "reindex" in warning_msg

    print("✅ Provider switch logged warning suggesting reindex")


def test_dimension_mismatch_detection():
    """
    User Story: Prevent dimension mismatches that corrupt vector search.

    Given: Collection with 1536-dimensional embeddings
    When: User tries to use 768-dimensional embeddings
    Then: System raises DimensionMismatchError
    """
    from codeweaver.exceptions import DimensionMismatchError

    metadata_original = CollectionMetadata(
        provider="qdrant",
        project_name="test-project",
        embedding_model="voyage-code-3",
        embedding_dim_dense=1536,
        vector_config={},
        created_at=datetime.now(UTC),
    )

    metadata_switched = CollectionMetadata(
        provider="qdrant",
        project_name="test-project",
        embedding_model="voyage-code-3",  # Same model
        embedding_dim_dense=768,  # Different dimension - NOT OK
        vector_config={},
        created_at=datetime.now(UTC),
    )

    with pytest.raises(DimensionMismatchError) as exc_info:
        metadata_switched.validate_compatibility(metadata_original)

    error_msg = str(exc_info.value).lower()
    assert "1536" in error_msg
    assert "768" in error_msg
    assert "dimension" in error_msg

    print("✅ Dimension mismatch detected with clear error")


def test_compatible_metadata_no_error():
    """
    User Story: Allow compatible configurations.

    Given: Collection with specific metadata
    When: User uses same provider, model, and dimensions
    Then: No errors or warnings
    """
    metadata_original = CollectionMetadata(
        provider="qdrant",
        project_name="test-project",
        embedding_model="voyage-code-3",
        embedding_dim_dense=1536,
        vector_config={},
        created_at=datetime.now(UTC),
    )

    metadata_same = CollectionMetadata(
        provider="qdrant",
        project_name="test-project",
        embedding_model="voyage-code-3",
        embedding_dim_dense=1536,
        vector_config={},
        created_at=datetime.now(UTC),
    )

    # Should complete without error
    metadata_same.validate_compatibility(metadata_original)

    print("✅ Compatible metadata validation passed")


def test_model_switch_with_none_embedding():
    """
    Edge Case: Metadata with None embedding_model should not raise.

    Given: Old metadata without embedding_model field
    When: Validating against new metadata
    Then: No model switch error (backwards compatibility)
    """
    metadata_old = CollectionMetadata(
        provider="qdrant",
        project_name="test-project",
        embedding_model=None,  # Old collection without model tracking
        embedding_dim_dense=1536,
        vector_config={},
        created_at=datetime.now(UTC),
    )

    metadata_new = CollectionMetadata(
        provider="qdrant",
        project_name="test-project",
        embedding_model="voyage-code-3",  # New has model
        embedding_dim_dense=1536,
        vector_config={},
        created_at=datetime.now(UTC),
    )

    # Should not raise since old model is None
    metadata_new.validate_compatibility(metadata_old)

    print("✅ Backwards compatibility with None embedding_model")
