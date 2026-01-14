# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency injection setup for provider configuration.

This module provides DI type aliases and factory functions for provider settings.
Settings classes are configured via DI to enable:
- Decoupled configuration from provider implementations
- Automatic dependency resolution (e.g., embedding dimensions ← vector store size)
- Ready-built SDK clients injected into providers
- Lazy resolution of provider configurations

## Architecture

Provider settings follow this pattern:
```
User Config (TOML/env vars)
↓
ProviderSettings (root config container)
↓
DI Resolution: EmbeddingProviderSettingsDep = Annotated[EmbeddingProviderSettingsType, depends(...)]
↓
Provider receives: client (SDK), config (settings), embedding_options, query_options
```

Each provider kind has:
- A union type (e.g., EmbeddingProviderSettingsType) discriminating by provider
- A DI type alias (e.g., EmbeddingProviderSettingsDep) for injection
- A factory function (placeholder for now) that resolves settings → SDK client

## Placeholder Status

This module contains intentional placeholders:
- Type aliases without corresponding factories (marked with "⏳ Factory pending")
- Factory functions marked as `...` (to be implemented)
- Import statements for types not yet fully defined

This is expected on the feat/di_monorepo branch.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Annotated, Any

from codeweaver.core import (
    INJECTED,
    BaseCodeWeaverSettings,
    ConfigurationError,
    SDKClient,
    SettingsDep,
    TypeIs,
    dependency_provider,
    depends,
    lazy_import,
    rpartial,
)
from codeweaver.providers.backup_factory import create_backup_class
from codeweaver.providers.embedding.capabilities.resolver import (
    EmbeddingCapabilityResolver,
    SparseEmbeddingCapabilityResolver,
)
from codeweaver.providers.reranking.capabilities.resolver import RerankingCapabilityResolver


if TYPE_CHECKING:
    from codeweaver.core import LazyImport
    from codeweaver.providers.config import (
        AgentProviderSettings,
        BaseProviderSettings,
        ClientOptions,
        CodeWeaverProviderSettings,
        DataProviderSettings,
        EmbeddingConfigT,
        EmbeddingProviderSettings,
        ProviderSettings,
        RerankingConfigT,
        RerankingProviderSettings,
        SparseEmbeddingProviderSettings,
        VectorStoreProviderSettings,
    )


def _create_backup_func[T: Any](func: Callable[..., T]) -> Callable[..., T]:
    """Takes a factory function and returns a new function with backup=True.

    This only works for the factories here with no kwargs other than backup (well, it would work for others too, but that's the intended use case).

    Args:
        func: The original function to partially apply

    Returns:
        A callable that, when invoked, calls the original function with
        the bound arguments.
    """
    return rpartial(func, {"backup": True})


def _definitely_is_provider_settings_or_has_provider_settings_base(
    value: Any,
) -> TypeIs[CodeWeaverProviderSettings]:
    """Check if cls is CodeWeaverProviderSettings or has it as a base class."""
    return bool(
        isinstance(value, CodeWeaverProviderSettings)
        or (
            issubclass(value, CodeWeaverProviderSettings | BaseCodeWeaverSettings)
            and hasattr(value, "provider")
        )
    )


def _get_settings(settings: SettingsDep = INJECTED) -> CodeWeaverProviderSettings:
    """Helper to get BaseCodeWeaverSettings from SettingsDep."""
    resolved_settings = settings if hasattr(settings, "provider") else settings.resolve()  # ty:ignore[unresolved-attribute]
    if not _definitely_is_provider_settings_or_has_provider_settings_base(resolved_settings):
        raise TypeError(
            f"Expected CodeWeaverProviderSettings or BaseCodeWeaverSettings with 'provider' attribute (CodeWeaverEngineSettings or CodeWeaverSettings), got {type(resolved_settings)}"
        )
    return resolved_settings


@dependency_provider(ProviderSettings, scope="singleton")
def _get_provider_settings() -> Any:
    """Factory for creating root provider settings from configuration."""
    return _get_settings().provider


