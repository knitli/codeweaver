# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Initialization module for the engine managers package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.engine.managers.checkpoint_manager import (
        CheckpointManager,
        CheckpointSettingsFingerprint,
        IndexingCheckpoint,
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
    "CheckpointManager": (__spec__.parent, "checkpoint_manager"),
    "CheckpointSettingsFingerprint": (__spec__.parent, "checkpoint_manager"),
    "FileManifestEntry": (__spec__.parent, "manifest_manager"),
    "FileManifestManager": (__spec__.parent, "manifest_manager"),
    "FileManifestStats": (__spec__.parent, "manifest_manager"),
    "IndexFileManifest": (__spec__.parent, "manifest_manager"),
    "IndexingCheckpoint": (__spec__.parent, "checkpoint_manager"),
    "IndexingErrorDict": (__spec__.parent, "progress_tracker"),
    "IndexingPhase": (__spec__.parent, "progress_tracker"),
    "IndexingProgressTracker": (__spec__.parent, "progress_tracker"),
    "IndexingStats": (__spec__.parent, "progress_tracker"),
    "get_checkpoint_settings_map": (__spec__.parent, "checkpoint_manager"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CheckpointManager",
    "CheckpointSettingsFingerprint",
    "FileManifestEntry",
    "FileManifestManager",
    "FileManifestStats",
    "IndexFileManifest",
    "IndexingCheckpoint",
    "IndexingErrorDict",
    "IndexingPhase",
    "IndexingProgressTracker",
    "IndexingStats",
    "get_checkpoint_settings_map",
)


def __dir__() -> list[str]:
    """Override to include dynamically imported names."""
    return list(__all__)
