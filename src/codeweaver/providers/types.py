# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Shared types and base classes for provider systems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Generic, TypeVar


T = TypeVar("T")


class CapabilityResolver(ABC, Generic[T]):
    """Base class for capability resolvers.

    Provides a generic pattern for lazy-loading and resolving model capabilities
    by name. Subclasses must implement `_ensure_loaded()` to populate the
    capabilities registry.

    Type parameter T should be the capability model type (e.g., EmbeddingModelCapabilities).
    """

    def __init__(self) -> None:
        """Initialize the capability resolver with empty cache."""
        self._capabilities_by_name: dict[str, T] = {}
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

    def resolve(self, model_name: str) -> T | None:
        """Get capabilities for a specific model name.

        Args:
            model_name: The name of the model.

        Returns:
            The capabilities for the specified model, or None if not found.
        """
        self._ensure_loaded()
        return self._capabilities_by_name.get(model_name)

    def all_capabilities(self) -> Sequence[T]:
        """Get all registered model capabilities.

        Returns:
            A sequence of all registered capabilities.
        """
        self._ensure_loaded()
        return tuple(self._capabilities_by_name.values())

    def all_model_names(self) -> Sequence[str]:
        """Get all registered model names.

        Returns:
            A sequence of all registered model names.
        """
        self._ensure_loaded()
        return tuple(self._capabilities_by_name.keys())


__all__ = ("CapabilityResolver",)
