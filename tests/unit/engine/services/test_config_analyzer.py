# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for ConfigChangeAnalyzer service.

Tests cover:
- Configuration change classification (NONE, COMPATIBLE, TRANSFORMABLE, QUANTIZABLE, BREAKING)
- Model compatibility checking (symmetric vs asymmetric embeddings)
- Dimension reduction impact estimation (with empirical Matryoshka data)
- Quantization compatibility validation
- Configuration change simulation and validation
- Edge cases and error conditions
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest


if TYPE_CHECKING:
    from codeweaver.engine.managers.checkpoint_manager import CheckpointManager
    from codeweaver.engine.managers.manifest_manager import FileManifestManager


# ===========================================================================
# *                    Fixtures: Dependencies
# ===========================================================================


@pytest.fixture
def mock_settings() -> Mock:
    """Create mock Settings with embedding configuration."""
    settings = Mock()
    settings.provider = Mock()
    settings.provider.embedding = Mock()
    settings.provider.embedding.model_name = "voyage-code-3"
    settings.provider.embedding.dimension = 2048
    settings.provider.embedding.datatype = "float32"
    settings.model_copy = Mock(return_value=settings)
    return settings


@pytest.fixture
def mock_checkpoint_manager() -> Mock:
    """Create mock CheckpointManager."""
    manager = Mock(spec=["load_checkpoint"])
    manager.load_checkpoint = AsyncMock(return_value=None)
    return manager


@pytest.fixture
def mock_manifest_manager() -> Mock:
    """Create mock FileManifestManager."""
    manager = Mock(spec=["read_manifest"])
    manager.read_manifest = AsyncMock(return_value=None)
    return manager


@pytest.fixture
def config_analyzer(
    mock_settings: Mock,
    mock_checkpoint_manager: CheckpointManager,
    mock_manifest_manager: FileManifestManager,
) -> Mock:
    """Create ConfigChangeAnalyzer with mocked dependencies.

    Direct instantiation (NO DI container) for unit testing.
    """
    from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

    return ConfigChangeAnalyzer(
        settings=mock_settings,
        checkpoint_manager=mock_checkpoint_manager,
        manifest_manager=mock_manifest_manager,
    )


# ===========================================================================
# *                    Helper Functions & Fixtures
# ===========================================================================


@pytest.fixture
def collection_metadata() -> Mock:
    """Create mock CollectionMetadata for testing."""
    metadata = Mock()
    metadata.dense_model = "voyage-code-3"
    metadata.dense_model_family = "voyage-4"
    metadata.query_model = "voyage-4-large"
    metadata.dimension = 2048
    metadata.datatype = "float32"

    # Add methods
    metadata.get_vector_dimension = Mock(return_value=2048)
    metadata.get_vector_datatype = Mock(return_value="float32")

    return metadata


@pytest.fixture
def embedding_config() -> Mock:
    """Create mock SymmetricEmbeddingConfig."""
    config = Mock()
    config.model_name = "voyage-code-3"
    config.dimension = 2048
    config.datatype = "float32"
    return config


@pytest.fixture
def asymmetric_embedding_config() -> Mock:
    """Create mock AsymmetricEmbeddingConfig."""
    config = Mock()
    config.embed_model = "voyage-code-3"
    config.embed_model_family = "voyage-4"
    config.query_model = "voyage-4-large"
    config.dimension = 2048
    config.datatype = "float32"
    return config


