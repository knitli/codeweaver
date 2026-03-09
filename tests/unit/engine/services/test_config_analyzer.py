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

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock

import pytest


if TYPE_CHECKING:
    pass


# ===========================================================================
# *                    Fixtures: Dependencies
# ===========================================================================


@pytest.fixture
def mock_settings() -> Mock:
    """Create mock Settings with embedding configuration."""
    settings = Mock()
    settings.provider = Mock()
    embedding_config = Mock()
    embedding_config.model_name = "voyage-code-3"
    embedding_config.dimension = 2048
    embedding_config.datatype = "float32"
    settings.provider.embedding = [embedding_config]
    embedding_config = Mock()
    embedding_config.model_name = "voyage-code-3"
    embedding_config.dimension = 2048
    embedding_config.datatype = "float32"
    settings.provider.embedding = [embedding_config]
    settings.model_copy = Mock(return_value=settings)
    return settings


@pytest.fixture
def mock_checkpoint_manager() -> Mock:
    """Create mock CheckpointManager."""
    manager = Mock(spec=["load", "_create_fingerprint", "_extract_fingerprint"])
    manager.load = AsyncMock(return_value=None)

    # mock _create_fingerprint to return something compatible with analysis
    def create_fp(config):
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact
        fp = Mock()
        fp.embed_model = str(getattr(config, "model_name", "voyage-code-3"))
        fp.dimension = getattr(config, "dimension", 2048)
        fp.datatype = getattr(config, "datatype", "float32")
        fp.embedding_config_type = "symmetric"

        # Real logic for is_compatible_with that takes ANOTHER fingerprint
        def is_compatible_with(other):
            if fp.embed_model != other.embed_model:
                return (False, ChangeImpact.BREAKING)
            if fp.dimension > other.dimension:
                return (False, ChangeImpact.BREAKING)
            if fp.dimension < other.dimension:
                return (True, ChangeImpact.TRANSFORMABLE)
            if fp.datatype != other.datatype:
                return (True, ChangeImpact.QUANTIZABLE)
            return (True, ChangeImpact.NONE)

        fp.is_compatible_with = Mock(side_effect=is_compatible_with)
        # Mock unpacking
        fp.__iter__ = Mock(side_effect=lambda: iter(is_compatible_with(fp)))
        return fp

    manager._create_fingerprint = Mock(side_effect=create_fp)
    manager._extract_fingerprint = Mock(side_effect=create_fp)
    return manager


@pytest.fixture
def mock_manifest_manager() -> Mock:
    """Create mock FileManifestManager."""
    manager = Mock(spec=["read_manifest", "load"])
    manager = Mock(spec=["read_manifest", "load"])
    manager.read_manifest = AsyncMock(return_value=None)
    manager.load = AsyncMock(return_value=None)
    manager.load = AsyncMock(return_value=None)
    return manager


# ===========================================================================
# *                    Helper Functions & Fixtures
# ===========================================================================


@pytest.fixture
def collection_metadata() -> Mock:
    """Create mock CollectionMetadata for testing."""
    from codeweaver.engine.managers.checkpoint_manager import ChangeImpact
    from codeweaver.engine.managers.checkpoint_manager import ChangeImpact
    metadata = Mock()
    metadata.embed_model = "voyage-code-3"
    metadata.embed_model = "voyage-code-3"
    metadata.dense_model = "voyage-code-3"
    metadata.dense_model_family = "voyage-4"
    metadata.query_model = "voyage-4-large"
    metadata.dimension = 2048
    metadata.datatype = "float32"
    metadata.embedding_config_type = "symmetric"
    metadata.embedding_config_type = "symmetric"

    # Add methods
    metadata.get_vector_dimension = Mock(return_value=2048)
    metadata.get_vector_datatype = Mock(return_value="float32")

    # This mock needs to handle comparison with ANOTHER fingerprint/metadata
    def is_compatible_with(other):
        other_embed_model = getattr(other, "embed_model", str(other))
        other_dim = getattr(other, "dimension", 0)
        other_dtype = getattr(other, "datatype", "")

        if metadata.embed_model != other_embed_model:
            return (False, ChangeImpact.BREAKING)
        if metadata.dimension > other_dim:
            return (False, ChangeImpact.BREAKING)
        if metadata.dimension < other_dim:
            return (True, ChangeImpact.TRANSFORMABLE)
        if metadata.datatype != other_dtype:
            return (True, ChangeImpact.QUANTIZABLE)
        return (True, ChangeImpact.NONE)

    metadata.is_compatible_with = Mock(side_effect=is_compatible_with)
    metadata.__iter__ = Mock(side_effect=lambda: iter(is_compatible_with(metadata)))

    return metadata


