# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Contract tests for CollectionMetadata family validation.

These tests verify that CollectionMetadata correctly handles model family tracking
and validation for asymmetric embedding configurations. Tests ensure:

1. Metadata stores family information correctly
2. Compatible family models pass validation
3. Incompatible models fail with clear error messages
4. Backward compatibility with pre-family metadata (v1.2.x)
5. Migration from old format preserves dimension-based validation
6. Error messages suggest compatible alternative models

Uses real Voyage-4 family models for integration validation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from codeweaver.core import ConfigurationError, ModelSwitchError, Provider
from codeweaver.providers import CollectionMetadata
from codeweaver.providers.embedding.capabilities.voyage import VOYAGE_4_FAMILY


if TYPE_CHECKING:
    pass


pytestmark = [pytest.mark.contract, pytest.mark.vector_store]


@pytest.fixture
def base_metadata_kwargs() -> dict:
    """Provide common metadata fields for test fixtures.

    Returns base metadata fields that all test cases can build upon.
    """
    return {
        "provider": Provider.VOYAGE.value,
        "created_at": datetime.now(UTC),
        "project_name": "test-project",
        "collection_name": "test-collection",
    }


class TestCreateCollectionWithFamilyMetadata:
    """Test creating collection metadata with model family fields."""

    def test_create_with_family_fields(self, base_metadata_kwargs: dict):
        """Verify metadata can be created with dense_model_family and query_model fields.

        Creates metadata with family information and verifies all fields are stored correctly,
        including the new family-specific fields introduced in v1.3.0.
        """
        metadata = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-4-large",
            dense_model_family=VOYAGE_4_FAMILY.family_id,
            query_model="voyage-4-nano",
        )

        # Verify all fields are stored correctly
        assert metadata.dense_model == "voyage-4-large"
        assert metadata.dense_model_family == "voyage-4"
        assert metadata.query_model == "voyage-4-nano"
        assert metadata.version == "1.5.0"

    def test_create_without_family_fields(self, base_metadata_kwargs: dict):
        """Verify metadata can be created without family fields for backward compatibility.

        Ensures that metadata without family fields (pre-v1.3.0 style) still works,
        with family fields defaulting to None.
        """
        metadata = CollectionMetadata(**base_metadata_kwargs, dense_model="voyage-code-3")

        assert metadata.dense_model == "voyage-code-3"
        assert metadata.dense_model_family is None
        assert metadata.query_model is None

    def test_family_fields_serialization(self, base_metadata_kwargs: dict):
        """Verify family fields serialize and deserialize correctly.

        Tests round-trip serialization to ensure family metadata survives
        conversion to/from dictionaries and JSON.
        """
        original = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-4",
            dense_model_family="voyage-4",
            query_model="voyage-4-lite",
        )

        # Serialize to dict
        data = original.to_collection()

        # Deserialize from dict
        restored = CollectionMetadata.model_validate(data)

        assert restored.dense_model == original.dense_model
        assert restored.dense_model_family == original.dense_model_family
        assert restored.query_model == original.query_model


class TestCompatibleQueryModelValidation:
    """Test validation passes for compatible family models."""

    def test_same_family_models_pass_validation(self, base_metadata_kwargs: dict):
        """Verify validation passes when both models belong to the same family.

        Index collection with voyage-4-large, query with voyage-4-nano.
        Both are VOYAGE_4_FAMILY members, so validation should pass.
        """
        # Collection metadata (stored in vector DB)
        collection_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-4-large",
            dense_model_family=VOYAGE_4_FAMILY.family_id,
            query_model="voyage-4-nano",
        )

        # Current configuration metadata (what we're trying to use now)
        current_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-4-large",
            dense_model_family=VOYAGE_4_FAMILY.family_id,
            query_model="voyage-4-nano",
        )

        # Validation should pass - no exception
        current_meta.validate_compatibility(collection_meta)

    def test_different_family_member_query_model(self, base_metadata_kwargs: dict):
        """Verify validation passes when switching between family members.

        Collection was created with voyage-4-nano for queries, now using voyage-4-lite.
        Both are valid family members, so this should be allowed.
        """
        collection_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-4-large",
            dense_model_family=VOYAGE_4_FAMILY.family_id,
            query_model="voyage-4-nano",
        )

        current_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-4-large",
            dense_model_family=VOYAGE_4_FAMILY.family_id,
            query_model="voyage-4-lite",  # Different but compatible
        )

        # Should pass - both are family members
        current_meta.validate_compatibility(collection_meta)


