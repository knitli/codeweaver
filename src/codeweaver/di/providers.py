# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Standard dependency providers for CodeWeaver."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from codeweaver.di.depends import Depends


if TYPE_CHECKING:
    from codeweaver.common.registry import ModelRegistry, ProviderRegistry, ServicesRegistry
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.engine.chunker import ChunkGovernor
    from codeweaver.engine.chunking_service import ChunkingService
    from codeweaver.engine.failover import VectorStoreFailoverManager
    from codeweaver.engine.indexer.indexer import Indexer
    from codeweaver.providers.embedding.providers.base import EmbeddingProvider
    from codeweaver.providers.reranking.providers.base import RerankingProvider
    from codeweaver.providers.vector_stores.base import VectorStoreProvider
    from codeweaver.server.health.health_service import HealthService


async def get_embedding_provider() -> EmbeddingProvider:
    """Resolve the configured embedding provider from the registry.

    This factory bridges the old registry system with the new DI system.
    """
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    provider_enum = registry.get_provider_enum_for("embedding")
    if not provider_enum:
        from codeweaver.exceptions import ConfigurationError

        raise ConfigurationError("No embedding provider configured.")

    return registry.get_provider_instance(provider_enum, "embedding", singleton=True)  # type: ignore


async def get_sparse_embedding_provider() -> EmbeddingProvider | None:
    """Resolve the configured sparse embedding provider from the registry."""
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    if provider_enum := registry.get_provider_enum_for("sparse_embedding"):
        return registry.get_provider_instance(provider_enum, "sparse_embedding", singleton=True)  # type: ignore
    return None


async def get_vector_store() -> VectorStoreProvider:
    """Resolve the configured vector store provider from the registry."""
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    provider_enum = registry.get_provider_enum_for("vector_store")
    if not provider_enum:
        from codeweaver.exceptions import ConfigurationError

        raise ConfigurationError("No vector store provider configured.")

    return registry.get_provider_instance(provider_enum, "vector_store", singleton=True)  # type: ignore


async def get_chunk_governor() -> ChunkGovernor:
    """Resolve the chunk governor."""
    from codeweaver.common.registry import get_model_registry
    from codeweaver.config.chunker import ChunkerSettings
    from codeweaver.config.settings import Unset, get_settings
    from codeweaver.core.types.provider import ProviderKind
    from codeweaver.engine.chunker import ChunkGovernor

    settings = get_settings().chunker
    chunk_settings = ChunkerSettings() if isinstance(settings, Unset) else settings

    # Resolve capabilities for the governor
    registry = get_model_registry()
    embedding_caps = registry.configured_models_for_kind(ProviderKind.EMBEDDING) or ()
    reranking_caps = registry.configured_models_for_kind(ProviderKind.RERANKING) or ()

    return ChunkGovernor(settings=chunk_settings, capabilities=(*embedding_caps, *reranking_caps))


async def get_chunking_service() -> ChunkingService:
    """Resolve the chunking service."""
    from codeweaver.di import get_container
    from codeweaver.engine.chunking_service import ChunkingService

    # ChunkingService will have its own dependencies resolved by the container
    return await get_container().resolve(ChunkingService)


async def get_reranking_provider() -> RerankingProvider | None:
    """Resolve the configured reranking provider from the registry."""
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    if provider_enum := registry.get_provider_enum_for("reranking"):
        return registry.get_provider_instance(provider_enum, "reranking", singleton=True)  # type: ignore
    return None


async def get_settings() -> CodeWeaverSettings:
    """Resolve the global settings."""
    from codeweaver.config.settings import get_settings

    return get_settings()


async def get_indexer() -> Indexer:
    """Resolve the indexer service."""
    from codeweaver.engine.indexer.indexer import Indexer

    return await Indexer.from_settings_async()


async def get_ignore_filter() -> Any:
    """Resolve the ignore filter."""
    from codeweaver.engine.watcher.watch_filters import IgnoreFilter

    return await IgnoreFilter.from_settings_async()


async def get_tokenizer() -> Any:
    """Resolve the tokenizer for the configured embedding model."""
    from codeweaver_tokenizers import get_tokenizer

    provider = await get_embedding_provider()
    # Most models use "tokenizers", tiktoken is primarily for OpenAI
    tokenizer_type = getattr(provider.caps, "tokenizer", "tokenizers")
    tokenizer_model = getattr(provider.caps, "tokenizer_model", None) or provider.caps.name

    return get_tokenizer(tokenizer_type, tokenizer_model)  # type: ignore


async def get_provider_registry() -> ProviderRegistry:
    """Resolve the provider registry."""
    from codeweaver.common.registry import get_provider_registry

    return get_provider_registry()


