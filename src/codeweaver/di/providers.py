# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Standard dependency providers for CodeWeaver."""

from typing import TYPE_CHECKING, Annotated, Any

# Top-level imports for DI keys where safe (no circularity)
from codeweaver.config.settings import CodeWeaverSettings
from codeweaver.core.types.sentinel import Unset
from codeweaver.di.container import Container, get_container
from codeweaver.di.depends import Depends
from codeweaver.engine.chunker.base import ChunkGovernor
from codeweaver.providers.embedding.providers.base import EmbeddingProvider
from codeweaver.providers.reranking.providers.base import RerankingProvider
from codeweaver.providers.vector_stores.base import VectorStoreProvider


if TYPE_CHECKING:
    from codeweaver.common.registry import ModelRegistry, ProviderRegistry, ServicesRegistry
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.common.telemetry.client import PostHogClient
    from codeweaver.engine.failover import VectorStoreFailoverManager
    from codeweaver.engine.indexer.indexer import Indexer

# Type aliases for cleaner injection - defined early for use in function signatures
# without 'from __future__ import annotations'
SettingsDep = Annotated[CodeWeaverSettings, Depends(CodeWeaverSettings)]
EmbeddingDep = Annotated[Any, Depends(EmbeddingProvider)]
VectorStoreDep = Annotated[Any, Depends(VectorStoreProvider)]
GovernorDep = Annotated[Any, Depends(ChunkGovernor)]
RerankingDep = Annotated[Any | None, Depends(RerankingProvider)]


# These use factories to avoid circular imports with the modules they define
# We keep them here, but ensure they are available for function signatures below
async def get_chunking_service() -> Any: ...  # Forward decl if needed, but Any is fine
async def get_indexer(*args: Any, **kwargs: Any) -> Any: ...
async def get_sparse_embedding_provider() -> Any: ...
async def get_ignore_filter(*args: Any, **kwargs: Any) -> Any: ...
async def get_tokenizer(*args: Any, **kwargs: Any) -> Any: ...
async def get_provider_registry() -> Any: ...
async def get_services_registry() -> Any: ...
async def get_model_registry() -> Any: ...
async def get_statistics() -> Any: ...
async def get_failover_manager() -> Any: ...
async def get_health_service(*args: Any, **kwargs: Any) -> Any: ...
async def get_file_watcher(*args: Any, **kwargs: Any) -> Any: ...
async def get_telemetry(*args: Any, **kwargs: Any) -> Any: ...
async def get_state(*args: Any, **kwargs: Any) -> Any: ...


ChunkingServiceDep = Annotated[Any, Depends(get_chunking_service)]
IndexerDep = Annotated[Any, Depends(get_indexer)]
SparseEmbeddingDep = Annotated[Any | None, Depends(get_sparse_embedding_provider)]
IgnoreFilterDep = Annotated[Any, Depends(get_ignore_filter)]
TokenizerDep = Annotated[Any, Depends(get_tokenizer)]
ProviderRegistryDep = Annotated[Any, Depends(get_provider_registry)]
ServicesRegistryDep = Annotated[Any, Depends(get_services_registry)]
ModelRegistryDep = Annotated[Any, Depends(get_model_registry)]
StatisticsDep = Annotated[Any, Depends(get_statistics)]
FailoverManagerDep = Annotated[Any, Depends(get_failover_manager)]
HealthServiceDep = Annotated[Any, Depends(get_health_service)]
FileWatcherDep = Annotated[Any, Depends(get_file_watcher)]
StateDep = Annotated[Any, Depends(get_state)]
TelemetryDep = Annotated[Any, Depends(get_telemetry)]


# ===========================================================================
# *                            Legacy DI Bridge
#
# * This is a bridge between the old registry system and the new DI system.
# * It will die a needed death with phase 3 of the monorepo plan :)
# ===========================================================================

# We use `Any` return types here to avoid circular imports and missing packages


async def get_embedding_provider() -> Any:
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


async def get_sparse_embedding_provider() -> Any:
    """Resolve the configured sparse embedding provider from the registry."""
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    if provider_enum := registry.get_provider_enum_for("sparse_embedding"):
        return registry.get_provider_instance(provider_enum, "sparse_embedding", singleton=True)  # type: ignore
    return None


async def get_vector_store() -> Any:
    """Resolve the configured vector store provider from the registry."""
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    provider_enum = registry.get_provider_enum_for("vector_store")
    if not provider_enum:
        from codeweaver.exceptions import ConfigurationError

        raise ConfigurationError("No vector store provider configured.")

    return registry.get_provider_instance(provider_enum, "vector_store", singleton=True)  # type: ignore