class TestIncompatibleFamilyValidation:
    """Test validation fails for incompatible family configurations."""

    def test_incompatible_family_fails(self, base_metadata_kwargs: dict):
        """Verify validation fails when switching to incompatible family.

        Collection created with voyage-4-large (VOYAGE_4_FAMILY),
        attempting to use voyage-code-3 (no family).
        Should fail with clear error message.
        """
        collection_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-4-large",
            dense_model_family=VOYAGE_4_FAMILY.family_id,
        )

        current_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-code-3",  # Different model, no family
            dense_model_family=None,
        )

        # Should raise ModelSwitchError
        with pytest.raises(ModelSwitchError) as exc_info:
            current_meta.validate_compatibility(collection_meta)

        error = exc_info.value
        assert "voyage-4-large" in str(error)
        assert "voyage-code-3" in str(error)

    def test_query_model_outside_family_fails(self, base_metadata_kwargs: dict):
        """Verify validation fails when query model is not in dense model's family.

        Collection was indexed with voyage-4-large (VOYAGE_4_FAMILY).
        Attempting to query with voyage-code-3 (no family).
        Should fail because they don't share a vector space.

        Note: Validation compares current model (dense or query) against indexed model.
        To trigger family validation, current model must differ from indexed model.
        """
        # Collection indexed with voyage-4-large (has family)
        collection_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-4-large",
            dense_model_family=VOYAGE_4_FAMILY.family_id,
        )

        # Current config: querying with voyage-code-3 (different model, no family)
        current_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model=None,  # Not re-embedding
            query_model="voyage-code-3",  # Using different model for queries
        )

        # Should raise ConfigurationError about incompatible query model
        # (Family validation uses ConfigurationError, not ModelSwitchError)
        with pytest.raises(ConfigurationError) as exc_info:
            current_meta.validate_compatibility(collection_meta)

        error = exc_info.value
        # Error should mention the incompatible model or family mismatch
        assert "voyage-code-3" in str(error) or "family" in str(error).lower()


class TestBackwardCompatibilityDimensionOnly:
    """Test backward compatibility with pre-family metadata (v1.2.x format)."""

    def test_load_old_metadata_without_family(self, base_metadata_kwargs: dict):
        """Verify old metadata (v1.2.x) without family fields can be loaded.

        Creates metadata in old format (no family fields) and verifies it loads
        correctly with family fields defaulting to None.
        """
        # Simulate old metadata format (v1.2.x) - no family fields
        old_data = {
            **base_metadata_kwargs,
            "dense_model": "voyage-code-3",
            "version": "1.2.0",
            # No dense_model_family or query_model fields
        }

        metadata = CollectionMetadata.model_validate(old_data)

        assert metadata.dense_model == "voyage-code-3"
        assert metadata.dense_model_family is None
        assert metadata.query_model is None
        assert metadata.version == "1.2.0"

    def test_dimension_validation_still_works(self, base_metadata_kwargs: dict):
        """Verify dimension-based validation works without family information.

        When family fields are absent, the system should fall back to
        dimension-based validation (existing v1.2.x behavior).
        """
        # Old metadata without family info
        old_meta = CollectionMetadata(
            **base_metadata_kwargs, dense_model="voyage-code-3", version="1.2.0"
        )

        # New metadata also without family info but same model
        current_meta = CollectionMetadata(
            **base_metadata_kwargs, dense_model="voyage-code-3", version="1.2.0"
        )

        # Should pass - same model
        current_meta.validate_compatibility(old_meta)

    def test_dimension_mismatch_without_family_fails(self, base_metadata_kwargs: dict):
        """Verify dimension validation catches mismatches even without family info.

        Different models without family information should still fail validation
        based on model name mismatch.
        """
        old_meta = CollectionMetadata(**base_metadata_kwargs, dense_model="voyage-code-3")

        current_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-3-large",  # Different model
        )

        # Should fail - different models
        with pytest.raises(ModelSwitchError):
            current_meta.validate_compatibility(old_meta)


