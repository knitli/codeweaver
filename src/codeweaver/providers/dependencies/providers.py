# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency types and factories for SDK clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, TypeAliasType, cast

from pydantic_ai import Agent, Tool
from pydantic_ai.models import Model

from codeweaver.core import ProviderCategoryLiteralString
from codeweaver.core.types import LiteralProviderCategory, ProviderCategory
from codeweaver.providers.agent.providers import AgentProvider
from codeweaver.providers.config import ProviderCategorySettingsType
from codeweaver.providers.config.categories import (
    AsymmetricEmbeddingProviderSettings,
    BaseProviderCategorySettings,
)
from codeweaver.providers.embedding import EmbeddingProvider


if TYPE_CHECKING:
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType
    from codeweaver.core.types.service_cards import ServiceCard
    from codeweaver.providers.config.categories.agent import AgentProviderSettingsType
    from codeweaver.providers.config.providers import ProviderSettings


async def _resolve_type_from_container[T: Any | TypeAliasType[Any]](
    provider_type: type[T], *, tags: list[str] | None = None
) -> T:
    """Helper function to resolve a provider type from the DI container."""
    from codeweaver.core.di.container import get_container

    container = get_container()
    return await container.resolve(provider_type, tags=tags)


async def _get_global_settings() -> CodeWeaverSettingsType:
    """Get the global settings from the DI container."""
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType

    return await _resolve_type_from_container(CodeWeaverSettingsType)


async def _get_provider_settings() -> ProviderSettings:
    """Get the provider settings from the global settings."""
    global_settings = await _get_global_settings()
    return global_settings.provider


async def _get_settings_for_category(
    category: ProviderCategoryLiteralString,
) -> tuple[ProviderCategorySettingsType, ...]:
    """Get the settings for a given provider category."""
    provider_settings = await _get_provider_settings()
    match category:
        case "agent":
            return provider_settings.agent
        case "embedding":
            return provider_settings.embedding
        case "data":
            return provider_settings.data
        case "sparse_embedding":
            return provider_settings.sparse_embedding
        case "vector_store":
            return provider_settings.vector_store
        case "reranking":
            return provider_settings.reranking
    raise ValueError(f"Unknown provider category: {category}")


async def _get_capabilities_for_model(
    model_name: str, *, sparse: bool = False, reranking: bool = False
) -> Any:
    """Helper function to get capabilities for a specific model."""
    from codeweaver.core.di.container import get_container

    container = get_container()
    if reranking:
        from codeweaver.providers.reranking.capabilities.resolver import RerankingCapabilityResolver

        resolver = await container.resolve(RerankingCapabilityResolver)
    elif sparse:
        from codeweaver.providers.embedding.capabilities.resolver import (
            SparseEmbeddingCapabilityResolver,
        )

        resolver = await container.resolve(SparseEmbeddingCapabilityResolver)
    else:
        from codeweaver.providers.embedding.capabilities.resolver import EmbeddingCapabilityResolver

        resolver = await container.resolve(EmbeddingCapabilityResolver)
    return resolver.resolve(model_name)


