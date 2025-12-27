# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency Injection for CodeWeaver.

Provides a FastAPI-inspired declarative injection system.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.di.container import Container, get_container
    from codeweaver.di.depends import INJECTED, Depends, DependsPlaceholder, depends
    from codeweaver.di.providers import (
        ChunkingServiceDep,
        EmbeddingDep,
        FailoverManagerDep,
        FileWatcherDep,
        GovernorDep,
        HealthServiceDep,
        IgnoreFilterDep,
        IndexerDep,
        ModelRegistryDep,
        ProviderRegistryDep,
        RerankingDep,
        ServicesRegistryDep,
        SettingsDep,
        SparseEmbeddingDep,
        StatisticsDep,
        TokenizerDep,
        VectorStoreDep,
    )
    from codeweaver.di.types import ComponentLifecycle, DependencyProvider


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "Container": (__spec__.parent, "container"),
    "get_container": (__spec__.parent, "container"),
    "INJECTED": (__spec__.parent, "depends"),
    "Depends": (__spec__.parent, "depends"),
    "DependsPlaceholder": (__spec__.parent, "depends"),
    "depends": (__spec__.parent, "depends"),
    "ChunkingServiceDep": (__spec__.parent, "providers"),
    "ComponentLifecycle": (__spec__.parent, "types"),
    "DependencyProvider": (__spec__.parent, "types"),
    "EmbeddingDep": (__spec__.parent, "providers"),
    "FailoverManagerDep": (__spec__.parent, "providers"),
    "FileWatcherDep": (__spec__.parent, "providers"),
    "GovernorDep": (__spec__.parent, "providers"),
    "HealthServiceDep": (__spec__.parent, "providers"),
    "IgnoreFilterDep": (__spec__.parent, "providers"),
    "IndexerDep": (__spec__.parent, "providers"),
    "ModelRegistryDep": (__spec__.parent, "providers"),
    "ProviderRegistryDep": (__spec__.parent, "providers"),
    "RerankingDep": (__spec__.parent, "providers"),
    "ServicesRegistryDep": (__spec__.parent, "providers"),
    "SettingsDep": (__spec__.parent, "providers"),
    "SparseEmbeddingDep": (__spec__.parent, "providers"),
    "StatisticsDep": (__spec__.parent, "providers"),
    "TokenizerDep": (__spec__.parent, "providers"),
    "VectorStoreDep": (__spec__.parent, "providers"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "INJECTED",
    "ChunkingServiceDep",
    "ComponentLifecycle",
    "Container",
    "DependencyProvider",
    "Depends",
    "DependsPlaceholder",
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
    "StatisticsDep",
    "TokenizerDep",
    "VectorStoreDep",
    "depends",
    "get_container",
)
