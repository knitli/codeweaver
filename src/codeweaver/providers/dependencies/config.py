# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider configuration dependencies and factories."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from codeweaver.core.dependencies.utils import ensure_settings_initialized


ensure_settings_initialized()

from codeweaver.core.config.settings_type import CodeWeaverSettingsType


async def _get_global_settings() -> CodeWeaverSettingsType:
    """Get the global CodeWeaver settings."""
    from codeweaver.core.di.container import get_container

    container = get_container()
    return await container.resolve(CodeWeaverSettingsType)


from codeweaver.core.di.dependency import depends
from codeweaver.core.di.utils import dependency_provider
from codeweaver.providers.config.providers import ProviderSettings


@dependency_provider(ProviderSettings, scope="singleton", tags=["provider_settings"])
async def _get_provider_settings() -> ProviderSettings:
    """Get the provider settings from the global settings."""
    global_settings = await _get_global_settings()
    provider_settings = global_settings.provider
    if provider_settings is None:
        raise ValueError("Provider settings not found in global settings.")
    return provider_settings


type ProviderSettingsDep = Annotated[
    ProviderSettings, depends(_get_provider_settings, use_cache=False)
]
"""Type alias for DI injection of root provider settings."""

from codeweaver.core.exceptions import ConfigurationError
from codeweaver.providers.config.categories import (
    AgentProviderSettingsType,
    DataProviderSettingsType,
    EmbeddingProviderSettingsType,
    RerankingProviderSettingsType,
    SparseEmbeddingProviderSettingsType,
    VectorStoreProviderSettingsType,
)


def _get_primary_provider_config_for[
    T: EmbeddingProviderSettingsType
    | SparseEmbeddingProviderSettingsType
    | RerankingProviderSettingsType
    | VectorStoreProviderSettingsType
    | AgentProviderSettingsType
    | DataProviderSettingsType
](settings: Sequence[T]) -> T:
    """Helper to get the primary provider config from a sequence of configs."""
    if settings:
        return settings[0] if isinstance(settings, tuple) else settings
    raise ConfigurationError(
        "No provider configuration found",
        suggestions=["Ensure at least one provider is configured in settings"],
    )


@dependency_provider(EmbeddingProviderSettingsType, scope="singleton", collection=True)
async def _get_embedding_provider_settings() -> tuple[EmbeddingProviderSettingsType, ...]:
    """Get the embedding provider settings."""
    provider_settings = await _get_provider_settings()
    return (
        provider_settings.embedding
        if isinstance(provider_settings.embedding, tuple)
        else (provider_settings.embedding,)
    )


type AllEmbeddingConfigsDep = Annotated[
    Sequence[EmbeddingProviderSettingsType],
    depends(_get_embedding_provider_settings, use_cache=False),
]
"""Type alias for DI injection of all embedding provider settings.
"""


@dependency_provider(EmbeddingProviderSettingsType, scope="singleton")
async def _create_primary_embedding_config() -> EmbeddingProviderSettingsType:
    """Factory for creating PRIMARY embedding config from settings."""
    configs = await _get_embedding_provider_settings()
    return _get_primary_provider_config_for(configs)


type EmbeddingProviderSettingsDep = Annotated[
    EmbeddingProviderSettingsType, depends(_create_primary_embedding_config, use_cache=False)
]
"""Type alias for DI injection of primary embedding provider settings.
"""


@dependency_provider(SparseEmbeddingProviderSettingsType, scope="singleton", collection=True)
async def _get_sparse_embedding_provider_settings() -> tuple[
    SparseEmbeddingProviderSettingsType, ...
]:
    """Get the sparse embedding provider settings."""
    provider_settings = await _get_provider_settings()
    return (
        provider_settings.sparse_embedding
        if isinstance(provider_settings.sparse_embedding, tuple)
        else (provider_settings.sparse_embedding,)
    )


type AllSparseEmbeddingConfigsDep = Annotated[
    Sequence[SparseEmbeddingProviderSettingsType],
    depends(_get_sparse_embedding_provider_settings, use_cache=False),
]
"""Type alias for DI injection of all sparse embedding provider settings.
"""


@dependency_provider(SparseEmbeddingProviderSettingsType, scope="singleton")
async def _create_primary_sparse_embedding_config() -> SparseEmbeddingProviderSettingsType:
    """Factory for creating PRIMARY sparse embedding config from settings."""
    configs = await _get_sparse_embedding_provider_settings()
    return _get_primary_provider_config_for(configs)


type SparseEmbeddingProviderSettingsDep = Annotated[
    SparseEmbeddingProviderSettingsType,
    depends(_create_primary_sparse_embedding_config, use_cache=False),
]
"""Type alias for DI injection of primary sparse embedding provider settings.
"""


@dependency_provider(RerankingProviderSettingsType, scope="singleton", collection=True)
async def _get_reranking_provider_settings() -> tuple[RerankingProviderSettingsType, ...]:
    """Get the reranking provider settings."""
    provider_settings = await _get_provider_settings()
    return (
        provider_settings.reranking
        if isinstance(provider_settings.reranking, tuple)
        else (provider_settings.reranking,)
    )


