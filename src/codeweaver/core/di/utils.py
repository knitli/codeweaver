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
from threading import Lock
from typing import Any, Literal, NamedTuple, TypeVar, cast, overload


T = TypeVar("T")

_registry_lock = Lock()

# Storage: type -> list of (factory, metadata) tuples to support multiple providers per type
_providers: dict[type, list[tuple[Callable[..., Any], ProviderMetadata]]] = {}


class ProviderMetadata(NamedTuple):
    """Metadata about a registered provider.

    Attributes:
        scope: The lifecycle scope (singleton, request, or function)
        is_generator: Whether the provider is a generator function (for cleanup)
        is_async_generator: Whether the provider is an async generator (for cleanup)
        module: Optional module name for scoped registration
        tags: Optional tags for categorizing providers (e.g. "backup")
    """

    scope: Literal["singleton", "request", "function"]
    is_generator: bool
    is_async_generator: bool
    module: str | None
    tags: frozenset[str] = frozenset()

    @classmethod
    def from_provider(
        cls,
        scope: Literal["singleton", "request", "function"],
        factory: Callable[..., Any],
        module: str | None = None,
        tags: Sequence[str] | None = None,
    ) -> ProviderMetadata:
        """Create ProviderMetadata from a factory function.

        Args:
            scope: The lifecycle scope.
            factory: The provider function or class.
            module: Optional module name.
            tags: Optional tags.

        Returns:
            An instance of ProviderMetadata.
        """
        is_async_gen = inspect.isasyncgenfunction(factory)
        is_gen = inspect.isgeneratorfunction(factory)
        return cls(
            scope=scope,
            is_generator=is_gen,
            is_async_generator=is_async_gen,
            module=module,
            tags=frozenset(tags) if tags else frozenset(),
        )


@overload
def dependency_provider[T](
    cls: type[T],
    *,
    scope: Literal["singleton", "request", "function"] = "singleton",
    module: str | None = None,
    tags: Sequence[str] | None = None,
    collection: Literal[True],
) -> Callable[[Callable[..., Sequence[T]]], Callable[..., Sequence[T]]]: ...


@overload
def dependency_provider[T](
    cls: type[T],
    *,
    scope: Literal["singleton", "request", "function"] = "singleton",
    module: str | None = None,
    tags: Sequence[str] | None = None,
    collection: Literal[False] = False,
) -> Callable[[Callable[..., T]], Callable[..., T]]: ...


@overload
def dependency_provider[T](
    cls: None = None,
    *,
    scope: Literal["singleton", "request", "function"] = "singleton",
    module: str | None = None,
    tags: Sequence[str] | None = None,
    collection: Literal[False] = False,
) -> Callable[[type[T]], type[T]]: ...


def dependency_provider[T](
    cls: type[T] | None = None,
    *,
    scope: Literal["singleton", "request", "function"] = "singleton",
    module: str | None = None,
    tags: Sequence[str] | None = None,
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
        tags: Optional tags for categorizing providers.
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
            _register_provider(
                interface=target_cls, factory=target_cls, scope=scope, module=module, tags=tags
            )
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
            tags=tags,
        )
        return fn_or_cls

    return decorator


def _register_provider[T](
    interface: type[T],
    factory: Callable[..., T],
    scope: Literal["singleton", "request", "function"],
    module: str | None,
    tags: Sequence[str] | None,
) -> None:
    """Register a provider with metadata in a thread-safe manner.

    Args:
        interface: The type being provided.
        factory: The factory function or class.
        scope: The lifecycle scope.
        module: Optional module name.
        tags: Optional tags.
    """
    # Detect generator functions for lifecycle management
    is_async_gen = inspect.isasyncgenfunction(factory)
    is_gen = inspect.isgeneratorfunction(factory)

    # Create metadata
    metadata = ProviderMetadata(
        scope=scope,
        is_generator=is_gen,
        is_async_generator=is_async_gen,
        module=module,
        tags=frozenset(tags) if tags else frozenset(),
    )

    # Thread-safe registration - append to list to support multiple providers per type
    with _registry_lock:
        if interface not in _providers:
            _providers[interface] = []
        _providers[interface].append((factory, metadata))