# ===========================================================================
# *                      Agent Factory Architecture
# ===========================================================================
#
# Agents use a different construction pattern from other CodeWeaver providers because they're
# built on pydantic_ai, which uses a 3-layer architecture vs CodeWeaver's 2-layer pattern.
#
# ARCHITECTURE COMPARISON
# =======================
#
# pydantic_ai (3 layers):           CodeWeaver (2 layers):
#   1. Provider (auth/client) [^1]    1. Client (instance) (i.e. `anthropic.AsyncAnthropic`)
#   2. Model (API interface)          2. Provider (interface)
#   3. Agent (orchestration)
#
# [^1]: pydantic_ai Providers can receive auth and connection parameters *or* a client instance, but typically construct the client internally. All CodeWeaver providers expect a client instance to be passed in, and don't handle auth or connection management directly. Since pydantic_ai allows this, we stick to the pattern for Agents, passing in a constructed client. If we didn't, we'd lose our extensive customization of the client construction process, which is part of our "everything configurable; nothing requires configuration" philosophy.
#
#
# COMPONENT MAPPING
# =================
#
# Pydantic AI          | CodeWeaver Alias     | Purpose
# ---------------------|----------------------|----------------------------------
# Provider             | AgentProvider        | Auth, connection management
# Model                | (no equivalent)      | API abstraction layer
# ModelSettings        | AgentModelConfig     | Request config (temp, max_tokens)
# ModelProfile         | AgentModelCapabilities* | API compatibility (JSON schemas)
# Agent                | (no equivalent)      | Conversation orchestration
#
# * Note: ModelProfile is more focused on API compatibility than general capabilities
#
# CONSTRUCTION FLOW
# =================
#
# Factory must perform 3-step construction:
#
#   1. Construct Provider (client wrapper with auth):
#      # This following is how pydantic_ai constructs providers internally:
#      provider = infer_provider(provider_name, api_key=...)
#      # but we can also (and will):
#      provider = SomeProviderClass(client=constructed_client)
#
#   2. Construct Model (with provider + settings + profile):
#      model = ModelClass(
#          model_name,
#          provider=provider,
#          settings=agent_model_config,
#          profile=None  # Usually auto-selected by provider
#      ) # unlike with CodeWeaver providers, you don't need to pass profile/capabilities here.
# we do resolve profiles internally, but primarily for things like the cli `list` command.
#
#   3. Construct Agent (with model + tools + prompts):
#      agent = Agent(
#          model,
#          output_type=output_type,
#          tools=tools,  <-- N.B. tools are CodeWeaver's 'data providers', which are Tool instances that wrap a provider.
#          system_prompt=system_prompt
#      )
#
# WHY THE DIFFERENCE?
# ===================
#
# pydantic_ai prioritizes:
#   - Multi-vendor flexibility (swap providers without code changes)
#   - Composability (mix providers/models/profiles independently)
#   - Better separation of concerns (auth vs API vs orchestration)
#
# CodeWeaver prioritizes:
#   - Simplicity (direct provider interface)
#   - Consistency (unified pattern across categories)
#   - Ease of reasoning (fewer abstraction layers, simpler abstractions)
#   - CodeWeaver's focus on vector search and embeddings means the third abstraction layer for orchestration is
#     less relevant, since most of the complexity is in the provider/model layer for embedding/reranking models.
#
# The pydantic_ai approach is more flexible and has cleaner separation of concerns,
# but requires understanding its multi-layer architecture for proper construction.
#
# The CodeWeaver approach is simpler and more consistent across categories, but can lead to more complex
# provider implementations that handle both auth and API logic, may also require: more boilerplate in providers,
# and more overlap between provider implementations.
#
# We may eventually want to move our architecture closer to the pydantic_ai pattern, or even directly extend it.
#
# Importantly, we originally planned to follow the same pattern as Pydantic AI for all providers, but we changed
# course for one reason: we couldn't understand it. We do understand it now, but the learning curve was steep,
# which is a good argument against it.


async def _construct_agent_provider(
    provider_settings: AgentProviderSettingsType, card: ServiceCard
) -> AgentProvider:
    """Construct the AgentProvider instance based on its settings."""
    client_options = (
        provider_settings.client_options.as_settings() if provider_settings.client_options else {}
    )
    if card.metadata and card.metadata.provider_handler:
        # Card has a custom handler — let it manage client creation/passing.
        client_instance = await card.create_instance_async(target="client", **client_options)
        return await card.create_instance_async(target="provider", client=client_instance)
    # No provider_handler: instantiate the provider directly with client_options
    # (e.g., AnthropicProvider(api_key=...) instead of AnthropicProvider(client=...)).
    # Pydantic-ai providers accept api_key and similar kwargs directly.
    return await card.create_instance_async(target="provider", **client_options)


async def _get_agent_resolver() -> Any:
    """Get the ModelProfile (capabilities) for the AgentProvider based on its settings."""
    from codeweaver.core.di.container import get_container
    from codeweaver.providers.agent.resolver import AgentCapabilityResolver

    container = get_container()
    return await container.resolve(AgentCapabilityResolver)