async def get_chunk_governor(settings: SettingsDep) -> Any:
    """Resolve the chunk governor."""
    from codeweaver.common.registry import get_model_registry
    from codeweaver.config.chunker import ChunkerSettings
    from codeweaver.config.settings import Unset
    from codeweaver.core.types.provider import ProviderKind
    from codeweaver.engine.chunker import ChunkGovernor

    chunk_settings_raw = settings.chunker
    chunk_settings = (
        ChunkerSettings() if isinstance(chunk_settings_raw, Unset) else chunk_settings_raw
    )

    # Resolve capabilities for the governor
    registry = get_model_registry()
    embedding_caps = registry.configured_models_for_kind(ProviderKind.EMBEDDING) or ()
    reranking_caps = registry.configured_models_for_kind(ProviderKind.RERANKING) or ()

    return ChunkGovernor(settings=chunk_settings, capabilities=(*embedding_caps, *reranking_caps))


async def get_chunking_service() -> Any:
    """Resolve the chunking service."""
    from codeweaver.engine.chunking_service import ChunkingService

    # ChunkingService will have its own dependencies resolved by the container
    return await get_container().resolve(ChunkingService)


async def get_reranking_provider() -> Any:
    """Resolve the configured reranking provider from the registry."""
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    if provider_enum := registry.get_provider_enum_for("reranking"):
        return registry.get_provider_instance(provider_enum, "reranking", singleton=True)  # type: ignore
    return None


async def get_settings() -> CodeWeaverSettings:
    """Resolve the global settings."""
    from codeweaver.config.settings import get_settings

    settings = get_settings()
    if settings.project_path is Unset:
        from codeweaver.core import get_project_path

        settings.update(project_path=get_project_path())
    return settings


async def get_indexer(
    settings: SettingsDep,
    chunking_service: ChunkingServiceDep,
    embedding_provider: EmbeddingDep,
    sparse_provider: SparseEmbeddingDep,
    vector_store: VectorStoreDep,
) -> Any:
    """Resolve the indexer service."""
    from codeweaver.engine.indexer.indexer import Indexer

    return Indexer(
        settings=settings,
        chunking_service=chunking_service,
        embedding_provider=embedding_provider,
        sparse_provider=sparse_provider,
        vector_store=vector_store,
    )


async def get_ignore_filter(settings: SettingsDep) -> Any:
    """Resolve the ignore filter."""
    from codeweaver.engine.watcher.watch_filters import IgnoreFilter

    return await IgnoreFilter.from_settings_async(settings=settings.view)


async def get_tokenizer(embedding_provider: EmbeddingDep) -> Any:
    """Resolve the tokenizer for the configured embedding model."""
    from codeweaver_tokenizers import get_tokenizer

    provider = embedding_provider
    # Most models use "tokenizers", tiktoken is primarily for OpenAI
    tokenizer_type = getattr(provider.caps, "tokenizer", "tokenizers")
    tokenizer_model = getattr(provider.caps, "tokenizer_model", None) or provider.caps.name

    return get_tokenizer(tokenizer_type, tokenizer_model)  # type: ignore


async def get_provider_registry() -> Any:
    """Resolve the provider registry."""
    from codeweaver.common.registry import get_provider_registry

    return get_provider_registry()


async def get_services_registry() -> Any:
    """Resolve the services registry."""
    from codeweaver.common.registry import get_services_registry

    return get_services_registry()


async def get_model_registry() -> Any:
    """Resolve the model registry."""
    from codeweaver.common.registry import get_model_registry

    return get_model_registry()


async def get_statistics() -> Any:
    """Resolve the session statistics."""
    from codeweaver.common.statistics import get_session_statistics

    return get_session_statistics()


async def get_failover_manager() -> Any:
    """Resolve the failover manager."""
    from codeweaver.engine.failover import VectorStoreFailoverManager

    return VectorStoreFailoverManager()


async def get_health_service(
    provider_registry: ProviderRegistryDep,
    statistics: StatisticsDep,
    indexer: IndexerDep,
    failover_manager: FailoverManagerDep,
) -> Any:
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
    indexer: IndexerDep, ignore_filter: IgnoreFilterDep, settings: SettingsDep
) -> Any:
    """Resolve the file watcher."""
    from codeweaver.core import get_project_path
    from codeweaver.core.types.sentinel import Unset
    from codeweaver.engine.watcher.watcher import FileWatcher

    project_path = (
        get_project_path() if isinstance(settings.project_path, Unset) else settings.project_path
    )

    return await FileWatcher.create(project_path, indexer=indexer, file_filter=ignore_filter)