def is_provider_registered(cls: type[Any], tags: frozenset[str] | set[str] | None = None) -> bool:
    """Check if a provider is registered for a specific type, optionally filtered by tags.

    Args:
        cls: The type to check for a registered provider.
        tags: Optional set of tags to filter providers. If provided, checks if any
              provider has ALL specified tags.

    Returns:
        True if a provider is registered for the given type (and matches tags if specified),
        False otherwise.
    """
    if cls not in _providers:
        return False

    if not tags:
        return True

    # Check if any provider has all specified tags
    tag_set = frozenset(tags) if isinstance(tags, set) else tags
    return any(tag_set.issubset(metadata.tags) for _, metadata in _providers[cls])


def get_provider[T](
    cls: type[T], tags: frozenset[str] | set[str] | None = None
) -> Callable[..., T]:
    """Retrieve a registered provider function for a specific type, optionally filtered by tags.

    Args:
        cls: The type for which to retrieve the provider.
        tags: Optional set of tags to filter providers. If provided, only returns
              providers that have ALL specified tags.

    Returns:
        The callable (factory function or class) registered to provide instances
        of `cls`. If multiple providers match the tags, returns the last registered one.

    Raises:
        KeyError: If no provider has been registered for the given type, or no provider
                  matches the specified tags.
    """
    with _registry_lock:
        if cls not in _providers:
            raise KeyError(f"No provider registered for type {cls}")

        providers_list = _providers[cls]

        # If no tags specified, return the last (most recently registered) provider
        if not tags:
            return cast(Callable[..., T], providers_list[-1][0])

        # Filter by tags - provider must have ALL specified tags
        tag_set = frozenset(tags) if isinstance(tags, set) else tags
        for factory, metadata in reversed(providers_list):  # Check most recent first
            if tag_set.issubset(metadata.tags):
                return cast(Callable[..., T], factory)

        raise KeyError(f"No provider registered for type {cls} with tags {tag_set}")


def get_provider_metadata(
    cls: type[Any], tags: frozenset[str] | set[str] | None = None
) -> ProviderMetadata | None:
    """Retrieve metadata for a registered provider, optionally filtered by tags.

    Args:
        cls: The type for which to retrieve metadata.
        tags: Optional set of tags to filter providers. If provided, returns metadata
              for the provider that has ALL specified tags.

    Returns:
        The ProviderMetadata for the given type, or None if not registered.
        If multiple providers match the tags, returns the last registered one.
    """
    with _registry_lock:
        if cls not in _providers:
            return None

        providers_list = _providers[cls]

        # If no tags specified, return the last (most recently registered) provider's metadata
        if not tags:
            return providers_list[-1][1]

        # Filter by tags - provider must have ALL specified tags
        tag_set = frozenset(tags) if isinstance(tags, set) else tags
        for _, metadata in reversed(providers_list):  # Check most recent first
            if tag_set.issubset(metadata.tags):
                return metadata

        return None


def get_all_providers() -> dict[type, list[tuple[Callable[..., Any], ProviderMetadata]]]:
    """Retrieve all registered providers with their metadata.

    Returns:
        A dictionary mapping types to lists of (factory, metadata) tuples.
        Each type may have multiple providers registered with different tags.
    """
    with _registry_lock:
        return {k: list(v) for k, v in _providers.items()}


def get_all_provider_metadata() -> dict[type, list[ProviderMetadata]]:
    """Retrieve metadata for all registered providers.

    Returns:
        A dictionary mapping types to lists of ProviderMetadata.
        Each type may have multiple providers registered with different tags.
    """
    with _registry_lock:
        return {
            interface: [metadata for _, metadata in providers_list]
            for interface, providers_list in _providers.items()
        }


__all__ = (
    "ProviderMetadata",
    "dependency_provider",
    "get_all_provider_metadata",
    "get_all_providers",
    "get_provider",
    "get_provider_metadata",
    "is_provider_registered",
)
