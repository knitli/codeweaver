from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.engine.config.chunker import (
        ChunkerSettings,
        ChunkerSettingsDict,
        CustomDelimiter,
        CustomLanguage,
    )
    from codeweaver.engine.config.indexer import (
        IndexerSettings,
        IndexerSettingsDict,
        RignoreSettings,
    )
    from codeweaver.engine.config.root_settings import CodeWeaverEngineSettings


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ChunkerSettings": (__spec__.parent, "chunker"),
    "ChunkerSettingsDict": (__spec__.parent, "chunker"),
    "CodeWeaverEngineSettings": (__spec__.parent, "root_settings"),
    "CustomDelimiter": (__spec__.parent, "chunker"),
    "CustomLanguage": (__spec__.parent, "chunker"),
    "IndexerSettings": (__spec__.parent, "indexer"),
    "IndexerSettingsDict": (__spec__.parent, "indexer"),
    "RignoreSettings": (__spec__.parent, "indexer"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "ChunkerSettings",
    "ChunkerSettingsDict",
    "CodeWeaverEngineSettings",
    "CustomDelimiter",
    "CustomLanguage",
    "IndexerSettings",
    "IndexerSettingsDict",
    "RignoreSettings",
)


def __dir__() -> list[str]:
    return list(__all__)
