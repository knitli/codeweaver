# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency marker for declarative injection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from codeweaver.core.types.aliases import SentinelName
from codeweaver.core.types.sentinel import Sentinel


class DependsPlaceholder(Sentinel):
    """Indicates that a parameter's value should be injected by the DI container.
    
    DependencyPlaceholder primarily serves as a placeholder to satisfy type checkers and linters, indicating that the actual value will be provided by the DI container at runtime.
    
    Usage:
        async def my_function(
            embedding:  Annotated[EmbeddingProvider, Depends[EmbeddingProvider](get_embedding)] = INJECTED
        ) -> None:
            # embedding will be injected by the container
            ...
    """


INJECTED = DependsPlaceholder(
    name=SentinelName("InjectedDependency"), module_name=Sentinel._get_module_name_generator()()
)  # ty:ignore[invalid-argument-type]


class Depends[T: Any]:
    """Dependency marker, inspired by FastAPI.

    Usage:
        def my_service(provider: EmbeddingProvider = Depends(get_embedding)):
            ...
    """

    def __init__(
        self, dependency: Callable[..., T] | None = None, *, use_cache: bool = True
    ) -> None:
        """Initialize the dependency marker.

        Args:
            dependency: The factory function or class to use.
            use_cache: Whether to cache the result within a scope.
        """
        self.dependency = dependency
        self.use_cache = use_cache

    def __repr__(self) -> str:
        """Return a string representation of the marker."""
        attr = getattr(self.dependency, "__name__", type(self.dependency).__name__)
        return f"Depends({attr})"


def depends[T: Any](
    dependency: Callable[..., T] | None = None, *, use_cache: bool = True
) -> Depends[T]:
    """Helper function to create a Depends marker."""
    return Depends(dependency, use_cache=use_cache)


__all__ = ("INJECTED", "Depends", "depends")
