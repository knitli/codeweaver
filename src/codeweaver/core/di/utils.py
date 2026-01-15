# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Utility functions for CodeWeaver's dependency injection (DI) system.

This module provides a lightweight registry for dependency providers. It allows
registering factory functions or classes that provide instances of specific types,
and retrieving them later. This is a fundamental building block for the
application's dependency injection architecture.
"""

from __future__ import annotations

import inspect

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from threading import Lock
from typing import Any, Literal, TypeVar, cast, overload


T = TypeVar("T")

_registry_lock = Lock()

_providers: dict[type, Callable[..., Any]] = {}
_provider_metadata: dict[type, ProviderMetadata] = {}


@dataclass(frozen=True)
class ProviderMetadata:
    """Metadata about a registered provider.

    Attributes:
        scope: The lifecycle scope (singleton, request, or function)
        is_generator: Whether the provider is a generator function (for cleanup)
        is_async_generator: Whether the provider is an async generator (for cleanup)
        module: Optional module name for scoped registration
    """

    scope: Literal["singleton", "request", "function"]
    is_generator: bool
    is_async_generator: bool
    module: str | None

    @classmethod
    def from_provider(
        cls,
        scope: Literal["singleton", "request", "function"],
        factory: Callable[..., Any],
        module: str | None = None,
    ) -> ProviderMetadata:
        """Create ProviderMetadata from a factory function.

        Args:
            scope: The lifecycle scope.
            factory: The provider function or class.
            module: Optional module name.

        Returns:
            An instance of ProviderMetadata.
        """
        is_async_gen = inspect.isasyncgenfunction(factory)
        is_gen = inspect.isgeneratorfunction(factory)
        return cls(scope=scope, is_generator=is_gen, is_async_generator=is_async_gen, module=module)


@overload
def dependency_provider[T](
    cls: type[T],
    *,
    scope: Literal["singleton", "request", "function"] = "singleton",
    module: str | None = None,
    collection: Literal[True],
) -> Callable[[Callable[..., Sequence[T]]], Callable[..., Sequence[T]]]: ...


@overload
def dependency_provider[T](
    cls: type[T],
    *,
    scope: Literal["singleton", "request", "function"] = "singleton",
    module: str | None = None,
    collection: Literal[False] = False,
) -> Callable[[Callable[..., T]], Callable[..., T]]: ...


@overload
def dependency_provider[T](
    cls: None = None,
    *,
    scope: Literal["singleton", "request", "function"] = "singleton",
    module: str | None = None,
    collection: Literal[False] = False,
) -> Callable[[type[T]], type[T]]: ...


def dependency_provider[T](
    cls: type[T] | None = None,
    *,
    scope: Literal["singleton", "request", "function"] = "singleton",
    module: str | None = None,
    collection: bool = False,
) -> (
    Callable[[Callable[..., T]], Callable[..., T]]
    | Callable[[Callable[..., Sequence[T]]], Callable[..., Sequence[T]]]
    | Callable[[type[T]], type[T]]
    | type[T]
):
    """Decorator that registers a function or class as the provider for a specific type.

    This decorator binds a factory function (or class) to the type it produces.
    When the DI system needs an instance of `cls`, it will use the decorated
    function or class to create it.

    Supports three usage patterns:

    1. Function registration (explicit type):
        ```python
        dependency_provider(MyService, scope="singleton")


        async def create_my_service() -> MyService:
            return MyService()
        ```

    2. Class registration (self-registration):
        Note: In this case, the class *must* implement __call__.
        ```python
        dependency_provider(scope="request")


        class MyService:
            def __init__(self, config: Config):
                self.config = config
        ```

    3. Collection registration (returns multiple instances):
        ```python
        dependency_provider(MyCapability, scope="singleton", collection=True)


        def get_capabilities() -> Sequence[MyCapability]:
            return (MyCapability(...), MyCapability(...))
        ```

    Args:
        cls: The type (class) that the decorated function provides.
        scope: The lifecycle scope - "singleton" (app lifetime, default),
               "request" (per request), or "function" (per call, no caching).
        module: Optional module name for scoped registration.
        collection: If True, the factory returns a Sequence[T] instead of T.
                   Use this when registering a provider that returns multiple instances.

    Returns:
        When used as `dependency_provider(SomeType)`: Returns a decorator function.
        When used as `dependency_provider` on a class: Returns the class unchanged.

    Example:
        ```python
        # Singleton factory function
        dependency_provider(DatabaseConnection, scope="singleton")


        async def get_db() -> DatabaseConnection:
            return DatabaseConnection()


        # Request-scoped service
        dependency_provider(RequestContext, scope="request")


        async def get_context() -> RequestContext:
            return RequestContext()


        # Function-scoped (no caching)
        dependency_provider(TempFile, scope="function")


        async def create_temp() -> TempFile:
            return TempFile()


        # Generator with cleanup
        dependency_provider(ResourcePool, scope="singleton")


        async def get_pool() -> AsyncIterator[ResourcePool]:
            pool = ResourcePool()
            await pool.connect()
            yield pool
            await pool.disconnect()


        # Class self-registration (no cls argument)
        dependency_provider(scope="singleton")


        class SimpleService:
            def __init__(self):
                self.value = 42


        # Collection provider (returns multiple instances)
        dependency_provider(Capability, scope="singleton", collection=True)


        def get_all_capabilities() -> Sequence[Capability]:
            return (
                Capability(name="feature1"),
                Capability(name="feature2"),
                Capability(name="feature3"),
            )
        ```
    """
    # Case 1: Used without cls argument (for class self-registration)
    # dependency_provider(scope="request")
    # class MyClass: ...
    if cls is None:

        def class_decorator(target_cls: type[T]) -> type[T]:
            _register_provider(interface=target_cls, factory=target_cls, scope=scope, module=module)
            return target_cls

        return class_decorator

    # Case 2: Used with explicit type - return decorator function
    # dependency_provider(SomeType, scope="singleton")
    # def factory() -> SomeType: ...
    # OR
    # dependency_provider(SomeType, scope="singleton")
    # class SomeType: ...  # Self-registration with explicit type
    def decorator(fn_or_cls: Callable[..., T] | type[T]) -> Callable[..., T] | type[T]:
        _register_provider(
            interface=cls,  # type: ignore - we know cls is not None here
            factory=fn_or_cls,  # type: ignore
            scope=scope,
            module=module,
        )
        return fn_or_cls

    return decorator


def _register_provider[T](
    interface: type[T],
    factory: Callable[..., T],
    scope: Literal["singleton", "request", "function"],
    module: str | None,
) -> None:
    """Register a provider with metadata in a thread-safe manner.

    Args:
        interface: The type being provided.
        factory: The factory function or class.
        scope: The lifecycle scope.
        module: Optional module name.
    """
    # Detect generator functions for lifecycle management
    is_async_gen = inspect.isasyncgenfunction(factory)
    is_gen = inspect.isgeneratorfunction(factory)

    # Create metadata
    metadata = ProviderMetadata(
        scope=scope, is_generator=is_gen, is_async_generator=is_async_gen, module=module
    )

    # Thread-safe registration
    with _registry_lock:
        _providers[interface] = factory
        _provider_metadata[interface] = metadata


def is_provider_registered(cls: type[Any]) -> bool:
    """Check if a provider is registered for a specific type.

    Args:
        cls: The type to check for a registered provider.

    Returns:
        True if a provider is registered for the given type, False otherwise.
    """
    return cls in _providers


def get_provider[T](cls: type[T]) -> Callable[..., T]:
    """Retrieve the registered provider function for a specific type.

    Args:
        cls: The type for which to retrieve the provider.

    Returns:
        The callable (factory function or class) registered to provide instances
        of `cls`.

    Raises:
        KeyError: If no provider has been registered for the given type.
    """
    with _registry_lock:
        if cls not in _providers:
            raise KeyError(f"No provider registered for type {cls}")
        return cast(Callable[..., T], _providers[cls])


def get_provider_metadata(cls: type[Any]) -> ProviderMetadata | None:
    """Retrieve the metadata for a registered provider.

    Args:
        cls: The type for which to retrieve metadata.

    Returns:
        The provider metadata if registered, None otherwise.
    """
    with _registry_lock:
        return _provider_metadata.get(cls)


def get_all_providers() -> dict[type, Callable[..., Any]]:
    """Retrieve all registered providers.

    Returns:
        A dictionary mapping types to their provider callables.
    """
    with _registry_lock:
        return _providers.copy()


def get_all_provider_metadata() -> dict[type, ProviderMetadata]:
    """Retrieve metadata for all registered providers.

    Returns:
        A dictionary mapping types to their provider metadata.
    """
    with _registry_lock:
        return _provider_metadata.copy()


__all__ = (
    "ProviderMetadata",
    "dependency_provider",
    "get_all_provider_metadata",
    "get_all_providers",
    "get_provider",
    "get_provider_metadata",
    "is_provider_registered",
)