# ===========================================================================
# *                    Tests: Analyze Current Config
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestAnalyzeCurrentConfig:
    """Tests for analyze_current_config method."""

    async def test_no_checkpoint_returns_none(
        self,
        config_analyzer: Mock,
        mock_checkpoint_manager: Mock,
    ) -> None:
        """Test that None is returned when no checkpoint exists."""
        mock_checkpoint_manager.load_checkpoint.return_value = None

        result = await config_analyzer.analyze_current_config()

        assert result is None
        mock_checkpoint_manager.load_checkpoint.assert_called_once()

    async def test_loads_checkpoint_metadata(
        self,
        config_analyzer: Mock,
        mock_checkpoint_manager: Mock,
        collection_metadata: Mock,
    ) -> None:
        """Test that checkpoint metadata is loaded correctly."""
        checkpoint = Mock()
        checkpoint.collection_metadata = collection_metadata
        checkpoint.total_vectors = 1000
        mock_checkpoint_manager.load_checkpoint.return_value = checkpoint

        # Mock the analyze_config_change method to verify it's called
        config_analyzer.analyze_config_change = AsyncMock(
            return_value=Mock(impact="COMPATIBLE")
        )

        result = await config_analyzer.analyze_current_config()

        assert result is not None
        config_analyzer.analyze_config_change.assert_called_once()

    async def test_calls_analyze_with_current_config(
        self,
        config_analyzer: Mock,
        mock_checkpoint_manager: Mock,
        collection_metadata: Mock,
    ) -> None:
        """Test that analyze_config_change is called with current settings."""
        checkpoint = Mock()
        checkpoint.collection_metadata = collection_metadata
        checkpoint.total_vectors = 5000
        mock_checkpoint_manager.load_checkpoint.return_value = checkpoint

        config_analyzer.analyze_config_change = AsyncMock(
            return_value=Mock(impact="COMPATIBLE")
        )

        await config_analyzer.analyze_current_config()

        # Verify the call includes current embedding config
        call_kwargs = config_analyzer.analyze_config_change.call_args[1]
        assert call_kwargs["vector_count"] == 5000
        assert call_kwargs["old_meta"] == collection_metadata


