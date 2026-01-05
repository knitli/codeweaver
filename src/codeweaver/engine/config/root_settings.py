"""Root settings for engine-only CodeWeaver installation.

This module provides the root settings class when only the engine package
is installed (along with core and providers). This enables use of indexing
and chunking functionality without the full CodeWeaver server.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from codeweaver.core.config._logging import LoggingSettingsDict
from codeweaver.core.config.telemetry import TelemetrySettings
from codeweaver.core.types.aliases import FilteredKey, FilteredKeyT
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.sentinel import UNSET, Unset
from codeweaver.core.types.settings_model import BaseCodeWeaverSettings
from codeweaver.engine.config.chunker import ChunkerSettings
from codeweaver.engine.config.indexer import IndexerSettings


class CodeWeaverEngineSettings(BaseCodeWeaverSettings):
    """Root settings wrapper for engine-only installation.

    When only the engine package is installed (with core and providers),
    this provides configuration for indexing and chunking operations.

    Configuration structure:
        ```toml
        [indexer]
        batch_size = 100
        parallel_workers = 4

        [chunker]
        max_chunk_size = 1000
        overlap = 200

        [logging]
        level = "INFO"

        [telemetry]
        enabled = true
        ```

    Note:
        This is the root settings class for engine-only installations.
        When the full server package is installed, CodeWeaverSettings
        should be used instead, which nests IndexerSettings and
        ChunkerSettings under their respective fields.
    """

    indexer: Annotated[
        IndexerSettings,
        Field(
            default_factory=IndexerSettings,
            description="Indexing configuration for code discovery and processing",
        ),
    ]

    chunker: Annotated[
        ChunkerSettings,
        Field(
            default_factory=ChunkerSettings,
            description="Chunking configuration for code segmentation",
        ),
    ]

    logging: Annotated[
        LoggingSettingsDict | Unset,
        Field(
            default=UNSET,
            description="Logging configuration for CodeWeaver",
            validate_default=False,
        ),
    ] = UNSET

    telemetry: Annotated[
        TelemetrySettings | Unset,
        Field(
            default=UNSET,
            description="Telemetry configuration for CodeWeaver",
            validate_default=False,
        ),
    ] = UNSET

    def _initialize(self) -> None:
        """Initialize engine settings - nothing special needed."""
        pass

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Define telemetry filtering for engine settings."""
        return {
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("user_config_dir"): AnonymityConversion.HASH,
            FilteredKey("config_file"): AnonymityConversion.HASH,
        }


__all__ = ("CodeWeaverEngineSettings",)
