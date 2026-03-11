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
        embedding.model_name = "voyage-code-3"

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

    def __init__(
        self,
        indexer: IndexerSettings | Unset = UNSET,
        chunker: ChunkerSettings | Unset = UNSET,
        failover: FailoverSettings | Unset = UNSET,
        **data: Any,
    ) -> None:
        """Initialize engine settings."""
        self._set_unset_fields(indexer=indexer, chunker=chunker, failover=failover)
        data["indexer"] = (
            indexer
            if indexer is not UNSET and indexer is not None
            else IndexerSettings.model_construct(**DefaultIndexerSettings)
        )
        data["chunker"] = (
            chunker
            if chunker is not UNSET and chunker is not None
            else ChunkerSettings.model_construct(**DefaultChunkerSettings)
        )
        data["failover"] = (
            failover
            if failover is not UNSET and failover is not None
            else FailoverSettings.model_construct(**DefaultFailoverSettings)
        )
        super().__init__(**data)

    async def _initialize(self, **kwargs: Any) -> None:
        """Initialize engine settings - resolve defaults."""
        fields_and_defaults = (
            ("indexer", DefaultIndexerSettings, IndexerSettings),
            ("chunker", DefaultChunkerSettings, ChunkerSettings),
            ("failover", DefaultFailoverSettings, FailoverSettings),
        )
        for field_name, default, type_cls in fields_and_defaults:
            field_value = (
                resolved_field
                if (resolved_field := kwargs.get(field_name)) and resolved_field is not UNSET
                else getattr(self, field_name, None)
            )
            if field_value is UNSET or field_value is None:
                setattr(self, field_name, default)
            else:
                existing_value = (
                    existing
                    if (existing := getattr(self, field_name, None)) and existing is not UNSET
                    else default
                )
                resolved_value = (
                    field_value if isinstance(field_value, dict) else field_value.model_dump()
                )
                finalized_value = self._resolve_default_and_provided(
                    existing_value
                    if isinstance(existing_value, dict)
                    else existing_value.model_dump(),  # ty:ignore[unresolved-attribute]
                    resolved_value,
                )
                setattr(self, field_name, type_cls.model_construct(**finalized_value))
        await super()._initialize(**kwargs)


__all__ = ("CodeWeaverEngineSettings",)
