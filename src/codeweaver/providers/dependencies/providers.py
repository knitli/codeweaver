# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency types and factories for SDK clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAliasType, cast

from codeweaver.core import ProviderCategoryLiteralString
from codeweaver.core.types import LiteralProviderCategory, ProviderCategory
from codeweaver.providers.config import ProviderCategorySettingsType
from codeweaver.providers.config.categories import (
    AsymmetricEmbeddingProviderSettings,
    BaseProviderCategorySettings,
)
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


async def _instantiate_provider_from_settings[T](
    settings: BaseProviderCategorySettings, interface: type[T]
) -> T:
    """Universal factory to instantiate a provider from its settings.

    This replaces the manual `get_client` logic in settings classes and
    unifies on the `ServiceCard` registry.
    """
    from codeweaver.core.di.container import get_container
    from codeweaver.core.types.service_cards import get_service_card
    from codeweaver.providers.embedding.capabilities import EmbeddingModelCapabilities
    from codeweaver.providers.embedding.registry import EmbeddingRegistry
    from codeweaver.providers.types import EmbeddingCapabilityGroup

    # 1. Resolve the ServiceCard
    model_hint = getattr(settings, "model_name", None)
    card = get_service_card(
        provider=settings.provider.variable,
        category=settings.category.variable,
        client_preference=settings.client.variable,
        model_hint=str(model_hint) if model_hint else None,
    )

    if not card:
        raise ValueError(
            f"No ServiceCard found for {settings.provider}/{settings.category} "
            f"with client {settings.client}"
        )

    # 2. Get client options
    client_options = settings.client_options.as_settings() if settings.client_options else {}

    # 3. Create the client instance
    client = await card.create_instance_async(target="client", **client_options)

    # 4. Resolve Category-Specific Dependencies
    container = get_container()
    provider_kwargs = {"client": client, "config": settings}

    match settings.category:
        case ProviderCategory.EMBEDDING | ProviderCategory.SPARSE_EMBEDDING:
            provider_kwargs["registry"] = await container.resolve(EmbeddingRegistry)
            # EmbeddingCacheManager might not be available yet, using Any for now or resolving it
            try:
                # Need to import it here to avoid circulars
                from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager

                provider_kwargs["cache_manager"] = await container.resolve(EmbeddingCacheManager)
            except (ImportError, KeyError):
                provider_kwargs["cache_manager"] = None

            # Resolve capabilities for the specific model
            if model_hint:
                try:
                    provider_kwargs["caps"] = await container.resolve(
                        EmbeddingModelCapabilities, tags={str(model_hint)}
                    )
                except (KeyError, Exception):
                    provider_kwargs["caps"] = None

        case ProviderCategory.VECTOR_STORE:
            provider_kwargs["caps"] = await container.resolve(EmbeddingCapabilityGroup)

        case ProviderCategory.RERANKING:
            # Reranking providers might need capabilities too
            pass

    # 5. Create the provider instance
    # Most providers take (client, config, ...)
    provider = await card.create_instance_async(target="provider", **provider_kwargs)

    return cast(T, provider)


from codeweaver.core.di.utils import dependency_provider


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
    """Factory function to create embedding providers."""
    category_settings = await _get_settings_for_category("embedding")

    providers = []
    for settings in category_settings:
        if isinstance(settings, AsymmetricEmbeddingProviderSettings):
            # For asymmetric, we instantiate both providers
            # They should probably be returned as a specialized composite or just both in the collection
            embed_provider = await _instantiate_provider_from_settings(
                settings.embed_provider, EmbeddingProvider
            )
            query_provider = await _instantiate_provider_from_settings(
                settings.query_provider, EmbeddingProvider
            )
            providers.extend([embed_provider, query_provider])
        else:
            provider = await _instantiate_provider_from_settings(settings, EmbeddingProvider)
            providers.append(provider)

    return tuple(providers)


from codeweaver.providers.embedding import SparseEmbeddingProvider


@dependency_provider(
    SparseEmbeddingProvider, scope="singleton", tags=["sparse_embedding"], collection=True
)
async def _create_sparse_embedding_providers() -> tuple[SparseEmbeddingProvider, ...]:
    """Factory function to create sparse embedding providers."""
    category_settings = await _get_settings_for_category("sparse_embedding")
    return tuple(
        await _instantiate_provider_from_settings(s, SparseEmbeddingProvider)
        for s in category_settings
    )


from codeweaver.providers.agent.providers import AgentProvider


@dependency_provider(AgentProvider, scope="singleton", tags=["agent"], collection=True)
async def _create_agent_providers() -> tuple[AgentProvider, ...]:
    """Factory function to create agent providers."""
    category_settings = await _get_settings_for_category("agent")
    return tuple(
        await _instantiate_provider_from_settings(s, AgentProvider) for s in category_settings
    )


from codeweaver.providers.vector_stores.base import VectorStoreProvider


@dependency_provider(VectorStoreProvider, scope="singleton", tags=["vector_store"], collection=True)
async def _create_vector_store_providers() -> tuple[VectorStoreProvider, ...]:
    """Factory function to create vector store providers."""
    category_settings = await _get_settings_for_category("vector_store")
    return tuple(
        await _instantiate_provider_from_settings(s, VectorStoreProvider) for s in category_settings
    )


from codeweaver.providers.reranking.providers.base import RerankingProvider


@dependency_provider(RerankingProvider, scope="singleton", tags=["reranking"], collection=True)
async def _create_reranking_providers() -> tuple[RerankingProvider, ...]:
    """Factory function to create reranking providers."""
    category_settings = await _get_settings_for_category("reranking")
    return tuple(
        await _instantiate_provider_from_settings(s, RerankingProvider) for s in category_settings
    )