# ===========================================================================
# *                    Tests: Model Compatibility
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestModelCompatibility:
    """Tests for _models_compatible method."""

    def test_symmetric_same_model_is_compatible(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that same symmetric model is compatible."""
        embedding_config.model_name = "voyage-code-3"

        result = config_analyzer._models_compatible(
            collection_metadata, embedding_config
        )

        assert result is True

    def test_symmetric_different_model_is_incompatible(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that different symmetric model is incompatible."""
        embedding_config.model_name = "voyage-code-2"

        result = config_analyzer._models_compatible(
            collection_metadata, embedding_config
        )

        assert result is False

    def test_asymmetric_same_family_compatible(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        asymmetric_embedding_config: Mock,
    ) -> None:
        """Test that asymmetric with same family and embed model is compatible."""
        asymmetric_embedding_config.embed_model = "voyage-code-3"
        asymmetric_embedding_config.embed_model_family = "voyage-4"
        asymmetric_embedding_config.query_model = "voyage-4-nano"

        result = config_analyzer._models_compatible(
            collection_metadata, asymmetric_embedding_config
        )

        assert result is True

    def test_asymmetric_different_family_incompatible(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        asymmetric_embedding_config: Mock,
    ) -> None:
        """Test that asymmetric with different family is incompatible."""
        collection_metadata.dense_model_family = "voyage-3"
        asymmetric_embedding_config.embed_model_family = "voyage-4"

        result = config_analyzer._models_compatible(
            collection_metadata, asymmetric_embedding_config
        )

        assert result is False

    def test_asymmetric_different_embed_model_incompatible(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        asymmetric_embedding_config: Mock,
    ) -> None:
        """Test that asymmetric with different embed model is incompatible."""
        collection_metadata.dense_model = "voyage-code-2"
        asymmetric_embedding_config.embed_model = "voyage-code-3"

        result = config_analyzer._models_compatible(
            collection_metadata, asymmetric_embedding_config
        )

        assert result is False


# ===========================================================================
# *                    Tests: Configuration Change Analysis
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestAnalyzeConfigChangeNoChange:
    """Tests for no-change scenarios."""

    async def test_identical_config_returns_none_impact(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that identical config returns NONE impact."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        embedding_config.model_name = "voyage-code-3"
        embedding_config.dimension = 2048
        embedding_config.datatype = "float32"

        # Mock compatible models
        config_analyzer._models_compatible = Mock(return_value=True)

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=1000,
        )

        assert analysis.impact == ChangeImpact.NONE
        assert len(analysis.transformations) == 0
        assert analysis.migration_strategy is None


# ===========================================================================
# *                    Tests: Breaking Changes
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestAnalyzeConfigChangeBreaking:
    """Tests for breaking change detection."""

    async def test_incompatible_models_returns_breaking(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that incompatible models return BREAKING impact."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        embedding_config.model_name = "voyage-code-2"

        # Mock incompatible models
        config_analyzer._models_compatible = Mock(return_value=False)

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=1000,
        )

        assert analysis.impact == ChangeImpact.BREAKING
        assert "Revert config" in " ".join(analysis.recommendations)
        assert analysis.migration_strategy == "full_reindex"

    async def test_dimension_increase_returns_breaking(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that dimension increase returns BREAKING impact."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        collection_metadata.dimension = 2048
        embedding_config.dimension = 4096  # Increase
        config_analyzer._models_compatible = Mock(return_value=True)

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=1000,
        )

        assert analysis.impact == ChangeImpact.BREAKING

    async def test_invalid_precision_increase_returns_breaking(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that increasing precision returns BREAKING."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        collection_metadata.datatype = "int8"
        embedding_config.datatype = "float32"
        config_analyzer._models_compatible = Mock(return_value=True)
        config_analyzer._is_valid_quantization = Mock(return_value=False)

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=1000,
        )

        assert analysis.impact == ChangeImpact.BREAKING


# ===========================================================================
# *                    Tests: Quantization
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestAnalyzeConfigChangeQuantization:
    """Tests for quantization scenarios."""

    async def test_valid_quantization_returns_quantizable(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that valid quantization returns QUANTIZABLE impact."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        collection_metadata.datatype = "float32"
        embedding_config.datatype = "int8"
        config_analyzer._models_compatible = Mock(return_value=True)
        config_analyzer._is_valid_quantization = Mock(return_value=True)

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=1000,
        )

        assert analysis.impact == ChangeImpact.QUANTIZABLE
        assert len(analysis.transformations) == 1
        assert analysis.transformations[0].type == "quantization"

    async def test_quantization_details_accurate(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that quantization transformation details are accurate."""
        collection_metadata.datatype = "float32"
        embedding_config.datatype = "int8"
        config_analyzer._models_compatible = Mock(return_value=True)
        config_analyzer._is_valid_quantization = Mock(return_value=True)

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=1000,
        )

        transform = analysis.transformations[0]
        assert transform.old_value == "float32"
        assert transform.new_value == "int8"
        assert transform.complexity == "low"
        assert not transform.requires_vector_update
        assert "2%" in transform.accuracy_impact


# ===========================================================================
# *                    Tests: Dimension Reduction
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestAnalyzeConfigChangeDimensionReduction:
    """Tests for dimension reduction scenarios."""

    async def test_dimension_reduction_returns_transformable(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that dimension reduction returns TRANSFORMABLE impact."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        collection_metadata.dimension = 2048
        embedding_config.dimension = 1024
        config_analyzer._models_compatible = Mock(return_value=True)
        config_analyzer._estimate_matryoshka_impact = Mock(
            return_value="~0.5% (empirical)"
        )

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=1000,
        )

        assert analysis.impact == ChangeImpact.TRANSFORMABLE
        assert len(analysis.transformations) == 1
        assert analysis.transformations[0].type == "dimension_reduction"

    async def test_dimension_reduction_details_accurate(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that dimension reduction transformation details are accurate."""
        collection_metadata.dense_model = "voyage-code-3"
        collection_metadata.dimension = 2048
        embedding_config.dimension = 512
        config_analyzer._models_compatible = Mock(return_value=True)
        config_analyzer._estimate_matryoshka_impact = Mock(
            return_value="~0.47% (empirical)"
        )

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=5000,
        )

        transform = analysis.transformations[0]
        assert transform.old_value == 2048
        assert transform.new_value == 512
        assert transform.complexity == "medium"
        assert transform.requires_vector_update
        assert "0.47%" in transform.accuracy_impact

    async def test_dimension_reduction_estimates_time(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that time estimate is calculated for reduction."""
        collection_metadata.dimension = 2048
        embedding_config.dimension = 1024
        config_analyzer._models_compatible = Mock(return_value=True)
        config_analyzer._estimate_matryoshka_impact = Mock(return_value="~0.5%")
        config_analyzer._estimate_migration_time = Mock(
            return_value=timedelta(seconds=300)
        )

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=10000,
        )

        assert analysis.estimated_time > timedelta(0)
        config_analyzer._estimate_migration_time.assert_called_once_with(10000)


# ===========================================================================
# *                    Tests: Matryoshka Impact Estimation
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestMatryoshkaImpactEstimation:
    """Tests for Matryoshka impact estimation with empirical data."""

    def test_voyage_code_3_empirical_2048_to_1024(
        self,
        config_analyzer: Mock,
    ) -> None:
        """Test empirical Voyage-3 impact for 2048->1024 reduction."""
        impact = config_analyzer._estimate_matryoshka_impact(
            "voyage-code-3", 2048, 1024
        )

        # Empirical data: 75.16% → 75.20% = +0.04% impact
        assert "0.04" in impact
        assert "empirical" in impact.lower()

    def test_voyage_code_3_empirical_2048_to_512(
        self,
        config_analyzer: Mock,
    ) -> None:
        """Test empirical Voyage-3 impact for 2048->512 reduction."""
        impact = config_analyzer._estimate_matryoshka_impact(
            "voyage-code-3", 2048, 512
        )

        # Empirical data: 75.16% → 74.69% = ~0.47% impact
        assert "0.47" in impact
        assert "empirical" in impact.lower()

    def test_voyage_code_3_empirical_2048_to_256(
        self,
        config_analyzer: Mock,
    ) -> None:
        """Test empirical Voyage-3 impact for 2048->256 reduction."""
        impact = config_analyzer._estimate_matryoshka_impact(
            "voyage-code-3", 2048, 256
        )

        # Empirical data: 75.16% → 72.73% = ~2.43% impact
        assert "2.43" in impact
        assert "empirical" in impact.lower()

    def test_voyage_code_3_empirical_1024_to_512(
        self,
        config_analyzer: Mock,
    ) -> None:
        """Test empirical Voyage-3 impact for 1024->512 reduction (int8)."""
        impact = config_analyzer._estimate_matryoshka_impact(
            "voyage-code-3", 1024, 512
        )

        # Empirical data: 74.87% → 74.69% = ~0.51% impact
        assert "0.51" in impact
        assert "empirical" in impact.lower()

    def test_non_voyage_model_uses_generic_estimate(
        self,
        config_analyzer: Mock,
    ) -> None:
        """Test that non-Voyage models use generic estimation."""
        impact = config_analyzer._estimate_matryoshka_impact(
            "sentence-transformers/model", 2048, 512
        )

        # Generic: no empirical data match
        assert "estimated" in impact.lower()

    def test_unmapped_dimension_pair_uses_generic(
        self,
        config_analyzer: Mock,
    ) -> None:
        """Test that unmapped dimension pairs use generic estimation."""
        impact = config_analyzer._estimate_matryoshka_impact(
            "voyage-code-3", 1024, 256
        )

        # Not in empirical map, uses generic
        assert "estimated" in impact.lower()


# ===========================================================================
# *                    Tests: Config Change Validation
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestValidateConfigChange:
    """Tests for proactive config change validation."""

    async def test_non_embedding_config_returns_none(
        self,
        config_analyzer: Mock,
    ) -> None:
        """Test that non-embedding config changes return None."""
        result = await config_analyzer.validate_config_change(
            "server.port", 9330
        )

        assert result is None

    async def test_no_checkpoint_returns_none(
        self,
        config_analyzer: Mock,
        mock_checkpoint_manager: Mock,
    ) -> None:
        """Test that no checkpoint means change is safe (returns None)."""
        mock_checkpoint_manager.load_checkpoint.return_value = None

        result = await config_analyzer.validate_config_change(
            "provider.embedding.dimension", 1024
        )

        assert result is None

    async def test_embedding_change_is_analyzed(
        self,
        config_analyzer: Mock,
        mock_checkpoint_manager: Mock,
        collection_metadata: Mock,
    ) -> None:
        """Test that embedding changes are analyzed against checkpoint."""
        checkpoint = Mock()
        checkpoint.collection_metadata = collection_metadata
        checkpoint.total_vectors = 1000
        mock_checkpoint_manager.load_checkpoint.return_value = checkpoint

        # Mock the simulation and analysis
        config_analyzer._simulate_config_change = Mock(return_value=config_analyzer.settings)
        config_analyzer.analyze_config_change = AsyncMock(
            return_value=Mock(impact="COMPATIBLE")
        )

        result = await config_analyzer.validate_config_change(
            "provider.embedding.dimension", 1024
        )

        assert result is not None
        config_analyzer.analyze_config_change.assert_called_once()


# ===========================================================================
# *                    Tests: Config Change Simulation
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestSimulateConfigChange:
    """Tests for config change simulation."""

    def test_simulate_simple_nested_change(
        self,
        config_analyzer: Mock,
        mock_settings: Mock,
    ) -> None:
        """Test simulating a simple nested config change."""
        new_settings = config_analyzer._simulate_config_change(
            "provider.embedding.dimension", 1024
        )

        assert new_settings is not None

    def test_simulate_creates_deep_copy(
        self,
        config_analyzer: Mock,
        mock_settings: Mock,
    ) -> None:
        """Test that simulation creates a deep copy of settings."""
        original_settings = config_analyzer.settings
        new_settings = config_analyzer._simulate_config_change(
            "provider.embedding.dimension", 1024
        )

        # Should be different objects (deep copy)
        assert new_settings is not original_settings

    def test_simulate_preserves_other_values(
        self,
        config_analyzer: Mock,
        mock_settings: Mock,
    ) -> None:
        """Test that simulation preserves unaffected values."""
        config_analyzer._simulate_config_change(
            "provider.embedding.dimension", 1024
        )

        # Original settings should be unchanged
        assert config_analyzer.settings.provider.embedding.model_name == "voyage-code-3"


# ===========================================================================
# *                    Tests: Edge Cases
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    async def test_zero_vectors_in_collection(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test handling of empty collection (zero vectors)."""
        config_analyzer._models_compatible = Mock(return_value=True)

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=0,
        )

        assert analysis is not None

    async def test_very_large_collection(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test handling of very large collection."""
        collection_metadata.dimension = 2048
        embedding_config.dimension = 1024
        config_analyzer._models_compatible = Mock(return_value=True)
        config_analyzer._estimate_matryoshka_impact = Mock(return_value="~0.5%")
        config_analyzer._estimate_migration_time = Mock(return_value=timedelta(hours=12))

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=10_000_000,
        )

        # Estimate time should reflect large collection
        assert analysis.estimated_time >= timedelta(hours=1)

    def test_quantization_validity_check(
        self,
        config_analyzer: Mock,
    ) -> None:
        """Test quantization validity checking."""
        # float32 -> int8 should be valid
        assert config_analyzer._is_valid_quantization("float32", "int8") is True

        # int8 -> float32 should be invalid (precision increase)
        assert config_analyzer._is_valid_quantization("int8", "float32") is False

        # int8 -> uint8 should be valid (similar precision)
        assert config_analyzer._is_valid_quantization("int8", "uint8") is True


# ===========================================================================
# *                    Tests: Recommendations Generation
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestRecommendationsGeneration:
    """Tests for user-facing recommendations."""

    async def test_breaking_change_includes_revert_recommendation(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that breaking changes include revert recommendation."""
        embedding_config.model_name = "voyage-code-2"
        config_analyzer._models_compatible = Mock(return_value=False)

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=1000,
        )

        assert "Revert config" in " ".join(analysis.recommendations)

    async def test_transformable_change_includes_strategy(
        self,
        config_analyzer: Mock,
        collection_metadata: Mock,
        embedding_config: Mock,
    ) -> None:
        """Test that transformable changes include migration strategy."""
        collection_metadata.dimension = 2048
        embedding_config.dimension = 1024
        config_analyzer._models_compatible = Mock(return_value=True)
        config_analyzer._estimate_matryoshka_impact = Mock(return_value="~0.5%")

        analysis = await config_analyzer.analyze_config_change(
            old_meta=collection_metadata,
            new_config=embedding_config,
            vector_count=1000,
        )

        assert analysis.migration_strategy is not None


# ===========================================================================
# *                    Tests: Helper Methods
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.config
@pytest.mark.mock_only
@pytest.mark.unit
class TestHelperMethods:
    """Tests for internal helper methods."""

    def test_estimate_reindex_time_increases_with_vector_count(
        self,
        config_analyzer: Mock,
    ) -> None:
        """Test that reindex time estimate increases with vector count."""
        time_1k = config_analyzer._estimate_reindex_time(1000)
        time_100k = config_analyzer._estimate_reindex_time(100_000)

        # Larger collection should take more time
        assert time_100k > time_1k

    def test_estimate_reindex_cost_increases_with_vector_count(
        self,
        config_analyzer: Mock,
    ) -> None:
        """Test that reindex cost estimate increases with vector count."""
        cost_1k = config_analyzer._estimate_reindex_cost(1000)
        cost_100k = config_analyzer._estimate_reindex_cost(100_000)

        # Larger collection should cost more
        assert cost_100k > cost_1k

    def test_estimate_migration_time_increases_with_vector_count(
        self,
        config_analyzer: Mock,
    ) -> None:
        """Test that migration time estimate increases with vector count."""
        time_1k = config_analyzer._estimate_migration_time(1000)
        time_100k = config_analyzer._estimate_migration_time(100_000)

        # Larger collection should take more time
        assert time_100k > time_1k