# ===========================================================================
# *                    CLIENT FACTORY (SDK CLIENT CREATION)
# ===========================================================================
#
# Universal client factory creates SDK clients (AsyncOpenAI, VoyageAI, etc.)
# based on the configured provider type. Since settings are bootstrapped before
# DI registration, pydantic discriminators already handle config typing, so we
# just need ONE factory that switches on provider type.
#
# Factory design:
# 1. Injects primary embedding config (EmbeddingProviderSettingsDep)
# 2. Extracts client options from config.client_options
# 3. Switches on config.provider to instantiate the right SDK client
# 4. Returns ready-to-use client
#
# Implementation Note: This factory is registered with @dependency_provider
# at module initialization to ensure it's available when providers are created.


def _resolve_client(client: SDKClient) -> Any:
    """Helper to resolve client if it's a LazyImport."""
    return client._resolve() if isinstance(client, LazyImport) else client


def _instantiate_client(client_cls: Any, options: ClientOptions | None = None) -> Any:
    """Instantiate an SDK client with the given options."""
    return client_cls(**(options.as_settings() if options else {}))


def _resolve_provider_settings(
    settings: BaseProviderSettings | tuple[BaseProviderSettings, ...], *, backup: bool = False
) -> BaseProviderSettings | None:
    """Helper to resolve provider settings if they're LazyImports."""
    if isinstance(settings, tuple) and backup:
        return next((s for s in settings if s.as_backup), None)
    if isinstance(settings, tuple):
        return next((s for s in settings if not s.as_backup), None)
    return settings


def _create_embedding_client(*, backup: bool = False) -> Any:  # AsyncOpenAI
    """Universal client factory for all embedding providers.

    Returns:
        Configured SDK client instance appropriate for the provider type

    Raises:
        ConfigurationError: If config is missing, provider unsupported, or SDK not installed
    """
    default_embedding_config: LazyImport[EmbeddingConfigT] = lazy_import(
        "codeweaver.providers.config.providers", "DefaultEmbeddingProviderSettings"
    )
    embedding_settings = _get_provider_settings().embedding or default_embedding_config._resolve()
    if backup and (config := _resolve_provider_settings(embedding_settings, backup=True)):
        resolved_settings = config
    else:
        resolved_settings = _resolve_provider_settings(embedding_settings)
    if not resolved_settings:
        raise ConfigurationError(
            "No embedding provider configuration found",
            suggestions=["Ensure at least one embedding provider is configured in settings"],
        )
    client = _resolve_client(resolved_settings.client)  # ty:ignore[invalid-argument-type]
    return _instantiate_client(client, resolved_settings.client_options)


def _create_sparse_embedding_client(*, backup: bool = False) -> Any:
    """Universal client factory for all sparse embedding providers.

    Returns:
        Configured SDK client instance appropriate for the provider type

    Raises:
        ConfigurationError: If config is missing, provider unsupported, or SDK not installed
    """
    default_sparse_embedding_config: LazyImport[EmbeddingConfigT] = lazy_import(
        "codeweaver.providers.config.providers", "DefaultSparseEmbeddingProviderSettings"
    )
    sparse_embedding_settings = (
        _get_provider_settings().sparse_embedding or default_sparse_embedding_config._resolve()
    )
    if backup and (config := _resolve_provider_settings(sparse_embedding_settings, backup=True)):
        resolved_settings = config
    else:
        resolved_settings = _resolve_provider_settings(sparse_embedding_settings)
    if not resolved_settings:
        raise ConfigurationError(
            "No sparse embedding provider configuration found",
            suggestions=["Ensure at least one sparse embedding provider is configured in settings"],
        )
    client = _resolve_client(resolved_settings.client)  # ty:ignore[invalid-argument-type]
    return _instantiate_client(client, resolved_settings.client_options)


