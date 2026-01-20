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
from typing import TYPE_CHECKING, Annotated, Any, TypedDict, cast

from codeweaver_tokenizers import Tokenizer

from codeweaver.core import (
    INJECTED,
    BaseCodeWeaverSettings,
    ConfigurationError,
    SDKClient,
    SettingsDep,
    TypeIs,
    Unset,
    create_backup_class,
    dependency_provider,
    depends,
    lazy_import,
    rpartial,
)
from codeweaver.core.types import ModelName
from codeweaver.providers import AllDefaultProviderSettings, EmbeddingCapabilityGroup
from codeweaver.providers.embedding.capabilities.resolver import (
    EmbeddingCapabilityResolver,
    SparseEmbeddingCapabilityResolver,
)
from codeweaver.providers.embedding.registry import EmbeddingRegistry
from codeweaver.providers.reranking.capabilities.resolver import RerankingCapabilityResolver


if TYPE_CHECKING:
    from codeweaver.core import LazyImport
    from codeweaver.providers.config import (
        AgentProviderSettings,
        CodeWeaverProviderSettings,
        DataProviderSettings,
        EmbeddingConfigT,
        EmbeddingProviderSettings,
        MemoryVectorStoreProviderSettings,
        ProviderSettings,
        QdrantVectorStoreProviderSettings,
        RerankingConfigT,
        RerankingProviderSettings,
        SparseEmbeddingProviderSettings,
        VectorStoreProviderSettings,
    )
    from codeweaver.providers.config.kinds import _BaseQdrantVectorStoreProviderSettings
    from codeweaver.providers.embedding import EmbeddingProvider, SparseEmbeddingProvider
    from codeweaver.providers.reranking import RerankingProvider
    from codeweaver.providers.types import (
        ConfiguredCapability,
        EmbeddingCapabilityGroup,
        SearchPackage,
    )
    from codeweaver.providers.vector_stores import (
        MemoryVectorStoreProvider,
        QdrantVectorStoreProvider,
        VectorStoreProvider,
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
def _get_provider_settings(settings: SettingsDep = INJECTED) -> ProviderSettings:
    """Factory for creating root provider settings from configuration."""
    from codeweaver.providers.config import ProviderSettings

    return cast(
        ProviderSettings,
        ProviderSettings.model_validate(AllDefaultProviderSettings)
        if settings.provider is Unset  # ty:ignore[unresolved-attribute]
        else settings.provider,  # ty:ignore[unresolved-attribute]
    )


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


def _resolve_provider_settings[
    T: EmbeddingProviderSettings
    | RerankingProviderSettings
    | VectorStoreProviderSettings
    | AgentProviderSettings
    | DataProviderSettings
](settings: tuple[T, ...], *, backup: bool = False) -> T | None:
    """Helper to resolve provider settings if they're LazyImports."""
    if isinstance(settings, tuple) and backup:
        return next((s for s in settings if s.as_backup), None)
    if isinstance(settings, tuple):
        return next((s for s in settings if not s.as_backup), None)
    return settings


# ===========================================================================
# *                    ROOT PROVIDER SETTINGS - DI TYPE ALIAS
# ===========================================================================


type ProviderSettingsDep = Annotated[
    ProviderSettings,  # type: ignore[name-defined]
    depends(_get_provider_settings, use_cache=False),
]
"""Type alias for DI injection of root provider settings."""


def _create_embedding_client(
    provider_settings: ProviderSettingsDep = INJECTED,
) -> Any:  # AsyncOpenAI
    """Universal client factory for all embedding providers.

    Returns:
        Configured SDK client instance appropriate for the provider type

    Raises:
        ConfigurationError: If config is missing, provider unsupported, or SDK not installed
    """
    default_embedding_config: LazyImport[EmbeddingConfigT] = lazy_import(
        "codeweaver.providers.config.providers", "DefaultEmbeddingProviderSettings"
    )
    embedding_settings = provider_settings.embedding or default_embedding_config._resolve()
    if resolved_settings := _resolve_provider_settings(embedding_settings):
        return resolved_settings.get_client()
    raise ConfigurationError(
        "No embedding provider configuration found",
        suggestions=["Ensure at least one embedding provider is configured in settings"],
    )


def _create_sparse_embedding_client(provider_settings: ProviderSettingsDep = INJECTED) -> Any:
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
        provider_settings.sparse_embedding or default_sparse_embedding_config._resolve()
    )
    if resolved_settings := _resolve_provider_settings(sparse_embedding_settings):
        return resolved_settings.get_client()
    raise ConfigurationError(
        "No sparse embedding provider configuration found",
        suggestions=["Ensure at least one sparse embedding provider is configured in settings"],
    )


def _create_reranking_client(provider_settings: ProviderSettingsDep = INJECTED) -> Any:
    """Universal client factory for all reranking providers.

    Returns:
        Configured SDK client instance appropriate for the provider type

    Raises:
        ConfigurationError: If config is missing, provider unsupported, or SDK not installed
    """
    default_reranking_config: LazyImport[RerankingConfigT] = lazy_import(
        "codeweaver.providers.config.providers", "DefaultRerankingProviderSettings"
    )
    reranking_settings = provider_settings.reranking or default_reranking_config._resolve()
    if resolved_settings := _resolve_provider_settings(reranking_settings):
        return resolved_settings.get_client()

    raise ConfigurationError(
        "No reranking provider configuration found",
        suggestions=["Ensure at least one reranking provider is configured in settings"],
    )


def _create_vector_client(provider_settings: ProviderSettingsDep = INJECTED) -> Any:
    """Universal client factory for all vector store providers.

    Returns:
        Configured SDK client instance appropriate for the provider type

    Raises:
        ConfigurationError: If config is missing, provider unsupported, or SDK not installed
    """
    default_vector_store_config: LazyImport[VectorStoreProviderSettings] = lazy_import(
        "codeweaver.providers.config.providers", "DefaultVectorStoreProviderSettings"
    )
    vector_store_settings = provider_settings.vector_store or default_vector_store_config._resolve()
    if resolved_settings := _resolve_provider_settings(vector_store_settings):
        return resolved_settings.get_client()
    raise ConfigurationError(
        "No vector store provider configuration found",
        suggestions=["Ensure at least one vector store provider is configured in settings"],
    )


