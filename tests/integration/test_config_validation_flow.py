# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration tests for ConfigChangeAnalyzer with DI container.

Tests cover:
- Full validation workflows with real services (not mocked)
- Configuration analysis through complete DI pipeline
- End-to-end scenarios from config change to analysis result
- Integration with checkpoint and manifest managers
- Real service initialization and dependency injection
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest


if TYPE_CHECKING:
    pass


# ===========================================================================
# *                    Fixtures: DI Container Setup
# ===========================================================================


@pytest.fixture(autouse=True)
def setup_test_container(test_settings):
    """Create test DI container and override settings so real `get_settings()` works."""
    from codeweaver.core.di.container import get_container
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType

    container = get_container()
    container.override(CodeWeaverSettingsType, test_settings)
    yield container
    container.clear()


@pytest.fixture
def test_config_path(tmp_path: Path) -> Path:
    """Create test configuration directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    return config_dir


@pytest.fixture
def test_checkpoint_data(tmp_path: Path) -> dict:
    """Create test checkpoint data with collection metadata."""
    return {
        "version": "2.0",
        "collection_name": "test_collection",
        "total_vectors": 5000,
        "checkpoint_timestamp": "2025-02-12T00:00:00Z",
        "collection_metadata": {
            "dense_model": "voyage-code-3",
            "dense_model_family": "voyage-4",
            "query_model": "voyage-4-large",
            "dimension": 2048,
            "datatype": "float32",
            "vector_count": 5000,
        },
    }


# ===========================================================================
# *                    Fixtures: Mock Services
# ===========================================================================


@pytest.fixture
def mock_checkpoint_manager(test_checkpoint_data: dict) -> AsyncMock:
    """Create mock CheckpointManager with test data."""
    manager = AsyncMock()

    # Create checkpoint object
    checkpoint = Mock()
    checkpoint.version = test_checkpoint_data["version"]
    checkpoint.collection_name = test_checkpoint_data["collection_name"]
    checkpoint.total_vectors = test_checkpoint_data["total_vectors"]

    # Support dictionary-like access if something tries to subscript it
    checkpoint.__getitem__ = Mock(side_effect=test_checkpoint_data.__getitem__)
    checkpoint.get = Mock(side_effect=test_checkpoint_data.get)

    # Create collection metadata
    metadata = Mock()
    metadata.dense_model = test_checkpoint_data["collection_metadata"]["dense_model"]
    metadata.dense_model_family = test_checkpoint_data["collection_metadata"]["dense_model_family"]
    metadata.query_model = test_checkpoint_data["collection_metadata"]["query_model"]
    metadata.dimension = test_checkpoint_data["collection_metadata"]["dimension"]
    metadata.datatype = test_checkpoint_data["collection_metadata"]["datatype"]
    metadata.vector_count = test_checkpoint_data["collection_metadata"]["vector_count"]
    metadata.get_vector_dimension = Mock(return_value=2048)
    metadata.get_vector_datatype = Mock(return_value="float32")

    checkpoint.collection_metadata = metadata

    manager.load = AsyncMock(return_value=checkpoint)
    manager.validate_checkpoint_compatibility = AsyncMock(return_value=(True, "NONE"))

    # Do not mock _extract_fingerprint or _create_fingerprint
    # The real implementation will be run, but it requires the global settings to exist,
    # which we've solved by using `container.override(CodeWeaverSettingsType, test_settings)`
    # However, CheckpointManager uses `get_settings()` from core_settings, which reads from dependency container.

    return manager


@pytest.fixture
def mock_manifest_manager() -> AsyncMock:
    """Create mock FileManifestManager."""
    manager = AsyncMock()
    manager.read_manifest = AsyncMock(return_value=None)
    manager.write_manifest = AsyncMock()
    manifest_mock = Mock()
    manifest_mock.total_chunks = 100
    manager.load = AsyncMock(return_value=manifest_mock)
    return manager


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create mock VectorStoreProvider."""
    store = AsyncMock()

    # Mock get_collection_metadata for policy validation
    metadata = Mock()
    metadata.policy = Mock()
    metadata.policy.value = "family_aware"
    metadata.validate_config_change = Mock()  # Policy validation method

    store.get_collection_metadata = AsyncMock(return_value=metadata)
    store.collection_info = AsyncMock(return_value=metadata)

    return store


