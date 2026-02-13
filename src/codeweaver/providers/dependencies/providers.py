# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency types and factories for SDK clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAliasType

from codeweaver.core import INJECTED, ProviderCategoryLiteralString
from codeweaver.core.dependencies import ServiceCardsDep
from codeweaver.core.types import (
    LiteralProvider,
    LiteralProviderCategory,
    LiteralSDKClient,
    ModelNameT,
    ProviderCategory,
)
from codeweaver.providers.config import ProviderCategorySettingsType
from codeweaver.providers.config.categories import AsymmetricEmbeddingProviderSettings
from codeweaver.providers.embedding import EmbeddingProvider


if TYPE_CHECKING:
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType
    from codeweaver.providers.config.providers import ProviderSettings


async def _resolve_type_from_container[T: Any | TypeAliasType[Any]](provider_type: type[T]) -> T:
    """Helper function to resolve a provider type from the DI container."""
    from codeweaver.core.di.container import get_container

    container = get_container()
    return await container.resolve(provider_type)


async def _get_global_settings() -> CodeWeaverSettingsType:
    """Get the global settings from the DI container."""
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType

    return await _resolve_type_from_container(CodeWeaverSettingsType)


async def _get_provider_settings() -> ProviderSettings:
    """Get the provider settings from the global settings."""
    global_settings = await _get_global_settings()
    return global_settings.providers


async def _get_settings_for_category(
    category: ProviderCategoryLiteralString,
) -> tuple[ProviderCategorySettingsType, ...]:
    """Get the settings for a given provider category."""
    match category:
        case "agent":
            return await _get_provider_settings().agent
        case "embedding":
            return await _get_provider_settings().embedding
        case "data":
            return await _get_provider_settings().data
        case "sparse_embedding":
            return await _get_provider_settings().sparse_embedding
        case "vector_store":
            return await _get_provider_settings().vector_store
        case "reranking":
            return await _get_provider_settings().reranking
    raise ValueError(f"Unknown provider category: {category}")


from codeweaver.core.di.utils import dependency_provider


async def _get_service_card_for_provider(
    provider: LiteralProvider,
    category: LiteralProviderCategory,
    model_name: ModelNameT,
    sdk: LiteralSDKClient,
    service_cards: ServiceCardsDep = INJECTED,
) -> str | None:
    """Get the service card for a given provider."""


def _properties_for_category(
    category: LiteralProviderCategory,
) -> dict[LiteralProviderCategory, set[str]]:
    """Get the properties for a given provider category."""
    return {
        ProviderCategory.AGENT: {"agent_config"},
        ProviderCategory.DATA: {"tool_config"},
        ProviderCategory.EMBEDDING: {"embed_config", "query_config"},
        ProviderCategory.SPARSE_EMBEDDING: {"embed_config", "query_config"},
        ProviderCategory.RERANKING: {"reranking_config"},
        ProviderCategory.VECTOR_STORE: {"collection"},
    }[category]


@dependency_provider(EmbeddingProvider, scope="singleton", tags=["embedding"], collection=True)
async def _create_embedding_providers() -> tuple[EmbeddingProvider, ...]:
    """Factory function to create embedding providers.

    Because of asymmetric retrieval configs, we need to handle this category specially.
    """
    settings = await _get_settings_for_category("embedding")
    settings = settings.embedding
    if isinstance(settings, AsymmetricEmbeddingProviderSettings) or (
        isinstance(settings, tuple)
        and settings
        and isinstance(settings[0], AsymmetricEmbeddingProviderSettings)
    ):
        others = settings[1:] if len(settings) > 1 else ()
        settings = (
            (settings.embed_provider, settings.query_provider, *others)
            if isinstance(settings, AsymmetricEmbeddingProviderSettings)
            else (settings[0].embed_provider, settings[1].query_provider, *others)
        )
    if not isinstance(settings, tuple):
        settings = (settings,)
    providers = []
    for setting in settings:
        client_options = setting.client_options
        embed_config = setting.embed_config
        query_config = setting.query_config
        model_config = setting.model_config if hasattr(setting, "model_config") else {}