# Universal client dependency type for all embedding providers
type EmbeddingClientDep[T] = Annotated[T, depends(_create_embedding_client, scope="function")]
"""Type alias for DI injection of embedding SDK client."""

type SparseEmbeddingClientDep[T] = Annotated[
    T, depends(_create_sparse_embedding_client, scope="function")
]
"""Type alias for DI injection of sparse embedding SDK client."""

type RerankingClientDep[T] = Annotated[T, depends(_create_reranking_client, scope="function")]
"""Type alias for DI injection of reranking SDK client."""

type VectorStoreClientDep[T] = Annotated[T, depends(_create_vector_client, scope="function")]
"""Type alias for DI injection of vector store SDK client."""


# ===========================================================================
# *              Provider Kinds Factories - DI TYPE ALIASES
# ===========================================================================
# --- Provider Settings Backup classes ---
BackupEmbeddingProviderSettings = create_backup_class(EmbeddingProviderSettings)
BackupSparseEmbeddingProviderSettings = create_backup_class(SparseEmbeddingProviderSettings)
BackupRerankingProviderSettings = create_backup_class(RerankingProviderSettings)
BackupVectorStoreProviderSettings = create_backup_class(QdrantVectorStoreProviderSettings)

BackupMemoryVectorStoreProviderSettings = create_backup_class(MemoryVectorStoreProviderSettings)
BackupAgentProviderSettings = create_backup_class(AgentProviderSettings)
BackupDataProviderSettings = create_backup_class(DataProviderSettings)

# --- Resolver Backup classes ---
BackupEmbeddingCapabilityResolver = create_backup_class(EmbeddingCapabilityResolver)
BackupSparseEmbeddingCapabilityResolver = create_backup_class(SparseEmbeddingCapabilityResolver)
BackupRerankingCapabilityResolver = create_backup_class(RerankingCapabilityResolver)


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
    | _BaseQdrantVectorStoreProviderSettings
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
def _create_all_embedding_configs(
    provider_settings: ProviderSettingsDep = INJECTED,
) -> tuple[EmbeddingProviderSettings, ...]:
    """Factory for creating ALL embedding configs (primary + backups) from settings."""
    embedding_configs = provider_settings.embedding
    return (
        embedding_configs
        if isinstance(embedding_configs, tuple)
        else (embedding_configs,)
        if embedding_configs
        else ()
    )


type AllEmbeddingConfigsDep = Annotated[
    Sequence[EmbeddingProviderSettings], depends(_create_all_embedding_configs, use_cache=False)
]
"""Type alias for DI injection of all embedding provider settings.
"""


@dependency_provider(EmbeddingProviderSettings, scope="singleton")
def _create_primary_embedding_config(
    configs: AllEmbeddingConfigsDep = INJECTED,
) -> EmbeddingProviderSettings:
    """Factory for creating PRIMARY embedding config from settings."""
    return _get_primary_provider_config_for(configs)


@dependency_provider(BackupEmbeddingProviderSettings, scope="singleton")
def _create_backup_embedding_config(
    configs: AllEmbeddingConfigsDep = INJECTED,
) -> EmbeddingProviderSettings:
    """Factory for creating BACKUP embedding config from settings."""
    return _get_backup_provider_config_for(configs)


@dependency_provider(SparseEmbeddingProviderSettings, scope="singleton", collection=True)
def _create_all_sparse_embedding_configs(
    provider_settings: ProviderSettingsDep = INJECTED,
) -> tuple[SparseEmbeddingProviderSettings, ...]:
    """Factory for creating ALL sparse embedding configs (primary + backups) from settings.

    Returns a sequence of all configured sparse embedding providers.
    Use this when you need access to backup providers, not just the primary.

    Note: This factory should be decorated with @dependency_provider at module init.
    """
    sparse_embedding_configs = provider_settings.sparse_embedding
    return (
        sparse_embedding_configs
        if isinstance(sparse_embedding_configs, tuple)
        else (sparse_embedding_configs,)
        if sparse_embedding_configs
        else ()
    )


@dependency_provider(SparseEmbeddingProviderSettings, scope="singleton")
def _create_primary_sparse_embedding_config(
    configs: AllSparseEmbeddingConfigsDep = INJECTED,
) -> SparseEmbeddingProviderSettings:
    """Factory for creating PRIMARY sparse embedding config from settings."""
    return _get_primary_provider_config_for(configs)


@dependency_provider(BackupSparseEmbeddingProviderSettings, scope="singleton")
def _create_backup_sparse_embedding_config(
    configs: AllSparseEmbeddingConfigsDep = INJECTED,
) -> SparseEmbeddingProviderSettings:
    """Factory for creating BACKUP sparse embedding config from settings."""
    return _get_backup_provider_config_for(configs)


type AllSparseEmbeddingConfigsDep = Annotated[
    Sequence[SparseEmbeddingProviderSettings],
    depends(_create_all_sparse_embedding_configs, use_cache=False),
]


@dependency_provider(RerankingProviderSettings, scope="singleton", collection=True)
def _create_all_reranking_configs(
    provider_settings: ProviderSettingsDep = INJECTED,
) -> tuple[RerankingProviderSettings, ...]:
    """Factory for creating ALL reranking configs (primary + backups) from settings."""
    reranking_configs = provider_settings.reranking
    return (
        reranking_configs
        if isinstance(reranking_configs, tuple)
        else (reranking_configs,)
        if reranking_configs
        else ()
    )


@dependency_provider(RerankingProviderSettings, scope="singleton")
def _create_primary_reranking_config(
    configs: AllRerankingConfigsDep = INJECTED,
) -> RerankingProviderSettings:
    """Factory for creating PRIMARY reranking config from settings."""
    return _get_primary_provider_config_for(configs)


