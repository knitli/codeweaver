# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Indexer utilities for processing and managing documents.

`Indexer` is CodeWeaver's backend-end pipeline for handling document ingestion, processing, and storage. It provides tools to efficiently index documents, making them easily searchable and retrievable, principally the `Indexer` class itself.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.common.utils.lazy_importer import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.engine.indexer.checkpoint import (
        CheckpointManager,
        CheckpointSettingsFingerprint,
        IndexingCheckpoint,
    )
    from codeweaver.engine.indexer.indexer import Indexer
    from codeweaver.engine.indexer.progress import (
        IndexingPhase,
        IndexingProgressTracker,
        IndexingStats,
    )

parent = __spec__.parent or "codeweaver.engine.indexer"

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "Indexer": (parent, "indexer"),
    "CheckpointManager": (parent, "checkpoint"),
    "CheckpointSettingsFingerprint": (parent, "checkpoint"),
    "IndexingCheckpoint": (parent, "checkpoint"),
    "IndexingStats": (parent, "progress"),
    "IndexingPhase": (parent, "progress"),
    "IndexingProgressTracker": (parent, "progress"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CheckpointManager",
    "CheckpointSettingsFingerprint",
    "Indexer",
    "IndexingCheckpoint",
    "IndexingPhase",
    "IndexingProgressTracker",
    "IndexingStats",
)


def __dir__() -> list[str]:
    return list(__all__)
