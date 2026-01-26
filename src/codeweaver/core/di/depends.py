# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency marker for declarative injection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, cast, overload

from beartype.typing import TypeVar

from codeweaver.core.types.sentinel import Sentinel, SentinelName
from codeweaver.core.utils.checks import TypeIs


T = TypeVar("T", bound=Any)
T_co = TypeVar("T_co", bound=Any, covariant=True)


class _InjectedProxy[Dep: type[T], S: Sentinel]:
    """Proxy object that provides type-safe subscript syntax for dependency injection.

    This class acts as a wrapper that supports `INJECTED[Type]` syntax while
    maintaining compatibility with the DI container's sentinel detection.

    The proxy allows both subscripted and bare usage:
    - `INJECTED[SomeType]` returns the sentinel cast to SomeType
    - `INJECTED` works as a default value, with type checkers inferring the type
      from the parameter annotation
    """

    def __init__(self, sentinel: S) -> None:
        """Initialize with the actual sentinel instance."""
        self._sentinel: S = sentinel

    @overload
    def __getitem__(self, item: type[T_co]) -> T_co: ...
    @overload
    def __getitem__(self, item: type[Dep]) -> Dep: ...
    def __getitem__(self, item: type[Dep | T_co]) -> Dep | T_co:
        """Return the sentinel cast to the requested type.

        This allows: `param: SomeType = INJECTED[SomeType]`
        Type checkers see it as type T, runtime gets the sentinel.
        """
        return cast(Dep | T_co, self._sentinel)

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the sentinel."""
        return getattr(self._sentinel, name)

    def __repr__(self) -> str:
        """Return a string representation."""
        return repr(self._sentinel)

    # NOTE: Support bare INJECTED usage by implementing __bool__ so type checkers
    # can better understand this as a sentinel value that works as a default.
    # This allows `def func(param: SomeType = INJECTED)` without subscripting.
    def __bool__(self) -> bool:
        """Always return True since the sentinel is always truthy."""
        return True


class DependsPlaceholder(Sentinel):
    """Indicates that a parameter's value should be injected by the DI container.

    Supports type-safe usage via subscript syntax to satisfy type checkers while
    maintaining sentinel behavior at runtime.

    Usage:
        # Type-safe with subscript (recommended):
        async def my_function(
            embedding: Annotated[EmbeddingProvider, Depends(get_embedding)] = INJECTED
        ) -> None:
            # embedding will be injected by the container
            ...

        # Or with type alias:
        async def my_function(
            embedding: EmbeddingDep = INJECTED
        ) -> None:
            ...
    """


_injected_sentinel: DependsPlaceholder = DependsPlaceholder(
    name=SentinelName("InjectedDependency"), module_name=Sentinel._get_module_name_generator()()
)  # ty:ignore[invalid-argument-type]

# INJECTED is a proxy that supports subscripting while wrapping the sentinel.
# Type annotation uses Any to allow it to work as a default value for any dependency-injected
# parameter. Type checkers will infer the correct type from the parameter annotation.
INJECTED: _InjectedProxy[Any, DependsPlaceholder] = _InjectedProxy(_injected_sentinel)  # type: ignore[assignment]


class Depends:
    """Dependency marker, inspired by FastAPI.

    Marks a parameter for dependency injection by the DI container.

    ## Basic Usage (Auto-Resolution)

    The simplest approach is to use the INJECTED sentinel with a type annotation:

    ```python "Simple Auto-Resolution"
    from codeweaver.core.di import INJECTED, dependency_provider

    @dependency_provider(scope="singleton")
    class ServiceProvider:
        def __init__(self):
            self.value = 42

    async def my_function(service: ServiceProvider = INJECTED) -> None:
        # service is automatically injected based on the type annotation
        print(service.value)
    ```

    ## Advanced Usage (Explicit Factory)

    For more control, use the Depends marker with an explicit factory:

    ```python "Explicit Factory with Depends"
    from typing import Annotated
    from codeweaver.core.di import Depends, INJECTED, dependency_provider

    @dependency_provider(ServiceProvider)
    async def service_factory() -> ServiceProvider:
        # Custom initialization logic here
        return ServiceProvider()

    async def my_function(
        service: Annotated[ServiceProvider, Depends(service_factory)] = INJECTED
    ) -> None:
        print(service.value)
    ```

    ## Scope Control

    Control caching behavior with the `scope` parameter:

    ```python "Scope Control"
    from typing import Annotated
    from codeweaver.core.di import depends, INJECTED

    # Singleton: one instance per application lifetime
    type SingletonService = Annotated[Service, depends(scope="singleton")]

    # Request: one instance per request
    type RequestService = Annotated[Service, depends(scope="request")]

    # Function: new instance every time (no caching)
    type FunctionService = Annotated[Service, depends(scope="function")]

    async def handler(
        singleton: SingletonService = INJECTED,
        request: RequestService = INJECTED,
        fresh: FunctionService = INJECTED,
    ) -> None:
        ...
    ```

    ## Type Aliases for Clean Code

    Create type aliases to avoid repeating Annotated everywhere:

    ```python "Type Aliases"
    from typing import TYPE_CHECKING, Annotated
    from codeweaver.core.di import INJECTED, depends

    if TYPE_CHECKING:
        from someplace import ServiceProvider

    # Simple alias (uses default singleton scope)
    type ServiceDep = ServiceProvider

    # Or with explicit behavior
    type RequestScopedService = Annotated[ServiceProvider, depends(scope="request")]

    async def my_function(service: RequestScopedService = INJECTED) -> None:
        # service will be injected with request scope
        ...
    ```
    """

    def __init__(
        self,
        dependency: Callable[..., Any] | None = None,
        *,
        use_cache: bool = True,
        scope: Literal["singleton", "request", "function"] | None = None,
        tags: set[str] | None = None,
    ) -> None:
        """Initialize the dependency marker.

        Args:
            dependency: The factory function or class to use.
            use_cache: Whether to cache the result within a scope.
            scope: Lifecycle scope - singleton (app lifetime), request (per request),
                   function (per call). None means default to singleton if use_cache=True.
            tags: Optional set of tags to categorize the dependency.
        """
        self.dependency = dependency
        self.use_cache = use_cache
        self.scope = scope
        self.tags = tags

    def __repr__(self) -> str:
        """Return a string representation of the marker."""
        attr = getattr(self.dependency, "__name__", type(self.dependency).__name__)
        return f"Depends({attr})"


def depends[T: Any](
    dependency: Callable[..., T] | None = None,
    *,
    use_cache: bool = True,
    scope: Literal["singleton", "request", "function"] | None = None,
    tags: set[str] | None = None,
) -> Depends[T]:
    """Helper function to create a Depends marker."""
    return Depends(dependency, use_cache=use_cache, scope=scope, tags=tags)


def _is_injected_proxy[Dep: Any](value: Any) -> TypeIs[_InjectedProxy[Dep, DependsPlaceholder]]:
    """Check if a value is the injected sentinel proxy."""
    return value is _injected_sentinel


def is_depends_marker[Dep: Any](value: Any) -> bool:
    """Check if a value is a DI injection marker or sentinel.

    Handles Depends markers, DependsPlaceholder sentinels, and the INJECTED proxy.
    """
    if isinstance(value, (Depends, DependsPlaceholder, _InjectedProxy)):
        return True
    # Handle the raw sentinel if it escaped the proxy
    return _is_injected_proxy(value)


__all__ = ("INJECTED", "Depends", "DependsPlaceholder", "depends", "is_depends_marker")