@dependency_provider(BackupRerankingProviderSettings, scope="singleton")
def _create_backup_reranking_config(
    configs: AllRerankingConfigsDep = INJECTED,
) -> BackupRerankingProviderSettings:
    """Factory for creating BACKUP reranking config from settings."""
    return _get_backup_provider_config_for(configs)


type AllRerankingConfigsDep = Annotated[
    Sequence[RerankingProviderSettings],  # type: ignore[name-defined]
    depends(_create_all_reranking_configs, use_cache=False),
]
"""Type alias for DI injection of all reranking provider settings."""


@dependency_provider(VectorStoreProviderSettings, scope="singleton", collection=True)
def _create_all_vector_store_configs(
    provider_settings: ProviderSettingsDep = INJECTED,
) -> tuple[VectorStoreProviderSettings, ...]:
    """Factory for creating ALL vector store configs (primary + backups) from settings."""
    vector_store_configs = provider_settings.vector_store
    return (
        vector_store_configs
        if isinstance(vector_store_configs, tuple)
        else (vector_store_configs,)
        if vector_store_configs
        else ()
    )


@dependency_provider(_BaseQdrantVectorStoreProviderSettings, scope="singleton")
def _create_primary_vector_store_config(
    configs: AllVectorStoreConfigsDep = INJECTED,
) -> QdrantVectorStoreProviderSettings | MemoryVectorStoreProviderSettings:
    """Factory for creating PRIMARY vector store config from settings."""
    return _get_primary_provider_config_for(configs)


@dependency_provider(BackupVectorStoreProviderSettings, scope="singleton")
def _create_backup_vector_store_config(
    configs: AllVectorStoreConfigsDep = INJECTED,
) -> BackupVectorStoreProviderSettings:
    """Factory for creating BACKUP vector store config from settings."""
    return _get_backup_provider_config_for(configs)


type AllVectorStoreConfigsDep = Annotated[
    Sequence[VectorStoreProviderSettings],  # type: ignore[name-defined]
    depends(_create_all_vector_store_configs, use_cache=False),
]
"""Type alias for DI injection of all vector store provider settings."""


@dependency_provider(DataProviderSettings, scope="singleton", collection=True)
def _create_all_data_provider_configs(
    provider_settings: ProviderSettingsDep = INJECTED,
) -> tuple[DataProviderSettings, ...]:
    """Factory for creating ALL data provider configs (primary + backups) from settings."""
    data_provider_configs = provider_settings.data
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
def _create_all_agent_provider_configs(
    provider_settings: ProviderSettingsDep = INJECTED,
) -> tuple[AgentProviderSettings, ...]:
    """Factory for creating ALL agent provider configs (primary + backups) from settings."""
    agent_configs = provider_settings.agent
    return (
        agent_configs
        if isinstance(agent_configs, tuple)
        else (agent_configs,)
        if agent_configs
        else ()
    )


@dependency_provider(AgentProviderSettings, scope="singleton")
def _create_primary_agent_provider_config(
    configs: Annotated[
        Sequence[AgentProviderSettings], depends(_create_all_agent_provider_configs)
    ] = INJECTED,
) -> AgentProviderSettings:
    """Factory for creating PRIMARY agent provider config from settings."""
    if (agent_config := _get_primary_provider_config_for(configs)) is not None:
        return agent_config
    raise ConfigurationError("No primary agent provider config found")


type AgentProviderSettingsDep = Annotated[
    AgentProviderSettings, depends(_create_all_agent_provider_configs, use_cache=False)
]
"""Type alias for DI injection of agent provider settings."""


# ===========================================================================
# *    DI Type Aliases for All Settings Types and Capability Resolvers
# ===========================================================================

type EmbeddingProviderSettingsDep = Annotated[
    EmbeddingProviderSettings, depends(_create_primary_embedding_config, use_cache=False)
]
"""Type alias for DI injection of PRIMARY embedding provider settings."""

type BackupEmbeddingProviderSettingsDep = Annotated[
    EmbeddingProviderSettings, depends(_create_backup_embedding_config, use_cache=False)
]


type SparseEmbeddingProviderSettingsDep = Annotated[
    SparseEmbeddingProviderSettings,
    depends(_create_primary_sparse_embedding_config, use_cache=False),
]
type BackupSparseEmbeddingProviderSettingsDep = Annotated[
    BackupSparseEmbeddingProviderSettings,
    depends(_create_backup_sparse_embedding_config, use_cache=False),
]

type SparseCapabilityResolverDep = Annotated[
    SparseEmbeddingCapabilityResolver, depends(SparseEmbeddingCapabilityResolver)
]

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

type VectorStoreProviderSettingsDep = Annotated[
    VectorStoreProviderSettings, depends(_create_primary_vector_store_config, use_cache=False)
]
"""Type alias for DI injection of vector store provider settings."""

type BackupVectorStoreProviderSettingsDep = Annotated[
    BackupVectorStoreProviderSettings, depends(_create_backup_vector_store_config, use_cache=False)
]
"""Type alias for DI injection of vector store provider settings."""


# --- Resolvers ---

type EmbeddingCapabilityResolverDep = Annotated[
    EmbeddingCapabilityResolver, depends(EmbeddingCapabilityResolver)
]
"""Type alias for DI injection of embedding capability resolver."""

type SparseEmbeddingCapabilityResolverDep = Annotated[
    SparseEmbeddingCapabilityResolver, depends(SparseEmbeddingCapabilityResolver)
]
"""Type alias for DI injection of sparse embedding capability resolver."""


type BackupEmbeddingCapabilityResolverDep = Annotated[
    BackupEmbeddingCapabilityResolver, depends(BackupEmbeddingCapabilityResolver)
]

type BackupSparseEmbeddingCapabilityResolverDep = Annotated[
    BackupSparseEmbeddingCapabilityResolver, depends(BackupSparseEmbeddingCapabilityResolver)
]