def _create_reranking_client(*, backup: bool = False) -> Any:
    """Universal client factory for all reranking providers.

    Returns:
        Configured SDK client instance appropriate for the provider type

    Raises:
        ConfigurationError: If config is missing, provider unsupported, or SDK not installed
    """
    default_reranking_config: LazyImport[RerankingConfigT] = lazy_import(
        "codeweaver.providers.config.providers", "DefaultRerankingProviderSettings"
    )
    reranking_settings = _get_provider_settings().reranking or default_reranking_config._resolve()
    if backup and (config := _resolve_provider_settings(reranking_settings, backup=True)):
        resolved_settings = config
    else:
        resolved_settings = _resolve_provider_settings(reranking_settings)
    if not resolved_settings:
        raise ConfigurationError(
            "No reranking provider configuration found",
            suggestions=["Ensure at least one reranking provider is configured in settings"],
        )
    client = _resolve_client(resolved_settings.client)  # ty:ignore[invalid-argument-type]
    return _instantiate_client(client, resolved_settings.client_options)


def _create_vector_client(*, backup: bool = False) -> Any:
    """Universal client factory for all vector store providers.

    Returns:
        Configured SDK client instance appropriate for the provider type

    Raises:
        ConfigurationError: If config is missing, provider unsupported, or SDK not installed
    """
    default_vector_store_config: LazyImport[VectorStoreProviderSettings] = lazy_import(
        "codeweaver.providers.config.providers", "DefaultVectorStoreProviderSettings"
    )
    vector_store_settings = (
        _get_provider_settings().vector_store or default_vector_store_config._resolve()
    )
    if backup and (config := _resolve_provider_settings(vector_store_settings, backup=True)):
        resolved_settings = config
    else:
        resolved_settings = _resolve_provider_settings(vector_store_settings)
    if not resolved_settings:
        raise ConfigurationError(
            "No vector store provider configuration found",
            suggestions=["Ensure at least one vector store provider is configured in settings"],
        )
    client = _resolve_client(resolved_settings.client)  # ty:ignore[invalid-argument-type]
    return _instantiate_client(client, resolved_settings.client_options)


# Universal client dependency type for all embedding providers
type EmbeddingClientDep[T] = Annotated[T, depends(_create_embedding_client)]
"""Type alias for DI injection of embedding SDK client."""

type SparseEmbeddingClientDep[T] = Annotated[T, depends(_create_sparse_embedding_client)]
"""Type alias for DI injection of sparse embedding SDK client."""

type RerankingClientDep[T] = Annotated[T, depends(_create_reranking_client)]
"""Type alias for DI injection of reranking SDK client."""

type VectorStoreClientDep[T] = Annotated[T, depends(_create_vector_client)]
"""Type alias for DI injection of vector store SDK client."""


# ===========================================================================
# *              Provider Kinds Factories - DI TYPE ALIASES
# ===========================================================================
BackupEmbeddingProviderSettings = create_backup_class(EmbeddingProviderSettings)
BackupSparseEmbeddingProviderSettings = create_backup_class(SparseEmbeddingProviderSettings)
BackupRerankingProviderSettings = create_backup_class(RerankingProviderSettings)
BackupVectorStoreProviderSettings = create_backup_class(VectorStoreProviderSettings)
BackupAgentProviderSettings = create_backup_class(AgentProviderSettings)
BackupDataProviderSettings = create_backup_class(DataProviderSettings)


def _get_primary_provider_config_for[
    T: EmbeddingProviderSettings
    | SparseEmbeddingProviderSettings
    | RerankingProviderSettings
    | VectorStoreProviderSettings
    | AgentProviderSettings
    | DataProviderSettings
](settings: Sequence[T]) -> T:
    """Helper to get the primary provider config from a sequence of configs."""
    if primary_config := next((s for s in settings if not s.as_backup), None):
        return primary_config
    raise ConfigurationError(
        "No primary provider configuration found",
        suggestions=["Ensure at least one provider is configured as primary in settings"],
    )


