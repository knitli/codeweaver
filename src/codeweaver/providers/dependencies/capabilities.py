# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider capabilities dependencies and factories."""

from __future__ import annotations

from typing import Annotated

from codeweaver.core.dependencies.utils import ensure_container_initialized
from codeweaver.core.di.dependency import depends
from codeweaver.core.di.utils import dependency_provider
from codeweaver.providers import EmbeddingCapabilityGroup
from codeweaver.providers.agent.resolver import AgentCapabilityResolver
from codeweaver.providers.embedding.capabilities.resolver import (
    EmbeddingCapabilityResolver,
    SparseEmbeddingCapabilityResolver,
)
from codeweaver.providers.reranking.capabilities.resolver import RerankingCapabilityResolver
from codeweaver.providers.types import ConfiguredCapability


ensure_container_initialized()


async def _resolve_type_from_container(provider_type: type) -> object:
    """Helper function to resolve a provider type from the DI container."""
    from codeweaver.core.di.container import get_container

    container = get_container()
    return await container.resolve(provider_type)


@dependency_provider(EmbeddingCapabilityResolver, scope="singleton")
def _get_embedding_capability_resolver() -> EmbeddingCapabilityResolver:
    """Factory for creating an EmbeddingCapabilityResolver instance."""
    return EmbeddingCapabilityResolver()


@dependency_provider(SparseEmbeddingCapabilityResolver, scope="singleton")
def _get_sparse_embedding_capability_resolver() -> SparseEmbeddingCapabilityResolver:
    """Factory for creating a SparseEmbeddingCapabilityResolver instance."""
    return SparseEmbeddingCapabilityResolver()


@dependency_provider(RerankingCapabilityResolver, scope="singleton")
def _get_reranking_capability_resolver() -> RerankingCapabilityResolver:
    """Factory for creating a RerankingCapabilityResolver instance."""
    return RerankingCapabilityResolver()


@dependency_provider(AgentCapabilityResolver, scope="singleton")
def _get_agent_capability_resolver() -> AgentCapabilityResolver:
    """Factory for creating an AgentCapabilityResolver instance."""
    return AgentCapabilityResolver()


def _assemble_configured_capabilities(
    dense_configs,
    sparse_configs,
    dense_resolver: EmbeddingCapabilityResolver,
    sparse_resolver: SparseEmbeddingCapabilityResolver,
):
    """Assemble configured capabilities from dense and sparse configs."""
    dense_caps = (
        dense_resolver.resolve(config.model_name or config.embedding_config.model_name)
        for config in dense_configs
    )
    sparse_caps = (
        sparse_resolver.resolve(config.model_name or config.sparse_embedding_config.model_name)
        for config in sparse_configs
    )
    dense_conf_caps = zip(dense_configs, dense_caps, strict=True)
    sparse_conf_caps = zip(sparse_configs, sparse_caps, strict=True)

    return tuple(
        ConfiguredCapability(*conf_tup) for conf_tup in (*dense_conf_caps, *sparse_conf_caps)
    )


@dependency_provider(ConfiguredCapability, scope="singleton", collection=True)
async def _create_all_configured_capabilities() -> tuple[ConfiguredCapability, ...]:
    """Get all configured capabilities for providers."""
    from codeweaver.core.dependencies.utils import ensure_settings_initialized

    ensure_settings_initialized()
    from codeweaver.providers.config.providers import ProviderSettings

    settings = await _resolve_type_from_container(ProviderSettings)
    dense_configs = (
        settings.embedding if isinstance(settings.embedding, tuple) else (settings.embedding,)
    )
    sparse_configs = (
        settings.sparse_embedding
        if isinstance(settings.sparse_embedding, tuple)
        else (settings.sparse_embedding,)
    )
    dense_resolver = await _resolve_type_from_container(EmbeddingCapabilityResolver)
    sparse_resolver = await _resolve_type_from_container(SparseEmbeddingCapabilityResolver)
    return _assemble_configured_capabilities(
        dense_configs, sparse_configs, dense_resolver, sparse_resolver
    )