type RerankingCapabilityResolverDep = Annotated[
    RerankingCapabilityResolver, depends(RerankingCapabilityResolver)
]

"""Type alias for DI injection of reranking capability resolver."""


type BackupRerankingCapabilityResolverDep = Annotated[
    BackupRerankingCapabilityResolver, depends(BackupRerankingCapabilityResolver)
]
"""Type alias for DI injection of backup reranking capability resolver."""

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
# *              Embedding Registry
# ===========================================================================

BackupEmbeddingRegistry = lazy_import(
    "codeweaver.providers.embedding.registry", "BackupEmbeddingRegistry"
)._resolve()


def _get_embedding_registry() -> EmbeddingRegistry:
    from codeweaver.providers.embedding.registry import EmbeddingRegistry

    return EmbeddingRegistry()


def _get_backup_embedding_registry() -> BackupEmbeddingRegistry:
    return BackupEmbeddingRegistry(is_backup_provider=True)


type EmbeddingRegistryDep = Annotated[
    EmbeddingRegistry, depends(_get_embedding_registry, use_cache=True, scope="singleton")
]
"""Type alias for DI injection of embedding registry."""

type BackupEmbeddingRegistryDep = Annotated[
    BackupEmbeddingRegistry,
    depends(_get_backup_embedding_registry, use_cache=True, scope="singleton"),
]
"""Type alias for DI injection of backup embedding registry."""


# ===========================================================================
# *              Embedding and Sparse Embedding Providers
# ===========================================================================

BackupEmbeddingProvider = create_backup_class(
    lazy_import("codeweaver.providers.embedding.providers", "EmbeddingProvider")._resolve()
)
BackupSparseEmbeddingProvider = create_backup_class(
    lazy_import("codeweaver.providers.embedding.providers", "SparseEmbeddingProvider")._resolve()
)

BackupEmbeddingCapabilityGroup = create_backup_class(EmbeddingCapabilityGroup)


@dependency_provider(EmbeddingCapabilityGroup, scope="singleton")
def _get_primary_embedding_capability_group(
    configured_caps: ConfiguredCapabilitiesDep = INJECTED,
) -> EmbeddingCapabilityGroup:
    """Creates the primary embedding capability group from both embedding and sparse embedding settings."""
    return EmbeddingCapabilityGroup.from_capabilities(configured_caps)


type EmbeddingCapabilityGroupDep = Annotated[
    EmbeddingCapabilityGroup,
    depends(_get_primary_embedding_capability_group, use_cache=True, scope="singleton"),
]
"""Type alias for DI injection of primary embedding capability group."""


@dependency_provider(BackupEmbeddingCapabilityGroup, scope="singleton")
def _get_backup_embedding_capability_group(
    configured_caps: BackupConfiguredCapabilitiesDep = INJECTED,
) -> BackupEmbeddingCapabilityGroup:
    """Creates the backup embedding capability group from both embedding and sparse embedding settings."""
    return BackupEmbeddingCapabilityGroup.from_capabilities(configured_caps)


type BackupEmbeddingCapabilityGroupDep = Annotated[
    BackupEmbeddingCapabilityGroup,
    depends(_get_backup_embedding_capability_group, use_cache=True, scope="singleton"),
]
"""Type alias for DI injection of backup embedding capability group."""


def _get_embedding_provider_for_config(
    config: EmbeddingProviderSettings, registry: EmbeddingRegistryDep = INJECTED
) -> EmbeddingProvider:
    """Helper to get the embedding provider settings from config."""
    capabilities = config.embedding_config.capabilities
    provider = config.client.embedding_provider
    try:
        resolved_provider = provider._resolve()
    except (AttributeError, ImportError) as e:
        raise ConfigurationError(
            f"Failed to resolve embedding provider for config {config}",
            suggestions=[
                f"Ensure the embedding provider {config.client.as_title} SDK is installed and accessible",
                "Check that the provider client is correctly configured",
            ],
        ) from e
    client = config.get_client()
    if "openai" in config.client.variable:
        from codeweaver.providers.embedding.providers.openai_factory import OpenAIEmbeddingBase

        return cast(OpenAIEmbeddingBase, resolved_provider).get_provider_class(
            model_name=ModelName(config.model_name or config.embedding_config.model_name),
            client=client,
            provider=config.provider,
            registry=registry,
            caps=capabilities,  # ty:ignore[invalid-argument-type]
            config=config,  # ty:ignore[invalid-argument-type]
        )  # ty:ignore[invalid-return-type]
    return resolved_provider(client=client, registry=registry, caps=capabilities, config=config)


def _get_backup_embedding_provider_for_config(
    config: BackupEmbeddingProviderSettings, registry: BackupEmbeddingRegistryDep = INJECTED
) -> BackupEmbeddingProvider:
    """Helper to get the backup embedding provider settings from config."""
    capabilities = config.embedding_config.capabilities
    provider = config.client.embedding_provider
    try:
        resolved_provider = provider._resolve()
    except (AttributeError, ImportError) as e:
        raise ConfigurationError(
            f"Failed to resolve backup embedding provider for config {config}",
            suggestions=[
                f"Ensure the embedding provider {config.client.as_title} SDK is installed and accessible",
                "Check that the provider client is correctly configured",
            ],
        ) from e
    client = config.get_client()
    return resolved_provider(client=client, registry=registry, caps=capabilities, config=config)


type EmbeddingProviderDep = Annotated[
    EmbeddingProvider, depends(_create_embedding_provider, use_cache=False)
]
"""Type alias for DI injection of embedding provider."""

type BackupEmbeddingProviderDep = Annotated[
    BackupEmbeddingProvider, depends(_create_backup_embedding_provider, use_cache=False)
]
"""Type alias for DI injection of backup embedding provider."""


