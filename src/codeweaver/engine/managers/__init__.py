# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Initialization module for the engine managers package."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.engine.managers.checkpoint_manager import (
        EXCEPTION_PATTERN,
        AsyncPath,
        ChangeImpact,
        CheckpointManager,
        CheckpointSettingsFingerprint,
        CheckpointSettingsMap,
        CodeWeaverDeveloperError,
        EmbeddingProviderSettingsType,
        IndexingCheckpoint,
        ResolvedProjectNameDep,
        ResolvedProjectPathDep,
        SparseEmbeddingProviderSettingsType,
        VectorStoreProviderSettingsType,
        get_checkpoint_settings_map,
    )
    from codeweaver.engine.managers.manifest_manager import (
        FileManifestEntry,
        FileManifestManager,
        FileManifestStats,
        IndexFileManifest,
    )
    from codeweaver.engine.managers.progress_tracker import (
        IndexingErrorDict,
        IndexingPhase,
        IndexingProgressTracker,
        IndexingStats,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "EXCEPTION_PATTERN": (__spec__.parent, "checkpoint_manager"),
    "AsyncPath": (__spec__.parent, "checkpoint_manager"),
    "ChangeImpact": (__spec__.parent, "checkpoint_manager"),
    "CheckpointManager": (__spec__.parent, "checkpoint_manager"),
    "CheckpointSettingsFingerprint": (__spec__.parent, "checkpoint_manager"),
    "CheckpointSettingsMap": (__spec__.parent, "checkpoint_manager"),
    "CodeWeaverDeveloperError": (__spec__.parent, "checkpoint_manager"),
    "EmbeddingProviderSettingsType": (__spec__.parent, "checkpoint_manager"),
    "FileManifestEntry": (__spec__.parent, "manifest_manager"),
    "FileManifestManager": (__spec__.parent, "manifest_manager"),
    "FileManifestStats": (__spec__.parent, "manifest_manager"),
    "IndexFileManifest": (__spec__.parent, "manifest_manager"),
    "IndexingCheckpoint": (__spec__.parent, "checkpoint_manager"),
    "IndexingErrorDict": (__spec__.parent, "progress_tracker"),
    "IndexingPhase": (__spec__.parent, "progress_tracker"),
    "IndexingProgressTracker": (__spec__.parent, "progress_tracker"),
    "IndexingStats": (__spec__.parent, "progress_tracker"),
    "ResolvedProjectNameDep": (__spec__.parent, "checkpoint_manager"),
    "ResolvedProjectPathDep": (__spec__.parent, "checkpoint_manager"),
    "SparseEmbeddingProviderSettingsType": (__spec__.parent, "checkpoint_manager"),
    "VectorStoreProviderSettingsType": (__spec__.parent, "checkpoint_manager"),
    "get_checkpoint_settings_map": (__spec__.parent, "checkpoint_manager"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "EXCEPTION_PATTERN",
    "AsyncPath",
    "ChangeImpact",
    "CheckpointManager",
    "CheckpointSettingsFingerprint",
    "CheckpointSettingsMap",
    "CodeWeaverDeveloperError",
    "EmbeddingProviderSettingsType",
    "FileManifestEntry",
    "FileManifestManager",
    "FileManifestStats",
    "IndexFileManifest",
    "IndexingCheckpoint",
    "IndexingErrorDict",
    "IndexingPhase",
    "IndexingProgressTracker",
    "IndexingStats",
    "MappingProxyType",
    "ResolvedProjectNameDep",
    "ResolvedProjectPathDep",
    "SparseEmbeddingProviderSettingsType",
    "VectorStoreProviderSettingsType",
    "get_checkpoint_settings_map",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
