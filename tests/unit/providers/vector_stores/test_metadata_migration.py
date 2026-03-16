# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for CollectionMetadata migration from v1.2.x to v1.3.0.

Tests the migration path for asymmetric model families feature (Milestone 3, Task #4).

Migration Scenarios:
    1. Loading v1.2.x metadata (missing dense_model_family, query_model)
    2. Round-trip serialization (load → modify → save)
    3. Backward compatibility (v1.2.x collections work with v1.3.0 code)
    4. Forward compatibility (v1.3.0 metadata degrades gracefully)
"""

from datetime import UTC, datetime

import pytest

from codeweaver.providers.types.vector_store import CollectionMetadata


@pytest.mark.external_api
@pytest.mark.qdrant
@pytest.mark.unit
class TestMetadataMigration:
    """Test migration from v1.2.x to v1.3.0."""

    def test_load_v1_2_x_metadata_missing_family_fields(self):
        """
        User Story: Load v1.2.x metadata without family fields.

        Given: Metadata dict from v1.2.x collection (no dense_model_family, query_model)
        When: Loading with v1.3.0 CollectionMetadata
        Then: Fields default to None, no errors raised
        """
        # Simulate v1.2.x metadata dict (missing new fields)
        v1_2_metadata = {
            "provider": "qdrant",
            "created_at": datetime.now(UTC).isoformat(),
            "project_name": "test-project",
            "dense_model": "voyage-code-3",
            "sparse_model": None,
            "backup_enabled": False,
            "backup_model": None,
            "collection_name": "test_collection",
            "version": "1.2.0",
            # NOTE: dense_model_family and query_model are absent (v1.2.x schema)
        }

        # Load with v1.3.0 schema
        metadata = CollectionMetadata.model_validate(v1_2_metadata)

        # Verify migration defaults
        assert metadata.dense_model_family is None, "Should default to None for v1.2.x"
        assert metadata.query_model is None, "Should default to None for v1.2.x"
        assert metadata.version == "1.2.0", "Should preserve original version"

        # Verify existing fields preserved
        assert metadata.provider == "qdrant"
        assert metadata.project_name == "test-project"
        assert metadata.dense_model == "voyage-code-3"

    def test_round_trip_serialization_v1_2_x(self):
        """
        User Story: Load v1.2.x metadata, modify, and save.

        Given: v1.2.x metadata loaded into v1.3.0 model
        When: Modifying and serializing back
        Then: Round-trip succeeds, new fields remain None
        """
        v1_2_metadata = {
            "provider": "qdrant",
            "created_at": datetime.now(UTC).isoformat(),
            "project_name": "test-project",
            "dense_model": "voyage-code-3",
            "sparse_model": None,
            "backup_enabled": False,
            "backup_model": None,
            "collection_name": "test_collection",
            "version": "1.2.0",
        }

        # Load
        metadata = CollectionMetadata.model_validate(v1_2_metadata)

        # Serialize
        serialized = metadata.model_dump(mode="json", exclude_none=True)

        # Verify family fields not serialized (they're None)
        assert "dense_model_family" not in serialized
        assert "query_model" not in serialized

        # Reload from serialized
        reloaded = CollectionMetadata.model_validate(serialized)

        assert reloaded.dense_model == metadata.dense_model
        assert reloaded.dense_model_family is None
        assert reloaded.query_model is None

    def test_create_v1_3_0_metadata_with_family(self):
        """
        User Story: Create new v1.3.0 metadata with family support.

        Given: New collection with asymmetric embedding
        When: Creating metadata with dense_model_family and query_model
        Then: Fields are set correctly
        """
        metadata = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="test-project",
            dense_model="voyage-4-large",
            dense_model_family="voyage-4",  # NEW in v1.3.0
            query_model="voyage-4-nano",  # NEW in v1.3.0
            sparse_model=None,
            backup_enabled=False,
            backup_model=None,
            collection_name="test_collection",
            version="1.3.0",
        )

        assert metadata.dense_model == "voyage-4-large"
        assert metadata.dense_model_family == "voyage-4"
        assert metadata.query_model == "voyage-4-nano"
        assert metadata.version == "1.3.0"

    def test_v1_3_0_serialization_with_family(self):
        """
        User Story: Serialize v1.3.0 metadata with family fields.

        Given: Metadata with dense_model_family and query_model
        When: Serializing to dict
        Then: Family fields are included
        """
        metadata = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="test-project",
            dense_model="voyage-4-large",
            dense_model_family="voyage-4",
            query_model="voyage-4-nano",
            collection_name="test_collection",
            version="1.3.0",
        )

        serialized = metadata.model_dump(mode="json")

        assert serialized["dense_model_family"] == "voyage-4"
        assert serialized["query_model"] == "voyage-4-nano"
        assert serialized["version"] == "1.3.0"

    def test_backward_compatibility_validation(self):
        """
        User Story: v1.2.x collection validates against v1.3.0 code.

        Given: v1.2.x collection metadata (no family)
        When: Validating against compatible v1.3.0 metadata
        Then: Validation passes (backward compatible)
        """
        # Old v1.2.x collection
        v1_2_metadata = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="test-project",
            dense_model="voyage-code-3",
            collection_name="test_collection",
            version="1.2.0",
            # No family fields
        )

        # New v1.3.0 code using same model (symmetric mode)
        v1_3_metadata = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="test-project",
            dense_model="voyage-code-3",
            collection_name="test_collection",
            version="1.3.0",
            # Family fields default to None (symmetric mode)
        )

        # Should not raise
        v1_3_metadata.validate_compatibility(v1_2_metadata)

    def test_from_collection_dict_v1_2_x(self):
        """
        User Story: Load metadata from collection dict (v1.2.x format).

        Given: Collection dict in v1.2.x format
        When: Using from_collection() classmethod
        Then: Metadata loads with defaults for new fields
        """
        collection_dict = {
            "metadata": {
                "provider": "qdrant",
                "created_at": datetime.now(UTC).isoformat(),
                "project_name": "test-project",
                "dense_model": "voyage-code-3",
                "version": "1.2.0",
            }
        }

        metadata = CollectionMetadata.from_collection(collection_dict)

        assert metadata.dense_model == "voyage-code-3"
        assert metadata.dense_model_family is None
        assert metadata.query_model is None

    def test_to_collection_dict_excludes_none(self):
        """
        User Story: Serialize metadata for collection creation.

        Given: v1.2.x metadata (family fields are None)
        When: Using to_collection()
        Then: None fields excluded from dict
        """
        metadata = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="test-project",
            dense_model="voyage-code-3",
            collection_name="test_collection",
            version="1.2.0",
        )

        collection_dict = metadata.to_collection()

        # None fields should be excluded
        assert "dense_model_family" not in collection_dict
        assert "query_model" not in collection_dict

    def test_explicit_none_vs_missing_fields(self):
        """
        Edge Case: Explicit None vs missing fields behave identically.

        Given: Two metadata instances (one with explicit None, one missing fields)
        When: Comparing serialization
        Then: Both serialize identically
        """
        # Explicit None
        metadata_explicit = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="test-project",
            dense_model="voyage-code-3",
            dense_model_family=None,  # Explicit
            query_model=None,  # Explicit
            collection_name="test_collection",
            version="1.2.0",
        )

        # Fields omitted (pydantic defaults)
        metadata_implicit = CollectionMetadata.model_validate({
            "provider": "qdrant",
            "created_at": datetime.now(UTC).isoformat(),
            "project_name": "test-project",
            "dense_model": "voyage-code-3",
            "collection_name": "test_collection",
            "version": "1.2.0",
        })

        # Both should serialize identically (exclude_none=True)
        explicit_dict = metadata_explicit.model_dump(mode="json", exclude_none=True)
        implicit_dict = metadata_implicit.model_dump(mode="json", exclude_none=True)

        # Normalize created_at for comparison (may differ slightly)
        explicit_dict.pop("created_at")
        implicit_dict.pop("created_at")

        assert explicit_dict == implicit_dict


@pytest.mark.external_api
@pytest.mark.qdrant
@pytest.mark.unit
class TestMetadataVersioning:
    """Test version field behavior across schema versions."""

    def test_default_version_is_v1_5_0(self):
        """New metadata defaults to current schema version."""
        metadata = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="test-project",
            dense_model="voyage-code-3",
            collection_name="test_collection",
        )

        assert metadata.version == "1.5.0"

    def test_preserve_v1_2_0_version_on_load(self):
        """Loading v1.2.0 metadata preserves original version."""
        v1_2_metadata = {
            "provider": "qdrant",
            "created_at": datetime.now(UTC).isoformat(),
            "project_name": "test-project",
            "dense_model": "voyage-code-3",
            "collection_name": "test_collection",
            "version": "1.2.0",
        }

        metadata = CollectionMetadata.model_validate(v1_2_metadata)

        assert metadata.version == "1.2.0"

    def test_explicit_version_override(self):
        """Can explicitly set version field."""
        metadata = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="test-project",
            dense_model="voyage-code-3",
            collection_name="test_collection",
            version="1.2.5",  # Custom version
        )

        assert metadata.version == "1.2.5"


@pytest.mark.external_api
@pytest.mark.qdrant
@pytest.mark.unit
class TestAsymmetricEmbeddingFields:
    """Test behavior of new asymmetric embedding fields."""

    def test_symmetric_mode_query_model_none(self):
        """Symmetric mode: query_model is None (uses dense_model)."""
        metadata = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="test-project",
            dense_model="voyage-code-3",
            collection_name="test_collection",
        )

        assert metadata.query_model is None
        assert metadata.dense_model == "voyage-code-3"

    def test_asymmetric_mode_query_model_set(self):
        """Asymmetric mode: query_model differs from dense_model."""
        metadata = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="test-project",
            dense_model="voyage-4-large",
            dense_model_family="voyage-4",
            query_model="voyage-4-nano",
            collection_name="test_collection",
        )

        assert metadata.dense_model == "voyage-4-large"
        assert metadata.query_model == "voyage-4-nano"
        assert metadata.dense_model_family == "voyage-4"

    def test_family_without_query_model(self):
        """Can have family without asymmetric query model."""
        metadata = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="test-project",
            dense_model="voyage-4-large",
            dense_model_family="voyage-4",
            query_model=None,  # Symmetric mode within family
            collection_name="test_collection",
        )

        assert metadata.dense_model_family == "voyage-4"
        assert metadata.query_model is None


@pytest.mark.integration
@pytest.mark.external_api
@pytest.mark.qdrant
@pytest.mark.unit
class TestMetadataMigrationIntegration:
    """Integration tests for metadata migration scenarios."""

    def test_end_to_end_migration_workflow(self):
        """
        End-to-End: Full migration workflow from v1.2.x to v1.3.0.

        Simulates:
        1. User has existing v1.2.x collection
        2. Upgrades codebase to v1.3.0
        3. Loads existing metadata
        4. Adds new collection with asymmetric embedding
        5. Both collections work side-by-side
        """
        # Step 1: Existing v1.2.x collection
        v1_2_metadata_dict = {
            "provider": "qdrant",
            "created_at": datetime.now(UTC).isoformat(),
            "project_name": "legacy-project",
            "dense_model": "voyage-code-3",
            "collection_name": "legacy_collection",
            "version": "1.2.0",
        }

        # Step 2: Load with v1.3.0 code
        legacy_metadata = CollectionMetadata.model_validate(v1_2_metadata_dict)

        assert legacy_metadata.dense_model_family is None
        assert legacy_metadata.query_model is None

        # Step 3: Create new v1.3.0 collection with asymmetric embedding
        new_metadata = CollectionMetadata(
            provider="qdrant",
            created_at=datetime.now(UTC),
            project_name="new-project",
            dense_model="voyage-4-large",
            dense_model_family="voyage-4",
            query_model="voyage-4-nano",
            collection_name="new_collection",
            version="1.3.0",
        )

        # Step 4: Verify both work independently
        assert legacy_metadata.version == "1.2.0"
        assert new_metadata.version == "1.3.0"

        # Step 5: Validate each against themselves (should pass)
        legacy_metadata.validate_compatibility(legacy_metadata)
        new_metadata.validate_compatibility(new_metadata)