def _get_sparse_embedding_provider_for_config(
    config: SparseEmbeddingProviderSettings, registry: EmbeddingRegistryDep = INJECTED
) -> SparseEmbeddingProvider:
    """Helper to get the sparse embedding provider settings from config."""
    capabilities = config.sparse_embedding_config.capabilities
    provider = config.client.embedding_provider
    try:
        resolved_provider = provider._resolve()
    except (AttributeError, ImportError) as e:
        raise ConfigurationError(
            f"Failed to resolve sparse embedding provider for config {config}",
            suggestions=[
                f"Ensure the sparse embedding provider {config.client.as_title} SDK is installed and accessible",
                "Check that the provider client is correctly configured",
            ],
        ) from e
    client = config.get_client()
    return resolved_provider(client=client, registry=registry, caps=capabilities, config=config)


def _get_backup_sparse_embedding_provider_for_config(
    config: BackupSparseEmbeddingProviderSettings, registry: BackupEmbeddingRegistryDep = INJECTED
) -> BackupSparseEmbeddingProvider:
    """Helper to get the backup sparse embedding provider settings from config."""
    capabilities = config.sparse_embedding_config.capabilities
    provider = config.client.embedding_provider
    try:
        resolved_provider = provider._resolve()
    except (AttributeError, ImportError) as e:
        raise ConfigurationError(
            f"Failed to resolve backup sparse embedding provider for config {config}",
            suggestions=[
                f"Ensure the sparse embedding provider {config.client.as_title} SDK is installed and accessible",
                "Check that the provider client is correctly configured",
            ],
        ) from e
    client = config.get_client()
    return resolved_provider(client=client, registry=registry, caps=capabilities, config=config)


type SparseEmbeddingProviderDep = Annotated[
    SparseEmbeddingProvider, depends(_create_sparse_embedding_provider, use_cache=False)
]
"""Type alias for DI injection of sparse embedding provider."""

type BackupSparseEmbeddingProviderDep = Annotated[
    BackupSparseEmbeddingProvider,
    depends(_create_backup_sparse_embedding_provider, use_cache=False),
]
"""Type alias for DI injection of backup sparse embedding provider."""


# ===========================================================================
# *              Rerranking Provider
# ===========================================================================

BackupRerankingProvider = create_backup_class(
    lazy_import("codeweaver.providers.reranking.providers", "RerankingProvider")._resolve()
)


def _get_reranking_provider_for_config(config: RerankingProviderSettings) -> RerankingProvider:
    """Helper to get the reranking provider settings from config."""
    capabilities = config.reranking_config.capabilities
    provider = config.client.reranking_provider
    try:
        resolved_provider = provider._resolve()
    except (AttributeError, ImportError) as e:
        raise ConfigurationError(
            f"Failed to resolve reranking provider for config {config}",
            suggestions=[
                f"Ensure the reranking provider {config.client.as_title} SDK is installed and accessible",
                "Check that the provider client is correctly configured",
            ],
        ) from e
    client = config.get_client()
    return resolved_provider(client=client, config=config, caps=capabilities)


def _get_backup_reranking_provider_for_config(
    config: BackupRerankingProviderSettings,
) -> BackupRerankingProvider:
    """Helper to get the backup reranking provider settings from config."""
    capabilities = config.reranking_config.capabilities
    provider = config.client.reranking_provider
    try:
        resolved_provider = provider._resolve()
    except (AttributeError, ImportError) as e:
        raise ConfigurationError(
            f"Failed to resolve backup reranking provider for config {config}",
            suggestions=[
                f"Ensure the reranking provider {config.client.as_title} SDK is installed and accessible",
                "Check that the provider client is correctly configured",
            ],
        ) from e
    client = config.get_client()
    return resolved_provider(client=client, config=config, caps=capabilities)


type RerankingProviderDep = Annotated[
    RerankingProvider, depends(_create_reranking_provider, use_cache=False)
]
"""Type alias for DI injection of reranking provider."""

type BackupRerankingProviderDep = Annotated[
    BackupRerankingProvider, depends(_create_backup_reranking_provider, use_cache=False)
]
"""Type alias for DI injection of backup reranking provider."""

# ===========================================================================
# *              Vector Store Provider
# ===========================================================================

BackupQdrantVectorStoreProvider = create_backup_class(
    lazy_import("codeweaver.providers.vector_stores.qdrant", "QdrantVectorStoreProvider")._resolve()
)
BackupMemoryVectorStoreProvider = create_backup_class(
    lazy_import(
        "codeweaver.providers.vector_stores.inmemory", "MemoryVectorStoreProvider"
    )._resolve()
)


def _get_vector_store_provider_for_config(
    config: VectorStoreProviderSettings,
    embedding_capabilities: EmbeddingCapabilityGroupDep = INJECTED,
) -> QdrantVectorStoreProvider | MemoryVectorStoreProvider:
    """Helper to get the vector store provider settings from config."""
    # Build list of ConfiguredCapability objects
    if (provider := config.provider) and provider.variable == "qdrant":
        provider_cls = cast(SDKClient, config.client).vector_store_provider
    else:
        provider_cls = lazy_import(
            "codeweaver.providers.vector_stores.inmemory", "MemoryVectorStoreProvider"
        )
    try:
        resolved_provider = provider_cls._resolve()
    except (AttributeError, ImportError) as e:
        raise ConfigurationError(
            f"Failed to resolve vector store provider for config {config}",
            suggestions=[
                f"Ensure the vector store provider {config.client.as_title} SDK is installed and accessible",  # ty:ignore[unresolved-attribute]
                "Check that the provider client is correctly configured",
            ],
        ) from e
    client = config.get_client()
    return resolved_provider(client=client, config=config, caps=embedding_capabilities)


