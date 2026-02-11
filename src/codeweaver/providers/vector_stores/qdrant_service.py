# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Service layer for Qdrant vector store operations.

This module separates behavior (DI-dependent operations) from configuration (pure data).
The service uses QdrantVectorStoreProviderSettings (pure data) + injected dependencies
to perform vector store operations.

Architecture:
    - QdrantVectorStoreProviderSettings: Pure configuration (data)
    - QdrantVectorStoreService: Behavior + DI (service)
    - This separation enables:
        * Easy testing (instantiate service with mocks)
        * Clear responsibilities (settings = data, service = operations)
        * No pydantic issues with DI

Usage:
    # In tests (unit tests with mocks):
    settings = QdrantVectorStoreProviderSettings(...)
    mock_embedding = Mock(spec=EmbeddingCapabilityGroup)
    service = QdrantVectorStoreService(settings, mock_embedding)

    # In application (DI container resolves):
    service = await container.resolve(QdrantVectorStoreService)
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from codeweaver.core.di import INJECTED, dependency_provider
from codeweaver.providers import ProviderSettingsDep


if TYPE_CHECKING:
    from codeweaver.engine.config import FailoverSettings
    from codeweaver.engine.config.failover_detector import FailoverDetector
    from codeweaver.providers import CollectionMetadata
    from codeweaver.providers.config.categories.vector_store import (
        QdrantCollectionConfig,
        QdrantVectorStoreProviderSettings,
    )
    from codeweaver.providers.types import EmbeddingCapabilityGroup

logger = logging.getLogger(__name__)


class QdrantVectorStoreService:
    """Service layer for Qdrant vector store operations.

    Responsibilities:
        - Use settings (pure data) to perform operations
        - Manage injected dependencies (embedding group, failover settings)
        - Encapsulate business logic (WalConfig merging, collection configuration)

    This class separates behavior from configuration following SOLID principles:
        - Single Responsibility: Settings hold data, Service performs operations
        - Dependency Inversion: Service depends on abstractions (EmbeddingCapabilityGroup)
        - Open/Closed: Settings can be used without service infrastructure

    The service is testable:
        - Unit tests: Instantiate with mock dependencies
        - Integration tests: Let DI container resolve dependencies
    """

    def __init__(
        self,
        settings: QdrantVectorStoreProviderSettings,
        embedding_group: EmbeddingCapabilityGroup,
        failover_settings: FailoverSettings | None = None,
        failover_detector: FailoverDetector | None = None,
    ) -> None:
        """Initialize Qdrant vector store service.

        Args:
            settings: Pure configuration (no DI dependencies)
            embedding_group: Injected embedding capability group
            failover_settings: Optional failover configuration
            failover_detector: Optional failover detector for status checks
        """
        self.settings = settings
        self.embedding_group = embedding_group
        self.failover_settings = failover_settings
        self.failover_detector = failover_detector

    async def get_collection_config(self, metadata: CollectionMetadata) -> QdrantCollectionConfig:
        """Get collection configuration, merging failover WalConfig if backup system is enabled.

        When the backup system is active, failover WalConfig settings take precedence over
        user-configured settings to ensure proper snapshot and recovery functionality.

        Args:
            metadata: Collection metadata

        Returns:
            QdrantCollectionConfig with merged WalConfig settings

        Example:
            # Unit test with mocks
            service = QdrantVectorStoreService(
                settings=test_settings,
                embedding_group=mock_embedding_group,
                failover_settings=mock_failover,
            )
            config = await service.get_collection_config(metadata)

            # Integration test with DI
            service = await container.resolve(QdrantVectorStoreService)
            config = await service.get_collection_config(metadata)
        """
        # Set vector params if not already set
        # This uses the injected embedding_group instead of DI resolution
        if not self.settings.collection._vectors_set:
            await self.settings.collection.set_vector_params(self.embedding_group)

        # Get base qdrant config from collection settings
        qdrant_config = await self.settings.collection.as_qdrant_config(metadata=metadata)

        # Check if we need to merge failover WalConfig
        if self.failover_settings is not None:
            # Determine if failover is disabled
            is_disabled = self._is_failover_disabled()

            # Only merge if failover is enabled (not disabled)
            if not is_disabled:
                qdrant_config = self._merge_failover_wal_config(qdrant_config)

        return qdrant_config

    def _is_failover_disabled(self) -> bool:
        """Check if failover should be disabled.

        Uses failover_detector if available, otherwise falls back to explicit flag.

        Returns:
            True if failover is disabled, False otherwise
        """
        if self.failover_settings is None:
            return True

        if self.failover_detector is not None:
            return self.failover_settings._resolve_status_from_config(self.failover_detector)

        return self.failover_settings.is_disabled

    def _merge_failover_wal_config(
        self, qdrant_config: QdrantCollectionConfig
    ) -> QdrantCollectionConfig:
        """Merge failover WalConfig with user's config.

        Failover settings take precedence for critical settings (capacity, segments).

        Args:
            qdrant_config: Base Qdrant collection configuration

        Returns:
            QdrantCollectionConfig with merged WalConfig
        """
        from codeweaver.providers.config.sdk.vector_store import WalConfig

        if self.failover_settings is None:
            return qdrant_config

        # Create WalConfig from failover settings
        failover_wal_config = WalConfig(
            wal_capacity_mb=self.failover_settings.wal_capacity_mb,
            wal_segments_ahead=self.failover_settings.wal_segments_ahead,
        )

        # Merge with user's WalConfig (failover takes precedence for critical settings)
        if qdrant_config.wal_config:
            # Keep user's other settings, override capacity and segments
            merged_wal = qdrant_config.wal_config.model_copy(
                update={
                    "wal_capacity_mb": self.failover_settings.wal_capacity_mb,
                    "wal_segments_ahead": self.failover_settings.wal_segments_ahead,
                }
            )
            qdrant_config = qdrant_config.model_copy(update={"wal_config": merged_wal})
        else:
            # Use failover WalConfig directly
            qdrant_config = qdrant_config.model_copy(update={"wal_config": failover_wal_config})

        logger.debug(
            "Merged failover WalConfig: capacity=%d MB, segments_ahead=%d",
            self.failover_settings.wal_capacity_mb,
            self.failover_settings.wal_segments_ahead,
        )

        return qdrant_config