async def get_telemetry(settings: SettingsDep) -> Any:
    """Resolve the telemetry client."""
    from codeweaver.common.telemetry.client import PostHogClient

    return PostHogClient.from_settings(settings)


async def get_state(
    settings: Annotated[CodeWeaverSettings, Depends(get_settings)],
    statistics: Annotated["SessionStatistics", Depends(get_statistics)],
    provider_registry: Annotated["ProviderRegistry", Depends(get_provider_registry)],
    services_registry: Annotated["ServicesRegistry", Depends(get_services_registry)],
    model_registry: Annotated["ModelRegistry", Depends(get_model_registry)],
    indexer: Annotated["Indexer", Depends(get_indexer)],
    failover_manager: Annotated["VectorStoreFailoverManager", Depends(get_failover_manager)],
    telemetry: Annotated["PostHogClient", Depends(get_telemetry)],
) -> Any:
    """Resolve the application state."""
    from codeweaver.config.settings import Unset
    from codeweaver.server.server import CodeWeaverState

    return CodeWeaverState(
        initialized=True,
        settings=settings,
        statistics=statistics,
        project_path=settings.project_path,
        config_path=None if isinstance(settings.config_file, Unset) else settings.config_file,
        provider_registry=provider_registry,
        services_registry=services_registry,
        model_registry=model_registry,
        indexer=indexer,
        failover_manager=failover_manager,
        telemetry=telemetry,
    )


def setup_default_container(container: Container) -> None:
    """Setup the default container with all providers.

    Args:
        container: The container to configure.
    """
    from codeweaver.common.registry import ModelRegistry, ProviderRegistry, ServicesRegistry
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.common.telemetry.client import PostHogClient
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.engine.chunker import ChunkGovernor
    from codeweaver.engine.chunking_service import ChunkingService
    from codeweaver.engine.failover import VectorStoreFailoverManager
    from codeweaver.engine.indexer.indexer import Indexer
    from codeweaver.providers.embedding.providers.base import EmbeddingProvider
    from codeweaver.providers.reranking.providers.base import RerankingProvider
    from codeweaver.providers.vector_stores.base import VectorStoreProvider
    from codeweaver.server.health.health_service import HealthService
    from codeweaver.server.server import CodeWeaverState

    # Register by class
    container.register(ProviderRegistry, get_provider_registry)
    container.register(ServicesRegistry, get_services_registry)
    container.register(ModelRegistry, get_model_registry)
    container.register(SessionStatistics, get_statistics)
    container.register(CodeWeaverSettings, get_settings)
    container.register(EmbeddingProvider, get_embedding_provider)
    container.register(VectorStoreProvider, get_vector_store)
    container.register(RerankingProvider, get_reranking_provider)
    container.register(ChunkGovernor, get_chunk_governor)
    container.register(Indexer, get_indexer)
    container.register(VectorStoreFailoverManager, get_failover_manager)
    container.register(HealthService, get_health_service)
    container.register(CodeWeaverState, get_state)
    container.register(PostHogClient, get_telemetry)
    container.register(ChunkingService, get_chunking_service)

    # ALSO register the factory functions themselves so Depends(get_...) works
    container.register(get_provider_registry, get_provider_registry)
    container.register(get_services_registry, get_services_registry)
    container.register(get_model_registry, get_model_registry)
    container.register(get_statistics, get_statistics)
    container.register(get_settings, get_settings)
    container.register(get_embedding_provider, get_embedding_provider)
    container.register(get_vector_store, get_vector_store)
    container.register(get_reranking_provider, get_reranking_provider)
    container.register(get_chunk_governor, get_chunk_governor)
    container.register(get_indexer, get_indexer)
    container.register(get_failover_manager, get_failover_manager)
    container.register(get_health_service, get_health_service)
    container.register(get_state, get_state)
    container.register(get_telemetry, get_telemetry)
    container.register(get_chunking_service, get_chunking_service)


# Remove the duplicated type aliases at the bottom
__all__ = (
    "ChunkingServiceDep",
    "Container",
    "Depends",
    "EmbeddingDep",
    "FailoverManagerDep",
    "FileWatcherDep",
    "GovernorDep",
    "HealthServiceDep",
    "IgnoreFilterDep",
    "IndexerDep",
    "ModelRegistryDep",
    "ProviderRegistryDep",
    "RerankingDep",
    "ServicesRegistryDep",
    "SettingsDep",
    "SparseEmbeddingDep",
    "StateDep",
    "StatisticsDep",
    "TelemetryDep",
    "TokenizerDep",
    "VectorStoreDep",
)