async def get_services_registry() -> ServicesRegistry:
    """Resolve the services registry."""
    from codeweaver.common.registry import get_services_registry

    return get_services_registry()


async def get_model_registry() -> ModelRegistry:
    """Resolve the model registry."""
    from codeweaver.common.registry import get_model_registry

    return get_model_registry()


async def get_statistics() -> SessionStatistics:
    """Resolve the session statistics."""
    from codeweaver.common.statistics import get_session_statistics

    return get_session_statistics()


async def get_failover_manager() -> VectorStoreFailoverManager:
    """Resolve the failover manager."""
    from codeweaver.engine.failover import VectorStoreFailoverManager

    return VectorStoreFailoverManager()


async def get_health_service(
    provider_registry: ProviderRegistryDep,
    statistics: StatisticsDep,
    indexer: IndexerDep,
    failover_manager: FailoverManagerDep,
) -> HealthService:
    """Resolve the health service."""
    import time

    from codeweaver.server.health.health_service import HealthService

    return HealthService(
        provider_registry=provider_registry,
        statistics=statistics,
        indexer=indexer,
        failover_manager=failover_manager,
        startup_stopwatch=time.monotonic(),
    )


async def get_file_watcher(
    indexer: IndexerDep,
    ignore_filter: IgnoreFilterDep,
    settings: SettingsDep,
) -> Any:
    """Resolve the file watcher."""
    from codeweaver.common.utils.git import get_project_path
    from codeweaver.core.types.sentinel import Unset
    from codeweaver.engine.watcher.watcher import FileWatcher

    project_path = (
        get_project_path()
        if isinstance(settings.project_path, Unset)
        else settings.project_path
    )

    return await FileWatcher.create(
        project_path,
        indexer=indexer,
        file_filter=ignore_filter,
    )


def setup_default_container(container: Container) -> None:
    """Register all standard providers in the container."""
    from codeweaver.common.registry import ModelRegistry, ProviderRegistry, ServicesRegistry
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.engine.chunker import ChunkGovernor
    from codeweaver.engine.chunking_service import ChunkingService
    from codeweaver.engine.failover import VectorStoreFailoverManager
    from codeweaver.engine.indexer.indexer import Indexer
    from codeweaver.providers.embedding.providers.base import EmbeddingProvider
    from codeweaver.providers.reranking.providers.base import RerankingProvider
    from codeweaver.providers.vector_stores.base import VectorStoreProvider
    from codeweaver.server.health.health_service import HealthService

    container.register(ProviderRegistry, get_provider_registry)
    container.register(ServicesRegistry, get_services_registry)
    container.register(ModelRegistry, get_model_registry)
    container.register(SessionStatistics, get_statistics)
    container.register(CodeWeaverSettings, get_settings)
    container.register(EmbeddingProvider, get_embedding_provider)
    container.register(VectorStoreProvider, get_vector_store)
    container.register(RerankingProvider, get_reranking_provider)
    container.register(ChunkGovernor, get_chunk_governor)
    container.register(ChunkingService, get_chunking_service)
    container.register(Indexer, get_indexer)
    container.register(VectorStoreFailoverManager, get_failover_manager)
    container.register(HealthService, get_health_service)


# Type aliases for cleaner injection
EmbeddingDep = Annotated[Any, Depends(get_embedding_provider)]
SparseEmbeddingDep = Annotated[Any | None, Depends(get_sparse_embedding_provider)]
VectorStoreDep = Annotated[Any, Depends(get_vector_store)]
GovernorDep = Annotated[Any, Depends(get_chunk_governor)]
ChunkingServiceDep = Annotated[Any, Depends(get_chunking_service)]
IndexerDep = Annotated[Any, Depends(get_indexer)]
SettingsDep = Annotated[Any, Depends(get_settings)]
RerankingDep = Annotated[Any | None, Depends(get_reranking_provider)]
IgnoreFilterDep = Annotated[Any, Depends(get_ignore_filter)]
TokenizerDep = Annotated[Any, Depends(get_tokenizer)]
ProviderRegistryDep = Annotated[Any, Depends(get_provider_registry)]
ServicesRegistryDep = Annotated[Any, Depends(get_services_registry)]
ModelRegistryDep = Annotated[Any, Depends(get_model_registry)]
StatisticsDep = Annotated[Any, Depends(get_statistics)]
FailoverManagerDep = Annotated[Any, Depends(get_failover_manager)]
HealthServiceDep = Annotated[Any, Depends(get_health_service)]
FileWatcherDep = Annotated[Any, Depends(get_file_watcher)]
