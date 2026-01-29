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

from typing import Annotated, Any

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from codeweaver.core.types import UNSET, Unset
from codeweaver.engine import ChunkerSettings, DefaultChunkerSettings, IndexerSettings
from codeweaver.engine.config.failover import DefaultFailoverSettings, FailoverSettings
from codeweaver.engine.config.indexer import DefaultIndexerSettings
from codeweaver.providers.config import CodeWeaverProviderSettings


class CodeWeaverEngineSettings(CodeWeaverProviderSettings):
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

    model_config = model_config = CodeWeaverProviderSettings.model_config | SettingsConfigDict(
        title="CodeWeaver Engine Settings"
    )

    indexer: Annotated[
        IndexerSettings | Unset,
        Field(description="Indexing configuration for code discovery and processing"),
    ] = UNSET

    chunker: Annotated[
        ChunkerSettings | Unset, Field(description="Chunking configuration for code segmentation")
    ] = UNSET

    failover: Annotated[
        FailoverSettings | Unset, Field(description="Failover configuration for service resilience")
    ] = UNSET

    def _initialize(self, **kwargs: Any) -> dict[str, Any]:  # ty:ignore[invalid-method-override]
        """Initialize engine settings - nothing special needed."""
        if "indexer" not in kwargs or kwargs.get("indexer") is UNSET:
            kwargs["indexer"] = IndexerSettings.model_construct(**DefaultIndexerSettings)
        else:
            kwargs["indexer"] = IndexerSettings(
                **self._resolve_default_and_provided(DefaultIndexerSettings, kwargs["indexer"])  # ty:ignore[invalid-argument-type]
            )
        if "chunker" not in kwargs or kwargs.get("chunker") is UNSET:
            kwargs["chunker"] = ChunkerSettings.model_construct(**DefaultChunkerSettings)
        else:
            kwargs["chunker"] = ChunkerSettings.model_validate(
                self._resolve_default_and_provided(DefaultChunkerSettings, kwargs["chunker"])  # ty:ignore[invalid-argument-type]
            )
        if "failover" not in kwargs or kwargs.get("failover") is UNSET:
            kwargs["failover"] = FailoverSettings.model_construct(**DefaultFailoverSettings())
        else:
            kwargs["failover"] = FailoverSettings.model_validate(
                self._resolve_default_and_provided(DefaultFailoverSettings(), kwargs["failover"])  # ty:ignore[invalid-argument-type]
            )
        kwargs |= super()._initialize(**kwargs)
        return kwargs


__all__ = ("CodeWeaverEngineSettings",)
