# sourcery skip: no-complex-if-expressions
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

from typing import Annotated, Any, TypedDict, cast

from pydantic import DirectoryPath, Field, FilePath
from pydantic_settings import SettingsConfigDict

from codeweaver.core.config._logging import LoggingSettingsDict
from codeweaver.core.config.core_settings import CodeWeaverCoreSettings
from codeweaver.core.config.telemetry import TelemetrySettingsDict
from codeweaver.core.types.sentinel import UNSET, Unset
from codeweaver.core.utils import is_test_environment
from codeweaver.providers.config import ProviderProfile
from codeweaver.providers.config.providers import ProviderSettings, ProviderSettingsDict


class CodeWeaverProviderSettings(CodeWeaverCoreSettings):
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

    model_config = model_config = CodeWeaverCoreSettings.model_config | SettingsConfigDict(
        title="CodeWeaver Provider Settings"
    )

    provider: Annotated[
        ProviderSettings | Unset,
        Field(description="Provider configuration for embedding, vector store, reranking, etc."),
    ] = UNSET

    profile: Annotated[
        ProviderProfile | Unset | None,
        Field(
            description="""Use a premade provider profile.  The recommended profile uses Voyage AI for top-quality embedding and reranking, but requires an API key. The quickstart profile is entirely free and local, and does not require any API key. It sacrifices some search quality and performance compared to the recommended profile. The testing profile is only recommended for testing -- it uses an in-memory vector store and very light weight local models. The testing profile is also CodeWeaver's backup system when a cloud embedding or vector store provider isn't available. Both the quickstart and recommended profiles default to a local qdrant instance for the vector store. If you want to use a cloud or remote instance (which we recommend) you must also provide a URL for it, either with the environment variable CODEWEAVER_VECTOR_STORE_URL or in your codeweaver config in the vector_store settings.""",
            validate_default=False,
        ),
    ] = (
        profile
        if (profile := os.environ.get("CODEWEAVER_PROFILE"))
        and profile.lower() in tuple(p.name.lower() for p in ProviderProfile)
        else UNSET
    )  # ty: ignore[invalid-assignment]

    def __init__(
        self,
        provider: ProviderSettings | Unset = UNSET,
        profile: ProviderProfile | Unset | None = UNSET,
        **data: Any,
    ) -> None:
        """Initialize provider settings."""
        self._set_unset_fields(provider=provider, profile=profile)
        if (provider is UNSET or provider is None) and profile is not UNSET and profile is not None:
            data["provider"] = ProviderSettings.model_construct(
                **cast(ProviderProfile, profile).as_provider_settings()
            )
        if provider is not UNSET and provider is not None:
            if profile is not UNSET and profile is not None:
                data["provider"] = ProviderSettings.model_construct(
                    **(
                        self._resolve_default_and_provided(
                            cast(ProviderProfile, profile).as_provider_settings(),
                            provider.model_dump(),
                        )
                    )
                )
            else:
                data["provider"] = provider
        else:
            actual_profile = profile if profile is not UNSET and profile is not None else (
                ProviderProfile.TESTING if is_test_environment() else ProviderProfile.RECOMMENDED
            )
            data["provider"] = ProviderSettings.model_construct(
                **cast(ProviderProfile, actual_profile).as_provider_settings()
            )
        super().__init__(**data)

    async def _initialize(self, **kwargs: Any) -> None:
        """Initialize provider settings."""
        if is_test_environment() and "profile" not in kwargs and self.profile is UNSET:
            kwargs["profile"] = ProviderProfile.TESTING
            self.provider = UNSET
        profile_config = kwargs.get("profile") or self.profile
        if (
            (provider_config := kwargs.get("provider") or self.provider)
            and provider_config is not UNSET
            and profile_config
            and profile_config is not UNSET
        ):
            provider = ProviderSettings.model_validate(
                **(
                    self._resolve_default_and_provided(
                        cast(ProviderProfile, profile_config).as_provider_settings(),
                        provider_config
                        if isinstance(provider_config, dict)
                        else provider_config.model_dump(),
                    )
                )
            )
        else:
            provider = ProviderSettings.model_construct(
                **(
                    cast(ProviderProfile, profile_config or ProviderProfile.RECOMMENDED)
                ).as_provider_settings()
            )
        self.provider = provider
        await super()._initialize(**kwargs)


class CodeWeaverProviderSettingsDict(TypedDict, total=False):
    """TypedDict for CodeWeaver provider settings."""

    project_path: DirectoryPath | None
    project_name: str | None
    config_file: FilePath | None
    logging: LoggingSettingsDict | None
    provider: ProviderSettingsDict
    profile: ProviderProfile | None
    telemetry: TelemetrySettingsDict | None


__all__ = ("CodeWeaverProviderSettings", "CodeWeaverProviderSettingsDict")