def _get_backup_provider_config_for[
    T: BackupEmbeddingProviderSettings
    | BackupSparseEmbeddingProviderSettings
    | BackupRerankingProviderSettings
    | BackupVectorStoreProviderSettings
    | BackupAgentProviderSettings
    | BackupDataProviderSettings
](settings: Sequence[T]) -> T:
    """Helper to get the backup provider config from a sequence of configs."""
    if backup_config := next((s for s in settings if s.as_backup), None):
        return backup_config
    raise ConfigurationError(
        "No backup provider configuration found",
        suggestions=["Ensure at least one provider is configured as backup in settings"],
    )


@dependency_provider(EmbeddingProviderSettings, scope="singleton", collection=True)
def _create_all_embedding_configs() -> tuple[EmbeddingProviderSettings, ...]:
    """Factory for creating ALL embedding configs (primary + backups) from settings."""
    embedding_configs = _get_settings().provider.embedding
    return (
        embedding_configs
        if isinstance(embedding_configs, tuple)
        else (embedding_configs,)
        if embedding_configs
        else ()
    )


@dependency_provider(EmbeddingProviderSettings, scope="singleton")
def _create_primary_embedding_config() -> EmbeddingProviderSettings:
    """Factory for creating PRIMARY embedding config from settings."""
    return _get_primary_provider_config_for(_create_all_embedding_configs())


@dependency_provider(create_backup_class(EmbeddingProviderSettings), scope="singleton")
def _create_backup_embedding_config() -> EmbeddingProviderSettings:
    """Factory for creating BACKUP embedding config from settings."""
    return _get_backup_provider_config_for(_create_all_embedding_configs())


type EmbeddingProviderSettingsDep = Annotated[
    EmbeddingProviderSettings, depends(_create_primary_embedding_config, use_cache=False)
]
"""Type alias for DI injection of PRIMARY embedding provider settings."""

type BackupEmbeddingProviderSettingsDep = Annotated[
    EmbeddingProviderSettings, depends(_create_backup_embedding_config, use_cache=False)
]

type AllEmbeddingConfigsDep = Annotated[
    Sequence[EmbeddingProviderSettings], depends(_create_all_embedding_configs, use_cache=False)
]
"""Type alias for DI injection of all embedding provider settings.
"""

type EmbeddingCapabilityResolverDep = Annotated[
    EmbeddingCapabilityResolver, depends(EmbeddingCapabilityResolver)
]
"""Type alias for DI injection of embedding capability resolver."""


@dependency_provider(SparseEmbeddingProviderSettings, scope="singleton", collection=True)
def _create_all_sparse_embedding_configs() -> tuple[SparseEmbeddingProviderSettings, ...]:
    """Factory for creating ALL sparse embedding configs (primary + backups) from settings.

    Returns a sequence of all configured sparse embedding providers.
    Use this when you need access to backup providers, not just the primary.

    Note: This factory should be decorated with @dependency_provider at module init.
    """
    sparse_embedding_configs = _get_settings().provider.sparse_embedding
    return (
        sparse_embedding_configs
        if isinstance(sparse_embedding_configs, tuple)
        else (sparse_embedding_configs,)
        if sparse_embedding_configs
        else ()
    )


@dependency_provider(SparseEmbeddingProviderSettings, scope="singleton")
def _create_primary_sparse_embedding_config() -> SparseEmbeddingProviderSettings:
    """Factory for creating PRIMARY sparse embedding config from settings."""
    return _get_primary_provider_config_for(_create_all_sparse_embedding_configs())


@dependency_provider(BackupSparseEmbeddingProviderSettings, scope="singleton")
def _create_backup_sparse_embedding_config() -> SparseEmbeddingProviderSettings:
    """Factory for creating BACKUP sparse embedding config from settings."""
    return _get_backup_provider_config_for(_create_all_sparse_embedding_configs())