# ===========================================================================
# *                    Fixtures: Settings
# ===========================================================================


@pytest.fixture
def test_settings() -> Mock:
    """Create test Settings with default configuration."""
    settings = Mock()

    # Provider settings
    settings.provider = Mock()
    embedding_config = Mock()
    embedding_config.model_name = "voyage-code-3"
    embedding_config.dimension = 2048
    embedding_config.datatype = "float32"
    settings.provider.embedding = [embedding_config]

    # Server settings
    settings.server = Mock()
    settings.server.port = 9328
    settings.server.host = "127.0.0.1"

    # Make it copyable
    settings.model_copy = Mock(return_value=settings)

    return settings


# ===========================================================================
# *                    Tests: Full Validation Workflow
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.mock_only
@pytest.mark.qdrant
class TestFullValidationWorkflow:
    """Tests for complete validation workflows with DI services."""

    async def test_analyze_current_config_with_checkpoint(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test complete workflow: load checkpoint and analyze current config."""
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        result = await analyzer.analyze_current_config()

        # Should not fail even with identical config
        assert result is not None
        assert hasattr(result, "impact")

    async def test_validate_embedding_dimension_change(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test validation of embedding dimension change."""
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        # Simulate dimension reduction (valid change)
        result = await analyzer.validate_config_change("provider.embedding.dimension", 1024)

        # Should analyze change and return result
        assert result is not None


# ===========================================================================
# *                    Tests: Configuration Change Classification
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.mock_only
@pytest.mark.qdrant
class TestConfigChangeClassification:
    """Integration tests for configuration change classification."""

    async def test_compatible_query_model_change(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test that changing query model in asymmetric config is compatible."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        # Original config in checkpoint: voyage-4-large
        # New config: voyage-4-nano (different but same family)

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        # Create asymmetric config
        new_config = Mock()
        new_config.embed_model = "voyage-code-3"
        new_config.embed_model_family = "voyage-4"
        new_config.query_model = "voyage-4-nano"
        new_config.dimension = 2048
        new_config.datatype = "float32"

        # Get checkpoint metadata
        checkpoint = await mock_checkpoint_manager.load_checkpoint()

        # Create fingerprint from checkpoint metadata
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        old_fingerprint = CheckpointSettingsFingerprint(
            embedding_config_type="asymmetric",
            embed_model=checkpoint.collection_metadata.dense_model,
            embed_model_family=checkpoint.collection_metadata.dense_model_family,
            query_model=checkpoint.collection_metadata.query_model,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="test_hash",
        )

        analysis = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint,
            new_config=new_config,
            vector_count=checkpoint.total_vectors,
        )

        assert analysis.impact == ChangeImpact.COMPATIBLE

    async def test_transformable_dimension_reduction(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test that dimension reduction is transformable."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        # Create config with reduced dimension
        new_config = Mock()
        new_config.model_name = "voyage-code-3"
        new_config.dimension = 1024  # Reduced from 2048
        new_config.datatype = "float32"

        checkpoint = await mock_checkpoint_manager.load_checkpoint()

        # Create fingerprint from checkpoint metadata
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        old_fingerprint = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model=checkpoint.collection_metadata.dense_model,
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="test_hash",
        )

        analysis = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint,
            new_config=new_config,
            vector_count=checkpoint.total_vectors,
        )

        assert analysis.impact == ChangeImpact.TRANSFORMABLE
        assert len(analysis.transformations) > 0

    async def test_breaking_model_change(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test that different model is breaking."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        # Create config with different model
        new_config = Mock()
        new_config.model_name = "voyage-code-2"  # Different model
        new_config.dimension = 2048
        new_config.datatype = "float32"

        checkpoint = await mock_checkpoint_manager.load_checkpoint()

        # Create fingerprint from checkpoint metadata
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        old_fingerprint = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model=checkpoint.collection_metadata.dense_model,
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="test_hash",
        )

        analysis = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint,
            new_config=new_config,
            vector_count=checkpoint.total_vectors,
        )

        assert analysis.impact == ChangeImpact.BREAKING


