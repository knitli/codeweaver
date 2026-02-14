# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency types and factories for SDK clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAliasType

from codeweaver.core import ProviderCategoryLiteralString
from codeweaver.core.types import LiteralProviderCategory, ProviderCategory
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
    for setting in settings:
        embed_config = setting.embed_config
        setting.model_config if hasattr(setting, "model_config") else {}
        if card := setting.client.card_for_provider_and_category(
            setting.provider, type(setting).category.variable, str(embed_config.model_name)
        ):
            await card.create_instance(target="client")
        card.client_cls._resolve()


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
# [^1]: pydantic_ai Providers can receive auth and connection parameters or a client instance, but typically construct the client internally. All CodeWeaver providers expect a client instance to be passed in, and don't handle auth or connection management directly. Since pydantic_ai allows this, we stick to the pattern for Agents, passing in a constructed client. If we didn't, we'd lose our extensive customization of the client construction process, which is part of our "everything configurable; nothing requires configuration" philosophy.
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
#      provider = infer_provider(provider_name, api_key=...)
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
#          tools=tools,
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
#     less relevant, since most of the complexity is in the provider/model layer.
#
# The pydantic_ai approach is more flexible and has cleaner separation of concerns,
# but requires understanding its multi-layer architecture for proper construction.
#
# The CodeWeaver approach is simpler and more consistent across categories, but can lead to more complex
# provider implementations that handle both auth and API logic, may also require: more boilerplate in providers,
# and more overlap between provider implementations.
#
# We may eventually want to move our architecture closer to the pydantic_ai pattern, or even directly extend it. # We didn't do it originally because we didn't understand it, and that's a good indicator that it might be a
# barrier to contributions or extensibility. It's not magic, but it's also not intuitive.