async def _construct_model_for_agent_provider(
    provider_settings: AgentProviderSettingsType,
    card: ServiceCard,
    provider: AgentProvider | None = None,
) -> Model:
    """Construct the pydantic_ai Model instance for an AgentProvider based on its settings."""
    from pydantic_ai.models import infer_model

    model_settings = provider_settings.agent_config
    resolver = await _get_agent_resolver()
    model_name = provider_settings.model_name
    profile = resolver.resolve(model_name)
    provider = provider or await _construct_agent_provider(provider_settings, card)
    model_cls = type(infer_model(model_name, lambda: provider))
    return model_cls(model_name, provider=provider, profile=profile, settings=model_settings)  # ty:ignore[too-many-positional-arguments, unknown-argument]


async def _construct_multi_model_agent(
    models: tuple[Model, ...], tools: tuple[Tool, ...], system_prompt: str | None
) -> Agent:
    """Construct a pydantic_ai Agent instance that can orchestrate across multiple models."""
    from pydantic_ai.models.fallback import FallbackModel

    model = FallbackModel(models[0], *models[1:]) if len(models) > 1 else models[0]
    from pydantic_ai import Agent

    # TODO: Inject tools from data providers, add context agent system prompt
    return Agent(
        model, tools=tools, instructions=system_prompt
    )  # Tools and system prompt will be handled by the AgentProvider implementation


# ===========================================================================
# *                   Factories for Other Provider Categories
# ===========================================================================


async def _instantiate_provider_from_settings[T](
    settings: BaseProviderCategorySettings, interface: type[T]
) -> T:
    """Universal factory to instantiate a provider from its settings.

    This replaces the manual `get_client` logic in settings classes and
    unifies on the `ServiceCard` registry.

    NOTE: Agent providers don't use this factory. They're constructed separately because of their unique 3-layer architecture.
    """
    from codeweaver.core.di.container import get_container
    from codeweaver.core.types.service_cards import get_service_card
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
        case (
            ProviderCategory.EMBEDDING
            | ProviderCategory.SPARSE_EMBEDDING
            | ProviderCategory.RERANKING
        ):
            if settings.category in (ProviderCategory.EMBEDDING, ProviderCategory.SPARSE_EMBEDDING):
                provider_kwargs["registry"] = await container.resolve(EmbeddingRegistry)
                # EmbeddingCacheManager might not be available yet, using Any for now or resolving it
                try:
                    # Need to import it here to avoid circulars
                    from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager

                    provider_kwargs["cache_manager"] = await container.resolve(
                        EmbeddingCacheManager
                    )
                except (ImportError, AttributeError, KeyError):
                    provider_kwargs["cache_manager"] = None
            provider_kwargs["caps"] = await _get_capabilities_for_model(
                model_name=settings.model_name,
                sparse=settings.category == ProviderCategory.SPARSE_EMBEDDING,
                reranking=settings.category == ProviderCategory.RERANKING,
            )

        case ProviderCategory.VECTOR_STORE:
            provider_kwargs["caps"] = await container.resolve(EmbeddingCapabilityGroup)

        # NOTE: Data providers have no special handling for now, so this works without modification.
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


from codeweaver.core.di import INJECTED, depends


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


type EmbeddingProvidersDep = Annotated[
    tuple[EmbeddingProvider, ...],
    depends(_create_embedding_providers, use_cache=True, tags=["embedding"]),
]


@dependency_provider(EmbeddingProvider, scope="singleton", tags=["embedding", "corpus"])
async def _create_corpus_embedding_provider(
    providers: EmbeddingProvidersDep = INJECTED,
) -> EmbeddingProvider:
    """Factory function to create the primary embedding provider for corpus operations.

    If the user has asymmetric embedding providers configured, this returns the 'embed' provider. Otherwise, it returns the single symmetric embedding provider. This allows us to route corpus operations to the correct provider without requiring the user to specify it.
    """
    return providers[
        0
    ]  # This is the easy case; the first provider is always the 'embed' provider if there are asymmetric providers, and the only provider if there is just one symmetric provider.