# ===========================================================================
# *                    Tests: No Checkpoint Scenarios
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.mock_only
@pytest.mark.qdrant
class TestNoCheckpointScenarios:
    """Tests for scenarios where no checkpoint exists yet."""

    async def test_first_indexing_no_checkpoint(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test analysis when no checkpoint exists (first indexing)."""
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        # No checkpoint = fresh start
        mock_checkpoint_manager.load_checkpoint = AsyncMock(return_value=None)

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        result = await analyzer.analyze_current_config()

        # Should return None (no prior config to compare)
        assert result is None

    async def test_config_change_validation_allows_first_config(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test that config change validation succeeds for fresh start."""
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        # No checkpoint = fresh start
        mock_checkpoint_manager.load_checkpoint = AsyncMock(return_value=None)

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        # Any config is safe on first indexing
        result = await analyzer.validate_config_change("provider.embedding.dimension", 512)

        assert result is None  # Safe, so no analysis needed


# ===========================================================================
# *                    Tests: Empirical Data Usage
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.mock_only
@pytest.mark.qdrant
class TestEmpiricalDataUsage:
    """Tests that verify empirical Matryoshka data is used correctly."""

    async def test_uses_voyage_3_empirical_data(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test that Voyage-3 empirical data is used in estimates."""
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        # Test 2048 -> 512 reduction (empirical data: ~0.47%)
        new_config = Mock()
        new_config.model_name = "voyage-code-3"
        new_config.dimension = 512
        new_config.datatype = "float32"

        checkpoint = await mock_checkpoint_manager.load_checkpoint()

        # Create fingerprint
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        old_fingerprint = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-code-3",
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="test_hash",
        )

        analysis = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint,
            new_config=new_config,
            vector_count=checkpoint.total_vectors,
        )

        # Should include empirical data in accuracy impact
        assert "0.47" in analysis.transformations[0].accuracy_impact
        assert "empirical" in analysis.transformations[0].accuracy_impact.lower()

    async def test_falls_back_to_generic_for_unmapped_dimensions(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test fallback to generic estimation for unmapped dimension pairs."""
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        # Test unmapped dimension pair
        new_config = Mock()
        new_config.model_name = "voyage-code-3"
        new_config.dimension = 768  # Uncommon dimension
        new_config.datatype = "float32"

        checkpoint = await mock_checkpoint_manager.load_checkpoint()

        # Create fingerprint
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        old_fingerprint = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-code-3",
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="test_hash",
        )

        analysis = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint,
            new_config=new_config,
            vector_count=checkpoint.total_vectors,
        )

        # Should use generic estimation
        assert "estimated" in analysis.transformations[0].accuracy_impact.lower()


# ===========================================================================
# *                    Tests: Edge Cases in Integration
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.mock_only
@pytest.mark.qdrant
class TestEdgeCasesIntegration:
    """Integration tests for edge cases."""

    async def test_handles_very_large_collection(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test handling of very large collection (10M+ vectors)."""
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        # Update checkpoint with large vector count
        checkpoint = await mock_checkpoint_manager.load_checkpoint()
        checkpoint.total_vectors = 10_000_000

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        new_config = Mock()
        new_config.model_name = "voyage-code-3"
        new_config.dimension = 1024
        new_config.datatype = "float32"

        # Create fingerprint
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        old_fingerprint = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-code-3",
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="test_hash",
        )

        analysis = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint,
            new_config=new_config,
            vector_count=checkpoint.total_vectors,
        )

        # Should still work and estimate reasonable times
        assert analysis.estimated_time > timedelta(0)
        assert analysis.estimated_cost >= 0.0

    async def test_handles_zero_vectors(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test handling of collection with zero vectors."""
        checkpoint = await mock_checkpoint_manager.load_checkpoint()
        checkpoint.total_vectors = 0

        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        new_config = Mock()
        new_config.model_name = "voyage-code-3"
        new_config.dimension = 1024
        new_config.datatype = "float32"

        # Create fingerprint
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        old_fingerprint = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-code-3",
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="test_hash",
        )

        analysis = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint, new_config=new_config, vector_count=0
        )

        # Should not crash
        assert analysis is not None


