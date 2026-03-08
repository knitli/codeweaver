# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for unified checkpoint compatibility interface.

Tests the family-aware checkpoint compatibility system that determines whether
an existing index can be reused when configuration changes.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codeweaver.core import BlakeKey, get_blake_hash
from codeweaver.engine.managers.checkpoint_manager import (
    ChangeImpact,
    CheckpointManager,
    CheckpointSettingsFingerprint,
    IndexingCheckpoint,
)
from codeweaver.providers.config.categories import (
    AsymmetricEmbeddingProviderSettings,
    EmbeddingProviderSettings,
)
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities, ModelFamily


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def temp_checkpoint_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for checkpoints."""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir


@pytest.fixture
def checkpoint_manager(temp_checkpoint_dir: Path) -> CheckpointManager:
    """Provide a CheckpointManager instance."""
    return CheckpointManager(
        project_path=Path("/test/project"),
        project_name="test_project",
        checkpoint_dir=temp_checkpoint_dir,
    )


@pytest.fixture
def mock_voyage_3_family() -> ModelFamily:
    """Mock Voyage 3 model family for testing."""
    return ModelFamily(
        family_id="voyage-3",
        default_dimension=1024,
        member_models=frozenset({"voyage-3", "voyage-3-lite"}),
        asymmetric_query_models=frozenset({"voyage-3-lite"}),
        output_dimensions=(512, 1024),
        cross_provider_compatible=True,
        default_dtype="float16",
        is_normalized=True,
        preferred_metrics=("cosine", "dot"),
    )


@pytest.fixture
def mock_voyage_2_family() -> ModelFamily:
    """Mock Voyage 2 model family for testing."""
    return ModelFamily(
        family_id="voyage-2",
        default_dimension=1024,
        member_models=frozenset({"voyage-2", "voyage-code-2"}),
        output_dimensions=(1024,),
        cross_provider_compatible=False,
        default_dtype="float32",
        is_normalized=False,
        preferred_metrics=("cosine",),
    )


# ===========================================================================
# CheckpointSettingsFingerprint Tests
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.external_api
@pytest.mark.mock_only
@pytest.mark.qdrant
@pytest.mark.unit
class TestCheckpointSettingsFingerprint:
    """Test CheckpointSettingsFingerprint compatibility logic."""

    def test_symmetric_no_change(self):
        """Test that identical symmetric configs show NONE impact."""
        fp1 = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )
        fp2 = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )

        is_compatible, impact = fp1.is_compatible_with(fp2)

        assert is_compatible
        assert impact == ChangeImpact.NONE

    def test_symmetric_model_change_breaks(self):
        """Test that changing embed model in symmetric mode is BREAKING."""
        fp_old = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-2",
            embed_model_family="voyage-2",
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )
        fp_new = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="def456",
        )

        is_compatible, impact = fp_new.is_compatible_with(fp_old)

        assert not is_compatible
        assert impact == ChangeImpact.BREAKING

    def test_asymmetric_query_change_compatible(self):
        """Test that query model changes within family are COMPATIBLE."""
        fp_old = CheckpointSettingsFingerprint(
            embedding_config_type="asymmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model="voyage-3",
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )
        fp_new = CheckpointSettingsFingerprint(
            embedding_config_type="asymmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model="voyage-3-lite",
            sparse_model=None,
            vector_store="qdrant",
            config_hash="def456",
        )

        is_compatible, impact = fp_new.is_compatible_with(fp_old)

        assert is_compatible
        assert impact == ChangeImpact.COMPATIBLE

    def test_asymmetric_embed_model_change_breaks(self):
        """Test that embed model changes even within family are BREAKING."""
        fp_old = CheckpointSettingsFingerprint(
            embedding_config_type="asymmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model="voyage-3-lite",
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )
        fp_new = CheckpointSettingsFingerprint(
            embedding_config_type="asymmetric",
            embed_model="voyage-3-lite",
            embed_model_family="voyage-3",
            query_model="voyage-3-lite",
            sparse_model=None,
            vector_store="qdrant",
            config_hash="def456",
        )

        is_compatible, impact = fp_new.is_compatible_with(fp_old)

        assert not is_compatible
        assert impact == ChangeImpact.BREAKING

    def test_asymmetric_family_change_breaks(self):
        """Test that model family changes are BREAKING."""
        fp_old = CheckpointSettingsFingerprint(
            embedding_config_type="asymmetric",
            embed_model="voyage-2",
            embed_model_family="voyage-2",
            query_model="voyage-2",
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )
        fp_new = CheckpointSettingsFingerprint(
            embedding_config_type="asymmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model="voyage-3",
            sparse_model=None,
            vector_store="qdrant",
            config_hash="def456",
        )

        is_compatible, impact = fp_new.is_compatible_with(fp_old)

        assert not is_compatible
        assert impact == ChangeImpact.BREAKING

    def test_sparse_model_change_breaks(self):
        """Test that sparse model changes are BREAKING."""
        fp_old = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model=None,
            sparse_model="bm25",
            vector_store="qdrant",
            config_hash="abc123",
        )
        fp_new = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model=None,
            sparse_model="splade",
            vector_store="qdrant",
            config_hash="def456",
        )

        is_compatible, impact = fp_new.is_compatible_with(fp_old)

        assert not is_compatible
        assert impact == ChangeImpact.BREAKING

    def test_vector_store_change_breaks(self):
        """Test that vector store changes are BREAKING."""
        fp_old = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )
        fp_new = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model=None,
            sparse_model=None,
            vector_store="inmemory",
            config_hash="def456",
        )

        is_compatible, impact = fp_new.is_compatible_with(fp_old)

        assert not is_compatible
        assert impact == ChangeImpact.BREAKING

    def test_asymmetric_no_family_info_breaks(self):
        """Test that asymmetric configs without family info are BREAKING."""
        fp_old = CheckpointSettingsFingerprint(
            embedding_config_type="asymmetric",
            embed_model="voyage-3",
            embed_model_family=None,
            query_model="voyage-3",
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )
        fp_new = CheckpointSettingsFingerprint(
            embedding_config_type="asymmetric",
            embed_model="voyage-3",
            embed_model_family=None,
            query_model="voyage-3-lite",
            sparse_model=None,
            vector_store="qdrant",
            config_hash="def456",
        )

        is_compatible, impact = fp_new.is_compatible_with(fp_old)

        assert not is_compatible
        assert impact == ChangeImpact.BREAKING


# ===========================================================================
# CheckpointManager Integration Tests
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.external_api
@pytest.mark.mock_only
@pytest.mark.qdrant
@pytest.mark.unit
class TestCheckpointManagerCompatibility:
    """Test CheckpointManager unified compatibility checking."""

    @pytest.mark.asyncio
    async def test_checkpoint_save_load_roundtrip(self, checkpoint_manager: CheckpointManager):
        """Test basic checkpoint save and load."""
        checkpoint = IndexingCheckpoint(
            project_path=Path("/test/project"), files_discovered=10, files_indexed=5
        )

        await checkpoint_manager.save(checkpoint)
        loaded = await checkpoint_manager.load()

        assert loaded is not None
        assert loaded.files_discovered == 10
        assert loaded.files_indexed == 5

    def test_fingerprint_extraction_from_checkpoint(
        self, checkpoint_manager: CheckpointManager, mock_voyage_3_family: ModelFamily
    ):
        """Test extracting fingerprint from checkpoint."""
        # Create a checkpoint with settings
        checkpoint = IndexingCheckpoint(
            project_path=Path("/test/project"),
            settings_hash=BlakeKey(get_blake_hash(b"test_settings")),
        )

        # Mock settings with symmetric config
        with patch(
            "codeweaver.engine.managers.checkpoint_manager.get_settings"
        ) as mock_get_settings:
            mock_embedding_config = MagicMock()
            mock_embedding_config.model_name = "voyage-3"
            mock_embedding_config.embedding_config.capabilities = EmbeddingModelCapabilities(
                model_name="voyage-3", model_family=mock_voyage_3_family, default_dimension=1024
            )

            mock_provider_settings = MagicMock()
            mock_provider_settings.embedding = [mock_embedding_config]
            mock_provider_settings.sparse_embedding = None
            mock_provider_settings.vector_store = [MagicMock(provider="qdrant")]

            mock_settings = MagicMock()
            mock_settings.provider = mock_provider_settings

            mock_get_settings.return_value = mock_settings

            fingerprint = checkpoint_manager._extract_fingerprint(checkpoint)

            assert fingerprint.embedding_config_type == "symmetric"
            assert fingerprint.embed_model == "voyage-3"
            assert fingerprint.embed_model_family == "voyage-3"
            assert fingerprint.query_model is None
            assert fingerprint.vector_store == "qdrant"

    def test_fingerprint_creation_from_config(
        self, checkpoint_manager: CheckpointManager, mock_voyage_3_family: ModelFamily
    ):
        """Test creating fingerprint from new config."""
        # Mock settings and config
        with patch(
            "codeweaver.engine.managers.checkpoint_manager.get_settings"
        ) as mock_get_settings:
            mock_embedding_config = MagicMock(spec=EmbeddingProviderSettings)
            mock_embedding_config.model_name = "voyage-3"
            mock_embedding_config.embedding_config.capabilities = EmbeddingModelCapabilities(
                model_name="voyage-3", model_family=mock_voyage_3_family, default_dimension=1024
            )

            mock_provider_settings = MagicMock()
            mock_provider_settings.sparse_embedding = None
            mock_provider_settings.vector_store = [MagicMock(provider="qdrant")]

            mock_settings = MagicMock()
            mock_settings.provider = mock_provider_settings

            mock_get_settings.return_value = mock_settings

            with patch(
                "codeweaver.engine.managers.checkpoint_manager.get_checkpoint_settings_map"
            ) as mock_map:
                mock_map.return_value = {}

                fingerprint = checkpoint_manager._create_fingerprint(mock_embedding_config)

                assert fingerprint.embedding_config_type == "symmetric"
                assert fingerprint.embed_model == "voyage-3"
                assert fingerprint.embed_model_family == "voyage-3"
                assert fingerprint.vector_store == "qdrant"

    def test_is_index_valid_for_compatible_change(
        self, checkpoint_manager: CheckpointManager, mock_voyage_3_family: ModelFamily
    ):
        """Test that compatible query model changes don't invalidate index."""
        checkpoint = IndexingCheckpoint(
            project_path=Path("/test/project"),
            settings_hash=BlakeKey(get_blake_hash(b"old_settings")),
        )

        # Mock old config: asymmetric with voyage-3/voyage-3
        with patch(
            "codeweaver.engine.managers.checkpoint_manager.get_settings"
        ) as mock_get_settings:
            # Setup old config (for extraction)
            mock_embed_provider_old = MagicMock()
            mock_embed_provider_old.model_name = "voyage-3"
            mock_embed_provider_old.embedding_config.capabilities = EmbeddingModelCapabilities(
                model_name="voyage-3", model_family=mock_voyage_3_family, default_dimension=1024
            )

            mock_query_provider_old = MagicMock()
            mock_query_provider_old.model_name = "voyage-3"

            mock_old_embedding = MagicMock(spec=AsymmetricEmbeddingProviderSettings)
            mock_old_embedding.embed_provider = mock_embed_provider_old
            mock_old_embedding.query_provider = mock_query_provider_old

            # Setup new config: asymmetric with voyage-3/voyage-3-lite
            mock_embed_provider_new = MagicMock()
            mock_embed_provider_new.model_name = "voyage-3"
            mock_embed_provider_new.embedding_config.capabilities = EmbeddingModelCapabilities(
                model_name="voyage-3", model_family=mock_voyage_3_family, default_dimension=1024
            )

            mock_query_provider_new = MagicMock()
            mock_query_provider_new.model_name = "voyage-3-lite"

            mock_new_embedding = MagicMock(spec=AsymmetricEmbeddingProviderSettings)
            mock_new_embedding.embed_provider = mock_embed_provider_new
            mock_new_embedding.query_provider = mock_query_provider_new

            mock_provider_settings = MagicMock()
            mock_provider_settings.embedding = [mock_old_embedding]
            mock_provider_settings.sparse_embedding = None
            mock_provider_settings.vector_store = [MagicMock(provider="qdrant")]

            mock_settings = MagicMock()
            mock_settings.provider = mock_provider_settings

            mock_get_settings.return_value = mock_settings

            with patch(
                "codeweaver.engine.managers.checkpoint_manager.get_checkpoint_settings_map"
            ) as mock_map:
                mock_map.return_value = {}

                # First call extracts old, second call creates new
                is_valid, impact = checkpoint_manager.is_index_valid_for_config(
                    checkpoint, mock_new_embedding
                )

                assert is_valid
                assert impact == ChangeImpact.COMPATIBLE

    def test_is_index_valid_for_breaking_change(
        self,
        checkpoint_manager: CheckpointManager,
        mock_voyage_3_family: ModelFamily,
        mock_voyage_2_family: ModelFamily,
    ):
        """Test that model family changes invalidate index."""
        checkpoint = IndexingCheckpoint(
            project_path=Path("/test/project"),
            settings_hash=BlakeKey(get_blake_hash(b"old_settings")),
        )

        with patch(
            "codeweaver.engine.managers.checkpoint_manager.get_settings"
        ) as mock_get_settings:
            # Setup old config: voyage-2
            mock_old_embedding = MagicMock(spec=EmbeddingProviderSettings)
            mock_old_embedding.model_name = "voyage-2"
            mock_old_embedding.embedding_config.capabilities = EmbeddingModelCapabilities(
                model_name="voyage-2", model_family=mock_voyage_2_family, default_dimension=1024
            )

            # Setup new config: voyage-3
            mock_new_embedding = MagicMock(spec=EmbeddingProviderSettings)
            mock_new_embedding.model_name = "voyage-3"
            mock_new_embedding.embedding_config.capabilities = EmbeddingModelCapabilities(
                model_name="voyage-3", model_family=mock_voyage_3_family, default_dimension=1024
            )

            mock_provider_settings = MagicMock()
            mock_provider_settings.embedding = [mock_old_embedding]
            mock_provider_settings.sparse_embedding = None
            mock_provider_settings.vector_store = [MagicMock(provider="qdrant")]

            mock_settings = MagicMock()
            mock_settings.provider = mock_provider_settings

            mock_get_settings.return_value = mock_settings

            with patch(
                "codeweaver.engine.managers.checkpoint_manager.get_checkpoint_settings_map"
            ) as mock_map:
                mock_map.return_value = {}

                is_valid, impact = checkpoint_manager.is_index_valid_for_config(
                    checkpoint, mock_new_embedding
                )

                assert not is_valid
                assert impact == ChangeImpact.BREAKING