type SparseEmbeddingProviderSettingsDep = Annotated[
    SparseEmbeddingProviderSettings,
    depends(_create_primary_sparse_embedding_config, use_cache=False),
]
type BackupSparseEmbeddingProviderSettingsDep = Annotated[
    BackupSparseEmbeddingProviderSettings,
    depends(_create_backup_sparse_embedding_config, use_cache=False),
]
type AllSparseEmbeddingConfigsDep = Annotated[
    Sequence[SparseEmbeddingProviderSettings],
    depends(_create_all_sparse_embedding_configs, use_cache=False),
]

type SparseCapabilityResolverDep = Annotated[
    SparseEmbeddingCapabilityResolver, depends(SparseEmbeddingCapabilityResolver)
]


@dependency_provider(RerankingProviderSettings, scope="singleton", collection=True)
def _create_all_reranking_configs() -> tuple[RerankingProviderSettings, ...]:
    """Factory for creating ALL reranking configs (primary + backups) from settings."""
    reranking_configs = _get_settings().provider.reranking
    return (
        reranking_configs
        if isinstance(reranking_configs, tuple)
        else (reranking_configs,)
        if reranking_configs
        else ()
    )


@dependency_provider(RerankingProviderSettings, scope="singleton")
def _create_primary_reranking_config() -> RerankingProviderSettings:
    """Factory for creating PRIMARY reranking config from settings."""
    return _get_primary_provider_config_for(_create_all_reranking_configs())


@dependency_provider(BackupRerankingProviderSettings, scope="singleton")
def _create_backup_reranking_config() -> BackupRerankingProviderSettings:
    """Factory for creating BACKUP reranking config from settings."""
    return _get_backup_provider_config_for(_create_all_reranking_configs())


type RerankingProviderSettingsDep = Annotated[
    RerankingProviderSettings,  # type: ignore[name-defined]
    depends(_create_primary_reranking_config, use_cache=False),
]
"""Type alias for DI injection of reranking provider settings."""

type BackupRerankingProviderSettingsDep = Annotated[
    BackupRerankingProviderSettings,  # type: ignore[name-defined]
    depends(_create_backup_reranking_config, use_cache=False),
]
"""Type alias for DI injection of backup reranking provider settings."""

type AllRerankingConfigsDep = Annotated[
    Sequence[RerankingProviderSettings],  # type: ignore[name-defined]
    depends(_create_all_reranking_configs, use_cache=False),
]
"""Type alias for DI injection of all reranking provider settings."""

# Type alias for dependency injection
type RerankingCapabilityResolverDep = Annotated[
    RerankingCapabilityResolver, depends(RerankingCapabilityResolver)
]
"""Type alias for DI injection of reranking capability resolver."""


@dependency_provider(VectorStoreProviderSettings, scope="singleton", collection=True)
def _create_all_vector_store_configs() -> tuple[VectorStoreProviderSettings, ...]:
    """Factory for creating ALL vector store configs (primary + backups) from settings."""
    vector_store_configs = _get_settings().provider.vector_store
    return (
        vector_store_configs
        if isinstance(vector_store_configs, tuple)
        else (vector_store_configs,)
        if vector_store_configs
        else ()
    )


@dependency_provider(VectorStoreProviderSettings, scope="singleton")
def _create_primary_vector_store_config() -> VectorStoreProviderSettings:
    """Factory for creating PRIMARY vector store config from settings."""
    return _get_primary_provider_config_for(_create_all_vector_store_configs())


@dependency_provider(BackupVectorStoreProviderSettings, scope="singleton")
def _create_backup_vector_store_config() -> BackupVectorStoreProviderSettings:
    """Factory for creating BACKUP vector store config from settings."""
    return _get_backup_provider_config_for(_create_all_vector_store_configs())


type VectorStoreProviderSettingsDep = Annotated[
    VectorStoreProviderSettings,  # type: ignore[name-defined]
    depends(_create_primary_vector_store_config, use_cache=False),
]
"""Type alias for DI injection of vector store provider settings."""

type BackupVectorStoreProviderSettingsDep = Annotated[
    BackupVectorStoreProviderSettings,  # type: ignore[name-defined]
    depends(_create_backup_vector_store_config, use_cache=False),
]
"""Type alias for DI injection of backup vector store provider settings."""