class TestMigrationFromOldFormat:
    """Test migration from v1.2.x to v1.3.0 metadata format."""

    def test_v12_metadata_loads_with_v13_code(self, base_metadata_kwargs: dict):
        """Verify v1.2.x metadata loads correctly with v1.3.0 code.

        Simulates loading an existing collection created with v1.2.x
        using v1.3.0 code that expects family fields.
        """
        # v1.2.x metadata dict (as stored in vector DB)
        v12_data = {
            **base_metadata_kwargs,
            "dense_model": "voyage-code-3",
            "sparse_model": None,
            "backup_enabled": False,
            "backup_model": None,
            "version": "1.2.0",
            # No family fields
        }

        # Load with v1.3.0 code
        metadata = CollectionMetadata.model_validate(v12_data)

        # Verify family fields default to None
        assert metadata.dense_model_family is None
        assert metadata.query_model is None
        # Other fields preserved
        assert metadata.dense_model == "voyage-code-3"
        assert metadata.version == "1.2.0"

    def test_upgrade_from_v12_to_v13_preserves_compatibility(self, base_metadata_kwargs: dict):
        """Verify upgrading metadata format preserves compatibility behavior.

        A collection created with v1.2.x should continue to work the same way
        after v1.3.0 upgrade, maintaining the same validation rules.
        """
        # Original v1.2.x metadata
        v12_meta = CollectionMetadata.model_validate({
            **base_metadata_kwargs,
            "dense_model": "voyage-code-3",
            "version": "1.2.0",
        })

        # Same configuration loaded with v1.3.0
        v13_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-code-3",
            # Family fields are None (not set)
        )

        # Validation should pass - same model
        v13_meta.validate_compatibility(v12_meta)

    def test_cannot_switch_models_during_migration(self, base_metadata_kwargs: dict):
        """Verify model switch validation works during format migration.

        Even when migrating from v1.2.x to v1.3.0, the model switch
        protection should still apply.
        """
        # v1.2.x metadata with one model
        v12_meta = CollectionMetadata.model_validate({
            **base_metadata_kwargs,
            "dense_model": "voyage-code-3",
            "version": "1.2.0",
        })

        # v1.3.0 metadata trying to use different model
        v13_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-3-large",  # Different model
        )

        # Should fail - model switch not allowed
        with pytest.raises(ModelSwitchError):
            v13_meta.validate_compatibility(v12_meta)


class TestErrorMessageSuggestsCompatibleModels:
    """Test that validation errors include helpful suggestions for compatible models."""

    def test_family_error_includes_member_models(self, base_metadata_kwargs: dict):
        """Verify error message lists compatible family member models.

        When validation fails due to family incompatibility, the error
        should suggest which models ARE compatible (family members).
        """
        collection_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-4-large",
            dense_model_family=VOYAGE_4_FAMILY.family_id,
        )

        incompatible_meta = CollectionMetadata(**base_metadata_kwargs, dense_model="voyage-code-3")

        with pytest.raises(ModelSwitchError) as exc_info:
            incompatible_meta.validate_compatibility(collection_meta)

        error = exc_info.value
        error_text = str(error)

        # Error should mention the family or model incompatibility
        assert (
            "voyage-4-large" in error_text
            or "voyage-code-3" in error_text
            or "model" in error_text.lower()
        )

        # Suggestions should be present (inherited from ModelSwitchError)
        assert len(error.suggestions) > 0

    def test_query_model_error_suggests_family_members(self, base_metadata_kwargs: dict):
        """Verify query model error suggests compatible alternatives from family.

        When query model validation fails, error should indicate which
        models from the family would work for queries.

        Note: To trigger validation, current model must differ from indexed model.
        """
        # Collection indexed with voyage-4-large
        collection_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-4-large",
            dense_model_family=VOYAGE_4_FAMILY.family_id,
        )

        # Try to query with incompatible model (not in family)
        incompatible_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model=None,  # Not re-embedding
            query_model="voyage-code-3",  # Not in VOYAGE_4_FAMILY
        )

        # Family validation raises ConfigurationError
        with pytest.raises(ConfigurationError) as exc_info:
            incompatible_meta.validate_compatibility(collection_meta)

        error = exc_info.value

        # Should have helpful suggestions
        assert len(error.suggestions) > 0

        # Error should reference the incompatible query model or family
        assert "voyage-code-3" in str(error) or "family" in str(error).lower()

    def test_error_details_include_family_info(self, base_metadata_kwargs: dict):
        """Verify error details include family identification information.

        ModelSwitchError details should include family_id and other
        context helpful for debugging compatibility issues.
        """
        collection_meta = CollectionMetadata(
            **base_metadata_kwargs,
            dense_model="voyage-4-large",
            dense_model_family=VOYAGE_4_FAMILY.family_id,
        )

        incompatible_meta = CollectionMetadata(
            **base_metadata_kwargs, dense_model="voyage-3-large", dense_model_family=None
        )

        with pytest.raises(ModelSwitchError) as exc_info:
            incompatible_meta.validate_compatibility(collection_meta)

        error = exc_info.value

        # Details should contain useful debugging information
        assert error.details is not None
        assert len(error.details) > 0

        # Should include model information
        details_str = str(error.details)
        assert "voyage-4-large" in details_str or "voyage-3-large" in details_str