def _get_backup_vector_store_provider_for_config(
    config: BackupVectorStoreProviderSettings,
    embedding_capabilities: BackupEmbeddingCapabilityGroupDep = INJECTED,
) -> BackupQdrantVectorStoreProvider | BackupMemoryVectorStoreProvider:
    """Helper to get the backup vector store provider settings from config."""
    # Build list of ConfiguredCapability objects
    if (provider := config.provider) and provider.variable == "qdrant":
        provider_cls = cast(SDKClient, config.client).vector_store_provider
    else:
        provider_cls = lazy_import(
            "codeweaver.providers.vector_stores.inmemory", "MemoryVectorStoreProvider"
        )
    try:
        resolved_provider = provider_cls._resolve()
    except (AttributeError, ImportError) as e:
        raise ConfigurationError(
            f"Failed to resolve backup vector store provider for config {config}",
            suggestions=[
                f"Ensure the vector store provider {config.client.as_title} SDK is installed and accessible",  # ty:ignore[unresolved-attribute]
                "Check that the provider client is correctly configured",
            ],
        ) from e
    client = config.get_client()
    return resolved_provider(client=client, config=config, caps=embedding_capabilities)


type VectorStoreProviderDep = Annotated[
    QdrantVectorStoreProvider | MemoryVectorStoreProvider,
    depends(_create_vector_store_provider, use_cache=False),
]
"""Type alias for DI injection of vector store provider."""

type BackupQdrantVectorStoreProviderDep = Annotated[
    BackupQdrantVectorStoreProvider, depends(_create_backup_vector_store_provider, use_cache=False)
]
"""Type alias for DI injection of backup vector store provider."""

type BackupMemoryVectorStoreProviderDep = Annotated[
    BackupMemoryVectorStoreProvider, depends(_create_backup_vector_store_provider, use_cache=False)
]
"""Type alias for DI injection of backup memory vector store provider."""


# ===========================================================================
# *                            All Providers
# ===========================================================================


class ProviderDict(TypedDict):
    """TypedDict for all providers."""

    embedding: tuple[EmbeddingProvider | BackupEmbeddingProvider, ...]
    sparse_embedding: tuple[SparseEmbeddingProvider | BackupSparseEmbeddingProvider, ...]
    reranking: tuple[RerankingProvider | BackupRerankingProvider, ...]
    vector_store: tuple[VectorStoreProvider | BackupQdrantVectorStoreProvider, ...]


@dependency_provider(ProviderDict, scope="singleton")
def _get_all_provider_settings(
    embedding_configs: AllEmbeddingConfigsDep = INJECTED,
    sparse_embedding_configs: AllSparseEmbeddingConfigsDep = INJECTED,
    reranking_configs: AllRerankingConfigsDep = INJECTED,
    vector_store_configs: AllVectorStoreConfigsDep = INJECTED,
    registry: EmbeddingRegistryDep = INJECTED,
    backup_registry: BackupEmbeddingRegistryDep = INJECTED,
    provider_settings: ProviderSettingsDep = INJECTED,
) -> ProviderDict:
    """Factory to get all providers from settings."""
    embedding_providers = tuple(
        _get_backup_embedding_provider_for_config(cfg, backup_registry)
        if cfg.as_backup
        else _get_embedding_provider_for_config(cfg, registry)
        for cfg in embedding_configs or ()
    )
    sparse_embedding_providers = tuple(
        _get_backup_sparse_embedding_provider_for_config(cfg, backup_registry)
        if cfg.as_backup
        else _get_sparse_embedding_provider_for_config(cfg, registry)
        for cfg in sparse_embedding_configs or ()
    )
    reranking_providers = tuple(
        _get_backup_reranking_provider_for_config(cfg)
        if cfg.as_backup
        else _get_reranking_provider_for_config(cfg)
        for cfg in reranking_configs or ()
    )
    vector_store_providers = tuple(
        _get_backup_vector_store_provider_for_config(cfg, provider_settings)
        if cfg.as_backup
        else _get_vector_store_provider_for_config(cfg, provider_settings)  # ty:ignore[invalid-argument-type]
        for cfg in vector_store_configs or ()
    )
    return ProviderDict(
        embedding=embedding_providers,
        sparse_embedding=sparse_embedding_providers,
        reranking=reranking_providers,
        vector_store=vector_store_providers,
    )


type AllProviderSettingsDep = Annotated[
    ProviderDict, depends(_get_all_provider_settings, use_cache=True, scope="singleton")
]
"""Type alias for DI injection of all providers."""


@dependency_provider(EmbeddingProvider, scope="singleton")
def _create_embedding_provider(
    config: EmbeddingProviderSettingsDep = INJECTED, registry: EmbeddingRegistryDep = INJECTED
) -> EmbeddingProvider:
    return _get_embedding_provider_for_config(config, registry)


@dependency_provider(BackupEmbeddingProvider, scope="singleton")
def _create_backup_embedding_provider(
    config: BackupEmbeddingProviderSettingsDep = INJECTED,
    registry: BackupEmbeddingRegistryDep = INJECTED,
) -> BackupEmbeddingProvider:
    return _get_backup_embedding_provider_for_config(config, registry)


@dependency_provider(SparseEmbeddingProvider, scope="singleton")
def _create_sparse_embedding_provider(
    config: SparseEmbeddingProviderSettingsDep = INJECTED, registry: EmbeddingRegistryDep = INJECTED
) -> SparseEmbeddingProvider:
    return _get_sparse_embedding_provider_for_config(config, registry)


@dependency_provider(BackupSparseEmbeddingProvider, scope="singleton")
def _create_backup_sparse_embedding_provider(
    config: BackupSparseEmbeddingProviderSettingsDep = INJECTED,
    registry: BackupEmbeddingRegistryDep = INJECTED,
) -> BackupSparseEmbeddingProvider:
    return _get_backup_sparse_embedding_provider_for_config(config, registry)


@dependency_provider(RerankingProvider, scope="singleton")
def _create_reranking_provider(
    config: RerankingProviderSettingsDep = INJECTED,
) -> RerankingProvider:
    return _get_reranking_provider_for_config(config)


@dependency_provider(BackupRerankingProvider, scope="singleton")
def _create_backup_reranking_provider(
    config: BackupRerankingProviderSettingsDep = INJECTED,
) -> BackupRerankingProvider:
    return _get_backup_reranking_provider_for_config(config)