type AllVectorStoreConfigsDep = Annotated[
    Sequence[VectorStoreProviderSettings],  # type: ignore[name-defined]
    depends(_create_all_vector_store_configs, use_cache=False),
]
"""Type alias for DI injection of all vector store provider settings."""


@dependency_provider(DataProviderSettings, scope="singleton", collection=True)
def _create_all_data_provider_configs() -> tuple[DataProviderSettings, ...]:
    """Factory for creating ALL data provider configs (primary + backups) from settings."""
    data_provider_configs = _get_settings().provider.data
    return (
        data_provider_configs
        if isinstance(data_provider_configs, tuple)
        else (data_provider_configs,)
        if data_provider_configs
        else ()
    )


type AllDataProviderConfigsDep = Annotated[
    Sequence[DataProviderSettings],  # type: ignore[name-defined]
    depends(_create_all_data_provider_configs, use_cache=False),
]
"""Type alias for DI injection of all data provider settings."""


# ===========================================================================
# *                 AGENT PROVIDER SETTINGS - DI TYPE ALIASES
# ===========================================================================


@dependency_provider(AgentProviderSettings, scope="singleton", collection=True)
def _create_all_agent_provider_configs() -> tuple[AgentProviderSettings, ...]:
    """Factory for creating ALL agent provider configs (primary + backups) from settings."""
    agent_configs = _get_settings().provider.agent
    return (
        agent_configs
        if isinstance(agent_configs, tuple)
        else (agent_configs,)
        if agent_configs
        else ()
    )


@dependency_provider(AgentProviderSettings, scope="singleton")
def _create_primary_agent_provider_config() -> AgentProviderSettings:
    """Factory for creating PRIMARY agent provider config from settings."""
    if (
        agent_config := _get_primary_provider_config_for(_create_all_agent_provider_configs())
    ) is not None:
        return agent_config
    raise ConfigurationError("No primary agent provider config found")


type AgentProviderSettingsDep = Annotated[
    AgentProviderSettings, depends(_create_all_agent_provider_configs, use_cache=False)
]
"""Type alias for DI injection of agent provider settings."""


# ===========================================================================
# *                    ROOT PROVIDER SETTINGS - DI TYPE ALIAS
# ===========================================================================


type ProviderSettingsDep = Annotated[
    ProviderSettings,  # type: ignore[name-defined]
    depends(_get_provider_settings, use_cache=False),
]
"""Type alias for DI injection of root provider settings.

This is the top-level provider configuration. All provider-specific settings
are nested within this container. Requesting this type triggers resolution of
all configured providers.

Example:
    ```python
    async def initialize_providers(
        provider_settings: ProviderSettingsDep = INJECTED
    ) -> None:
        # provider_settings contains all configured providers
        embedding = provider_settings.embedding
        vector_store = provider_settings.vector_store
    ```
"""


# ===========================================================================
# *                            MODULE EXPORTS
# ===========================================================================

__all__ = (
    "AgentProviderSettingsDep",
    "AllDataProviderConfigsDep",
    "AllEmbeddingConfigsDep",
    "AllRerankingConfigsDep",
    "AllSparseEmbeddingConfigsDep",
    "AllVectorStoreConfigsDep",
    "BackupEmbeddingProviderSettingsDep",
    "BackupRerankingProviderSettingsDep",
    "BackupSparseEmbeddingProviderSettingsDep",
    "BackupVectorStoreProviderSettingsDep",
    "EmbeddingCapabilityResolverDep",
    "EmbeddingClientDep",
    "EmbeddingProviderSettingsDep",
    "ProviderSettingsDep",
    "RerankingCapabilityResolverDep",
    "RerankingClientDep",
    "RerankingProviderSettingsDep",
    "SparseCapabilityResolverDep",
    "SparseEmbeddingClientDep",
    "SparseEmbeddingProviderSettingsDep",
    "VectorStoreClientDep",
    "VectorStoreProviderSettingsDep",
)
