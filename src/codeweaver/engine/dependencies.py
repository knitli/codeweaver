"""Dependency injection types and factories for the CodeWeaver engine."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from codeweaver.core import INJECTED, CodeWeaverSettingsType, SettingsDep, Unset, depends
from codeweaver.engine.config import DefaultChunkerSettings, DefaultIndexerSettings


if TYPE_CHECKING:
    from codeweaver.engine.config import ChunkerSettings, IndexerSettings


def _get_settings(settings: SettingsDep = INJECTED) -> CodeWeaverSettingsType:
    """Get the current CodeWeaver settings."""
    return settings


def _get_indexer_settings() -> IndexerSettings:
    from codeweaver.engine.config import IndexerSettings

    settings = _get_settings()
    return cast(
        IndexerSettings,
        settings.indexer if settings.indexer is not Unset else DefaultIndexerSettings,
    )


type IndexerSettingsDep = Annotated[
    IndexerSettings, depends(_get_indexer_settings, scope="singleton")
]


def _get_chunker_settings(settings: SettingsDep = INJECTED) -> ChunkerSettings:
    """Get the current CodeWeaver engine settings."""
    settings = _get_settings()
    from codeweaver.engine.config import ChunkerSettings

    return cast(
        ChunkerSettings,
        settings.chunker if settings.chunker is not Unset else DefaultChunkerSettings,
    )


type ChunkerSettingsDep = Annotated[
    ChunkerSettings, depends(_get_chunker_settings, scope="singleton")
]

//


__all__ = ("ChunkerSettingsDep", "IndexerSettingsDep")