type PrimaryEmbeddingProviderDep = Annotated[
    EmbeddingProvider,
    depends(_create_corpus_embedding_provider, use_cache=True, tags=["embedding", "corpus"]),
]


@dependency_provider(EmbeddingProvider, scope="singleton", tags=["embedding", "query"])
async def _create_query_embedding_provider(
    providers: EmbeddingProvidersDep = INJECTED,
) -> EmbeddingProvider:
    """Factory function to create the primary embedding provider for query operations.

    If the user has asymmetric embedding providers configured, this returns the 'query' provider. Otherwise, it returns the single symmetric embedding provider. This allows us to route query operations to the correct provider without requiring the user to specify it.
    """
    first_caps = getattr(providers[0], "caps", None)
    if len(providers) == 1 or not (first_caps and first_caps.model_family):
        # If there's only one provider, or the first provider doesn't have capabilities that
        # indicate it's an asymmetric 'embed' provider, assume it's a symmetric provider.
        return providers[0]
    return next(
        (
            p
            for p in providers[1:]
            if (p_caps := getattr(p, "caps", None))
            and p_caps.model_family == first_caps.model_family
        ),
        providers[0],
    )


type QueryEmbeddingProviderDep = Annotated[
    EmbeddingProvider,
    depends(_create_query_embedding_provider, use_cache=True, tags=["embedding", "query"]),
]

from codeweaver.providers.embedding import SparseEmbeddingProvider


@dependency_provider(
    SparseEmbeddingProvider, scope="singleton", tags=["sparse_embedding"], collection=True
)
async def _create_sparse_embedding_providers() -> tuple[SparseEmbeddingProvider, ...]:
    """Factory function to create sparse embedding providers."""
    category_settings = await _get_settings_for_category("sparse_embedding")
    providers = [
        await _instantiate_provider_from_settings(s, SparseEmbeddingProvider)
        for s in category_settings
    ]
    return tuple(providers)


type SparseEmbeddingProvidersDep = Annotated[
    tuple[SparseEmbeddingProvider, ...],
    depends(_create_sparse_embedding_providers, use_cache=True, tags=["sparse_embedding"]),
]


@dependency_provider(
    SparseEmbeddingProvider, scope="singleton", tags=["sparse_embedding", "primary"]
)
async def _create_primary_sparse_embedding_provider(
    providers: SparseEmbeddingProvidersDep = INJECTED,
) -> SparseEmbeddingProvider:
    """Factory function to create the primary sparse embedding provider.

    If the user has multiple sparse embedding providers configured, this returns the first one. This allows us to route operations to the correct provider without requiring the user to specify it.
    """
    return providers[0]


type PrimarySparseEmbeddingProviderDep = Annotated[
    SparseEmbeddingProvider,
    depends(
        _create_primary_sparse_embedding_provider,
        use_cache=True,
        tags=["sparse_embedding", "primary"],
    ),
]

from codeweaver.providers.data import DataProviderType


@dependency_provider(DataProviderType, scope="singleton", tags=["data"], collection=True)
async def _create_data_providers() -> tuple[DataProviderType, ...]:
    """Factory function to create data providers."""
    category_settings = await _get_settings_for_category("data")
    # Data providers are a bit unique in that they also need to resolve tools, which are also configured by the user and can wrap providers themselves. So we need to resolve those as well and pass them in.
    providers = []
    for settings in category_settings:
        provider = await _instantiate_provider_from_settings(settings, DataProviderType)
        providers.append(provider)
    return tuple(providers)


type DataProvidersDep = Annotated[
    tuple[DataProviderType, ...], depends(_create_data_providers, use_cache=True, tags=["data"])
]


@dependency_provider(Agent, scope="singleton", tags=["agent"])
async def _create_agent_providers(tools: DataProvidersDep = INJECTED) -> Agent | None:
    """Factory function to create agent providers.

    Returns None when no agent provider settings are configured (e.g., testing profile).
    """
    from codeweaver.core.types.service_cards import get_service_card

    tools = await _resolve_type_from_container(tuple[DataProviderType, ...], tags=["data"])
    category_settings = await _get_settings_for_category("agent")
    if not category_settings:
        return None
    service_cards = tuple(
        get_service_card(
            s.provider.variable,
            "agent",
            model_hint=str(s.model_name),
            client_preference=s.client_options.sdk_client.variable if s.client_options else None,
        )
        for s in category_settings
    )
    models = tuple([
        await _construct_model_for_agent_provider(s, card)
        for s, card in zip(category_settings, service_cards, strict=True)
    ])
    return await _construct_multi_model_agent(models=models, tools=tools, system_prompt=None)


