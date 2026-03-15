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
        AllAgentProviderConfigsDep,
        AllDataProviderConfigsDep,
        AllEmbeddingConfigsDep,
        AllRerankingConfigsDep,
        AllSparseEmbeddingConfigsDep,
        AllVectorStoreConfigsDep,
        DataProviderSettingsDep,
        EmbeddingProviderSettingsDep,
        ProviderSettingsDep,
        RerankingProviderSettingsDep,
        SparseEmbeddingProviderSettingsDep,
        VectorStoreProviderSettingsDep,
    )
    from codeweaver.providers.dependencies.providers import (
        AgentProviderDep,
        DataProvidersDep,
        EmbeddingProvidersDep,
        PrimaryEmbeddingProviderDep,
        PrimarySparseEmbeddingProviderDep,
        PrimaryVectorStoreProviderDep,
        QueryEmbeddingProviderDep,
        RerankingProvidersDep,
        SearchPackageDep,
        SparseEmbeddingProvidersDep,
        VectorStoreProvidersDep,
    )
    from codeweaver.providers.dependencies.services import (
        EmbeddingCacheManagerDep,
        EmbeddingRegistryDep,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AgentCapabilityResolverDep": (__spec__.parent, "capabilities"),
    "AgentProviderDep": (__spec__.parent, "providers"),
    "AgentProviderSettingsDep": (__spec__.parent, "config"),
    "AllAgentProviderConfigsDep": (__spec__.parent, "config"),
    "AllDataProviderConfigsDep": (__spec__.parent, "config"),
    "AllEmbeddingConfigsDep": (__spec__.parent, "config"),
    "AllRerankingConfigsDep": (__spec__.parent, "config"),
    "AllSparseEmbeddingConfigsDep": (__spec__.parent, "config"),
    "AllVectorStoreConfigsDep": (__spec__.parent, "config"),
    "ConfiguredCapabilitiesDep": (__spec__.parent, "capabilities"),
    "DataProvidersDep": (__spec__.parent, "providers"),
    "DataProviderSettingsDep": (__spec__.parent, "config"),
    "EmbeddingCacheManagerDep": (__spec__.parent, "services"),
    "EmbeddingCapabilityGroupDep": (__spec__.parent, "capabilities"),
    "EmbeddingCapabilityResolverDep": (__spec__.parent, "capabilities"),
    "EmbeddingProvidersDep": (__spec__.parent, "providers"),
    "EmbeddingProviderSettingsDep": (__spec__.parent, "config"),
    "EmbeddingRegistryDep": (__spec__.parent, "services"),
    "PrimaryEmbeddingProviderDep": (__spec__.parent, "providers"),
    "PrimarySparseEmbeddingProviderDep": (__spec__.parent, "providers"),
    "PrimaryVectorStoreProviderDep": (__spec__.parent, "providers"),
    "ProviderSettingsDep": (__spec__.parent, "config"),
    "QueryEmbeddingProviderDep": (__spec__.parent, "providers"),
    "RerankingCapabilityResolverDep": (__spec__.parent, "capabilities"),
    "RerankingProvidersDep": (__spec__.parent, "providers"),
    "RerankingProviderSettingsDep": (__spec__.parent, "config"),
    "SearchPackageDep": (__spec__.parent, "providers"),
    "SparseCapabilityResolverDep": (__spec__.parent, "capabilities"),
    "SparseEmbeddingProvidersDep": (__spec__.parent, "providers"),
    "SparseEmbeddingProviderSettingsDep": (__spec__.parent, "config"),
    "TokenizerDep": (__spec__.parent, "capabilities"),
    "VectorStoreProvidersDep": (__spec__.parent, "providers"),
    "VectorStoreProviderSettingsDep": (__spec__.parent, "config"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "AgentCapabilityResolverDep",
    "AgentProviderDep",
    "AgentProviderSettingsDep",
    "AllAgentProviderConfigsDep",
    "AllDataProviderConfigsDep",
    "AllEmbeddingConfigsDep",
    "AllRerankingConfigsDep",
    "AllSparseEmbeddingConfigsDep",
    "AllVectorStoreConfigsDep",
    "ConfiguredCapabilitiesDep",
    "DataProviderSettingsDep",
    "DataProvidersDep",
    "EmbeddingCacheManagerDep",
    "EmbeddingCapabilityGroupDep",
    "EmbeddingCapabilityResolverDep",
    "EmbeddingProviderSettingsDep",
    "EmbeddingProvidersDep",
    "EmbeddingRegistryDep",
    "PrimaryEmbeddingProviderDep",
    "PrimarySparseEmbeddingProviderDep",
    "PrimaryVectorStoreProviderDep",
    "ProviderSettingsDep",
    "QueryEmbeddingProviderDep",
    "RerankingCapabilityResolverDep",
    "RerankingProviderSettingsDep",
    "RerankingProvidersDep",
    "SearchPackageDep",
    "SparseCapabilityResolverDep",
    "SparseEmbeddingProviderSettingsDep",
    "SparseEmbeddingProvidersDep",
    "TokenizerDep",
    "VectorStoreProviderSettingsDep",
    "VectorStoreProvidersDep",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
