"""Root settings for provider-only CodeWeaver installation.

This module provides the root settings class when only the providers package
is installed (along with core). This enables use of embedding, vector store,
and reranking providers without the full CodeWeaver server.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from codeweaver.core.config._logging import LoggingSettingsDict
from codeweaver.core.config.telemetry import TelemetrySettings
from codeweaver.core.types.aliases import FilteredKey, FilteredKeyT
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.sentinel import UNSET, Unset
from codeweaver.core.types.settings_model import BaseCodeWeaverSettings
from codeweaver.providers.config.providers import ProviderSettings


class CodeWeaverProviderSettings(BaseCodeWeaverSettings):
    """Root settings wrapper for provider-only installation.

    When only the providers package is installed (with core), this provides
    configuration for all provider types: embedding, vector store, reranking,
    data providers, and agents.

    Configuration structure:
        ```toml
        [provider]
        embedding.provider = "voyage"
        embedding.model_name = "voyage-code-3"

        vector_store.provider = "qdrant"
        vector_store.url = "http://localhost:6333"

        [logging]
        level = "INFO"
        ```

    Note:
        This is the root settings class for provider-only installations.
        When the full server package is installed, CodeWeaverSettings
        should be used instead, which nests ProviderSettings under the
        provider field.
    """

    model_config = model_config = BaseCodeWeaverSettings.model_config | SettingsConfigDict(
        title="CodeWeaver Provider Settings"
    )

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
        """Initialize provider settings - nothing special needed."""

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Define telemetry filtering for provider settings."""
        return {
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("user_config_dir"): AnonymityConversion.HASH,
            FilteredKey("config_file"): AnonymityConversion.HASH,
        }


__all__ = ("CodeWeaverProviderSettings",)
