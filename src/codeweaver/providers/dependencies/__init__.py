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
from typing import TYPE_CHECKING

from codeweaver.core.utils.lazy_importer import create_lazy_getattr


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
    from codeweaver.providers.dependencies.services import (
        EmbeddingCacheManagerDep,
        EmbeddingRegistryDep,
    )

_dynamic_imports = MappingProxyType({
    "AgentCapabilityResolverDep": (__spec__.parent, "capabilities"),
    "AgentProviderSettingsDep": (__spec__.parent, "config"),
    "AllAgentProviderConfigsDep": (__spec__.parent, "config"),
    "AllDataProviderConfigsDep": (__spec__.parent, "config"),
    "AllEmbeddingConfigsDep": (__spec__.parent, "config"),
    "AllRerankingConfigsDep": (__spec__.parent, "config"),
    "AllSparseEmbeddingConfigsDep": (__spec__.parent, "config"),
    "AllVectorStoreConfigsDep": (__spec__.parent, "config"),
    "ConfiguredCapabilitiesDep": (__spec__.parent, "capabilities"),
    "EmbeddingCapabilityGroupDep": (__spec__.parent, "capabilities"),
    "DataProviderSettingsDep": (__spec__.parent, "config"),
    "EmbeddingCacheManagerDep": (__spec__.parent, "services"),
    "EmbeddingCapabilityResolverDep": (__spec__.parent, "capabilities"),
    "EmbeddingProviderSettingsDep": (__spec__.parent, "config"),
    "EmbeddingRegistryDep": (__spec__.parent, "services"),
    "ProviderSettingsDep": (__spec__.parent, "config"),
    "RerankingCapabilityResolverDep": (__spec__.parent, "capabilities"),
    "RerankingProviderSettingsDep": (__spec__.parent, "config"),
    "SparseCapabilityResolverDep": (__spec__.parent, "capabilities"),
    "SparseEmbeddingProviderSettingsDep": (__spec__.parent, "config"),
    "TokenizerDep": (__spec__.parent, "capabilities"),
    "VectorStoreProviderSettingsDep": (__spec__.parent, "config"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "AgentCapabilityResolverDep",
    "AgentProviderSettingsDep",
    "AllAgentProviderConfigsDep",
    "AllDataProviderConfigsDep",
    "AllEmbeddingConfigsDep",
    "AllRerankingConfigsDep",
    "AllSparseEmbeddingConfigsDep",
    "AllVectorStoreConfigsDep",
    "ConfiguredCapabilitiesDep",
    "DataProviderSettingsDep",
    "EmbeddingCacheManagerDep",
    "EmbeddingCapabilityGroupDep",
    "EmbeddingCapabilityResolverDep",
    "EmbeddingProviderSettingsDep",
    "EmbeddingRegistryDep",
    "ProviderSettingsDep",
    "RerankingCapabilityResolverDep",
    "RerankingProviderSettingsDep",
    "SparseCapabilityResolverDep",
    "SparseEmbeddingProviderSettingsDep",
    "TokenizerDep",
    "VectorStoreProviderSettingsDep",
)


def __dir__() -> list[str]:
    """Custom __dir__ implementation to include dynamically imported names."""
    return list(__all__)
