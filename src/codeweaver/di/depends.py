# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency marker for declarative injection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

from codeweaver.core import Sentinel, SentinelName


T = TypeVar("T")


class _InjectedProxy:
    """Proxy object that provides type-safe subscript syntax for dependency injection.

    This class acts as a wrapper that supports `INJECTED[Type]` syntax while
    maintaining compatibility with the DI container's sentinel detection.
    """

    def __init__(self, sentinel: Any) -> None:
        """Initialize with the actual sentinel instance."""
        self._sentinel = sentinel

    def __getitem__(self, item: type[T]) -> T:
        """Return the sentinel cast to the requested type.

        This allows: `param: SomeType = INJECTED[SomeType]`
        Type checkers see it as type T, runtime gets the sentinel.
        """
        return cast(T, self._sentinel)

    def __repr__(self) -> str:
        """Return a string representation."""
        return repr(self._sentinel)


class DependsPlaceholder(Sentinel):
    """Indicates that a parameter's value should be injected by the DI container.

    Supports type-safe usage via subscript syntax to satisfy type checkers while
    maintaining sentinel behavior at runtime.

    Usage:
        # Type-safe with subscript (recommended):
        async def my_function(
            embedding: Annotated[EmbeddingProvider, Depends(get_embedding)] = INJECTED[EmbeddingProvider]
        ) -> None:
            # embedding will be injected by the container
            ...

        # Or with type alias:
        async def my_function(
            embedding: EmbeddingDep = INJECTED[EmbeddingProvider]
        ) -> None:
            ...
    """


_injected_sentinel = DependsPlaceholder(
    name=SentinelName("InjectedDependency"), module_name=Sentinel._get_module_name_generator()()
)  # ty:ignore[invalid-argument-type]

# INJECTED is a proxy that supports subscripting while wrapping the sentinel
INJECTED = _InjectedProxy(_injected_sentinel)


class Depends:
    """Dependency marker, inspired by FastAPI.

    Usage:
        def my_service(provider: Annotated[ServiceProvider, Depends(service_factory)] = INJECTED[ServiceProvider]) -> None:
            ...
    """

    def __init__(
        self, dependency: Callable[..., Any] | None = None, *, use_cache: bool = True
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


def is_depends_marker(value: Any) -> bool:
    """Check if a value is a DI injection marker or sentinel.

    Handles Depends markers, DependsPlaceholder sentinels, and the INJECTED proxy.
    """
    if isinstance(value, (Depends, DependsPlaceholder, _InjectedProxy)):
        return True
    # Handle the raw sentinel if it escaped the proxy
    return value is _injected_sentinel


__all__ = ("INJECTED", "Depends", "DependsPlaceholder", "depends", "is_depends_marker")
