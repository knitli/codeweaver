# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Dependency injection types and factories for embedding services."""

from __future__ import annotations

from typing import Annotated

from codeweaver.core.dependencies.utils import ensure_container_initialized


ensure_container_initialized()

from codeweaver.core.di.dependency import depends
from codeweaver.core.di.utils import dependency_provider
from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager
from codeweaver.providers.embedding.registry import EmbeddingRegistry, get_embedding_registry


# NOTE: EmbeddingRegistry is already registered by registry.py via @dependency_provider.
# Do NOT add a second registration here — it would create a fresh EmbeddingRegistry()
# (separate from the global _main_registry), causing the cache_manager to write embeddings
# to a different instance than the one _prepare_vectors resolves from the DI container.

type EmbeddingRegistryDep = Annotated[EmbeddingRegistry, depends(get_embedding_registry)]
"""DI type for EmbeddingRegistry dependency. Use this type in function signatures to have the EmbeddingRegistry automatically injected by the DI container."""


@dependency_provider(EmbeddingCacheManager, scope="singleton")
def _get_embedding_cache_manager() -> EmbeddingCacheManager:
    """Factory for creating an EmbeddingCacheManager instance."""
    # Use get_embedding_registry() (global singleton) so the cache_manager's registry
    # is the same instance that the DI container resolves for EmbeddingRegistry.
    registry = get_embedding_registry()
    return EmbeddingCacheManager(registry=registry)


type EmbeddingCacheManagerDep = Annotated[
    EmbeddingCacheManager, depends(_get_embedding_cache_manager)
]
"""DI type for EmbeddingCacheManager dependency. Use this type in function signatures to have the EmbeddingCacheManager automatically injected by the DI container."""


__all__ = ("EmbeddingCacheManagerDep", "EmbeddingRegistryDep")