@pytest.fixture
def embedding_config() -> Mock:
    """Create mock SymmetricEmbeddingConfig."""
    config = Mock()
    config.model_name = "voyage-code-3"
    config.dimension = 2048
    config.datatype = "float32"

    # Mock for _models_compatible
    config.embedding_config = Mock()
    config.embedding_config.capabilities = Mock()
    config.embedding_config.capabilities.model_family = Mock()
    config.embedding_config.capabilities.model_family.family_id = "voyage-4"

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

    # Nested structure
    config.embed_provider = Mock()
    config.embed_provider.model_name = "voyage-code-3"
    config.embed_provider.embedding_config = Mock()
    config.embed_provider.embedding_config.dimension = 2048
    config.embed_provider.embedding_config.datatype = "float32"
    config.embed_provider.embedding_config.capabilities = Mock()
    config.embed_provider.embedding_config.capabilities.model_family = Mock()
    config.embed_provider.embedding_config.capabilities.model_family.family_id = "voyage-4"

    config.query_provider = Mock()
    config.query_provider.model_name = "voyage-4-large"
    config.query_provider.embedding_config = Mock()

    return config


@pytest.fixture
def mock_vector_store() -> Mock:
    """Create mock VectorStoreProvider for ConfigChangeAnalyzer."""
    store = Mock()
    store.collection_info = AsyncMock(return_value=None)
    store.collection_info = AsyncMock(return_value=None)
    return store


@pytest.fixture
def config_analyzer(
    mock_settings: Mock,
    mock_checkpoint_manager: Mock,
    mock_manifest_manager: Mock,
    mock_vector_store: Mock,
) -> Any:
) -> Any:
    """Create ConfigChangeAnalyzer with mock dependencies."""
    from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

    return ConfigChangeAnalyzer(
        settings=mock_settings,
        checkpoint_manager=mock_checkpoint_manager,
        manifest_manager=mock_manifest_manager,
        vector_store=mock_vector_store,
    )


# ===========================================================================
# *                    Tests: Analyze Current Config
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.unit
class TestAnalyzeCurrentConfig:
    """Tests for analyze_current_config method."""

    async def test_no_checkpoint_returns_none(
        self, config_analyzer: Any, mock_checkpoint_manager: Mock
        self, config_analyzer: Any, mock_checkpoint_manager: Mock
    ) -> None:
        """Test that None is returned when no checkpoint exists."""
        mock_checkpoint_manager.load = AsyncMock(return_value=None)
        mock_checkpoint_manager.load = AsyncMock(return_value=None)

        result = await config_analyzer.analyze_current_config()

        assert result is None
        mock_checkpoint_manager.load.assert_called_once()
        mock_checkpoint_manager.load.assert_called_once()

    async def test_loads_checkpoint_metadata(
        self, config_analyzer: Any, mock_checkpoint_manager: Mock, collection_metadata: Mock
        self, config_analyzer: Any, mock_checkpoint_manager: Mock, collection_metadata: Mock
    ) -> None:
        """Test that checkpoint metadata is loaded correctly."""
        checkpoint = Mock()
        checkpoint.collection_metadata = collection_metadata
        checkpoint.total_vectors = 1000
        mock_checkpoint_manager.load = AsyncMock(return_value=checkpoint)
        mock_checkpoint_manager.load = AsyncMock(return_value=checkpoint)

        # Mock the analyze_config_change method to verify it's called
        config_analyzer.analyze_config_change = AsyncMock(return_value=Mock(impact="COMPATIBLE"))

        result = await config_analyzer.analyze_current_config()

        assert result is not None
        config_analyzer.analyze_config_change.assert_called_once()

    async def test_calls_analyze_with_current_config(
        self, config_analyzer: Any, mock_checkpoint_manager: Mock, collection_metadata: Mock
        self, config_analyzer: Any, mock_checkpoint_manager: Mock, collection_metadata: Mock
    ) -> None:
        """Test that analyze_config_change is called with current settings."""
        checkpoint = Mock()
        checkpoint.collection_metadata = collection_metadata
        checkpoint.total_vectors = 5000
        mock_checkpoint_manager.load = AsyncMock(return_value=checkpoint)
        mock_checkpoint_manager.load = AsyncMock(return_value=checkpoint)

        config_analyzer.analyze_config_change = AsyncMock(return_value=Mock(impact="COMPATIBLE"))

        await config_analyzer.analyze_current_config()

        # Verify the call includes current embedding config
        call_kwargs = config_analyzer.analyze_config_change.call_args[1]
        assert "vector_count" in call_kwargs
        assert call_kwargs["old_fingerprint"] is not None
        assert "vector_count" in call_kwargs
        assert call_kwargs["old_fingerprint"] is not None


