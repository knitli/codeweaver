# SPDX-FileCopyrightText: 2026 Knitli Inc.
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

Each provider category has:
- A union type (e.g., EmbeddingProviderSettingsType) discriminating by provider
- A DI type alias (e.g., EmbeddingProviderSettingsDep) for injection
- A factory function to create the provider settings instance, resolving dependencies as needed
- A DI type alias for the provider instance itself (e.g., EmbeddingProviderDep)

## Placeholder Status

This module contains intentional placeholders:
- Type aliases without corresponding factories (marked with "⏳ Factory pending")
- Factory functions marked as `...` (to be implemented)
- Import statements for types not yet fully defined

This is expected on the feat/di_monorepo branch.
"""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.dependencies.capabilities import (
        AgentCapabilityResolverDep,
        ConfiguredCapabilitiesDep,
        EmbeddingCapabilityGroupDep,
        EmbeddingCapabilityResolverDep,
        RerankingCapabilityResolverDep,
        SparseCapabilityResolverDep,
        TokenizerDep,
    )
    from codeweaver.providers.dependencies.config import (
        AgentProviderSettingsDep,
        AgentProviderSettingsType,
        AllAgentProviderConfigsDep,
        AllDataProviderConfigsDep,
        AllEmbeddingConfigsDep,
        AllRerankingConfigsDep,
        AllSparseEmbeddingConfigsDep,
        AllVectorStoreConfigsDep,
        CodeWeaverSettingsType,
        ConfigurationError,
        DataProviderSettingsDep,
        DataProviderSettingsType,
        EmbeddingProviderSettingsDep,
        EmbeddingProviderSettingsType,
        ProviderSettingsDep,
        RerankingProviderSettingsDep,
        RerankingProviderSettingsType,
        SparseEmbeddingProviderSettingsDep,
        SparseEmbeddingProviderSettingsType,
        VectorStoreProviderSettingsDep,
        VectorStoreProviderSettingsType,
    )
    from codeweaver.providers.dependencies.providers import (
        AgentProviderDep,
        DataProvidersDep,
        DataProviderType,
        EmbeddingProvidersDep,
        PrimaryEmbeddingProviderDep,
        PrimarySparseEmbeddingProviderDep,
        PrimaryVectorStoreProviderDep,
        ProviderCategorySettingsType,
        QueryEmbeddingProviderDep,
        RerankingProvidersDep,
        SearchPackageDep,
        SparseEmbeddingProvidersDep,
        TypeAliasType,
        VectorStoreProvidersDep,
    )
    from codeweaver.providers.dependencies.services import (
        EmbeddingCacheManagerDep,
        EmbeddingRegistryDep,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AgentProviderSettingsType": (__spec__.parent, "config"),
    "CodeWeaverSettingsType": (__spec__.parent, "config"),
    "ConfigurationError": (__spec__.parent, "config"),
    "DataProviderSettingsType": (__spec__.parent, "config"),
    "DataProviderType": (__spec__.parent, "providers"),
    "EmbeddingProviderSettingsType": (__spec__.parent, "config"),
    "ProviderCategorySettingsType": (__spec__.parent, "providers"),
    "RerankingProviderSettingsType": (__spec__.parent, "config"),
    "SparseEmbeddingProviderSettingsType": (__spec__.parent, "config"),
    "TypeAliasType": (__spec__.parent, "providers"),
    "VectorStoreProviderSettingsType": (__spec__.parent, "config"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "AgentCapabilityResolverDep",
    "AgentProviderDep",
    "AgentProviderSettingsDep",
    "AgentProviderSettingsType",
    "AllAgentProviderConfigsDep",
    "AllDataProviderConfigsDep",
    "AllEmbeddingConfigsDep",
    "AllRerankingConfigsDep",
    "AllSparseEmbeddingConfigsDep",
    "AllVectorStoreConfigsDep",
    "CodeWeaverSettingsType",
    "ConfigurationError",
    "ConfiguredCapabilitiesDep",
    "DataProviderSettingsDep",
    "DataProviderSettingsType",
    "DataProviderType",
    "DataProvidersDep",
    "EmbeddingCacheManagerDep",
    "EmbeddingCapabilityGroupDep",
    "EmbeddingCapabilityResolverDep",
    "EmbeddingProviderSettingsDep",
    "EmbeddingProviderSettingsType",
    "EmbeddingProvidersDep",
    "EmbeddingRegistryDep",
    "MappingProxyType",
    "PrimaryEmbeddingProviderDep",
    "PrimarySparseEmbeddingProviderDep",
    "PrimaryVectorStoreProviderDep",
    "ProviderCategorySettingsType",
    "ProviderSettingsDep",
    "QueryEmbeddingProviderDep",
    "RerankingCapabilityResolverDep",
    "RerankingProviderSettingsDep",
    "RerankingProviderSettingsType",
    "RerankingProvidersDep",
    "SearchPackageDep",
    "SparseCapabilityResolverDep",
    "SparseEmbeddingProviderSettingsDep",
    "SparseEmbeddingProviderSettingsType",
    "SparseEmbeddingProvidersDep",
    "TokenizerDep",
    "TypeAliasType",
    "VectorStoreProviderSettingsDep",
    "VectorStoreProviderSettingsType",
    "VectorStoreProvidersDep",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