@dependency_provider(EmbeddingCapabilityGroup, scope="singleton")
async def _create_embedding_capability_group() -> EmbeddingCapabilityGroup:
    """Factory for creating an EmbeddingCapabilityGroup instance."""
    capabilities = await _create_all_configured_capabilities()
    dense = next((cap for cap in capabilities if cap.is_dense), None)
    sparse = next((cap for cap in capabilities if cap.is_sparse), None)
    idf = next((cap for cap in capabilities if cap.is_idf), None)
    if sparse == idf:
        sparse = None
    return EmbeddingCapabilityGroup(dense=dense, sparse=sparse, idf=idf)


from codeweaver_tokenizers import Tokenizer


@dependency_provider(Tokenizer, scope="singleton")
async def _get_tokenizer() -> Tokenizer:
    """Factory for creating a Tokenizer instance."""
    from codeweaver.providers.config.providers import ProviderSettings

    settings = await _resolve_type_from_container(ProviderSettings)
    embedding_settings = (
        settings.embedding[0] if isinstance(settings.embedding, tuple) else settings.embedding
    )
    config = (
        embedding_settings.embedding_config
        if embedding_settings.config_type == "symmetric"
        else embedding_settings.embedding_provider.embedding_config
    )
    from codeweaver_tokenizers import get_tokenizer

    if (
        config
        and config.capabilities
        and (tokenizer := config.capabilities.tokenizer)
        and (tokenizer_name := config.capabilities.tokenizer_model)
    ):
        return get_tokenizer(tokenizer, tokenizer_name)
    return get_tokenizer("tiktoken", "o200k_base")


type EmbeddingCapabilityResolverDep = Annotated[
    EmbeddingCapabilityResolver, depends(_get_embedding_capability_resolver)
]
"""DI type for EmbeddingCapabilityResolver dependency. Use this type in function signatures to have the EmbeddingCapabilityResolver automatically injected by the DI container."""

type SparseCapabilityResolverDep = Annotated[
    SparseEmbeddingCapabilityResolver, depends(_get_sparse_embedding_capability_resolver)
]
"""DI type for SparseEmbeddingCapabilityResolver dependency. Use this type in function signatures to have the SparseEmbeddingCapabilityResolver automatically injected by the DI container."""

type RerankingCapabilityResolverDep = Annotated[
    RerankingCapabilityResolver, depends(_get_reranking_capability_resolver)
]
"""DI type for RerankingCapabilityResolver dependency. Use this type in function signatures to have the RerankingCapabilityResolver automatically injected by the DI container."""

type AgentCapabilityResolverDep = Annotated[
    AgentCapabilityResolver, depends(_get_agent_capability_resolver)
]
"""DI type for AgentCapabilityResolver dependency. Use this type in function signatures to have the AgentCapabilityResolver automatically injected by the DI container."""

type ConfiguredCapabilitiesDep = Annotated[
    tuple[ConfiguredCapability, ...], depends(_create_all_configured_capabilities)
]
"""DI type for all ConfiguredCapability dependencies. Use this type in function signatures to have all ConfiguredCapability instances automatically injected by the DI container."""

type EmbeddingCapabilityGroupDep = Annotated[
    EmbeddingCapabilityGroup, depends(_create_embedding_capability_group)
]
"""DI type for EmbeddingCapabilityGroup dependency. Use this type in function signatures to have the EmbeddingCapabilityGroup automatically injected by the DI container."""

type TokenizerDep = Annotated[Tokenizer, depends(_get_tokenizer)]
"""DI type for Tokenizer dependency. Use this type in function signatures to have the Tokenizer automatically injected by the DI container."""

__all__ = (
    "AgentCapabilityResolverDep",
    "ConfiguredCapabilitiesDep",
    "EmbeddingCapabilityGroupDep",
    "EmbeddingCapabilityResolverDep",
    "RerankingCapabilityResolverDep",
    "SparseCapabilityResolverDep",
    "TokenizerDep",
)
