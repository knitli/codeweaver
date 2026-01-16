# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


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
    from codeweaver.engine.config.indexer import (
        DefaultIndexerSettings,
        IndexerSettings,
        IndexerSettingsDict,
        RignoreSettings,
    )
    from codeweaver.engine.config.root_settings import CodeWeaverEngineSettings


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ChunkerSettings": (__spec__.parent, "chunker"),
    "ChunkerSettingsDict": (__spec__.parent, "chunker"),
    "CodeWeaverEngineSettings": (__spec__.parent, "root_settings"),
    "ConcurrencySettings": (__spec__.parent, "chunker"),
    "ConcurrencySettingsDict": (__spec__.parent, "chunker"),
    "CustomDelimiter": (__spec__.parent, "chunker"),
    "CustomLanguage": (__spec__.parent, "chunker"),
    "DefaultChunkerSettings": (__spec__.parent, "chunker"),
    "DefaultIndexerSettings": (__spec__.parent, "indexer"),
    "IndexerSettings": (__spec__.parent, "indexer"),
    "IndexerSettingsDict": (__spec__.parent, "indexer"),
    "PerformanceSettings": (__spec__.parent, "chunker"),
    "PerformanceSettingsDict": (__spec__.parent, "chunker"),
    "RignoreSettings": (__spec__.parent, "indexer"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "ChunkerSettings",
    "ChunkerSettingsDict",
    "CodeWeaverEngineSettings",
    "ConcurrencySettings",
    "ConcurrencySettingsDict",
    "CustomDelimiter",
    "CustomLanguage",
    "DefaultChunkerSettings",
    "DefaultIndexerSettings",
    "IndexerSettings",
    "IndexerSettingsDict",
    "PerformanceSettings",
    "PerformanceSettingsDict",
    "RignoreSettings",
)


def __dir__() -> list[str]:
    return list(__all__)