@dependency_provider(MemoryVectorStoreProvider, scope="singleton")
def _create_memory_vector_store_provider(
    config: VectorStoreProviderSettingsDep = INJECTED,
    provider_settings: ProviderSettingsDep = INJECTED,
) -> MemoryVectorStoreProvider:
    return _get_vector_store_provider_for_config(config, provider_settings)  # ty:ignore[invalid-argument-type, invalid-return-type]


@dependency_provider(QdrantVectorStoreProvider, scope="singleton")  # ty:ignore[invalid-argument-type]
def _create_vector_store_provider(
    config: VectorStoreProviderSettingsDep = INJECTED,
    provider_settings: ProviderSettingsDep = INJECTED,
) -> QdrantVectorStoreProvider | MemoryVectorStoreProvider:
    return _get_vector_store_provider_for_config(config, provider_settings)  # ty:ignore[invalid-argument-type]


@dependency_provider(BackupQdrantVectorStoreProvider, scope="singleton")
def _create_backup_vector_store_provider(
    config: VectorStoreProviderSettingsDep = INJECTED,
    provider_settings: ProviderSettingsDep = INJECTED,
) -> BackupQdrantVectorStoreProvider:
    return _get_backup_vector_store_provider_for_config(config, provider_settings)


@dependency_provider(BackupMemoryVectorStoreProvider, scope="singleton")
def _create_backup_memory_vector_store_provider(
    config: VectorStoreProviderSettingsDep = INJECTED,
    provider_settings: ProviderSettingsDep = INJECTED,
) -> BackupMemoryVectorStoreProvider:
    return _get_backup_vector_store_provider_for_config(config, provider_settings)


@dependency_provider(ProviderDict, scope="singleton")
def _get_all_provider_settings(
    embedding_configs: AllEmbeddingConfigsDep = INJECTED,
    sparse_embedding_configs: AllSparseEmbeddingConfigsDep = INJECTED,
    reranking_configs: AllRerankingConfigsDep = INJECTED,
    vector_store_configs: AllVectorStoreConfigsDep = INJECTED,
    registry: EmbeddingRegistryDep = INJECTED,
    backup_registry: BackupEmbeddingRegistryDep = INJECTED,
    provider_settings: ProviderSettingsDep = INJECTED,
) -> ProviderDict:
    """Factory to get all providers from settings."""
    embedding_providers = tuple(
        _get_backup_embedding_provider_for_config(cfg, backup_registry)
        if cfg.as_backup
        else _get_embedding_provider_for_config(cfg, registry)
        for cfg in embedding_configs or ()
    )
    sparse_embedding_providers = tuple(
        _get_backup_sparse_embedding_provider_for_config(cfg, backup_registry)
        if cfg.as_backup
        else _get_sparse_embedding_provider_for_config(cfg, registry)
        for cfg in sparse_embedding_configs or ()
    )
    reranking_providers = tuple(
        _get_backup_reranking_provider_for_config(cfg)
        if cfg.as_backup
        else _get_reranking_provider_for_config(cfg)
        for cfg in reranking_configs or ()
    )
    vector_store_providers = tuple(
        _get_backup_vector_store_provider_for_config(cfg)
        if cfg.as_backup
        else _get_vector_store_provider_for_config(cfg)
        for cfg in vector_store_configs or ()
    )
    return ProviderDict(
        embedding=embedding_providers,
        sparse_embedding=sparse_embedding_providers,
        reranking=reranking_providers,
        vector_store=vector_store_providers,
    )


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
    from codeweaver.providers.types import ConfiguredCapability

    return tuple(
        ConfiguredCapability(*conf_tup) for conf_tup in (*dense_conf_caps, *sparse_conf_caps)
    )


def _create_all_configured_capabilities(
    dense_configs: AllEmbeddingConfigsDep = INJECTED,
    sparse_configs: AllSparseEmbeddingConfigsDep = INJECTED,
    dense_resolver: EmbeddingCapabilityResolverDep = INJECTED,
    sparse_resolver: SparseEmbeddingCapabilityResolverDep = INJECTED,
) -> tuple[ConfiguredCapability, ...]:
    """Get all configured capabilities for non-backup providers."""
    # dense_configs = (cfg for cfg in _create_all_embedding_configs() if not cfg.as_backup)
    # sparse_configs = (cfg for cfg in _create_all_sparse_embedding_configs() if not cfg.as_backup)
    # We now inject all configs, so we need to filter for non-backup
    non_backup_dense = (cfg for cfg in dense_configs if not cfg.as_backup)
    non_backup_sparse = (cfg for cfg in sparse_configs if not cfg.as_backup)
    return _assemble_configured_capabilities(
        non_backup_dense, non_backup_sparse, dense_resolver, sparse_resolver
    )


def _create_all_backup_configured_capabilities(
    dense_configs: AllEmbeddingConfigsDep = INJECTED,
    sparse_configs: AllSparseEmbeddingConfigsDep = INJECTED,
    dense_resolver: BackupEmbeddingCapabilityResolverDep = INJECTED,
    sparse_resolver: BackupSparseEmbeddingCapabilityResolverDep = INJECTED,
) -> tuple[ConfiguredCapability, ...]:
    """Get all configured capabilities for backup providers."""
    backup_dense = (cfg for cfg in dense_configs if cfg.as_backup)
    backup_sparse = (cfg for cfg in sparse_configs if cfg.as_backup)
    return _assemble_configured_capabilities(
        backup_dense, backup_sparse, dense_resolver, sparse_resolver
    )


type ConfiguredCapabilitiesDep = Annotated[
    tuple[ConfiguredCapability],
    depends(_create_all_configured_capabilities, use_cache=True, scope="singleton"),
]
"""Assembled configured capabilities for non-backup sparse/dense embedding providers."""

