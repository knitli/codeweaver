# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency marker for declarative injection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, TypeVar, cast

from codeweaver.core.types import Sentinel, SentinelName
from codeweaver.core.utils import TypeIs


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
    ```python
        from typing import Annotated

        from codeweaver.core.di import Depends, INJECTED
        from someplace import ServiceProvider, service_factory

        def my_service(provider: Annotated[ServiceProvider, Depends(service_factory)] = INJECTED[ServiceProvider]) -> None:
            ...
    ```
    This marker indicates that the parameter should be resolved by the DI container
    using the specified factory function or class. The `use_cache` flag determines
    whether the result should be cached within a scope.

    ## Registering Providers

    To register a provider function or class with the DI container, you can use the provider decorator from
    the `codeweaver.core.di` module:

    ```python "Registering a Provider"
    from codeweaver.core.di import provider


    dependency_provider


    def service_factory() -> ServiceProvider:
        return ServiceProvider()
    ```

    ## Creating a Dependency factory

    You can create a factory for your dependencies using the `create_provider_factory` function:

    ```python "Creating a Dependency Factory"
    # ⚠️ Important: Your must register your provider before calling this function. Order matters! ⚠️

    from codeweaver.core.di import create_provider_factory

    service_factory_provider = create_provider_factory(ServiceProvider)
    ```

    ## Creating a Dependency Marker

    You can create a dependency marker using the `depends` helper function:

    ```python "Creating a Dependency Marker"
    from codeweaver.core.di import depends

    service_dependency = depends(service_factory_provider, use_cache=True)
    ```

    ## Create a Type Alias for Dependency Injection

    Calling a function in a function signature is a bit sloppy. Create a type alias for cleaner code:

    ```python "Creating a Type Alias for Dependency Injection"
    from typing import TYPE_CHECKING, Annotated

    from codeweaver.core.di import depends

    if TYPE_CHECKING:
        from someplace import ServiceProvider

    type ServiceDep = Annotated[ServiceProvider, depends(service_factory_provider)]

    # or if you created your own depends variable already:

    type ServiceDep = Annotated[ServiceProvider, service_dependency]
    ```

    ## Using Your Dependency in Functions

    Now you can use your dependency type alias in function signatures:

    ```python "Using Your Dependency in Functions"
    from typing import TYPE_CHECKING
    from codeweaver.core.di import INJECTED
    from wherever import ServiceDep

    if TYPE_CHECKING:
        from someplace import ServiceProvider


    def my_function(service: ServiceDep = INJECTED[ServiceProvider]) -> None:
        # service will be injected by the DI container
        ...
    ```
    """

    def __init__(
        self,
        dependency: Callable[..., Any] | None = None,
        *,
        use_cache: bool = True,
        scope: Literal["singleton", "request", "function"] | None = None,
    ) -> None:
        """Initialize the dependency marker.

        Args:
            dependency: The factory function or class to use.
            use_cache: Whether to cache the result within a scope.
            scope: Lifecycle scope - singleton (app lifetime), request (per request),
                   function (per call). None means default to singleton if use_cache=True.
        """
        self.dependency = dependency
        self.use_cache = use_cache
        self.scope = scope

    def __repr__(self) -> str:
        """Return a string representation of the marker."""
        attr = getattr(self.dependency, "__name__", type(self.dependency).__name__)
        return f"Depends({attr})"


def depends[T: Any](
    dependency: Callable[..., T] | None = None,
    *,
    use_cache: bool = True,
    scope: Literal["singleton", "request", "function"] | None = None,
) -> Depends[T]:
    """Helper function to create a Depends marker."""
    return Depends(dependency, use_cache=use_cache, scope=scope)


def _is_injected_proxy(value: Any) -> TypeIs[_InjectedProxy]:
    """Check if a value is the injected sentinel proxy."""
    return value is _injected_sentinel


def is_depends_marker[U: Any](value: U) -> bool:
    """Check if a value is a DI injection marker or sentinel.

    Handles Depends markers, DependsPlaceholder sentinels, and the INJECTED proxy.
    """
    if isinstance(value, (Depends, DependsPlaceholder, _InjectedProxy)):
        return True
    # Handle the raw sentinel if it escaped the proxy
    return _is_injected_proxy(value)


__all__ = ("INJECTED", "Depends", "DependsPlaceholder", "depends", "is_depends_marker")