# ===========================================================================
# *                    Tests: Model Compatibility
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.unit
class TestModelCompatibility:
    """Tests for _models_compatible method."""

    def test_symmetric_same_model_is_compatible(
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
    ) -> None:
        """Test that same symmetric model is compatible."""
        embedding_config.model_name = "voyage-code-3"
        collection_metadata.dense_model = "voyage-code-3"
        collection_metadata.dense_model_family = "voyage-4"
        collection_metadata.dense_model = "voyage-code-3"
        collection_metadata.dense_model_family = "voyage-4"

        result = config_analyzer._models_compatible(collection_metadata, embedding_config)

        assert result is True

    def test_symmetric_different_model_is_incompatible(
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
    ) -> None:
        """Test that different symmetric model is incompatible."""
        embedding_config.model_name = "voyage-code-2"
        embedding_config.embedding_config.capabilities.model_family.family_id = "voyage-2"
        collection_metadata.dense_model_family = "voyage-4"
        embedding_config.embedding_config.capabilities.model_family.family_id = "voyage-2"
        collection_metadata.dense_model_family = "voyage-4"

        result = config_analyzer._models_compatible(collection_metadata, embedding_config)

        assert result is False

    def test_asymmetric_same_family_compatible(
        self, config_analyzer: Any, collection_metadata: Mock, asymmetric_embedding_config: Mock
        self, config_analyzer: Any, collection_metadata: Mock, asymmetric_embedding_config: Mock
    ) -> None:
        """Test that asymmetric with same family and embed model is compatible."""
        from codeweaver.providers.config.categories import AsymmetricEmbeddingProviderSettings

        # Make asymmetric_embedding_config appear as the correct type
        asymmetric_embedding_config.__class__ = AsymmetricEmbeddingProviderSettings

        asymmetric_embedding_config.embed_provider.model_name = "voyage-code-3"
        collection_metadata.dense_model = "voyage-code-3"
        collection_metadata.dense_model_family = "voyage-4"

        # Mock capabilities
        embed_caps = Mock()
        embed_caps.model_family = Mock()
        embed_caps.model_family.family_id = "voyage-4"
        asymmetric_embedding_config.embed_provider.embedding_config.capabilities = embed_caps

        result = config_analyzer._models_compatible(
            collection_metadata, asymmetric_embedding_config
        )

        assert result is True


