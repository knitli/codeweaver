# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency injection setup for engine components.

This module provides DI factories for engine services and managers.
All construction logic lives here, keeping business logic clean.

Architecture:
- Services receive dependencies from other codeweaver packages via INJECTED markers
- Inter-dependencies from within the engine package handled in dependencies.py
- Managers are constructed here and injected into services
- Configuration flows: Settings → Config → Dependencies → Services
"""

from __future__ import annotations

from typing import Annotated

from codeweaver.core import (
    DEFAULT_EXCLUDED_EXTENSIONS,
    INJECTED,
    UNSET,
    ProgressReporterDep,
    ResolvedProjectNameDep,
    ResolvedProjectPathDep,
    SettingsDep,
    dependency_provider,
    depends,
)
from codeweaver.core.config.settings_type import CodeWeaverSettingsType

# Runtime imports needed for dependency_provider decorators
from codeweaver.engine.chunker.base import ChunkGovernor
from codeweaver.engine.chunker.registry import SourceIdRegistry
from codeweaver.engine.config import (
    ChunkerSettings,
    DefaultChunkerSettings,
    DefaultFailoverSettings,
    DefaultIndexerSettings,
    FailoverSettings,
    IndexerSettings,
)
from codeweaver.engine.managers.checkpoint_manager import CheckpointManager
from codeweaver.engine.managers.manifest_manager import FileManifestManager
from codeweaver.engine.managers.progress_tracker import IndexingProgressTracker, IndexingStats
from codeweaver.engine.services.chunking_service import ChunkingService
from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer
from codeweaver.engine.services.failover_service import FailoverService
from codeweaver.engine.services.indexing_service import IndexingService
from codeweaver.engine.services.migration_service import MigrationService
from codeweaver.engine.services.watching_service import FileWatchingService
from codeweaver.engine.watcher.watch_filters import ExtensionFilter, IgnoreFilter
from codeweaver.providers import (
    PrimaryEmbeddingProviderDep,
    PrimarySparseEmbeddingProviderDep,
    PrimaryVectorStoreProviderDep,
    TokenizerDep,
)


# ===========================================================================
# Configuration Providers
# ===========================================================================


def _get_settings(settings: SettingsDep = INJECTED) -> CodeWeaverSettingsType:
    """Get the current CodeWeaver settings."""
    return settings


@dependency_provider(IndexerSettings, scope="singleton")
def _get_indexer_settings(settings: SettingsDep = INJECTED) -> IndexerSettings:
    """Factory for indexing service settings."""
    if settings.indexer is not UNSET:
        return settings.indexer
    return IndexerSettings.model_validate(DefaultIndexerSettings)


@dependency_provider(ChunkerSettings, scope="singleton")
def _get_chunker_settings(settings: SettingsDep = INJECTED) -> ChunkerSettings:
    """Factory for chunking service settings."""
    if settings.chunker is not UNSET:
        return settings.chunker
    return ChunkerSettings.model_validate(DefaultChunkerSettings)


@dependency_provider(FailoverSettings, scope="singleton")
def _get_failover_settings(settings: SettingsDep = INJECTED) -> FailoverSettings:
    """Factory for failover service settings."""
    if settings.failover is not UNSET:
        return settings.failover
    return FailoverSettings.model_validate(DefaultFailoverSettings())


type IndexerSettingsDep = Annotated[
    IndexerSettings, depends(_get_indexer_settings, scope="singleton")
]
type ChunkerSettingsDep = Annotated[
    ChunkerSettings, depends(_get_chunker_settings, scope="singleton")
]
type FailoverSettingsDep = Annotated[
    FailoverSettings, depends(_get_failover_settings, scope="singleton")
]


# ===========================================================================
# Manager Factories
# ===========================================================================


@dependency_provider(CheckpointManager, scope="singleton")
def _create_checkpoint_manager(
    project_path: ResolvedProjectPathDep = INJECTED,
    settings: IndexerSettingsDep = INJECTED,
    project_name: ResolvedProjectNameDep = INJECTED,
) -> CheckpointManager:
    """Factory for checkpoint manager."""
    return CheckpointManager(
        project_path=project_path,
        project_name=project_name,
        checkpoint_dir=settings.checkpoint_file.parent,
    )


@dependency_provider(FileManifestManager, scope="singleton")
def _create_manifest_manager(
    project_path: ResolvedProjectPathDep = INJECTED,
    project_name: ResolvedProjectNameDep = INJECTED,
    settings: IndexerSettingsDep = INJECTED,
) -> FileManifestManager:
    """Factory for file manifest manager."""
    return FileManifestManager(
        project_path=project_path,
        project_name=project_name,
        manifest_dir=settings.cache_dir / "manifests",
    )


@dependency_provider(IndexingStats, scope="function")
def _create_indexing_stats() -> IndexingStats:
    """Factory for indexing stats."""
    return IndexingStats()


@dependency_provider(IndexingProgressTracker, scope="function")
def _create_progress_tracker() -> IndexingProgressTracker:
    """Factory for progress tracker (function-scoped for per-operation tracking)."""
    return IndexingProgressTracker()


type CheckpointManagerDep = Annotated[
    "CheckpointManager", depends(_create_checkpoint_manager, scope="singleton")
]
type ManifestManagerDep = Annotated[
    "FileManifestManager", depends(_create_manifest_manager, scope="singleton")
]
type IndexingStatsDep = Annotated[
    "IndexingStats", depends(_create_indexing_stats, scope="function")
]
type ProgressTrackerDep = Annotated[
    "IndexingProgressTracker", depends(_create_progress_tracker, scope="function")
]


# ===========================================================================
# Service Factories
# ===========================================================================


@dependency_provider(ChunkGovernor, scope="singleton")
def _create_chunk_governor(settings: ChunkerSettingsDep = INJECTED) -> ChunkGovernor:
    """Factory for chunk governor."""
    return ChunkGovernor.from_settings(settings)


type ChunkGovernorDep = Annotated[
    "ChunkGovernor", depends(_create_chunk_governor, scope="singleton")
]


@dependency_provider(ChunkingService, scope="singleton")
def _create_chunking_service(
    governor: ChunkGovernorDep = INJECTED,
    tokenizer: TokenizerDep = INJECTED,
    settings: ChunkerSettingsDep = INJECTED,
) -> ChunkingService:
    """Factory for primary chunking service."""
    return ChunkingService(governor=governor, tokenizer=tokenizer, settings=settings)


type ChunkingServiceDep = Annotated[
    "ChunkingService", depends(_create_chunking_service, scope="singleton")
]


@dependency_provider(IndexingService, scope="singleton")
def _create_indexing_service(
    chunking_service: ChunkingServiceDep = INJECTED,
    embedding_provider: PrimaryEmbeddingProviderDep = INJECTED,
    sparse_provider: PrimarySparseEmbeddingProviderDep = INJECTED,
    vector_store: PrimaryVectorStoreProviderDep = INJECTED,
    settings: IndexerSettingsDep = INJECTED,
    progress_reporter: ProgressReporterDep = INJECTED,
    progress_tracker: ProgressTrackerDep = INJECTED,
    checkpoint_manager: CheckpointManagerDep = INJECTED,
    manifest_manager: ManifestManagerDep = INJECTED,
    project_path: ResolvedProjectPathDep = INJECTED,
) -> IndexingService:
    """Factory for indexing service."""
    return IndexingService(
        chunking_service=chunking_service,
        embedding_provider=embedding_provider,
        sparse_provider=sparse_provider,
        vector_store=vector_store,
        settings=settings,
        progress_reporter=progress_reporter,
        progress_tracker=progress_tracker,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
        project_path=project_path,
    )


@dependency_provider(FailoverService, scope="singleton")
def _create_failover_service(
    primary_store: PrimaryVectorStoreProviderDep = INJECTED,
    backup_store: PrimaryVectorStoreProviderDep | None = None,
    indexing_service: IndexingServiceDep = INJECTED,
    settings: FailoverSettingsDep = INJECTED,
) -> FailoverService:
    """Create FailoverService with dependencies.

    Note: Phase 2 removed backup_indexing_service - new multi-vector approach
    stores backup embeddings as additional vectors on same points.
    """
    return FailoverService(
        primary_store=primary_store,
        backup_store=backup_store,
        indexing_service=indexing_service,
        settings=settings,
    )


type ChunkingServiceDep = Annotated[
    "ChunkingService", depends(_create_chunking_service, scope="singleton")
]

type IndexingServiceDep = Annotated[
    "IndexingService", depends(_create_indexing_service, scope="singleton")
]
type FailoverServiceDep = Annotated[
    "FailoverService", depends(_create_failover_service, scope="singleton")
]


@dependency_provider(FileWatchingService, scope="singleton")
def _create_watching_service(
    indexer: IndexingServiceDep = INJECTED,
    progress_reporter: ProgressReporterDep = INJECTED,
    file_filter: IgnoreFilterDep = INJECTED,
    project_path: ResolvedProjectPathDep = INJECTED,
    # Optional settings could be injected here if needed, or defaults used
) -> FileWatchingService:
    """Factory for file watching service."""
    return FileWatchingService(
        indexer=indexer,
        progress_reporter=progress_reporter,
        file_filter=file_filter,
        project_path=project_path,
    )


type FileWatchingServiceDep = Annotated[
    "FileWatchingService", depends(_create_watching_service, scope="singleton")
]


@dependency_provider(ConfigChangeAnalyzer, scope="singleton")
def _create_config_analyzer(
    settings: SettingsDep = INJECTED,
    checkpoint_manager: CheckpointManagerDep = INJECTED,
    manifest_manager: ManifestManagerDep = INJECTED,
    vector_store: PrimaryVectorStoreProviderDep = INJECTED,
) -> ConfigChangeAnalyzer:
    """Factory for configuration change analyzer service.

    The ConfigChangeAnalyzer is a plain class with no DI markers in its
    constructor. DI integration is handled entirely by this factory function.

    Note: Vector store dependency added for policy enforcement (Phase 2).
    """
    return ConfigChangeAnalyzer(
        settings=settings,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
        vector_store=vector_store,
    )


type ConfigChangeAnalyzerDep = Annotated[
    ConfigChangeAnalyzer, depends(_create_config_analyzer, scope="singleton")
]


@dependency_provider(MigrationService, scope="singleton")
def _create_migration_service(
    vector_store: PrimaryVectorStoreProviderDep = INJECTED,
    config_analyzer: ConfigChangeAnalyzerDep = INJECTED,
    checkpoint_manager: CheckpointManagerDep = INJECTED,
    manifest_manager: ManifestManagerDep = INJECTED,
) -> MigrationService:
    """Factory creates migration service with DI-resolved dependencies.

    The service itself is a plain class. This factory wraps it for DI integration.
    """
    return MigrationService(
        vector_store=vector_store,
        config_analyzer=config_analyzer,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
    )


type MigrationServiceDep = Annotated[
    MigrationService, depends(_create_migration_service, scope="singleton")
]


# ===========================================================================
# Watcher Factories
# ===========================================================================


@dependency_provider(ExtensionFilter, scope="singleton")
def _create_extension_filter() -> ExtensionFilter:
    return ExtensionFilter(tuple(str(s) for s in DEFAULT_EXCLUDED_EXTENSIONS))


@dependency_provider(IgnoreFilter, scope="singleton")
def _create_ignore_filter(
    project_path: ResolvedProjectPathDep, indexer_settings: IndexerSettingsDep
) -> IgnoreFilter:
    return IgnoreFilter(base_path=project_path, settings=indexer_settings)


type ExtensionFilterDep = Annotated[
    ExtensionFilter, depends(_create_extension_filter, scope="singleton")
]
type IgnoreFilterDep = Annotated[IgnoreFilter, depends(_create_ignore_filter, scope="singleton")]


@dependency_provider(SourceIdRegistry, scope="singleton")
def _create_sourceid_registry() -> SourceIdRegistry:
    """Factory for SourceIdRegistry."""
    return SourceIdRegistry()


type SourceIdRegistryDep = Annotated[
    SourceIdRegistry, depends(_create_sourceid_registry, scope="singleton")
]


__all__ = (
    "CheckpointManagerDep",
    "ChunkGovernorDep",
    "ChunkerSettingsDep",
    "ChunkingServiceDep",
    "ConfigChangeAnalyzerDep",
    "ExtensionFilterDep",
    "FailoverServiceDep",
    "FailoverSettingsDep",
    "FileWatchingServiceDep",
    "IgnoreFilterDep",
    "IndexerSettingsDep",
    "IndexingServiceDep",
    "IndexingStatsDep",
    "ManifestManagerDep",
    "MigrationServiceDep",
    "ProgressTrackerDep",
    "SourceIdRegistryDep",
)