@dependency_provider(QdrantVectorStoreService, scope="singleton")
def create_qdrant_service(
    settings_dep: ProviderSettingsDep = INJECTED,
    embedding_group: EmbeddingCapabilityGroup = INJECTED,
    failover_settings: FailoverSettings = INJECTED,
    failover_detector: FailoverDetector = INJECTED,
) -> QdrantVectorStoreService:
    """Factory function with DI for application startup.

    The DI container resolves all dependencies and creates the service.
    This is used in production code paths.

    Args:
        settings_dep: Provider settings (DI resolves)
        embedding_group: Embedding capability group (DI resolves)
        failover_settings: Failover configuration (DI resolves)
        failover_detector: Failover detector (DI resolves)

    Returns:
        Configured QdrantVectorStoreService

    Example:
        # In application startup or endpoint handlers
        service = await container.resolve(QdrantVectorStoreService)
        config = await service.get_collection_config(metadata)
    """
    from codeweaver.providers.config.categories import QdrantVectorStoreProviderSettings

    # Extract Qdrant-specific settings from provider settings
    # Assuming first vector_store is Qdrant (may need to filter by provider type)
    qdrant_settings = None
    if settings_dep.vector_store is not None:
        for vs_settings in settings_dep.vector_store:
            if isinstance(vs_settings, QdrantVectorStoreProviderSettings):
                qdrant_settings = vs_settings
                break

    if qdrant_settings is None:
        raise ValueError("No QdrantVectorStoreProviderSettings found in provider settings")

    return QdrantVectorStoreService(
        settings=qdrant_settings,
        embedding_group=embedding_group,
        failover_settings=failover_settings,
        failover_detector=failover_detector,
    )
