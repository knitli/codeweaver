# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration tests for WalConfig merging with FailoverSettings.

Tests the integration between user-configured WalConfig and failover
WalConfig settings through the DI container, ensuring proper precedence
and graceful fallback in real scenarios.
"""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration]


@pytest.fixture
def wal_config():
    """Create a user WalConfig."""
    from codeweaver.providers.config.kinds import WalConfig

    return WalConfig(
        wal_capacity_mb=128,  # User wants 128MB
        wal_segments_ahead=1,  # User wants 1 segment
    )


class TestWalConfigIntegration:
    """Integration tests for WalConfig merging when backup system is enabled."""

    @pytest.mark.asyncio
    async def test_wal_config_merges_failover_when_backup_enabled(self, wal_config, tmp_path: Path):
        """Test that failover WalConfig takes precedence when backup system is enabled."""
        from unittest.mock import Mock

        from pydantic import AnyUrl

        from codeweaver.core import Provider
        from codeweaver.engine.config.failover import FailoverSettings
        from codeweaver.providers import CollectionMetadata
        from codeweaver.providers.config.kinds import (
            CollectionConfig,
            QdrantClientOptions,
            QdrantVectorStoreProviderSettings,
        )
        from codeweaver.providers.types import EmbeddingCapabilityGroup

        # Create failover settings with backup enabled
        failover_settings = FailoverSettings(
            disable_failover=False,  # Backup system enabled
            wal_capacity_mb=256,  # Failover wants 256MB
            wal_segments_ahead=2,  # Failover wants 2 segments
            snapshot_storage_path=str(tmp_path / "snapshots"),
        )

        # Create mock embedding group (no DI container needed)
        mock_embedding = Mock(spec=EmbeddingCapabilityGroup)
        mock_embedding.as_vector_params.return_value = Mock(
            vectors=Mock(
                model_dump=Mock(return_value={"default": {"size": 768, "distance": "Cosine"}})
            ),
            sparse_vectors={},
        )

        # Create provider settings with user WalConfig
        settings = QdrantVectorStoreProviderSettings(
            provider=Provider.QDRANT,
            client_options=QdrantClientOptions(url=AnyUrl("http://localhost:6333")),
            collection=CollectionConfig(
                collection_name="test_collection",
                wal_config=wal_config,  # User's WalConfig
            ),
        )

        # Create metadata
        metadata = CollectionMetadata(
            provider="test-provider",
            project_name="test-project",
            dense_vector_size=768,
            sparse_vector_size=1000,
            distance_metric="cosine",
            collection_name="test_collection",
        )

        # Call get_collection_config with explicit dependencies (no DI container!)
        result = await settings.get_collection_config(
            metadata, embedding_group=mock_embedding, failover_settings=failover_settings
        )

        # Verify failover settings took precedence
        assert result.wal_config is not None
        assert result.wal_config.wal_capacity_mb == 256  # Failover value
        assert result.wal_config.wal_segments_ahead == 2  # Failover value

    @pytest.mark.asyncio
    async def test_wal_config_uses_user_config_when_failover_disabled(
        self, wal_config, tmp_path: Path
    ):
        """Test that user WalConfig is preserved when failover is disabled."""
        from unittest.mock import Mock

        from pydantic import AnyUrl

        from codeweaver.core import Provider
        from codeweaver.engine.config.failover import FailoverSettings
        from codeweaver.providers import CollectionMetadata
        from codeweaver.providers.config.kinds import (
            CollectionConfig,
            QdrantClientOptions,
            QdrantVectorStoreProviderSettings,
        )
        from codeweaver.providers.types import EmbeddingCapabilityGroup

        # Create failover settings with backup DISABLED
        failover_settings = FailoverSettings(
            disable_failover=True,  # Backup system disabled
            wal_capacity_mb=256,  # These values should be ignored
            wal_segments_ahead=2,
            snapshot_storage_path=str(tmp_path / "snapshots"),
        )

        # Create mock embedding group
        mock_embedding = Mock(spec=EmbeddingCapabilityGroup)
        mock_embedding.as_vector_params.return_value = Mock(
            vectors=Mock(
                model_dump=Mock(return_value={"default": {"size": 768, "distance": "Cosine"}})
            ),
            sparse_vectors={},
        )

        # Create provider settings with user WalConfig
        settings = QdrantVectorStoreProviderSettings(
            provider=Provider.QDRANT,
            client_options=QdrantClientOptions(url=AnyUrl("http://localhost:6333")),
            collection=CollectionConfig(
                collection_name="test_collection",
                wal_config=wal_config,  # User's WalConfig
            ),
        )

        # Create metadata
        metadata = CollectionMetadata(
            provider="test-provider",
            project_name="test-project",
            dense_vector_size=768,
            sparse_vector_size=1000,
            distance_metric="cosine",
            collection_name="test_collection",
        )

        # Call get_collection_config with explicit dependencies
        result = await settings.get_collection_config(
            metadata, embedding_group=mock_embedding, failover_settings=failover_settings
        )

        # Verify user settings were preserved (no merging happened)
        assert result.wal_config is not None
        assert result.wal_config.wal_capacity_mb == 128  # User value
        assert result.wal_config.wal_segments_ahead == 1  # User value

    @pytest.mark.asyncio
    async def test_wal_config_creates_default_when_none_exists(self, tmp_path: Path):
        """Test that WalConfig is created from failover settings when user has none."""
        from unittest.mock import Mock

        from pydantic import AnyUrl

        from codeweaver.core import Provider
        from codeweaver.engine.config.failover import FailoverSettings
        from codeweaver.providers import CollectionMetadata
        from codeweaver.providers.config.kinds import (
            CollectionConfig,
            QdrantClientOptions,
            QdrantVectorStoreProviderSettings,
        )
        from codeweaver.providers.types import EmbeddingCapabilityGroup

        # Create failover settings with backup enabled
        failover_settings = FailoverSettings(
            disable_failover=False,
            wal_capacity_mb=256,
            wal_segments_ahead=2,
            snapshot_storage_path=str(tmp_path / "snapshots"),
        )

        # Create mock embedding group
        mock_embedding = Mock(spec=EmbeddingCapabilityGroup)
        mock_embedding.as_vector_params.return_value = Mock(
            vectors=Mock(
                model_dump=Mock(return_value={"default": {"size": 768, "distance": "Cosine"}})
            ),
            sparse_vectors={},
        )

        # Create provider settings WITHOUT user WalConfig
        settings = QdrantVectorStoreProviderSettings(
            provider=Provider.QDRANT,
            client_options=QdrantClientOptions(url=AnyUrl("http://localhost:6333")),
            collection=CollectionConfig(
                collection_name="test_collection"
                # No wal_config provided
            ),
        )

        # Create metadata
        metadata = CollectionMetadata(
            provider="test-provider",
            project_name="test-project",
            dense_vector_size=768,
            sparse_vector_size=1000,
            distance_metric="cosine",
            collection_name="test_collection",
        )

        # Call get_collection_config with explicit dependencies
        result = await settings.get_collection_config(
            metadata, embedding_group=mock_embedding, failover_settings=failover_settings
        )

        # Verify WalConfig was created from failover settings
        assert result.wal_config is not None
        assert result.wal_config.wal_capacity_mb == 256
        assert result.wal_config.wal_segments_ahead == 2

    @pytest.mark.asyncio
    async def test_collection_config_without_wal_and_disabled_failover(self, tmp_path: Path):
        """Test collection config with no WalConfig and failover disabled."""
        from unittest.mock import Mock

        from pydantic import AnyUrl

        from codeweaver.core import Provider
        from codeweaver.engine.config.failover import FailoverSettings
        from codeweaver.providers import CollectionMetadata
        from codeweaver.providers.config.kinds import (
            CollectionConfig,
            QdrantClientOptions,
            QdrantVectorStoreProviderSettings,
        )
        from codeweaver.providers.types import EmbeddingCapabilityGroup

        # Create failover settings with backup DISABLED
        failover_settings = FailoverSettings(
            disable_failover=True, snapshot_storage_path=str(tmp_path / "snapshots")
        )

        # Create mock embedding group
        mock_embedding = Mock(spec=EmbeddingCapabilityGroup)
        mock_embedding.as_vector_params.return_value = Mock(
            vectors=Mock(
                model_dump=Mock(return_value={"default": {"size": 768, "distance": "Cosine"}})
            ),
            sparse_vectors={},
        )

        # Create provider settings WITHOUT user WalConfig
        settings = QdrantVectorStoreProviderSettings(
            provider=Provider.QDRANT,
            client_options=QdrantClientOptions(url=AnyUrl("http://localhost:6333")),
            collection=CollectionConfig(
                collection_name="test_collection"
                # No wal_config provided
            ),
        )

        # Create metadata
        metadata = CollectionMetadata(
            provider="test-provider",
            project_name="test-project",
            dense_vector_size=768,
            sparse_vector_size=1000,
            distance_metric="cosine",
            collection_name="test_collection",
        )

        # Call get_collection_config with explicit dependencies
        result = await settings.get_collection_config(
            metadata, embedding_group=mock_embedding, failover_settings=failover_settings
        )

        # Should have no WalConfig (both user and failover are None/disabled)
        assert result.wal_config is None

    @pytest.mark.asyncio
    async def test_wal_config_merge_with_different_capacity_values(self, tmp_path: Path):
        """Test that failover settings override user's higher capacity values."""
        from unittest.mock import Mock

        from pydantic import AnyUrl

        from codeweaver.core import Provider
        from codeweaver.engine.config.failover import FailoverSettings
        from codeweaver.providers import CollectionMetadata
        from codeweaver.providers.config.kinds import (
            CollectionConfig,
            QdrantClientOptions,
            QdrantVectorStoreProviderSettings,
            WalConfig,
        )
        from codeweaver.providers.types import EmbeddingCapabilityGroup

        # User wants 512MB capacity (higher than failover)
        user_wal_config = WalConfig(wal_capacity_mb=512, wal_segments_ahead=5)

        # Failover wants 256MB capacity (lower than user)
        failover_settings = FailoverSettings(
            disable_failover=False,
            wal_capacity_mb=256,
            wal_segments_ahead=2,
            snapshot_storage_path=str(tmp_path / "snapshots"),
        )

        # Create mock embedding group
        mock_embedding = Mock(spec=EmbeddingCapabilityGroup)
        mock_embedding.as_vector_params.return_value = Mock(
            vectors=Mock(
                model_dump=Mock(return_value={"default": {"size": 768, "distance": "Cosine"}})
            ),
            sparse_vectors={},
        )

        # Create provider settings with user WalConfig
        settings = QdrantVectorStoreProviderSettings(
            provider=Provider.QDRANT,
            client_options=QdrantClientOptions(url=AnyUrl("http://localhost:6333")),
            collection=CollectionConfig(
                collection_name="test_collection", wal_config=user_wal_config
            ),
        )

        # Create metadata
        metadata = CollectionMetadata(
            provider="test-provider",
            project_name="test-project",
            dense_vector_size=768,
            sparse_vector_size=1000,
            distance_metric="cosine",
            collection_name="test_collection",
        )

        # Call get_collection_config with explicit dependencies
        result = await settings.get_collection_config(
            metadata, embedding_group=mock_embedding, failover_settings=failover_settings
        )

        # Failover should override user's higher capacity
        assert result.wal_config is not None
        assert result.wal_config.wal_capacity_mb == 256  # Failover wins
        assert result.wal_config.wal_segments_ahead == 2  # Failover wins


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
