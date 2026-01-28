# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Base capability resolvers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from threading import Lock
from types import MappingProxyType

from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    SparseEmbeddingModelCapabilities,
)
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


type EmbeddingCapabilityType = EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities
type RerankingCapabilityType = RerankingModelCapabilities


class BaseCapabilityResolver[Capability: (EmbeddingCapabilityType | RerankingCapabilityType)](ABC):
    """Base class for capability resolvers.

    Provides a generic pattern for lazy-loading and resolving model capabilities
    by name. Subclasses must implement `_ensure_loaded()` to populate the
    capabilities registry.

    Type parameter Capability should be the capability model type (e.g., EmbeddingModelCapabilities).
    """

    def __init__(self) -> None:
        """Initialize the capability resolver with empty cache."""
        self._lock = Lock()
        self._capabilities_by_name: MappingProxyType[str, Capability] = MappingProxyType({})
        self._loaded = False

    @abstractmethod
    def _ensure_loaded(self) -> None:
        """Load all capabilities into the registry.

        Subclasses must implement this to:
        1. Import all capability getter functions
        2. Call each getter and populate self._capabilities_by_name
        3. Set self._loaded = True

        This method should be idempotent - calling multiple times should be safe.
        """
        ...

    def resolve(self, model_name: str) -> Capability | None:
        """Get capabilities for a specific model name.

        Args:
            model_name: The name of the model.

        Returns:
            The capabilities for the specified model, or None if not found.
        """
        with self._lock:
            self._ensure_loaded()
        return self._capabilities_by_name.get(model_name)

    def all_capabilities(self) -> Sequence[Capability]:
        """Get all registered model capabilities.

        Returns:
            A sequence of all registered capabilities.
        """
        with self._lock:
            self._ensure_loaded()
        return tuple(self._capabilities_by_name.values())

    def all_model_names(self) -> Sequence[str]:
        """Get all registered model names.

        Returns:
            A sequence of all registered model names.
        """
        with self._lock:
            self._ensure_loaded()
        return tuple(self._capabilities_by_name.keys())


class BaseRerankingCapabilityResolver(BaseCapabilityResolver[RerankingCapabilityType]):
    """A capability resolver for reranking models."""


class BaseEmbeddingCapabilityResolver(BaseCapabilityResolver[EmbeddingModelCapabilities]):
    """A capability resolver for embedding models."""


class BaseSparseEmbeddingCapabilityResolver(
    BaseCapabilityResolver[SparseEmbeddingModelCapabilities]
):
    """A capability resolver for sparse embedding models."""


__all__ = (
    "BaseCapabilityResolver",
    "BaseEmbeddingCapabilityResolver",
    "BaseRerankingCapabilityResolver",
    "BaseSparseEmbeddingCapabilityResolver",
    "EmbeddingCapabilityType",
    "RerankingCapabilityType",
)