type AllRerankingConfigsDep = Annotated[
    Sequence[RerankingProviderSettingsType],
    depends(_get_reranking_provider_settings, use_cache=False),
]
"""Type alias for DI injection of all reranking provider settings.
"""


@dependency_provider(RerankingProviderSettingsType, scope="singleton")
async def _create_primary_reranking_config() -> RerankingProviderSettingsType:
    """Factory for creating PRIMARY reranking config from settings."""
    configs = await _get_reranking_provider_settings()
    return _get_primary_provider_config_for(configs)


type RerankingProviderSettingsDep = Annotated[
    RerankingProviderSettingsType, depends(_create_primary_reranking_config, use_cache=False)
]
"""Type alias for DI injection of primary reranking provider settings.
"""


@dependency_provider(VectorStoreProviderSettingsType, scope="singleton", collection=True)
async def _get_vector_store_provider_settings() -> tuple[VectorStoreProviderSettingsType, ...]:
    """Get the vector store provider settings."""
    provider_settings = await _get_provider_settings()
    return (
        provider_settings.vector_store
        if isinstance(provider_settings.vector_store, tuple)
        else (provider_settings.vector_store,)
    )


type AllVectorStoreConfigsDep = Annotated[
    Sequence[VectorStoreProviderSettingsType],
    depends(_get_vector_store_provider_settings, use_cache=False),
]
"""Type alias for DI injection of all vector store provider settings.
"""


@dependency_provider(VectorStoreProviderSettingsType, scope="singleton")
async def _create_primary_vector_store_config() -> VectorStoreProviderSettingsType:
    """Factory for creating PRIMARY vector store config from settings."""
    configs = await _get_vector_store_provider_settings()
    return _get_primary_provider_config_for(configs)


type VectorStoreProviderSettingsDep = Annotated[
    VectorStoreProviderSettingsType, depends(_create_primary_vector_store_config, use_cache=False)
]
"""Type alias for DI injection of primary vector store provider settings.
"""


@dependency_provider(AgentProviderSettingsType, scope="singleton", collection=True)
async def _get_agent_provider_settings() -> tuple[AgentProviderSettingsType, ...]:
    """Get the agent provider settings."""
    provider_settings = await _get_provider_settings()
    return (
        provider_settings.agent
        if isinstance(provider_settings.agent, tuple)
        else (provider_settings.agent,)
    )


type AllAgentProviderConfigsDep = Annotated[
    Sequence[AgentProviderSettingsType], depends(_get_agent_provider_settings, use_cache=False)
]
"""Type alias for DI injection of all agent provider settings.
"""


@dependency_provider(AgentProviderSettingsType, scope="singleton")
async def _create_primary_agent_provider_config() -> AgentProviderSettingsType:
    """Factory for creating PRIMARY agent provider config from settings."""
    configs = await _get_agent_provider_settings()
    return _get_primary_provider_config_for(configs)


type AgentProviderSettingsDep = Annotated[
    AgentProviderSettingsType, depends(_create_primary_agent_provider_config, use_cache=False)
]
"""Type alias for DI injection of primary agent provider settings.
"""


@dependency_provider(DataProviderSettingsType, scope="singleton", collection=True)
async def _get_data_provider_settings() -> tuple[DataProviderSettingsType, ...]:
    """Get the data provider settings."""
    provider_settings = await _get_provider_settings()
    return (
        provider_settings.data
        if isinstance(provider_settings.data, tuple)
        else (provider_settings.data,)
    )


type AllDataProviderConfigsDep = Annotated[
    Sequence[DataProviderSettingsType], depends(_get_data_provider_settings, use_cache=False)
]
"""Type alias for DI injection of all data provider settings.
"""


@dependency_provider(DataProviderSettingsType, scope="singleton")
async def _create_primary_data_provider_config() -> DataProviderSettingsType:
    """Factory for creating PRIMARY data provider config from settings."""
    configs = await _get_data_provider_settings()
    return _get_primary_provider_config_for(configs)


type DataProviderSettingsDep = Annotated[
    DataProviderSettingsType, depends(_create_primary_data_provider_config, use_cache=False)
]
"""Type alias for DI injection of primary data provider settings.
"""


__all__ = (
    "AgentProviderSettingsDep",
    "AllAgentProviderConfigsDep",
    "AllDataProviderConfigsDep",
    "AllEmbeddingConfigsDep",
    "AllRerankingConfigsDep",
    "AllSparseEmbeddingConfigsDep",
    "AllVectorStoreConfigsDep",
    "DataProviderSettingsDep",
    "EmbeddingProviderSettingsDep",
    "ProviderSettingsDep",
    "RerankingProviderSettingsDep",
    "SparseEmbeddingProviderSettingsDep",
    "VectorStoreProviderSettingsDep",
)
