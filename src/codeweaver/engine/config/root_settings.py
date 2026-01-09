# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Root settings for engine-only CodeWeaver installation.

This module provides the root settings class when only the engine package
is installed (along with core and providers). This enables use of indexing
and chunking functionality without the full CodeWeaver server.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from codeweaver.core.config._logging import LoggingSettingsDict
from codeweaver.core.config.telemetry import TelemetrySettings
from codeweaver.core.types import (
    UNSET,
    AnonymityConversion,
    BaseCodeWeaverSettings,
    FilteredKey,
    FilteredKeyT,
    Unset,
)
from codeweaver.engine import ChunkerSettings, IndexerSettings
from codeweaver.providers.config import ProviderSettings


class CodeWeaverEngineSettings(BaseCodeWeaverSettings):
    """Root settings wrapper for engine-only installation.

    When only the engine package is installed (with core and providers),
    this provides configuration for indexing and chunking operations. The config structure is identical to CodeWeaverSettings, but without server-specific settings.

    Configuration structure:
        ```toml
        [indexer]
        batch_size = 100
        parallel_workers = 4

        [chunker]
        max_chunk_size = 1000
        overlap = 200

        [provider]
        embedding.provider = "voyage"
        primary.embedding.model_name = "voyage-code-3"

        [logging]
        level = "INFO"
        ```

    Note:
        This is the root settings class for engine-only installations.
        When the full server package is installed, CodeWeaverSettings
        should be used instead, which nests IndexerSettings and
        ChunkerSettings under their respective fields.
    """

    model_config = model_config = BaseCodeWeaverSettings.model_config | SettingsConfigDict(
        title="CodeWeaver Engine Settings"
    )

    indexer: Annotated[
        IndexerSettings | Unset,
        Field(
            default_factory=IndexerSettings,
            description="Indexing configuration for code discovery and processing",
        ),
    ] = UNSET

    chunker: Annotated[
        ChunkerSettings | Unset,
        Field(
            default_factory=ChunkerSettings,
            description="Chunking configuration for code segmentation",
        ),
    ] = UNSET

    provider: Annotated[
        ProviderSettings | Unset,
        Field(
            default_factory=ProviderSettings,
            description="Provider configuration for embedding, vector store, reranking, etc.",
        ),
    ] = UNSET

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

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Define telemetry filtering for engine settings."""
        return {
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("user_config_dir"): AnonymityConversion.HASH,
            FilteredKey("config_file"): AnonymityConversion.HASH,
        }


__all__ = ("CodeWeaverEngineSettings",)
