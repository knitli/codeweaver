# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Root settings for provider-only CodeWeaver installation.

This module provides the root settings class when only the providers package
is installed (along with core). This enables use of embedding, vector store,
and reranking providers without the full CodeWeaver server.
"""

from __future__ import annotations

import os

from typing import Annotated, Literal

from pydantic import Field
from pydantic_settings import SettingsConfigDict

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
        primary.embedding.model_name = "voyage-code-3"

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

    profile: Annotated[
        Literal["recommended", "quickstart", "testing"] | Unset | None,
        Field(
            description="""Use a premade provider profile.  The recommended profile uses Voyage AI for top-quality embedding and reranking, but requires an API key. The quickstart profile is entirely free and local, and does not require any API key. It sacrifices some search quality and performance compared to the recommended profile. The testing profile is only recommended for testing -- it uses an in-memory vector store and very light weight local models. The testing profile is also CodeWeaver's backup system when a cloud embedding or vector store provider isn't available. Both the quickstart and recommended profiles default to a local qdrant instance for the vector store. If you want to use a cloud or remote instance (which we recommend) you must also provide a URL for it, either with the environment variable CODEWEAVER_VECTOR_STORE_URL or in your codeweaver config in the vector_store settings.""",
            validate_default=False,
        ),
    ] = (
        profile
        if (profile := os.environ.get("CODEWEAVER_PROFILE"))
        and profile.lower() in ("recommended", "quickstart", "testing")
        else UNSET
    )  # ty: ignore[invalid-assignment]

    def _initialize(self) -> None:
        """Initialize provider settings."""
        if self.profile:
            pass

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Define telemetry filtering for provider settings."""
        return {
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("user_config_dir"): AnonymityConversion.HASH,
            FilteredKey("config_file"): AnonymityConversion.HASH,
        }


__all__ = ("CodeWeaverProviderSettings",)
