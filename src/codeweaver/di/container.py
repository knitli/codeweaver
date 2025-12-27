# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Central dependency container for CodeWeaver."""

from __future__ import annotations

import asyncio
import inspect
import logging

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any, cast, get_args, get_origin

from codeweaver.di.depends import Depends, DependsPlaceholder


logger = logging.getLogger(__name__)


class Container[T]:
    """Dependency container for managing component lifecycles and resolution.

    Supports:
    - Factory and singleton registration
    - Recursive dependency resolution via Depends markers
    - Testing overrides
    - Async startup/shutdown hooks
    """

    def __init__(self) -> None:
        """Initialize the container."""
        self._factories: dict[type[Any], Callable[..., Any]] = {}
        self._singletons: dict[type[Any], Any] = {}
        self._overrides: dict[type[Any], Any] = {}
        self._is_singleton: dict[type[Any], bool] = {}
        self._startup_hooks: list[Callable[..., Any]] = []
        self._shutdown_hooks: list[Callable[..., Any]] = []

    def register(
        self, interface: type[T], factory: Callable[..., T] | None = None, *, singleton: bool = True
    ) -> None:
        """Register a dependency.

        Args:
            interface: The type or interface to register.
            factory: The factory function or class. If None, the interface itself is used.
            singleton: Whether to cache the instance.
        """
        target = factory or interface
        self._factories[interface] = target
        self._is_singleton[interface] = singleton
        logger.debug("Registered %s -> %s (singleton=%s)", interface.__name__, target, singleton)

    def override(self, interface: type[T], instance: Any) -> None:
        """Override a dependency, primarily for testing.

        Args:
            interface: The type to override.
            instance: The instance or factory to use instead.
        """
        self._overrides[interface] = instance

    def clear_overrides(self) -> None:
        """Clear all registered overrides."""
        self._overrides.clear()

    def add_startup_hook(self, hook: Callable[..., Any]) -> None:
        """Add a startup hook."""
        self._startup_hooks.append(hook)

    def add_shutdown_hook(self, hook: Callable[..., Any]) -> None:
        """Add a shutdown hook."""
        self._shutdown_hooks.append(hook)

    async def resolve(self, interface: type[T]) -> T:
        """Resolve a dependency.

        Args:
            interface: The type to resolve.

        Returns:
            The resolved instance.
        """
        # 1. Check overrides first
        if interface in self._overrides:
            override = self._overrides[interface]
            if callable(override) and not isinstance(override, type):
                return await self._call_with_injection(override)
            return cast(T, override)

        # 2. Check singleton cache
        if self._is_singleton.get(interface) and interface in self._singletons:
            return cast(T, self._singletons[interface])

        # 3. Find factory
        factory = self._factories.get(interface, interface)

        # 4. Create instance
        instance = await self._call_with_injection(factory)

        # 5. Cache if singleton
        if self._is_singleton.get(interface, True):
            self._singletons[interface] = instance

        return cast(T, instance)

    async def _call_with_injection(self, obj: Callable[..., Any]) -> Any:
        """Call a function or instantiate a class, injecting its dependencies.

        Looks for Depends() markers in the signature or Annotated type hints.
        """
        try:
            signature = inspect.signature(obj)
        except (ValueError, TypeError):
            # Fallback for objects that don't support signature inspection
            return obj() if callable(obj) else obj

        kwargs = {}
        for name, param in signature.parameters.items():
            # Check if the default is the INJECTED sentinel
            if marker := self._find_depends_marker(param):
                kwargs[name] = await self._resolve_dependency(name, param, marker)
            elif isinstance(param.default, DependsPlaceholder):
                # Has INJECTED sentinel but no Depends marker - try to resolve by type
                if marker := self._create_depends_from_type(param):
                    kwargs[name] = await self._resolve_dependency(name, param, marker)
                else:
                    raise TypeError(
                        f"Parameter '{name}' in {obj.__name__} has INJECTED sentinel "  # ty:ignore[unresolved-attribute]
                        f"but no Depends() marker and type cannot be auto-resolved.  "
                        f"Use:  Annotated[{param.annotation}, Depends(... )]"
                    )
            elif param.default is inspect.Parameter.empty:
                # Required parameter with no dependency info - this is fine,
                # it might be provided by the caller
                continue

        if inspect.iscoroutinefunction(obj):
            return await obj(**kwargs)

        return obj(**kwargs)

    def _create_depends_from_type(self, param: inspect.Parameter) -> Depends[Any] | None:
        """Try to create a Depends marker from just the type annotation.

        This allows for simpler syntax:
            async def func(embedding: EmbeddingProvider = INJECTED) -> None: ...

        Instead of requiring:
            async def func(embedding:  Annotated[EmbeddingProvider, Depends()] = INJECTED) -> None: ...
        """
        target_type = param.annotation

        # Unwrap Annotated if present
        if get_origin(param.annotation) is Annotated:
            target_type = get_args(param.annotation)[0]

        # Can't auto-resolve without a concrete type
        if target_type is inspect.Parameter.empty or target_type is Any:
            return None

        # Check if this type is registered in the container or is a concrete class
        if (
            target_type in self._factories
            or target_type in self._overrides
            or isinstance(target_type, type)
        ):
            return Depends(dependency=None)  # Will resolve by type

        return None

    def _find_depends_marker(self, param: inspect.Parameter) -> Depends | None:
        """Find a Depends marker in a parameter's default value or Annotated type hint."""
        if isinstance(param.default, Depends):
            return param.default

        if get_origin(param.annotation) is Annotated:
            for arg in get_args(param.annotation):
                if isinstance(arg, Depends):
                    return arg
        return None

    async def _resolve_dependency(
        self, name: str, param: inspect.Parameter, marker: Depends
    ) -> Any:
        """Resolve a dependency from a Depends marker."""
        if marker.dependency:
            return await self._call_with_injection(marker.dependency)

        target_type = param.annotation
        if get_origin(param.annotation) is Annotated:
            target_type = get_args(param.annotation)[0]

        if target_type is inspect.Parameter.empty:
            raise ValueError(f"Parameter {name} has Depends() but no type hint.")

        return await self.resolve(target_type)

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[Container]:
        """Async context manager for managing container lifecycle hooks."""
        # Startup
        for hook in self._startup_hooks:
            if asyncio.iscoroutinefunction(hook):
                await hook()
            else:
                hook()

        try:
            yield self
        finally:
            # Shutdown
            for hook in self._shutdown_hooks:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()

    def __getitem__(self, interface: type[T]) -> T:
        """Synchronous access to resolved singletons.

        WARNING: Only works for already resolved singletons.
        """
        if interface in self._singletons:
            return cast(T, self._singletons[interface])
        raise KeyError(f"Type {interface.__name__} not yet resolved or not a singleton.")


# Global default container for convenience (though explicit usage is preferred)
_default_container: Container | None = None


def get_container() -> Container:
    """Get or create the global default container."""
    global _default_container
    if _default_container is None:
        _default_container = Container()
        from codeweaver.di.providers import setup_default_container

        setup_default_container(_default_container)
    return _default_container


__all__ = ("Container", "get_container")
