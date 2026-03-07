# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Entry point for engine services package."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.engine.services.chunking_service import ChunkingError, ChunkingService
    from codeweaver.engine.services.config_analyzer import (
        ConfigChangeAnalysis,
        ConfigChangeAnalyzer,
        TransformationDetails,
    )
    from codeweaver.engine.services.failover_service import FailoverService
    from codeweaver.engine.services.indexing_service import (
        EmbeddingRegistryDep,
        IndexingService,
        ProgressCallback,
    )
    from codeweaver.engine.services.migration_service import (
        AsyncPath,
        ChunkResult,
        InvalidStateTransitionError,
        MigrationCheckpoint,
        MigrationError,
        MigrationResult,
        MigrationService,
        MigrationState,
        ValidationError,
        WorkItem,
    )
    from codeweaver.engine.services.reconciliation_service import (
        ReconciliationResult,
        RepairStats,
        VectorReconciliationService,
    )
    from codeweaver.engine.services.snapshot_service import QdrantSnapshotBackupService
    from codeweaver.engine.services.watching_service import USE_RICH, FileWatchingService

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "USE_RICH": (__spec__.parent, "watching_service"),
    "AsyncPath": (__spec__.parent, "migration_service"),
    "ChunkingError": (__spec__.parent, "chunking_service"),
    "ChunkingService": (__spec__.parent, "chunking_service"),
    "ChunkResult": (__spec__.parent, "migration_service"),
    "ConfigChangeAnalysis": (__spec__.parent, "config_analyzer"),
    "ConfigChangeAnalyzer": (__spec__.parent, "config_analyzer"),
    "EmbeddingRegistryDep": (__spec__.parent, "indexing_service"),
    "FailoverService": (__spec__.parent, "failover_service"),
    "FileWatchingService": (__spec__.parent, "watching_service"),
    "IndexingService": (__spec__.parent, "indexing_service"),
    "InvalidStateTransitionError": (__spec__.parent, "migration_service"),
    "MigrationCheckpoint": (__spec__.parent, "migration_service"),
    "MigrationError": (__spec__.parent, "migration_service"),
    "MigrationResult": (__spec__.parent, "migration_service"),
    "MigrationService": (__spec__.parent, "migration_service"),
    "MigrationState": (__spec__.parent, "migration_service"),
    "ProgressCallback": (__spec__.parent, "indexing_service"),
    "QdrantSnapshotBackupService": (__spec__.parent, "snapshot_service"),
    "ReconciliationResult": (__spec__.parent, "reconciliation_service"),
    "RepairStats": (__spec__.parent, "reconciliation_service"),
    "TransformationDetails": (__spec__.parent, "config_analyzer"),
    "ValidationError": (__spec__.parent, "migration_service"),
    "VectorReconciliationService": (__spec__.parent, "reconciliation_service"),
    "WorkItem": (__spec__.parent, "migration_service"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "USE_RICH",
    "AsyncPath",
    "ChunkResult",
    "ChunkingError",
    "ChunkingService",
    "ConfigChangeAnalysis",
    "ConfigChangeAnalyzer",
    "EmbeddingRegistryDep",
    "FailoverService",
    "FileWatchingService",
    "IndexingService",
    "InvalidStateTransitionError",
    "MappingProxyType",
    "MigrationCheckpoint",
    "MigrationError",
    "MigrationResult",
    "MigrationService",
    "MigrationState",
    "ProgressCallback",
    "QdrantSnapshotBackupService",
    "ReconciliationResult",
    "RepairStats",
    "TransformationDetails",
    "ValidationError",
    "VectorReconciliationService",
    "WorkItem",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