type AgentProviderDep = Annotated[
    Agent | None, depends(_create_agent_providers, use_cache=True, tags=["agent"])
]

from codeweaver.providers.vector_stores.base import VectorStoreProvider


@dependency_provider(VectorStoreProvider, scope="singleton", tags=["vector_store"], collection=True)
async def _create_vector_store_providers() -> tuple[VectorStoreProvider, ...]:
    """Factory function to create vector store providers."""
    category_settings = await _get_settings_for_category("vector_store")
    providers = [
        await _instantiate_provider_from_settings(s, VectorStoreProvider)
        for s in category_settings
    ]
    return tuple(providers)


type VectorStoreProvidersDep = Annotated[
    tuple[VectorStoreProvider, ...],
    depends(_create_vector_store_providers, use_cache=True, tags=["vector_store"]),
]


@dependency_provider(VectorStoreProvider, scope="singleton", tags=["vector_store", "primary"])
async def _create_primary_vector_store_provider(
    providers: VectorStoreProvidersDep = INJECTED,
) -> VectorStoreProvider:
    """Factory function to create the primary vector store provider."""
    return providers[0]


type PrimaryVectorStoreProviderDep = Annotated[
    VectorStoreProvider,
    depends(
        _create_primary_vector_store_provider, use_cache=True, tags=["vector_store", "primary"]
    ),
]

from codeweaver.providers.reranking.providers.base import RerankingProvider


@dependency_provider(RerankingProvider, scope="singleton", tags=["reranking"], collection=True)
async def _create_reranking_providers() -> tuple[RerankingProvider, ...]:
    """Factory function to create reranking providers."""
    category_settings = await _get_settings_for_category("reranking")
    providers = [
        await _instantiate_provider_from_settings(s, RerankingProvider)
        for s in category_settings
    ]
    return tuple(providers)


type RerankingProvidersDep = Annotated[
    tuple[RerankingProvider, ...],
    depends(_create_reranking_providers, use_cache=True, tags=["reranking"]),
]

from codeweaver.providers.types.search import SearchPackage


@dependency_provider(SearchPackage, scope="singleton", tags=["search_package"])
async def _create_search_package(
    query_provider: QueryEmbeddingProviderDep = INJECTED,
    sparse_provider: PrimarySparseEmbeddingProviderDep = INJECTED,
    reranking_providers: RerankingProvidersDep = INJECTED,
    vector_store_provider: PrimaryVectorStoreProviderDep = INJECTED,
    agent_provider: AgentProviderDep = INJECTED,
) -> SearchPackage:
    """Factory function to create a search package.

    agent_provider may be None when no agent settings are configured (e.g., testing profile).
    """
    # agent_provider is Agent | None — SearchPackage accepts None gracefully.
    return SearchPackage(
        embedding=query_provider,
        sparse_embedding=sparse_provider,
        reranking=reranking_providers,
        vector_store=vector_store_provider,
        capabilities=None,  # Replace with actual capabilities if available
        agent=agent_provider,
    )


type SearchPackageDep = Annotated[
    SearchPackage, depends(_create_search_package, use_cache=True, tags=["search_package"])
]


__all__ = (
    "AgentProviderDep",
    "DataProvidersDep",
    "EmbeddingProvidersDep",
    "PrimaryEmbeddingProviderDep",
    "PrimarySparseEmbeddingProviderDep",
    "PrimaryVectorStoreProviderDep",
    "QueryEmbeddingProviderDep",
    "RerankingProvidersDep",
    "SearchPackageDep",
    "SparseEmbeddingProvidersDep",
    "VectorStoreProvidersDep",
)
