# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Engine configuration types for CodeWeaver.
"""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.engine.config.chunker import (
        ChunkerSettings,
        ChunkerSettingsDict,
        ConcurrencySettings,
        ConcurrencySettingsDict,
        CustomDelimiter,
        CustomLanguage,
        DefaultChunkerSettings,
        PerformanceSettings,
        PerformanceSettingsDict,
    )
    from codeweaver.engine.config.failover import (
        FIVE_MINUTES_IN_SECONDS,
        MAX_RAM_MB,
        DefaultFailoverSettings,
        FailoverSettings,
        FailoverSettingsDict,
        get_default_failover_settings,
    )
    from codeweaver.engine.config.failover_detector import FailoverDetector, LocalEmbeddingDetector
    from codeweaver.engine.config.indexer import (
        BRACKET_PATTERN,
        AsyncPath,
        DefaultIndexerSettings,
        FastMCPContext,
        FilteredPaths,
        IndexerSettings,
        IndexerSettingsDict,
        ResolvedProjectNameDep,
        ResolvedProjectPathDep,
        RignoreSettings,
        get_storage_path,
    )
    from codeweaver.engine.config.root_settings import CodeWeaverEngineSettings

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "BRACKET_PATTERN": (__spec__.parent, "indexer"),
    "FIVE_MINUTES_IN_SECONDS": (__spec__.parent, "failover"),
    "MAX_RAM_MB": (__spec__.parent, "failover"),
    "AsyncPath": (__spec__.parent, "indexer"),
    "ChunkerSettings": (__spec__.parent, "chunker"),
    "ChunkerSettingsDict": (__spec__.parent, "chunker"),
    "CodeWeaverEngineSettings": (__spec__.parent, "root_settings"),
    "ConcurrencySettings": (__spec__.parent, "chunker"),
    "ConcurrencySettingsDict": (__spec__.parent, "chunker"),
    "CustomDelimiter": (__spec__.parent, "chunker"),
    "CustomLanguage": (__spec__.parent, "chunker"),
    "DefaultChunkerSettings": (__spec__.parent, "chunker"),
    "DefaultFailoverSettings": (__spec__.parent, "failover"),
    "DefaultIndexerSettings": (__spec__.parent, "indexer"),
    "FailoverDetector": (__spec__.parent, "failover_detector"),
    "FailoverSettings": (__spec__.parent, "failover"),
    "FailoverSettingsDict": (__spec__.parent, "failover"),
    "FilteredPaths": (__spec__.parent, "indexer"),
    "IndexerSettings": (__spec__.parent, "indexer"),
    "IndexerSettingsDict": (__spec__.parent, "indexer"),
    "LocalEmbeddingDetector": (__spec__.parent, "failover_detector"),
    "PerformanceSettings": (__spec__.parent, "chunker"),
    "PerformanceSettingsDict": (__spec__.parent, "chunker"),
    "ResolvedProjectNameDep": (__spec__.parent, "indexer"),
    "ResolvedProjectPathDep": (__spec__.parent, "indexer"),
    "RignoreSettings": (__spec__.parent, "indexer"),
    "FastMCPContext": (__spec__.parent, "indexer"),
    "get_default_failover_settings": (__spec__.parent, "failover"),
    "get_storage_path": (__spec__.parent, "indexer"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "BRACKET_PATTERN",
    "FIVE_MINUTES_IN_SECONDS",
    "MAX_RAM_MB",
    "AsyncPath",
    "ChunkerSettings",
    "ChunkerSettingsDict",
    "CodeWeaverEngineSettings",
    "ConcurrencySettings",
    "ConcurrencySettingsDict",
    "CustomDelimiter",
    "CustomLanguage",
    "DefaultChunkerSettings",
    "DefaultFailoverSettings",
    "DefaultIndexerSettings",
    "FailoverDetector",
    "FailoverSettings",
    "FailoverSettingsDict",
    "FastMCPContext",
    "FilteredPaths",
    "IndexerSettings",
    "IndexerSettingsDict",
    "LocalEmbeddingDetector",
    "MappingProxyType",
    "PerformanceSettings",
    "PerformanceSettingsDict",
    "ResolvedProjectNameDep",
    "ResolvedProjectPathDep",
    "RignoreSettings",
    "get_default_failover_settings",
    "get_storage_path",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
