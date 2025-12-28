# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Central dependency container for CodeWeaver."""

from __future__ import annotations

import asyncio
import inspect
import logging
import sys

from collections.abc import AsyncIterator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager, suppress
from typing import Annotated, Any, cast, get_args, get_origin, get_type_hints

from codeweaver.di.depends import Depends, DependsPlaceholder, _InjectedProxy


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

    @staticmethod
    def _unwrap_annotated(annotation: Any) -> Any:
        """Unwrap Annotated type hints to get the underlying type.

        Args:
            annotation: The type annotation, possibly Annotated.

        Returns:
            The unwrapped type, or the original annotation if not Annotated.
        """
        if get_origin(annotation) is Annotated:
            return get_args(annotation)[0]
        return annotation

    def _resolve_string_type(
        self, type_str: str, globalns: dict[str, Any] | None = None
    ) -> Any | None:
        """Resolve a string type annotation to an actual type.

        Note: We use eval() here (not ast.literal_eval()) because we're resolving
        type names like "EmbeddingProvider" to actual type objects, not evaluating
        literal values. ast.literal_eval() only works for Python literals (strings,
        numbers, lists, dicts, etc.) and cannot resolve type names.

        This is safe because:
        1. We only eval in the controlled globalns namespace from the module
        2. This is the standard approach for resolving string type annotations
        3. typing.get_type_hints() uses eval internally for the same purpose

        Args:
            type_str: The string representation of a type.
            globalns: The global namespace to use for evaluation.

        Returns:
            The resolved type, or None if resolution fails.
        """
        if not globalns:
            return None

        # Try to evaluate the string as a type reference
        # ruff: noqa: S307 - eval is necessary for type resolution, not literal evaluation
        with suppress(Exception):
            return eval(type_str, globalns)

        return next(
            (factory_type for factory_type in self._factories if factory_type.__name__ == type_str),
            None,
        )

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

    @contextmanager
    def use_overrides(self, overrides: dict[type[Any], Any]) -> Generator[Container, None, None]:
        """Context manager to temporarily apply multiple overrides.

        Args:
            overrides: A dictionary mapping interfaces to their override instances/factories.

        Yields:
            The container instance with overrides applied.
        """
        old_overrides = self._overrides.copy()
        self._overrides.update(overrides)
        try:
            yield self
        finally:
            self._overrides = old_overrides

    def clear_overrides(self) -> None:
        """Clear all registered overrides."""
        self._overrides.clear()

    def add_startup_hook(self, hook: Callable[..., Any]) -> None:
        """Add a startup hook."""
        self._startup_hooks.append(hook)

    def add_shutdown_hook(self, hook: Callable[..., Any]) -> None:
        """Add a shutdown hook."""
        self._shutdown_hooks.append(hook)

    def clear(self) -> None:
        """Clear all registered dependencies and state."""
        self._factories.clear()
        self._singletons.clear()
        self._overrides.clear()
        self._is_singleton.clear()
        self._startup_hooks.clear()
        self._shutdown_hooks.clear()

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

    def _get_globalns(self, obj: Callable[..., Any]) -> dict[str, Any]:
        """Get the global namespace for type hint resolution.

        Args:
            obj: The callable or class to get the namespace for.

        Returns:
            The global namespace dictionary.
        """
        if inspect.isclass(obj):
            return sys.modules[obj.__module__].__dict__
        return getattr(obj, "__globals__", {})

    def _get_signature_and_hints(
        self, obj: Callable[..., Any], globalns: dict[str, Any]
    ) -> tuple[inspect.Signature, dict[str, Any]]:
        """Get signature and type hints for an object.

        Args:
            obj: The callable or class to inspect.
            globalns: The global namespace for type resolution.

        Returns:
            Tuple of (signature, type_hints).

        Raises:
            ValueError: If signature inspection fails completely.
        """
        try:
            signature = inspect.signature(obj)
            # Resolve type hints to handle string annotations from 'from __future__ import annotations'
            # include_extras=True is required to see Annotated metadata
            type_hints = get_type_hints(obj, globalns=globalns, include_extras=True)
        except NameError:
            # NameError happens if a type hint cannot be resolved (e.g. forward ref in TYPE_CHECKING)
            # Fallback to signature annotations which might be strings
            signature = inspect.signature(obj)
            type_hints = {}

        return signature, type_hints

    async def _resolve_injected_parameter(
        self,
        name: str,
        param: inspect.Parameter,
        annotation: Any,
        real_type: Any,
        globalns: dict[str, Any],
        obj: Callable[..., Any],
    ) -> Any:
        """Resolve a parameter with INJECTED sentinel.

        Args:
            name: Parameter name.
            param: Parameter object.
            annotation: Raw annotation.
            real_type: Unwrapped annotation.
            globalns: Global namespace.
            obj: The callable being injected.

        Returns:
            The resolved dependency value.

        Raises:
            TypeError: If the parameter cannot be auto-resolved.
        """
        # Try to resolve by annotation
        if marker := self._create_depends_from_type(param, annotation, globalns):
            return await self._resolve_dependency(name, param, marker, annotation, globalns)

        # Try to resolve by unwrapped real_type
        if real_type != annotation and (
            marker := self._create_depends_from_type(param, real_type, globalns)
        ):
            return await self._resolve_dependency(name, param, marker, real_type, globalns)

        # Special case: if the annotation is still a string, try to resolve it
        if (
            isinstance(annotation, str)
            and (resolved_type := self._resolve_string_type(annotation, globalns))
            and (marker := self._create_depends_from_type(param, resolved_type, globalns))
        ):
            return await self._resolve_dependency(name, param, marker, resolved_type, globalns)

        raise TypeError(
            f"Parameter '{name}' in {obj.__name__} has INJECTED sentinel "  # ty:ignore[unresolved-attribute]
            f"but no Depends() marker and type cannot be auto-resolved.  "
            f"Use:  Annotated[{annotation}, Depends(... )]"
        )

    async def _try_resolve_required_parameter(
        self,
        name: str,
        param: inspect.Parameter,
        annotation: Any,
        real_type: Any,
        globalns: dict[str, Any],
    ) -> Any | None:
        """Try to auto-resolve a required parameter by type hint.

        Args:
            name: Parameter name.
            param: Parameter object.
            annotation: Raw annotation.
            real_type: Unwrapped annotation.
            globalns: Global namespace.

        Returns:
            The resolved dependency value, or None if it can't be resolved.
        """
        # Try to resolve by annotation
        if marker := self._create_depends_from_type(param, annotation, globalns):
            return await self._resolve_dependency(name, param, marker, annotation, globalns)

        # Try to resolve by unwrapped real_type
        if real_type != annotation and (
            marker := self._create_depends_from_type(param, real_type, globalns)
        ):
            return await self._resolve_dependency(name, param, marker, real_type, globalns)

        # Not a dependency, might be provided by caller
        return None

    async def _call_with_injection(self, obj: Callable[..., Any]) -> Any:
        """Call a function or instantiate a class, injecting its dependencies.

        Looks for Depends() markers in the signature or Annotated type hints.
        """
        globalns = self._get_globalns(obj)

        try:
            signature, type_hints = self._get_signature_and_hints(obj, globalns)
        except (ValueError, TypeError):
            # Fallback for objects that don't support signature inspection
            return obj() if callable(obj) else obj

        kwargs = {}
        for name, param in signature.parameters.items():
            # Get resolved annotation from type hints if available
            # THIS IS CRITICAL: type_hints contains the EVALUATED types (not strings)
            annotation = type_hints.get(name, param.annotation)
            real_type = self._unwrap_annotated(annotation)

            # Check if the default is the INJECTED sentinel OR if it's a Depends marker
            if marker := self._find_depends_marker(param, annotation, globalns):
                kwargs[name] = await self._resolve_dependency(
                    name, param, marker, annotation, globalns
                )
            elif isinstance(param.default, (DependsPlaceholder, _InjectedProxy)):
                kwargs[name] = await self._resolve_injected_parameter(
                    name, param, annotation, real_type, globalns, obj
                )
            elif param.default is inspect.Parameter.empty:
                resolved = await self._try_resolve_required_parameter(
                    name, param, annotation, real_type, globalns
                )
                if resolved is not None:
                    kwargs[name] = resolved

        if inspect.iscoroutinefunction(obj):
            return await obj(**kwargs)

        return obj(**kwargs)

    def _create_depends_from_type(
        self,
        param: inspect.Parameter,
        annotation: Any = None,
        globalns: dict[str, Any] | None = None,
    ) -> Depends[Any] | None:
        """Try to create a Depends marker from just the type annotation.

        This allows for simpler syntax:
            async def func(embedding: EmbeddingProvider = INJECTED[EmbeddingProvider]) -> None: ...

        Instead of requiring:
            async def func(embedding:  Annotated[EmbeddingProvider, Depends()] = INJECTED[EmbeddingProvider]) -> None: ...
        """
        target_type = annotation or param.annotation

        # If it's a string, try to resolve it
        if isinstance(target_type, str):
            resolved = self._resolve_string_type(target_type, globalns)
            if resolved is None:
                return None
            target_type = resolved

        # Unwrap Annotated if present
        target_type = self._unwrap_annotated(target_type)

        # Can't auto-resolve without a concrete type
        if target_type is inspect.Parameter.empty or target_type is Any:
            return None

        # Check if this type is registered in the container or is a concrete class
        if (
            target_type in self._factories
            or target_type in self._overrides
            or (isinstance(target_type, type) and not target_type.__module__.startswith("typing"))
        ):
            return Depends(dependency=None)  # Will resolve by type

        return None

    def _find_depends_marker(
        self,
        param: inspect.Parameter,
        annotation: Any = None,
        globalns: dict[str, Any] | None = None,
    ) -> Depends | None:
        """Find a Depends marker in a parameter's default value or Annotated type hint."""
        if isinstance(param.default, Depends):
            return param.default

        target_annotation = annotation or param.annotation

        # If it's a string, try to resolve it
        if isinstance(target_annotation, str):
            resolved = self._resolve_string_type(target_annotation, globalns)
            if resolved is not None:
                target_annotation = resolved

        if get_origin(target_annotation) is Annotated:
            for arg in get_args(target_annotation):
                # Handle both direct Depends and nested Depends if it was resolved
                if isinstance(arg, Depends):
                    return arg
        return None

    async def _resolve_dependency(
        self,
        name: str,
        param: inspect.Parameter,
        marker: Depends,
        annotation: Any = None,
        globalns: dict[str, Any] | None = None,
    ) -> Any:
        """Resolve a dependency from a Depends marker."""
        if marker.dependency:
            # Resolve via container to support registration, singletons, and overrides
            # If it's a factory function, the container will resolve it
            return await self.resolve(marker.dependency)

        target_type = annotation or param.annotation

        # If it's a string, try to resolve it
        if isinstance(target_type, str):
            resolved = self._resolve_string_type(target_type, globalns)
            if resolved is not None:
                target_type = resolved

        # Unwrap Annotated if present
        target_type = self._unwrap_annotated(target_type)

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


def reset_container() -> None:
    """Reset the global default container."""
    global _default_container
    if _default_container:
        _default_container.clear()
    _default_container = None


__all__ = ("Container", "get_container", "reset_container")