type BackupConfiguredCapabilitiesDep = Annotated[
    tuple[ConfiguredCapability],
    depends(_create_all_backup_configured_capabilities, use_cache=True, scope="singleton"),
]
"""Assembled configured capabilities for backup sparse/dense embedding providers."""


def _create_primary_embedding_capability_group(caps: ConfiguredCapabilitiesDep = INJECTED):
    """Create a primary embedding capability group from the given configured capabilities."""
    dense = next((cap for cap in caps if cap.is_dense), None)
    sparse = next((cap for cap in caps if cap.is_sparse), None)
    idf = next((cap for cap in caps if cap.is_idf), None)
    if sparse == idf:
        sparse = None
    return EmbeddingCapabilityGroup(dense=dense, sparse=sparse, idf=idf)


type EmbeddingCapabilityGroupDep = Annotated[
    "EmbeddingCapabilityGroup",
    depends(_create_primary_embedding_capability_group, use_cache=True, scope="singleton"),
]
"""Type alias for DI injection of primary embedding capability group."""

# ===========================================================================
# *                           Embedding Tokenizers
# ===========================================================================
BackupTokenizer = create_backup_class(lazy_import("codeweaver_tokenizers", "Tokenizer")._resolve())


@dependency_provider(Tokenizer, scope="singleton")
def _get_primary_tokenizer(settings: EmbeddingProviderSettingsDep = INJECTED) -> Tokenizer:
    """Get the primary embedding tokenizer from the resolver."""
    from codeweaver_tokenizers import get_tokenizer

    if (
        (caps := settings.embedding_config.capabilities)
        and (tokenizer := caps.tokenizer)
        and (tokenizer_model := caps.tokenizer_model)
    ):
        return get_tokenizer(tokenizer, tokenizer_model)
    return get_tokenizer("tiktoken", "o200k_base")


@dependency_provider(BackupTokenizer, scope="singleton")
def _get_backup_tokenizer(
    settings: BackupEmbeddingProviderSettingsDep = INJECTED,
) -> BackupTokenizer:
    """Get the backup embedding tokenizer from the resolver."""
    from codeweaver_tokenizers import get_tokenizer

    if (
        (caps := settings.embedding_config.capabilities)
        and (tokenizer := caps.tokenizer)
        and (tokenizer_model := caps.tokenizer_model)
    ):
        return get_tokenizer(tokenizer, tokenizer_model)
    return get_tokenizer("tiktoken", "o200k_base")


type TokenizerDep = Annotated[
    Tokenizer, depends(_get_primary_tokenizer, use_cache=True, scope="singleton")
]
"""Type alias for DI injection of primary embedding tokenizer."""


type BackupTokenizerDep = Annotated[
    BackupTokenizer, depends(_get_backup_tokenizer, use_cache=True, scope="singleton")
]
"""Type alias for DI injection of backup embedding tokenizer."""


async def _get_search_package(
    embedding: EmbeddingProviderDep = INJECTED,
    sparse: SparseEmbeddingProviderDep = INJECTED,
    reranking: RerankingProviderDep = INJECTED,
    vector_store: VectorStoreProviderDep = INJECTED,
    capabilities: EmbeddingCapabilityGroupDep = INJECTED,
):
    """Get the search package containing all necessary providers and capabilities."""
    return SearchPackage(
        embedding=embedding,
        sparse_embedding=sparse,
        reranking=reranking,
        vector_store=vector_store,
        capabilities=capabilities,
    )


type SearchPackageDep = Annotated[
    SearchPackage, depends(_get_search_package, use_cache=True, scope="singleton")
]
"""Type alias for DI injection of search package."""

# ===========================================================================
# *                            MODULE EXPORTS
# ===========================================================================

__all__ = (
    "AgentProviderSettingsDep",
    "AllDataProviderConfigsDep",
    "AllEmbeddingConfigsDep",
    "AllProviderSettingsDep",
    "AllRerankingConfigsDep",
    "AllSparseEmbeddingConfigsDep",
    "AllVectorStoreConfigsDep",
    "BackupConfiguredCapabilitiesDep",
    "BackupEmbeddingCapabilityResolver",
    "BackupEmbeddingProvider",
    "BackupEmbeddingProviderDep",
    "BackupEmbeddingProviderSettings",
    "BackupEmbeddingProviderSettingsDep",
    "BackupEmbeddingRegistryDep",
    "BackupQdrantVectorStoreProvider",
    "BackupQdrantVectorStoreProviderDep",
    "BackupRerankingCapabilityResolver",
    "BackupRerankingCapabilityResolverDep",
    "BackupRerankingProvider",
    "BackupRerankingProviderDep",
    "BackupRerankingProviderSettings",
    "BackupRerankingProviderSettingsDep",
    "BackupSparseEmbeddingCapabilityResolver",
    "BackupSparseEmbeddingProvider",
    "BackupSparseEmbeddingProviderDep",
    "BackupSparseEmbeddingProviderSettings",
    "BackupSparseEmbeddingProviderSettingsDep",
    "BackupTokenizer",
    "BackupTokenizerDep",
    "BackupVectorStoreProviderSettings",
    "BackupVectorStoreProviderSettingsDep",
    "ConfiguredCapabilitiesDep",
    "EmbeddingCapabilityGroupDep",
    "EmbeddingCapabilityResolverDep",
    "EmbeddingClientDep",
    "EmbeddingProviderDep",
    "EmbeddingProviderSettingsDep",
    "EmbeddingRegistryDep",
    "ProviderSettingsDep",
    "RerankingCapabilityResolverDep",
    "RerankingClientDep",
    "RerankingProviderDep",
    "RerankingProviderSettingsDep",
    "SearchPackageDep",
    "SparseCapabilityResolverDep",
    "SparseEmbeddingClientDep",
    "SparseEmbeddingProviderDep",
    "SparseEmbeddingProviderSettingsDep",
    "TokenizerDep",
    "VectorStoreClientDep",
    "VectorStoreProviderDep",
    "VectorStoreProviderSettingsDep",
)
