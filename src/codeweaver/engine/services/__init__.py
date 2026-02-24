# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

"""Entry point for engine services package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.engine.services.chunking_service import ChunkingService
    from codeweaver.engine.services.config_analyzer import (
        ConfigChangeAnalysis,
        ConfigChangeAnalyzer,
        TransformationDetails,
    )
    from codeweaver.engine.services.failover_service import FailoverService
    from codeweaver.engine.services.indexing_service import IndexingService
    from codeweaver.engine.services.migration_service import MigrationService
    from codeweaver.engine.services.watching_service import FileWatchingService

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ChunkingService": (__spec__.parent, "chunking_service"),
    "ConfigChangeAnalysis": (__spec__.parent, "config_analyzer"),
    "ConfigChangeAnalyzer": (__spec__.parent, "config_analyzer"),
    "FailoverService": (__spec__.parent, "failover_service"),
    "IndexingService": (__spec__.parent, "indexing_service"),
    "TransformationDetails": (__spec__.parent, "config_analyzer"),
    "FileWatchingService": (__spec__.parent, "watching_service"),
    "MigrationService": (__spec__.parent, "migration_service"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "ChunkingService",
    "ConfigChangeAnalysis",
    "ConfigChangeAnalyzer",
    "FailoverService",
    "FileWatchingService",
    "IndexingService",
    "MigrationService",
    "TransformationDetails",
)


def __dir__():
    """Return a list of all public objects of this module."""
    return list(__all__)
