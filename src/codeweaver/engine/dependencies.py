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

from typing import TYPE_CHECKING, Annotated

from codeweaver.core import (
    DEFAULT_EXCLUDED_EXTENSIONS,
    INJECTED,
    CodeWeaverSettingsType,
    ProgressReporterDep,
    ResolvedProjectPathDep,
    SettingsDep,
    Unset,
    dependency_provider,
    depends,
)
from codeweaver.engine.config import (
    ChunkerSettings,
    DefaultChunkerSettings,
    DefaultFailoverSettings,
    DefaultIndexerSettings,
    FailoverSettings,
    IndexerSettings,
)
from codeweaver.providers import (
    BackupVectorStoreProviderDep,
    EmbeddingProviderDep,
    SparseEmbeddingProviderDep,
    VectorStoreProviderDep,
)


if TYPE_CHECKING:
    from codeweaver.engine.managers.checkpoint_manager import CheckpointManager
    from codeweaver.engine.managers.manifest_manager import FileManifestManager
    from codeweaver.engine.managers.progress_tracker import IndexingProgressTracker, IndexingStats
    from codeweaver.engine.services.chunking_service import ChunkingService
    from codeweaver.engine.services.failover_service import FailoverService
    from codeweaver.engine.services.indexing_service import IndexingService
    from codeweaver.engine.watcher.watch_filters import ExtensionFilter, IgnoreFilter


# ===========================================================================
# Configuration Providers
# ===========================================================================


def _get_settings(settings: SettingsDep = INJECTED) -> CodeWeaverSettingsType:
    """Get the current CodeWeaver settings."""
    return settings


@dependency_provider(IndexerSettings, scope="singleton")
def _get_indexer_settings(settings: SettingsDep = INJECTED) -> IndexerSettings:
    """Factory for indexing service settings."""
    if settings.indexer is not Unset:
        return settings.indexer  # type: ignore
    return IndexerSettings.model_validate(DefaultIndexerSettings)


@dependency_provider(ChunkerSettings, scope="singleton")
def _get_chunker_settings(settings: SettingsDep = INJECTED) -> ChunkerSettings:
    """Factory for chunking service settings."""
    if settings.chunker is not Unset:
        return settings.chunker  # type: ignore
    return ChunkerSettings.model_validate(DefaultChunkerSettings)


@dependency_provider(FailoverSettings, scope="singleton")
def _get_failover_settings(settings: SettingsDep = INJECTED) -> FailoverSettings:
    """Factory for failover service settings."""
    if settings.failover is not Unset:
        return settings.failover  # type: ignore
    return FailoverSettings.model_validate(DefaultFailoverSettings)


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
    settings: Annotated[IndexerSettings, depends(_get_indexer_settings)] = INJECTED,
) -> CheckpointManager:
    """Factory for checkpoint manager."""
    from codeweaver.engine.managers.checkpoint_manager import CheckpointManager

    return CheckpointManager(
        project_path=project_path,
        project_name=get_project_name(project_path),
        checkpoint_dir=settings.checkpoint_file.parent,
    )


@dependency_provider(FileManifestManager, scope="singleton")
def _create_manifest_manager(
    project_path: ResolvedProjectPathDep = INJECTED,
    settings: Annotated[IndexerSettings, depends(_get_indexer_settings)] = INJECTED,
) -> FileManifestManager:
    """Factory for file manifest manager."""
    from codeweaver.engine.managers.manifest_manager import FileManifestManager

    return FileManifestManager(
        project_path=project_path,
        project_name=get_project_name(project_path),
        manifest_dir=settings.cache_dir / "manifests",
    )


@dependency_provider(IndexingStats, scope="function")
def _create_indexing_stats() -> IndexingStats:
    """Factory for indexing stats."""
    from codeweaver.engine.managers.progress_tracker import IndexingStats

    return IndexingStats()


@dependency_provider(IndexingProgressTracker, scope="function")
def _create_progress_tracker() -> IndexingProgressTracker:
    """Factory for progress tracker (function-scoped for per-operation tracking)."""
    from codeweaver.engine.managers.progress_tracker import IndexingProgressTracker

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


@dependency_provider(ChunkingService, scope="singleton")
def _create_chunking_service(
    governor: ChunkGovernorDep = INJECTED,  # Placeholder for GovernorDep
    tokenizer: TokenizerDep = INJECTED,  # Placeholder for TokenizerDep
    settings: ChunkerSettingsDep = INJECTED,
) -> ChunkingService:
    """Factory for primary chunking service."""
    from codeweaver.engine.services.chunking_service import ChunkingService

    return ChunkingService(governor=governor, tokenizer=tokenizer, settings=settings)


@dependency_provider(IndexingService, scope="singleton")
def _create_indexing_service(
    chunking_service: ChunkingServiceDep = INJECTED,
    embedding_provider: EmbeddingProviderDep = INJECTED,
    sparse_provider: SparseEmbeddingProviderDep = INJECTED,
    vector_store: VectorStoreProviderDep = INJECTED,
    settings: IndexerSettingsDep = INJECTED,
    progress_reporter: ProgressReporterDep = INJECTED,
    progress_tracker: IndexingProgressTrackerDep = INJECTED,
    checkpoint_manager: CheckpointManagerDep = INJECTED,
    manifest_manager: ManifestManagerDep = INJECTED,
    project_path: ResolvedProjectPathDep = INJECTED,
) -> IndexingService:
    """Factory for indexing service."""
    from codeweaver.engine.services.indexing_service import IndexingService

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
    primary_vector_store: VectorStoreProviderDep = INJECTED,
    backup_vector_store: BackupVectorStoreProviderDep = INJECTED,
    indexing_service: IndexingServiceDep = INJECTED,
    settings: FailoverSettingsDep = INJECTED,
) -> FailoverService:
    """Factory for failover service."""
    from codeweaver.engine.services.failover_service import FailoverService

    return FailoverService(
        primary_store=primary_vector_store,
        backup_store=backup_vector_store,
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


# ===========================================================================
# Watcher Factories
# ===========================================================================


@dependency_provider(ExtensionFilter, scope="singleton")
def _create_extension_filter() -> ExtensionFilter:
    from codeweaver.engine.watcher import ExtensionFilter

    return ExtensionFilter(tuple(str(s) for s in DEFAULT_EXCLUDED_EXTENSIONS))


@dependency_provider(IgnoreFilter, scope="request")
def _create_ignore_filter(
    project_path: ResolvedProjectPathDep, indexer_settings: IndexerSettingsDep
) -> IgnoreFilter:
    from codeweaver.engine.watcher import IgnoreFilter

    return IgnoreFilter(base_path=project_path, settings=indexer_settings)


type ExtensionFilterDep = Annotated[
    ExtensionFilter, depends(_create_extension_filter, scope="singleton")
]
type IgnoreFilterDep = Annotated[IgnoreFilter, depends(_create_ignore_filter, scope="request")]

__all__ = (
    "CheckpointManagerDep",
    "ChunkerSettingsDep",
    "ChunkingServiceDep",
    "ExtensionFilterDep",
    "FailoverServiceDep",
    "FailoverSettingsDep",
    "IgnoreFilterDep",
    "IndexerSettingsDep",
    "IndexingServiceDep",
    "IndexingStatsDep",
    "ManifestManagerDep",
    "ProgressTrackerDep",
)