# ===========================================================================
# Edge Cases
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.external_api
@pytest.mark.mock_only
@pytest.mark.qdrant
@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_none_sparse_model_compatibility(self):
        """Test that None sparse models are compatible."""
        fp1 = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )
        fp2 = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )

        is_compatible, impact = fp1.is_compatible_with(fp2)

        assert is_compatible
        assert impact == ChangeImpact.NONE

    def test_none_to_some_sparse_model_breaks(self):
        """Test that adding sparse model is BREAKING."""
        fp_old = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )
        fp_new = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="voyage-3",
            embed_model_family="voyage-3",
            query_model=None,
            sparse_model="bm25",
            vector_store="qdrant",
            config_hash="def456",
        )

        is_compatible, impact = fp_new.is_compatible_with(fp_old)

        assert not is_compatible
        assert impact == ChangeImpact.BREAKING

    def test_empty_model_names(self):
        """Test handling of empty model names."""
        fp1 = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="",
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )
        fp2 = CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model="",
            embed_model_family=None,
            query_model=None,
            sparse_model=None,
            vector_store="qdrant",
            config_hash="abc123",
        )

        is_compatible, impact = fp1.is_compatible_with(fp2)

        # Empty models should still match if identical
        assert is_compatible
        assert impact == ChangeImpact.NONE