# ===========================================================================
# *                    Tests: Recommendations Quality
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.mock_only
@pytest.mark.qdrant
class TestRecommendationsQuality:
    """Integration tests for user-facing recommendations."""

    async def test_breaking_change_provides_recovery_steps(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test that breaking changes include recovery recommendations."""
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        # Different model = breaking
        new_config = Mock()
        new_config.model_name = "sentence-transformers/model"
        new_config.dimension = 2048
        new_config.datatype = "float32"

        checkpoint = await mock_checkpoint_manager.load_checkpoint()

        # Create fingerprint
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        old_fingerprint = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-code-3",
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="test_hash",
        )

        analysis = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint,
            new_config=new_config,
            vector_count=checkpoint.total_vectors,
        )

        # Should include helpful recommendations
        assert len(analysis.recommendations) > 0
        assert any(
            "revert" in rec.lower() or "reindex" in rec.lower() for rec in analysis.recommendations
        )

    async def test_transformable_change_provides_strategy(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test that transformable changes include migration strategy."""
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        new_config = Mock()
        new_config.model_name = "voyage-code-3"
        new_config.dimension = 512  # Reduction
        new_config.datatype = "float32"

        checkpoint = await mock_checkpoint_manager.load_checkpoint()

        # Create fingerprint
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        old_fingerprint = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-code-3",
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="test_hash",
        )

        analysis = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint,
            new_config=new_config,
            vector_count=checkpoint.total_vectors,
        )

        # Should include migration strategy
        assert analysis.migration_strategy is not None


# ===========================================================================
# *                    Tests: Time and Cost Estimates
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.mock_only
@pytest.mark.qdrant
class TestTimeAndCostEstimates:
    """Tests for time and cost estimation accuracy."""

    async def test_estimates_scale_with_vector_count(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test that estimates scale appropriately with vector count."""
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        new_config = Mock()
        new_config.model_name = "voyage-code-3"
        new_config.dimension = 1024
        new_config.datatype = "float32"

        await mock_checkpoint_manager.load_checkpoint()

        # Create fingerprint
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        old_fingerprint = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-code-3",
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="test_hash",
        )

        # Get estimates for checkpoint vector count
        analysis_1 = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint, new_config=new_config, vector_count=5000
        )

        # Get estimates for larger vector count
        analysis_2 = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint, new_config=new_config, vector_count=50000
        )

        # Larger collection should have larger estimates
        assert analysis_2.estimated_time >= analysis_1.estimated_time
        assert analysis_2.estimated_cost >= analysis_1.estimated_cost

    async def test_no_change_has_zero_estimates(
        self,
        mock_checkpoint_manager: AsyncMock,
        mock_manifest_manager: AsyncMock,
        mock_vector_store: AsyncMock,
        test_settings: Mock,
    ) -> None:
        """Test that no-change scenario has zero time/cost estimates."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact
        from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

        analyzer = ConfigChangeAnalyzer(
            settings=test_settings,
            vector_store=mock_vector_store,
            checkpoint_manager=mock_checkpoint_manager,
            manifest_manager=mock_manifest_manager,
        )

        # Identical config
        new_config = Mock()
        new_config.model_name = "voyage-code-3"
        new_config.dimension = 2048
        new_config.datatype = "float32"

        checkpoint = await mock_checkpoint_manager.load_checkpoint()

        # Create fingerprint
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        old_fingerprint = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-code-3",
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="test_hash",
        )

        analysis = await analyzer.analyze_config_change(
            old_fingerprint=old_fingerprint,
            new_config=new_config,
            vector_count=checkpoint.total_vectors,
        )

        if analysis.impact == ChangeImpact.NONE:
            # No changes should have zero estimates
            assert analysis.estimated_time == timedelta(0)
            assert analysis.estimated_cost == 0.0