# ===========================================================================
# *                    Tests: Configuration Change Analysis
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.unit
class TestAnalyzeConfigChangeNoChange:
    """Tests for no-change scenarios."""

    async def test_identical_config_returns_none_impact(
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
    ) -> None:
        """Test that identical config returns NONE impact."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        embedding_config.model_name = "voyage-code-3"
        embedding_config.dimension = 2048
        embedding_config.datatype = "float32"

        # Ensure helper returns correct dimension
        embedding_config.embedding_config = Mock()
        embedding_config.embedding_config.dimension = 2048
        embedding_config.embedding_config.datatype = "float32"

        # Setup fingerprints to match
        old_fp = Mock()
        old_fp.embed_model = "voyage-code-3"
        old_fp.dimension = 2048
        old_fp.datatype = "float32"
        old_fp.embedding_config_type = "symmetric"
        old_fp.is_compatible_with = Mock(return_value=(True, ChangeImpact.NONE))
        old_fp.__iter__ = Mock(return_value=iter([True, ChangeImpact.NONE]))

        # Mock compatible models
        config_analyzer._models_compatible = Mock(return_value=True)

        analysis = await config_analyzer.analyze_config_change(
            old_fingerprint=old_fp, new_config=embedding_config, vector_count=1000
            old_fingerprint=old_fp, new_config=embedding_config, vector_count=1000
        )

        assert analysis.impact == ChangeImpact.NONE


# ===========================================================================
# *                    Tests: Breaking Changes
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.unit
class TestAnalyzeConfigChangeBreaking:
    """Tests for breaking change detection."""

    async def test_incompatible_models_returns_breaking(
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
    ) -> None:
        """Test that incompatible models return BREAKING impact."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        embedding_config.model_name = "voyage-code-2"
        # Old FP is different model
        collection_metadata.embed_model = "voyage-code-3"
        # Old FP is different model
        collection_metadata.embed_model = "voyage-code-3"

        # Mock incompatible models
        config_analyzer._models_compatible = Mock(return_value=False)

        analysis = await config_analyzer.analyze_config_change(
            old_fingerprint=collection_metadata, new_config=embedding_config, vector_count=1000
            old_fingerprint=collection_metadata, new_config=embedding_config, vector_count=1000
        )

        assert analysis.impact == ChangeImpact.BREAKING

    async def test_dimension_increase_returns_breaking(
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
    ) -> None:
        """Test that dimension increase returns BREAKING impact."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        embedding_config.model_name = "voyage-code-3"
        embedding_config.embedding_config = Mock()
        embedding_config.embedding_config.dimension = 4096  # Increase

        old_fp = Mock()
        old_fp.embed_model = "voyage-code-3"
        old_fp.dimension = 2048
        old_fp.datatype = "float32"
        old_fp.is_compatible_with = Mock(return_value=(False, ChangeImpact.BREAKING))
        old_fp.__iter__ = Mock(return_value=iter([False, ChangeImpact.BREAKING]))

        config_analyzer._models_compatible = Mock(return_value=True)

        analysis = await config_analyzer.analyze_config_change(
            old_fingerprint=old_fp, new_config=embedding_config, vector_count=1000
            old_fingerprint=old_fp, new_config=embedding_config, vector_count=1000
        )

        assert analysis.impact == ChangeImpact.BREAKING


# ===========================================================================
# *                    Tests: Quantization
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.unit
class TestAnalyzeConfigChangeQuantization:
    """Tests for quantization scenarios."""

    async def test_valid_quantization_returns_quantizable(
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
    ) -> None:
        """Test that valid quantization returns QUANTIZABLE impact."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        embedding_config.model_name = "voyage-code-3"
        embedding_config.embedding_config = Mock()
        embedding_config.embedding_config.datatype = "int8"
        embedding_config.embedding_config.dimension = 2048

        old_fp = Mock()
        old_fp.embed_model = "voyage-code-3"
        old_fp.dimension = 2048
        old_fp.datatype = "float32"

        # classification trigger
        old_fp.is_compatible_with = Mock(return_value=(True, ChangeImpact.QUANTIZABLE))
        old_fp.__iter__ = Mock(return_value=iter([True, ChangeImpact.QUANTIZABLE]))

        config_analyzer._models_compatible = Mock(return_value=True)
        config_analyzer._is_valid_quantization = Mock(return_value=True)

        analysis = await config_analyzer.analyze_config_change(
            old_fingerprint=old_fp, new_config=embedding_config, vector_count=1000
            old_fingerprint=old_fp, new_config=embedding_config, vector_count=1000
        )

        assert analysis.impact == ChangeImpact.QUANTIZABLE

# ===========================================================================
# *                    Tests: Dimension Reduction
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.unit
class TestAnalyzeConfigChangeDimensionReduction:
    """Tests for dimension reduction scenarios."""

    async def test_dimension_reduction_returns_transformable(
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
        self, config_analyzer: Any, collection_metadata: Mock, embedding_config: Mock
    ) -> None:
        """Test that dimension reduction returns TRANSFORMABLE impact."""
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        embedding_config.model_name = "voyage-code-3"
        embedding_config.embedding_config = Mock()
        embedding_config.embedding_config.dimension = 1024
        embedding_config.embedding_config.datatype = "float32"

        old_fp = Mock()
        old_fp.embed_model = "voyage-code-3"
        old_fp.dimension = 2048
        old_fp.datatype = "float32"

        # classification trigger
        old_fp.is_compatible_with = Mock(return_value=(True, ChangeImpact.TRANSFORMABLE))
        old_fp.__iter__ = Mock(return_value=iter([True, ChangeImpact.TRANSFORMABLE]))

        config_analyzer._models_compatible = Mock(return_value=True)
        config_analyzer._estimate_matryoshka_impact = Mock(return_value="~0.5% (empirical)")

        analysis = await config_analyzer.analyze_config_change(
            old_fingerprint=old_fp, new_config=embedding_config, vector_count=1000
            old_fingerprint=old_fp, new_config=embedding_config, vector_count=1000
        )

        assert analysis.impact == ChangeImpact.TRANSFORMABLE


