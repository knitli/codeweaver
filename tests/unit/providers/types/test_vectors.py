# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for vector types (VectorRole, VectorConfig, VectorSet).

Tests the new vector types implementation according to the refactoring plan.
These types replace the deprecated VectorStrategy and EmbeddingStrategy.
"""

from __future__ import annotations

import pytest

from pydantic import ValidationError
from qdrant_client.models import Distance, SparseVectorParams, VectorParams

from codeweaver.core.types import EmbeddingKind, ModelName

# Phase 1 implementation complete - tests enabled!
from codeweaver.providers.types.vectors import VectorConfig, VectorRole, VectorSet


@pytest.mark.unit
class TestVectorRole:
    """Test VectorRole enum functionality.

    Tests the extensible enum that defines semantic roles for vectors.
    Validates that the enum uses BaseEnum with the .variable property.
    """

    def test_variable_property_primary(self):
        """Test .variable property returns correct string for PRIMARY."""
        assert VectorRole.PRIMARY.variable == "primary"

    def test_variable_property_backup(self):
        """Test .variable property returns correct string for BACKUP."""
        assert VectorRole.BACKUP.variable == "backup"

    def test_variable_property_sparse(self):
        """Test .variable property returns correct string for SPARSE."""
        assert VectorRole.SPARSE.variable == "sparse"

    def test_string_values_match_variable(self):
        """Test that enum values are lowercase strings matching variable property."""
        assert VectorRole.PRIMARY.value == "primary"
        assert VectorRole.BACKUP.value == "backup"
        assert VectorRole.SPARSE.value == "sparse"

    def test_enum_extensibility(self):
        """Test that VectorRole can be extended for future strategies.

        This test documents the extension pattern for future roles like:
        - SEMANTIC_CODE
        - SEMANTIC_DOCS
        - KEYWORD

        The enum should support dynamic extension using aenum.extend_enum.
        """
        # Future extensions should work via:
        # from aenum import extend_enum
        # extend_enum(VectorRole, "SEMANTIC_CODE", "semantic_code")
        #
        # This test verifies the base enum is extensible (BaseEnum)
        from codeweaver.core.types import BaseEnum

        assert isinstance(VectorRole.PRIMARY, BaseEnum)

    def test_role_comparison(self):
        """Test that roles can be compared by value."""
        assert VectorRole.PRIMARY == VectorRole.PRIMARY
        assert VectorRole.PRIMARY != VectorRole.BACKUP
        assert VectorRole.PRIMARY.variable != VectorRole.BACKUP.variable


@pytest.mark.unit
class TestVectorConfig:
    """Test VectorConfig model functionality.

    Tests the immutable configuration for a single named vector in Qdrant.
    Validates alignment with Qdrant's VectorParams and SparseVectorParams.
    """

    @pytest.fixture
    def dense_params(self) -> VectorParams:
        """Provide standard dense vector parameters."""
        return VectorParams(size=1024, distance=Distance.COSINE)

    @pytest.fixture
    def sparse_params(self) -> SparseVectorParams:
        """Provide standard sparse vector parameters."""
        return SparseVectorParams()

    @pytest.fixture
    def primary_dense_config(self, dense_params: VectorParams) -> VectorConfig:
        """Provide a standard primary dense vector configuration."""
        return VectorConfig(
            name="primary",
            model_name=ModelName("voyage-3-large"),
            params=dense_params,
            role=VectorRole.PRIMARY,
        )

    @pytest.fixture
    def backup_dense_config(self) -> VectorConfig:
        """Provide a backup dense vector configuration."""
        return VectorConfig(
            name="backup",
            model_name=ModelName("jinaai/jina-embeddings-v3"),
            params=VectorParams(size=768, distance=Distance.COSINE),
            role=VectorRole.BACKUP,
        )

    @pytest.fixture
    def sparse_config(self, sparse_params: SparseVectorParams) -> VectorConfig:
        """Provide a sparse vector configuration."""
        return VectorConfig(
            name="sparse",
            model_name=ModelName("opensearch/sparse-encoding-v3"),
            params=sparse_params,
            role=VectorRole.SPARSE,
        )

    def test_creation_dense(self, dense_params: VectorParams):
        """Test creating a dense VectorConfig with all fields."""
        config = VectorConfig(
            name="primary",
            model_name=ModelName("voyage-large-2"),
            params=dense_params,
            role=VectorRole.PRIMARY,
        )

        assert config.name == "primary"
        assert config.model_name == ModelName("voyage-large-2")
        assert config.params is dense_params
        assert config.role == VectorRole.PRIMARY.variable

    def test_creation_sparse(self, sparse_params: SparseVectorParams):
        """Test creating a sparse VectorConfig with all fields."""
        config = VectorConfig(
            name="sparse",
            model_name=ModelName("opensearch/sparse-encoding"),
            params=sparse_params,
            role=VectorRole.SPARSE,
        )

        assert config.name == "sparse"
        assert config.is_sparse
        assert not config.is_dense
        assert config.role == VectorRole.SPARSE.variable

    def test_role_defaults_to_name(self, dense_params: VectorParams):
        """Test that role defaults to name when not provided."""
        config = VectorConfig(
            name="primary", model_name=ModelName("voyage-large-2"), params=dense_params
        )

        assert config.role == "primary"

    def test_role_can_be_custom_string(self, dense_params: VectorParams):
        """Test that role accepts custom string values (not just enum)."""
        config = VectorConfig(
            name="semantic_code",
            model_name=ModelName("voyage-code-2"),
            params=dense_params,
            role="semantic_code",
        )

        assert config.role == "semantic_code"
        assert config.name == "semantic_code"

    def test_kind_property_dense(self, primary_dense_config: VectorConfig):
        """Test that kind property correctly identifies dense vectors."""
        assert primary_dense_config.kind == EmbeddingKind.DENSE
        assert primary_dense_config.is_dense
        assert not primary_dense_config.is_sparse

    def test_kind_property_sparse(self, sparse_config: VectorConfig):
        """Test that kind property correctly identifies sparse vectors."""
        assert sparse_config.kind == EmbeddingKind.SPARSE
        assert sparse_config.is_sparse
        assert not sparse_config.is_dense

    def test_immutability_name(self, primary_dense_config: VectorConfig):
        """Test that VectorConfig is immutable (frozen=True) - name field."""
        with pytest.raises((ValidationError, AttributeError)):
            primary_dense_config.name = "backup"

    def test_immutability_model_name(self, primary_dense_config: VectorConfig):
        """Test that VectorConfig is immutable (frozen=True) - model_name field."""
        with pytest.raises((ValidationError, AttributeError)):
            primary_dense_config.model_name = ModelName("different-model")

    def test_immutability_params(self, primary_dense_config: VectorConfig):
        """Test that VectorConfig is immutable (frozen=True) - params field."""
        with pytest.raises((ValidationError, AttributeError)):
            primary_dense_config.params = VectorParams(size=512, distance=Distance.DOT)

    def test_immutability_role(self, primary_dense_config: VectorConfig):
        """Test that VectorConfig is immutable (frozen=True) - role field."""
        with pytest.raises((ValidationError, AttributeError)):
            primary_dense_config.role = VectorRole.BACKUP

    def test_name_validation_pattern(self, dense_params: VectorParams):
        """Test that name field validates against pattern (lowercase, snake_case)."""
        # Valid names
        for valid_name in ["primary", "backup", "sparse", "semantic_code", "my_vector_2"]:
            config = VectorConfig(
                name=valid_name, model_name=ModelName("test-model"), params=dense_params
            )
            assert config.name == valid_name

    def test_name_validation_rejects_invalid(self, dense_params: VectorParams):
        """Test that invalid names are rejected."""
        invalid_names = [
            "Primary",  # Uppercase
            "primary-backup",  # Hyphen
            "primary backup",  # Space
            "9primary",  # Starts with number
            "",  # Empty
            "a" * 51,  # Too long (>50 chars)
        ]

        for invalid_name in invalid_names:
            with pytest.raises(ValidationError):
                VectorConfig(
                    name=invalid_name, model_name=ModelName("test-model"), params=dense_params
                )

    def test_to_qdrant_config_dense(self, primary_dense_config: VectorConfig):
        """Test conversion to Qdrant config tuple for dense vectors."""
        name, params = primary_dense_config.to_qdrant_config()

        assert name == "primary"
        assert isinstance(params, VectorParams)
        assert params.size == 1024
        assert params.distance == Distance.COSINE
        assert params is primary_dense_config.params  # Same object

    def test_to_qdrant_config_sparse(self, sparse_config: VectorConfig):
        """Test conversion to Qdrant config tuple for sparse vectors."""
        name, params = sparse_config.to_qdrant_config()

        assert name == "sparse"
        assert isinstance(params, SparseVectorParams)
        assert params is sparse_config.params  # Same object

    @pytest.mark.asyncio
    async def test_from_provider_settings_dense(self):
        """Test factory method from_provider_settings for dense embeddings."""
        from codeweaver.core import Provider
        from codeweaver.providers.config.embedding import VoyageEmbeddingConfig
        from codeweaver.providers.config.kinds import EmbeddingProviderSettings

        # Create proper embedding config
        embedding_config = VoyageEmbeddingConfig(
            tag="voyage", provider=Provider.VOYAGE, model_name="voyage-3-large"
        )

        # Create provider settings with the proper embedding config
        settings = EmbeddingProviderSettings(
            provider=Provider.VOYAGE, model_name="voyage-3-large", embedding_config=embedding_config
        )

        config = await VectorConfig.from_provider_settings(
            settings, name="primary", role=VectorRole.PRIMARY
        )

        assert config.name == "primary"
        assert config.model_name == ModelName("voyage-3-large")
        assert config.role == VectorRole.PRIMARY.variable
        assert isinstance(config.params, VectorParams)

    @pytest.mark.asyncio
    async def test_from_provider_settings_sparse(self):
        """Test factory method from_provider_settings for sparse embeddings."""
        from codeweaver.core import Provider
        from codeweaver.providers.config.embedding import FastEmbedSparseEmbeddingConfig
        from codeweaver.providers.config.kinds import SparseEmbeddingProviderSettings

        # Create proper sparse embedding config
        sparse_embedding_config = FastEmbedSparseEmbeddingConfig(
            tag="fastembed", provider=Provider.FASTEMBED, model_name="Qdrant/bm25"
        )

        # Create sparse provider settings with the proper config
        settings = SparseEmbeddingProviderSettings(
            provider=Provider.FASTEMBED,
            model_name="Qdrant/bm25",
            sparse_embedding_config=sparse_embedding_config,
        )

        config = await VectorConfig.from_provider_settings(
            settings, name="sparse", role=VectorRole.SPARSE
        )

        assert config.name == "sparse"
        assert config.model_name == ModelName("Qdrant/bm25")
        assert config.role == VectorRole.SPARSE.variable
        assert isinstance(config.params, SparseVectorParams)

    @pytest.mark.asyncio
    async def test_from_provider_settings_role_defaults(self):
        """Test that from_provider_settings defaults role to name."""
        from codeweaver.core import Provider
        from codeweaver.providers.config.embedding import VoyageEmbeddingConfig
        from codeweaver.providers.config.kinds import EmbeddingProviderSettings

        # Create proper embedding config
        embedding_config = VoyageEmbeddingConfig(
            tag="voyage", provider=Provider.VOYAGE, model_name="voyage-3-large"
        )

        # Create provider settings with the proper embedding config
        settings = EmbeddingProviderSettings(
            provider=Provider.VOYAGE, model_name="voyage-3-large", embedding_config=embedding_config
        )

        config = await VectorConfig.from_provider_settings(settings, name="custom_vector")

        assert config.role == "custom_vector"  # Defaults to name


@pytest.mark.unit
class TestVectorSet:
    """Test VectorSet model functionality.

    Tests the immutable collection of vectors for search/indexing strategies.
    Validates query methods and Qdrant conversion.
    """

    @pytest.fixture
    def primary_config(self) -> VectorConfig:
        """Provide primary dense vector config."""
        return VectorConfig(
            name="primary",
            model_name=ModelName("voyage-3-large"),
            params=VectorParams(size=1024, distance=Distance.COSINE),
            role=VectorRole.PRIMARY,
        )

    @pytest.fixture
    def backup_config(self) -> VectorConfig:
        """Provide backup dense vector config."""
        return VectorConfig(
            name="backup",
            model_name=ModelName("jinaai/jina-embeddings-v3"),
            params=VectorParams(size=768, distance=Distance.COSINE),
            role=VectorRole.BACKUP,
        )

    @pytest.fixture
    def sparse_config(self) -> VectorConfig:
        """Provide sparse vector config."""
        return VectorConfig(
            name="sparse",
            model_name=ModelName("opensearch/sparse-encoding-v3"),
            params=SparseVectorParams(),
            role=VectorRole.SPARSE,
        )

    @pytest.fixture
    def basic_vector_set(
        self, primary_config: VectorConfig, sparse_config: VectorConfig
    ) -> VectorSet:
        """Provide a basic VectorSet with primary and sparse vectors."""
        return VectorSet(vectors={"primary": primary_config, "sparse": sparse_config})

    @pytest.fixture
    def complete_vector_set(
        self, primary_config: VectorConfig, backup_config: VectorConfig, sparse_config: VectorConfig
    ) -> VectorSet:
        """Provide a complete VectorSet with primary, backup, and sparse vectors."""
        return VectorSet(
            vectors={"primary": primary_config, "backup": backup_config, "sparse": sparse_config}
        )

    def test_creation_basic(self, basic_vector_set: VectorSet):
        """Test creating a basic VectorSet."""
        assert len(basic_vector_set.vectors) == 2
        assert "primary" in basic_vector_set.vectors
        assert "sparse" in basic_vector_set.vectors

    def test_creation_complete(self, complete_vector_set: VectorSet):
        """Test creating a complete VectorSet with all vector types."""
        assert len(complete_vector_set.vectors) == 3
        assert "primary" in complete_vector_set.vectors
        assert "backup" in complete_vector_set.vectors
        assert "sparse" in complete_vector_set.vectors

    def test_creation_empty(self):
        """Test that empty VectorSet can be created (edge case)."""
        vector_set = VectorSet(vectors={})
        assert len(vector_set.vectors) == 0

    def test_duplicate_physical_names_rejected(self, primary_config: VectorConfig):
        """Test that duplicate physical vector names are rejected in __init__."""
        # Create two configs with same physical name but different logical keys
        config1 = primary_config
        config2 = VectorConfig(
            name="primary",  # Same physical name!
            model_name=ModelName("different-model"),
            params=VectorParams(size=512, distance=Distance.DOT),
            role=VectorRole.BACKUP,
        )

        with pytest.raises(ValueError, match="Duplicate physical vector names"):
            VectorSet(vectors={"v1": config1, "v2": config2})

    def test_duplicate_names_error_message(self, primary_config: VectorConfig):
        """Test that duplicate name error includes the duplicated names."""
        config2 = VectorConfig(
            name="primary",
            model_name=ModelName("other-model"),
            params=VectorParams(size=512, distance=Distance.DOT),
        )

        with pytest.raises(ValueError) as exc_info:
            VectorSet(vectors={"a": primary_config, "b": config2})

        assert "primary" in str(exc_info.value)
        assert "Duplicate" in str(exc_info.value)

    def test_query_by_role_with_enum(self, complete_vector_set: VectorSet):
        """Test querying vectors by VectorRole enum."""
        primaries = complete_vector_set.by_role(VectorRole.PRIMARY)
        assert len(primaries) == 1
        assert primaries[0].name == "primary"

        backups = complete_vector_set.by_role(VectorRole.BACKUP)
        assert len(backups) == 1
        assert backups[0].name == "backup"

        sparse = complete_vector_set.by_role(VectorRole.SPARSE)
        assert len(sparse) == 1
        assert sparse[0].name == "sparse"

    def test_query_by_role_with_string(self, complete_vector_set: VectorSet):
        """Test querying vectors by string role name."""
        primaries = complete_vector_set.by_role("primary")
        assert len(primaries) == 1
        assert primaries[0].role == "primary"

    def test_query_by_role_returns_empty_list(self, basic_vector_set: VectorSet):
        """Test that by_role returns empty list when no matches found."""
        backups = basic_vector_set.by_role(VectorRole.BACKUP)
        assert backups == []
        assert isinstance(backups, list)

    def test_query_by_role_supports_multiple(self):
        """Test that by_role supports multiple vectors with same role (future-proofing)."""
        # Create two vectors with PRIMARY role (different names)
        config1 = VectorConfig(
            name="primary_v1",
            model_name=ModelName("voyage-large-2"),
            params=VectorParams(size=1024, distance=Distance.COSINE),
            role=VectorRole.PRIMARY,
        )
        config2 = VectorConfig(
            name="primary_v2",
            model_name=ModelName("voyage-large-3"),
            params=VectorParams(size=1024, distance=Distance.COSINE),
            role=VectorRole.PRIMARY,
        )

        vector_set = VectorSet(vectors={"v1": config1, "v2": config2})

        primaries = vector_set.by_role(VectorRole.PRIMARY)
        assert len(primaries) == 2
        assert {v.name for v in primaries} == {"primary_v1", "primary_v2"}

    def test_query_by_name(self, complete_vector_set: VectorSet):
        """Test querying vectors by physical Qdrant name."""
        primary = complete_vector_set.by_name("primary")
        assert primary is not None
        assert primary.name == "primary"

        backup = complete_vector_set.by_name("backup")
        assert backup is not None
        assert backup.name == "backup"

    def test_query_by_name_returns_none(self, basic_vector_set: VectorSet):
        """Test that by_name returns None when not found."""
        result = basic_vector_set.by_name("nonexistent")
        assert result is None

    def test_query_by_key(self, complete_vector_set: VectorSet):
        """Test querying vectors by logical dict key."""
        primary = complete_vector_set.by_key("primary")
        assert primary is not None
        assert primary.name == "primary"

        backup = complete_vector_set.by_key("backup")
        assert backup is not None
        assert backup.name == "backup"

    def test_query_by_key_returns_none(self, basic_vector_set: VectorSet):
        """Test that by_key returns None when not found."""
        result = basic_vector_set.by_key("nonexistent")
        assert result is None

    def test_query_by_key_different_from_name(self):
        """Test by_key with logical keys different from physical names."""
        config = VectorConfig(
            name="physical_primary",
            model_name=ModelName("voyage-large-2"),
            params=VectorParams(size=1024, distance=Distance.COSINE),
            role=VectorRole.PRIMARY,
        )

        vector_set = VectorSet(vectors={"logical_key": config})

        # by_key uses logical key
        assert vector_set.by_key("logical_key") is not None
        assert vector_set.by_key("physical_primary") is None

        # by_name uses physical name
        assert vector_set.by_name("physical_primary") is not None
        assert vector_set.by_name("logical_key") is None

    def test_dense_vectors_filter(self, complete_vector_set: VectorSet):
        """Test filtering for dense vectors only."""
        dense = complete_vector_set.dense_vectors()

        assert len(dense) == 2  # primary and backup
        assert "primary" in dense
        assert "backup" in dense
        assert "sparse" not in dense
        assert all(v.is_dense for v in dense.values())

    def test_sparse_vectors_filter(self, complete_vector_set: VectorSet):
        """Test filtering for sparse vectors only."""
        sparse = complete_vector_set.sparse_vectors()

        assert len(sparse) == 1
        assert "sparse" in sparse
        assert all(v.is_sparse for v in sparse.values())

    def test_dense_vectors_preserves_keys(self, complete_vector_set: VectorSet):
        """Test that dense_vectors() preserves original dict keys."""
        dense = complete_vector_set.dense_vectors()
        assert set(dense.keys()) == {"primary", "backup"}

    def test_convenience_accessor_primary(self, complete_vector_set: VectorSet):
        """Test primary() convenience accessor."""
        primary = complete_vector_set.primary()
        assert primary is not None
        assert primary.role == VectorRole.PRIMARY.variable
        assert primary.name == "primary"

    def test_convenience_accessor_backup(self, complete_vector_set: VectorSet):
        """Test backup() convenience accessor."""
        backup = complete_vector_set.backup()
        assert backup is not None
        assert backup.role == VectorRole.BACKUP.variable
        assert backup.name == "backup"

    def test_convenience_accessor_sparse(self, complete_vector_set: VectorSet):
        """Test sparse() convenience accessor."""
        sparse = complete_vector_set.sparse()
        assert sparse is not None
        assert sparse.role == VectorRole.SPARSE.variable
        assert sparse.name == "sparse"

    def test_convenience_accessors_return_none(self, basic_vector_set: VectorSet):
        """Test that convenience accessors return None when not present."""
        assert basic_vector_set.backup() is None

    def test_convenience_accessor_returns_first_match(self):
        """Test that convenience accessors return first match when multiple exist."""
        config1 = VectorConfig(
            name="primary_1",
            model_name=ModelName("voyage-large-2"),
            params=VectorParams(size=1024, distance=Distance.COSINE),
            role=VectorRole.PRIMARY,
        )
        config2 = VectorConfig(
            name="primary_2",
            model_name=ModelName("voyage-large-3"),
            params=VectorParams(size=1024, distance=Distance.COSINE),
            role=VectorRole.PRIMARY,
        )

        vector_set = VectorSet(vectors={"v1": config1, "v2": config2})

        primary = vector_set.primary()
        assert primary is not None
        # Should return first match (implementation-dependent order)
        assert primary.role == VectorRole.PRIMARY.variable

    def test_to_qdrant_vectors_config(self, complete_vector_set: VectorSet):
        """Test conversion to Qdrant vectors_config dict (dense only)."""
        vectors_config = complete_vector_set.to_qdrant_vectors_config()

        assert len(vectors_config) == 2  # primary and backup only
        assert "primary" in vectors_config
        assert "backup" in vectors_config
        assert "sparse" not in vectors_config

        assert isinstance(vectors_config["primary"], VectorParams)
        assert isinstance(vectors_config["backup"], VectorParams)
        assert vectors_config["primary"].size == 1024
        assert vectors_config["backup"].size == 768

    def test_to_qdrant_sparse_vectors_config(self, complete_vector_set: VectorSet):
        """Test conversion to Qdrant sparse_vectors_config dict (sparse only)."""
        sparse_config = complete_vector_set.to_qdrant_sparse_vectors_config()

        assert len(sparse_config) == 1
        assert "sparse" in sparse_config
        assert isinstance(sparse_config["sparse"], SparseVectorParams)

    def test_to_qdrant_vectors_config_empty_when_no_dense(self, sparse_config: VectorConfig):
        """Test that to_qdrant_vectors_config returns empty dict when no dense vectors."""
        vector_set = VectorSet(vectors={"sparse": sparse_config})
        vectors_config = vector_set.to_qdrant_vectors_config()

        assert vectors_config == {}

    def test_to_qdrant_sparse_vectors_config_empty_when_no_sparse(
        self, primary_config: VectorConfig
    ):
        """Test that to_qdrant_sparse_vectors_config returns empty dict when no sparse."""
        vector_set = VectorSet(vectors={"primary": primary_config})
        sparse_config = vector_set.to_qdrant_sparse_vectors_config()

        assert sparse_config == {}

    def test_qdrant_config_uses_physical_names(self, complete_vector_set: VectorSet):
        """Test that Qdrant configs use physical vector names, not logical keys."""
        vectors_config = complete_vector_set.to_qdrant_vectors_config()

        # Keys should be physical names from VectorConfig.name
        assert all(isinstance(k, str) for k in vectors_config.keys())
        assert "primary" in vectors_config  # Physical name
        assert "backup" in vectors_config  # Physical name

    @pytest.mark.asyncio
    async def test_from_profile_standard_layout(self):
        """Test factory method from_profile with standard vector layout."""
        from codeweaver.providers.config.profiles import ProviderProfile

        vector_set = await VectorSet.from_profile(ProviderProfile.RECOMMENDED)

        # Should have primary dense vector
        assert vector_set.primary() is not None
        assert vector_set.primary().name == "primary"
        assert vector_set.primary().role == VectorRole.PRIMARY.variable

        # May have backup and sparse depending on profile
        # At minimum, should have primary

    @pytest.mark.asyncio
    async def test_from_profile_uses_role_based_names(self):
        """Test that from_profile uses role-based physical names."""
        from codeweaver.providers.config.profiles import ProviderProfile

        vector_set = await VectorSet.from_profile(ProviderProfile.RECOMMENDED)

        # Physical names should be role-based, not model-based
        all_names = {v.name for v in vector_set.vectors.values()}

        # Should use names like "primary", "backup", "sparse"
        # Not names like "voyage_large_2" or "jina_v3"
        expected_role_names = {"primary", "backup", "sparse"}
        assert all_names <= expected_role_names  # Subset of expected names

    @pytest.mark.asyncio
    async def test_default_factory(self):
        """Test default() factory method returns recommended configuration."""
        vector_set = await VectorSet.default()

        assert vector_set is not None
        assert len(vector_set.vectors) > 0
        assert vector_set.primary() is not None

    def test_immutability_vectors_dict(self, basic_vector_set: VectorSet):
        """Test that VectorSet is immutable (frozen=True)."""
        with pytest.raises((ValidationError, AttributeError)):
            basic_vector_set.vectors = {}


@pytest.mark.integration
class TestVectorSetIntegration:
    """Integration tests for VectorSet with actual Qdrant usage patterns."""

    @pytest.mark.asyncio
    async def test_create_qdrant_collection_config(self):
        """Test creating Qdrant collection parameters from VectorSet."""
        from qdrant_client.models import CollectionParams

        # Create vector set
        vector_set = VectorSet(
            vectors={
                "primary": VectorConfig(
                    name="primary",
                    model_name=ModelName("voyage-large-2"),
                    params=VectorParams(size=1024, distance=Distance.COSINE),
                    role=VectorRole.PRIMARY,
                ),
                "sparse": VectorConfig(
                    name="sparse",
                    model_name=ModelName("opensearch/sparse"),
                    params=SparseVectorParams(),
                    role=VectorRole.SPARSE,
                ),
            }
        )

        # Create Qdrant collection params - this is what's used for creating collections
        params = CollectionParams(
            vectors=vector_set.to_qdrant_vectors_config(),
            sparse_vectors=vector_set.to_qdrant_sparse_vectors_config(),
        )

        # Verify the params are correctly structured
        assert params is not None
        assert params.vectors is not None
        assert "primary" in params.vectors
        assert params.sparse_vectors is not None
        assert "sparse" in params.sparse_vectors


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_vector_config_with_very_long_valid_name(self):
        """Test VectorConfig with maximum allowed name length."""
        long_name = "a" * 50  # Maximum is 50 characters
        config = VectorConfig(
            name=long_name,
            model_name=ModelName("test-model"),
            params=VectorParams(size=512, distance=Distance.COSINE),
        )
        assert config.name == long_name

    def test_vector_config_model_name_types(self):
        """Test VectorConfig accepts various ModelName formats."""
        # Test with ModelName instance
        config1 = VectorConfig(
            name="test1",
            model_name=ModelName("voyage-large-2"),
            params=VectorParams(size=1024, distance=Distance.COSINE),
        )
        assert config1.model_name == ModelName("voyage-large-2")

        # Test with org/model format
        config2 = VectorConfig(
            name="test2",
            model_name=ModelName("jinaai/jina-embeddings-v3"),
            params=VectorParams(size=768, distance=Distance.COSINE),
        )
        assert "jinaai" in str(config2.model_name)

    def test_vector_set_with_single_vector(self):
        """Test VectorSet with only one vector (minimal case)."""
        config = VectorConfig(
            name="solo",
            model_name=ModelName("test-model"),
            params=VectorParams(size=512, distance=Distance.COSINE),
        )

        vector_set = VectorSet(vectors={"solo": config})

        assert len(vector_set.vectors) == 1
        assert vector_set.by_key("solo") is not None

    def test_role_enum_to_string_conversion(self):
        """Test that VectorRole enum can be used interchangeably with strings."""
        config_with_enum = VectorConfig(
            name="test1",
            model_name=ModelName("test-model"),
            params=VectorParams(size=512, distance=Distance.COSINE),
            role=VectorRole.PRIMARY,
        )

        config_with_string = VectorConfig(
            name="test2",
            model_name=ModelName("test-model"),
            params=VectorParams(size=512, distance=Distance.COSINE),
            role="primary",
        )

        # Both should have same role value
        assert config_with_enum.role == config_with_string.role == "primary"