# ===========================================================================
# *                    Tests: Matryoshka Impact Estimation
# ===========================================================================


@pytest.mark.config
@pytest.mark.unit
class TestMatryoshkaImpactEstimation:
    """Tests for Matryoshka impact estimation with empirical data."""

    def test_voyage_code_3_empirical_2048_to_1024(self, config_analyzer: Any) -> None:
    def test_voyage_code_3_empirical_2048_to_1024(self, config_analyzer: Any) -> None:
        """Test empirical Voyage-3 impact for 2048->1024 reduction."""
        impact = config_analyzer._estimate_matryoshka_impact("voyage-code-3", 2048, 1024)

        assert "0.04" in impact or "0.0%" in impact
        assert "empirical" in impact.lower()


# ===========================================================================
# *                    Tests: Config Change Simulation
# ===========================================================================


@pytest.mark.config
@pytest.mark.unit
class TestSimulateConfigChange:
    """Tests for config change simulation."""

    def test_simulate_creates_copy(self, config_analyzer: Any, mock_settings: Mock) -> None:
        """Test that simulation creates a new settings object."""
        # Setup mock hierarchy to allow deepcopy and field access
        def mock_copy():
            new_mock = Mock()
            new_mock.provider = Mock()
            new_mock.provider.embedding = [Mock()]
            return new_mock

        mock_settings.__deepcopy__ = Mock(side_effect=lambda memo: mock_copy())

        new_settings = config_analyzer._simulate_config_change("provider", Mock())

        # Should be different objects
        assert new_settings is not mock_settings
        # Should be different objects
        assert new_settings is not mock_settings


# ===========================================================================
# *                    Tests: Policy Enforcement Integration
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.config
@pytest.mark.unit
class TestPolicyEnforcement:
    """Tests for collection policy enforcement."""

    async def test_strict_policy_blocks_change(
        self, config_analyzer: Any, mock_vector_store: Mock, embedding_config: Mock, collection_metadata: Mock
    """Tests for collection policy enforcement."""

    async def test_strict_policy_blocks_change(
        self, config_analyzer: Any, mock_vector_store: Mock, embedding_config: Mock, collection_metadata: Mock
    ) -> None:
        """Test that STRICT policy blocks any configuration change."""
        from codeweaver.core.exceptions import ConfigurationLockError
        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact
        from codeweaver.providers.types.vector_store import CollectionPolicy

        collection_metadata.policy = CollectionPolicy.STRICT
        mock_vector_store.collection_info.return_value = collection_metadata

        # Mock validate_config_change to raise policy error
        collection_metadata.validate_config_change = Mock(side_effect=ConfigurationLockError("Strict policy blocks change"))

        # Create different model
        # Create different model
        embedding_config.model_name = "voyage-4-large"
        collection_metadata.embed_model = "voyage-code-3"

        old_fp = Mock()
        old_fp.embed_model = "voyage-code-3"
        old_fp.dimension = 2048
        old_fp.datatype = "float32"
        # Tuple for unpacking
        old_fp.is_compatible_with = Mock(return_value=(False, ChangeImpact.BREAKING))
        old_fp.__iter__ = Mock(return_value=iter([False, ChangeImpact.BREAKING]))

        analysis = await config_analyzer.analyze_config_change(
            old_fingerprint=old_fp, new_config=embedding_config, vector_count=1000
        )

        assert analysis.impact == ChangeImpact.BREAKING
        # Use more robust check for policy mention
        assert any("policy" in str(rec).lower() for rec in analysis.recommendations) or "policy" in analysis.accuracy_impact.lower()
        # Use more robust check for policy mention
        assert any("policy" in str(rec).lower() for rec in analysis.recommendations) or "policy" in analysis.accuracy_impact.lower()
