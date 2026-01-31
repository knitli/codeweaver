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
import types

from collections.abc import AsyncIterator, Callable, Generator
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager, suppress
from dataclasses import dataclass
from typing import Annotated, Any, TypeAliasType, Union, cast, get_args, get_origin

# Pydantic internal utilities for robust type resolution
from pydantic._internal._core_utils import get_type_ref
from pydantic._internal._typing_extra import annotated_type, get_function_type_hints

from codeweaver.core.di.depends import Depends, DependsPlaceholder, _InjectedProxy
from codeweaver.core.exceptions import DependencyInjectionError


logger = logging.getLogger(__name__)


@dataclass
class ResolutionResult:
    """Result of dependency resolution with error tracking.

    Used when collect_errors=True to aggregate multiple dependency
    resolution errors instead of failing fast on the first error.

    Attributes:
        values: Successfully resolved parameter values by name
        errors: List of dependency injection errors encountered
    """

    values: dict[str, Any]
    errors: list[DependencyInjectionError]


class Container[T]:
    """Dependency container for managing component lifecycles and resolution.

    Supports:
    - Factory and singleton registration
    - Recursive dependency resolution via Depends markers
    - Testing overrides
    - Async startup/shutdown hooks
    - Auto-discovery of providers via dependency_provider decorator
    """

    def __init__(self) -> None:
        """Initialize the container."""
        # Store multiple providers per type with their tags
        self._factories: dict[type[Any], list[tuple[Callable[..., Any], frozenset[str]]]] = {}
        self._singletons: dict[type[Any], Any] = {}
        # Separate cache for tagged singletons: (type, frozenset[tags]) -> instance
        self._tagged_singletons: dict[tuple[type[Any], frozenset[str]], Any] = {}
        self._overrides: dict[type[Any], Any] = {}
        self._is_singleton: dict[type[Any], bool] = {}
        self._scope: dict[type[Any], str] = {}  # Track scope: singleton, request, or function
        self._startup_hooks: list[Callable[..., Any]] = []
        self._shutdown_hooks: list[Callable[..., Any]] = []
        self._cleanup_stack: AsyncExitStack | None = None
        self._request_cache: dict[Any, Any] = {}  # Keys can be types or callables
        self._providers_loaded: bool = False  # Track if auto-discovery has run  # Track if auto-discovery has run  # Track if auto-discovery has run

    @staticmethod
    def _unwrap_annotated(annotation: Any) -> Any:
        """Unwrap Annotated type hints to get the underlying type.

        Uses pydantic's annotated_type() for robust handling of Annotated types.

        Args:
            annotation: The type annotation, possibly Annotated.

        Returns:
            The unwrapped type, or the original annotation if not Annotated.
        """
        # Use pydantic's annotated_type() which handles edge cases better
        unwrapped = annotated_type(annotation)
        return unwrapped if unwrapped is not None else annotation

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

        # First, try to evaluate the string as a type reference
        # ruff: noqa: S307 - eval is necessary for type resolution, not literal evaluation
        with suppress(Exception):
            evaluated = eval(type_str, globalns)
            return evaluated
        
        # If direct eval failed, check if it's an Annotated pattern like "Annotated[SomeType, ...]"
        # In this case, try to resolve the base type from registered factories
        if type_str.startswith("Annotated["):
            # Extract the base type name (first argument to Annotated)
            # Simple parsing: "Annotated[TypeName, ...]" -> "TypeName"
            try:
                # Find the first comma or closing bracket
                start = len("Annotated[")
                end = type_str.find(",", start)
                if end == -1:
                    end = type_str.find("]", start)
                
                if end > start:
                    base_type_str = type_str[start:end].strip()
                    
                    # Try to find this type in registered factories
                    for factory_type in self._factories:
                        if factory_type.__name__ == base_type_str:
                            # Reconstruct the Annotated type using the resolved base type
                            # We need Annotated from typing
                            from typing import Annotated, get_args
                            
                            # Try to eval the full annotation with the base type injected
                            enhanced_globalns = globalns.copy()
                            enhanced_globalns[base_type_str] = factory_type
                            
                            with suppress(Exception):
                                return eval(type_str, enhanced_globalns)
            except Exception:
                # If anything goes wrong with parsing/resolution, fall through
                pass

        # Fallback: try to find a factory by matching type name
        return next(
            (factory_type for factory_type in self._factories if factory_type.__name__ == type_str),
            None,
        )

    def _load_providers(self) -> None:
        """Load providers from the global registry on first access.

        This method is called lazily on first `resolve()` call to ensure all
        dependency_provider decorators have been processed during module imports.

        Thread-safe via the _providers_loaded flag - only runs once.
        """
        if self._providers_loaded:
            return

        from codeweaver.core.di.utils import get_all_providers

        # New API returns dict[type, list[tuple[Callable, ProviderMetadata]]]
        providers_map = get_all_providers()

        for interface, providers_list in providers_map.items():
            for factory, metadata in providers_list:
                # Map scope to singleton flag
                # - "singleton" -> singleton=True (app lifetime cache)
                # - "request" -> singleton=False (request-scoped, managed by Container._request_cache)
                # - "function" -> singleton=False (no caching at all)
                is_singleton = metadata.scope == "singleton"

                # Register with tags and scope
                self.register(interface, factory, singleton=is_singleton, tags=metadata.tags, scope=metadata.scope)

                logger.debug(
                    "Auto-discovered provider: %s -> %s (scope=%s, tags=%s, is_generator=%s, is_async_generator=%s)",
                    interface.__name__,
                    factory.__name__ if hasattr(factory, "__name__") else factory,
                    metadata.scope,
                    metadata.tags,
                    metadata.is_generator,
                    metadata.is_async_generator,
                )

        self._providers_loaded = True
        logger.debug("Loaded providers from registry (total interfaces: %d)", len(providers_map))

    def register(
        self,
        interface: type[T],
        factory: Callable[..., T] | None = None,
        *,
        singleton: bool = True,
        tags: frozenset[str] | set[str] | None = None,
        scope: str | None = None,
    ) -> None:
        """Register a dependency.

        Args:
            interface: The type or interface to register.
            factory: The factory function or class. If None, the interface itself is used.
            singleton: Whether to cache the instance.
            tags: Optional tags to categorize this provider.
            scope: Optional scope (singleton, request, function). If not provided, inferred from singleton flag.
        """
        target = factory or interface
        tag_set = frozenset(tags) if tags else frozenset()

        # Store as list to support multiple providers per type
        if interface not in self._factories:
            self._factories[interface] = []
        self._factories[interface].append((target, tag_set))

        self._is_singleton[interface] = singleton
        
        # Store scope - infer from singleton flag if not explicitly provided
        if scope:
            self._scope[interface] = scope
        else:
            self._scope[interface] = "singleton" if singleton else "function"
        
        logger.debug(
            "Registered %s -> %s (singleton=%s, scope=%s, tags=%s)",
            interface.__name__,
            target,
            singleton,
            self._scope[interface],
            tag_set,
        )

    def override(self, interface: type[T] | TypeAliasType[T], instance: Any) -> None:
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
        self._scope.clear()
        self._startup_hooks.clear()
        self._shutdown_hooks.clear()
        self._cleanup_stack = None
        self._request_cache.clear()
        self._providers_loaded = False  # Reset to allow re-loading

    def clear_request_cache(self) -> None:
        """Clear the request-scoped dependency cache.

        Should be called at the end of each request to clean up request-scoped instances.
        """
        self._request_cache.clear()

    @staticmethod
    def _is_union_type(annotation: Any) -> bool:
        """Check if an annotation is a Union type (Union[...] or X | Y syntax).

        Handles both typing.Union and types.UnionType (Python 3.10+ | syntax).

        Args:
            annotation: The type annotation to check.

        Returns:
            True if the annotation is a union type, False otherwise.
        """
        origin = get_origin(annotation)
        return origin is Union or origin is types.UnionType

    async def _resolve_union_dependency(
        self, annotation: Any, _resolution_stack: list[str] | None = None
    ) -> Any:
        """Try to resolve from union types in order.

        Attempts to resolve each type in the union, skipping None types.
        Returns the first successfully resolved type.

        Args:
            annotation: The Union type annotation to resolve.
            _resolution_stack: Internal parameter for circular dependency tracking.

        Returns:
            The first successfully resolved instance from the union.

        Raises:
            ValueError: If the annotation is not a union type or if no type can be resolved.
        """
        if not self._is_union_type(annotation):
            raise ValueError(f"Not a union type: {annotation}")

        union_args = get_args(annotation)

        # Try each type in the union, skipping None
        for arg_type in union_args:
            # Skip None type
            if arg_type is type(None):
                continue

            # Check if registered in container
            if arg_type in self._factories or arg_type in self._overrides:
                return await self.resolve(arg_type, _resolution_stack)

        # Try to instantiate first non-None type
        for arg_type in union_args:
            if arg_type is not type(None):
                try:
                    return await self.resolve(arg_type, _resolution_stack)
                except Exception:  # noqa: S112
                    # Intentionally continue to try next union type
                    continue

        raise ValueError(f"Could not resolve any type from union: {union_args}")

    def _get_factory(
        self, interface: type[T], tags: frozenset[str] | set[str] | None = None
    ) -> Callable[..., T]:
        """Get a factory for the given interface, optionally filtered by tags.

        Args:
            interface: The type to get a factory for.
            tags: Optional tags to filter factories. If provided, returns the factory
                  that has ALL specified tags.

        Returns:
            The factory function or class for the interface.

        Raises:
            KeyError: If no factory is registered or no factory matches the tags.
        """
        if interface not in self._factories:
            # Fall back to the interface itself (might be a class)
            return interface  # type: ignore

        factories_list = self._factories[interface]

        # If no tags specified, return the last (most recently registered) factory
        if not tags:
            return factories_list[-1][0]  # type: ignore

        # Filter by tags - factory must have ALL specified tags
        tag_set = frozenset(tags) if isinstance(tags, set) else tags
        for factory, factory_tags in reversed(factories_list):  # Check most recent first
            if tag_set.issubset(factory_tags):
                return factory  # type: ignore

        raise KeyError(f"No factory registered for type {interface} with tags {tag_set}")

    async def _resolve_union_interface(
        self, interface: Any, cache_key: str, _resolution_stack: list[str]
    ) -> Any:
        """Resolve a Union-annotated interface with proper stack handling."""
        _resolution_stack.append(cache_key)
        try:
            return await self._resolve_union_dependency(interface, _resolution_stack)
        finally:
            _resolution_stack.pop()

    async def _resolve_override(
        self, interface: type[T] | TypeAliasType[T], cache_key: str, _resolution_stack: list[str]
    ) -> T | None:
        """Resolve an override for the given interface if one exists.

        Returns the resolved override instance, or None if no override applies.
        """
        if interface not in self._overrides:
            return None

        override = self._overrides[interface]
        if callable(override) and not isinstance(override, type):
            _resolution_stack.append(cache_key)
            try:
                return cast(T, await self._call_with_injection(override, _resolution_stack))
            finally:
                _resolution_stack.pop()
        return cast(T, override)

    def _get_cached_singleton(self, interface: type[T], tag_set: frozenset[str] | None) -> T | None:
        """Retrieve a cached singleton instance if available.

        Args:
            interface: The type to retrieve from cache.
            tag_set: Optional tags to identify tagged singletons.

        Returns:
            The cached singleton instance, or None if not cached or not marked as singleton.
        """
        if not self._is_singleton.get(interface):
            return None

        if tag_set:
            tagged_key = (interface, tag_set)
            return cast(T | None, self._tagged_singletons.get(tagged_key))

        return cast(T | None, self._singletons.get(interface))

    def _cache_singleton(
        self, interface: type[T], instance: T, tag_set: frozenset[str] | None
    ) -> None:
        """Cache a singleton instance if the interface is marked as singleton.

        Args:
            interface: The type being cached.
            instance: The instance to cache.
            tag_set: Optional tags to identify tagged singletons.
        """
        if not self._is_singleton.get(interface, True):
            return

        if tag_set:
            self._tagged_singletons[(interface, tag_set)] = instance
        else:
            self._singletons[interface] = instance

    async def resolve(
        self,
        interface: type[T] | TypeAliasType[T],
        _resolution_stack: list[str] | None = None,
        tags: frozenset[str] | set[str] | None = None,
    ) -> T:
        """Resolve a dependency with circular dependency detection.

        Args:
            interface: The type to resolve.
            _resolution_stack: Internal parameter for tracking resolution chain.
                DO NOT pass this manually - it's managed automatically.
            tags: Optional tags to filter providers. If provided, resolves the provider
                  that has ALL specified tags.

        Returns:
            The resolved instance.

        Raises:
            CircularDependencyError: If a circular dependency is detected.
        """
        from codeweaver.core.exceptions import CircularDependencyError

        if _resolution_stack is None:
            _resolution_stack = []

        self._load_providers()

        cache_key = self._create_cache_key(interface)
        tag_set = frozenset(tags) if tags else None

        if cache_key in _resolution_stack:
            cycle = " -> ".join([*_resolution_stack, cache_key])
            raise CircularDependencyError(cycle=cycle)

        if self._is_union_type(interface):
            instance = await self._resolve_union_interface(interface, cache_key, _resolution_stack)
            return cast(T, instance)

        # 1. Check overrides first (only for untagged resolution)
        if not tag_set and (
            override_result := await self._resolve_override(interface, cache_key, _resolution_stack)
        ):
            return override_result

        # 2. Check singleton cache
        if cached_instance := self._get_cached_singleton(interface, tag_set):
            return cached_instance

        # 3. Check request cache for request-scoped dependencies
        scope = self._scope.get(interface, "singleton")
        if scope == "request":
            request_cache_key = (interface, tag_set) if tag_set else interface
            if request_cache_key in self._request_cache:
                return cast(T, self._request_cache[request_cache_key])

        # 4. Find factory with tag filtering
        factory = self._get_factory(interface, tag_set)

        # 5. Create instance with circular dependency tracking
        _resolution_stack.append(cache_key)
        try:
            instance = await self._call_with_injection(factory, _resolution_stack)
        finally:
            _resolution_stack.pop()

        # 6. Cache based on scope
        if scope == "request":
            # Cache in request scope
            request_cache_key = (interface, tag_set) if tag_set else interface
            self._request_cache[request_cache_key] = instance
        else:
            # Cache if singleton
            self._cache_singleton(interface, instance, tag_set)

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

    @staticmethod
    def _create_cache_key(type_: type[Any]) -> str:
        """Create a stable cache key for a type.

        Uses pydantic's get_type_ref() which handles generics, type aliases,
        and edge cases better than using id() or __name__.

        Args:
            type_: The type to create a cache key for.

        Returns:
            A stable string key that uniquely identifies the type.
        """
        return get_type_ref(type_)

    def _get_signature_and_hints(
        self, obj: Callable[..., Any], globalns: dict[str, Any]
    ) -> tuple[inspect.Signature, dict[str, Any]]:
        """Get signature and type hints for an object.

        Uses pydantic's get_function_type_hints() for robust type resolution,
        which handles PEP 563 string annotations, forward refs, and Python 3.13+ changes.

        Args:
            obj: The callable or class to inspect.
            globalns: The global namespace for type resolution. Will be modified to include
                     Annotated if not present.

        Returns:
            Tuple of (signature, type_hints).

        Raises:
            ValueError: If signature inspection fails completely.
        """
        # Inject Annotated if not present (needed for TYPE_CHECKING imports)
        # We modify the original globalns here because:
        # 1. Annotated should already be available in normal Python code
        # 2. Adding it doesn't break anything
        # 3. We need it available for later calls to _find_depends_marker, etc.
        if "Annotated" not in globalns:
            from typing import Annotated
            globalns["Annotated"] = Annotated
        
        try:
            signature = inspect.signature(obj)
        except (ValueError, TypeError):
            raise ValueError(f"Cannot get signature for {obj}")
        
        # Try to get type hints with pydantic's robust resolver
        try:
            type_hints = get_function_type_hints(obj, globalns=globalns)
        except NameError:
            # NameError happens when type hints reference types not in globalns
            # (e.g., locally-defined classes in TYPE_CHECKING blocks)
            # In this case, we'll use the raw annotations from the signature
            # They'll be strings due to `from __future__ import annotations`
            type_hints = {}
            
            # Manually extract annotations from signature parameters
            # These will be strings that we can try to evaluate later
            for param_name, param in signature.parameters.items():
                if param.annotation is not inspect.Parameter.empty:
                    type_hints[param_name] = param.annotation

        return signature, type_hints

    async def _resolve_injected_parameter(
        self,
        name: str,
        param: inspect.Parameter,
        annotation: Any,
        real_type: Any,
        globalns: dict[str, Any],
        obj: Callable[..., Any],
        _resolution_stack: list[str] | None = None,
    ) -> Any:
        """Resolve a parameter with INJECTED sentinel.

        Args:
            name: Parameter name.
            param: Parameter object.
            annotation: Raw annotation.
            real_type: Unwrapped annotation.
            globalns: Global namespace.
            obj: The callable being injected.
            _resolution_stack: Internal parameter for circular dependency tracking.

        Returns:
            The resolved dependency value.

        Raises:
            TypeError: If the parameter cannot be auto-resolved.
        """
        # Try to resolve by annotation
        if marker := self._create_depends_from_type(param, annotation, globalns):
            return await self._resolve_dependency(
                name, param, marker, annotation, globalns, _resolution_stack
            )

        # Try to resolve by unwrapped real_type
        if real_type != annotation and (
            marker := self._create_depends_from_type(param, real_type, globalns)
        ):
            return await self._resolve_dependency(
                name, param, marker, real_type, globalns, _resolution_stack
            )

        # Special case: if the annotation is still a string, try to resolve it
        if (
            isinstance(annotation, str)
            and (resolved_type := self._resolve_string_type(annotation, globalns))
            and (marker := self._create_depends_from_type(param, resolved_type, globalns))
        ):
            return await self._resolve_dependency(
                name, param, marker, resolved_type, globalns, _resolution_stack
            )

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
        _resolution_stack: list[str] | None = None,
    ) -> Any | None:
        """Try to auto-resolve a required parameter by type hint.

        Args:
            name: Parameter name.
            param: Parameter object.
            annotation: Raw annotation.
            real_type: Unwrapped annotation.
            globalns: Global namespace.
            _resolution_stack: Internal parameter for circular dependency tracking.

        Returns:
            The resolved dependency value, or None if it can't be resolved.
        """
        # Try to resolve by annotation
        if marker := self._create_depends_from_type(param, annotation, globalns):
            return await self._resolve_dependency(
                name, param, marker, annotation, globalns, _resolution_stack
            )

        # Try to resolve by unwrapped real_type
        if real_type != annotation and (
            marker := self._create_depends_from_type(param, real_type, globalns)
        ):
            return await self._resolve_dependency(
                name, param, marker, real_type, globalns, _resolution_stack
            )

        # Not a dependency, might be provided by caller
        return None

    async def _call_with_injection(  # noqa: C901
        self,
        obj: Callable[..., Any],
        _resolution_stack: list[str] | None = None,
        *,
        collect_errors: bool = False,
    ) -> Any | ResolutionResult:
        """Call a function or instantiate a class, injecting its dependencies.

        Looks for Depends() markers in the signature or Annotated type hints.

        Args:
            obj: The callable or class to inject dependencies into.
            _resolution_stack: Internal parameter for circular dependency tracking.
            collect_errors: If True, collect all dependency errors instead of failing fast.
                           Returns ResolutionResult with both values and errors.

        Returns:
            The result of calling obj with injected dependencies, or ResolutionResult
            if collect_errors=True and errors were encountered.
        """
        globalns = self._get_globalns(obj)

        try:
            signature, type_hints = self._get_signature_and_hints(obj, globalns)
        except (ValueError, TypeError):
            # Fallback for objects that don't support signature inspection
            return obj() if callable(obj) else obj

        kwargs = {}
        errors: list[DependencyInjectionError] = []

        for name, param in signature.parameters.items():
            # Get resolved annotation from type hints if available
            # THIS IS CRITICAL: type_hints contains the EVALUATED types (not strings)
            annotation = type_hints.get(name, param.annotation)
            real_type = self._unwrap_annotated(annotation)

            try:
                # Check if the default is the INJECTED sentinel OR if it's a Depends marker
                if marker := self._find_depends_marker(param, annotation, globalns):
                    kwargs[name] = await self._resolve_dependency(
                        name, param, marker, annotation, globalns, _resolution_stack
                    )
                elif isinstance(param.default, (DependsPlaceholder, _InjectedProxy)):
                    kwargs[name] = await self._resolve_injected_parameter(
                        name, param, annotation, real_type, globalns, obj, _resolution_stack
                    )
                elif param.default is inspect.Parameter.empty:
                    resolved = await self._try_resolve_required_parameter(
                        name, param, annotation, real_type, globalns, _resolution_stack
                    )
                    if resolved is not None:
                        kwargs[name] = resolved
            except DependencyInjectionError as e:
                if collect_errors:
                    # Collect error and continue to next parameter
                    errors.append(e)
                    continue
                # Fail fast (existing behavior)
                raise

        # If we collected errors, return ResolutionResult
        if collect_errors and errors:
            return ResolutionResult(values=kwargs, errors=errors)

        # Check if this is a generator function
        if inspect.isasyncgenfunction(obj):
            # Wrap async generator in context manager
            @asynccontextmanager
            async def async_gen_cm():
                async_gen = obj(**kwargs)
                try:
                    yield await async_gen.__anext__()
                finally:
                    # Cleanup - exhaust the generator
                    with suppress(StopAsyncIteration):
                        await async_gen.__anext__()

            if self._cleanup_stack:
                return await self._cleanup_stack.enter_async_context(async_gen_cm())
            # No cleanup stack - use directly within context
            async with async_gen_cm() as value:
                return value

        if inspect.isgeneratorfunction(obj):
            # Wrap sync generator in async context manager for compatibility
            @asynccontextmanager
            async def async_sync_gen_cm():
                gen = obj(**kwargs)
                try:
                    yield next(gen)
                finally:
                    # Cleanup - exhaust the generator
                    with suppress(StopIteration):
                        next(gen)

            if self._cleanup_stack:
                # Enter async-wrapped sync context manager into async stack
                return await self._cleanup_stack.enter_async_context(async_sync_gen_cm())
            # No cleanup stack - use directly within context
            async with async_sync_gen_cm() as value:
                return value

        # Normal execution path
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
            async def func(embedding: EmbeddingProvider = INJECTED) -> None: ...

        Instead of requiring:
            async def func(embedding:  Annotated[EmbeddingProvider, Depends()] = INJECTED) -> None: ...
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
        _resolution_stack: list[str] | None = None,
    ) -> Any:
        """Resolve a dependency from a Depends marker with scope support.

        Args:
            name: Parameter name.
            param: Parameter object.
            marker: The Depends marker.
            annotation: Raw annotation.
            globalns: Global namespace.
            _resolution_stack: Internal parameter for circular dependency tracking.

        Returns:
            The resolved dependency value.
        """
        # Extract tags from marker
        tags = getattr(marker, "tags", None)
        tag_set = frozenset(tags) if tags else None

        # Get target type for caching
        target_type = annotation or param.annotation
        if isinstance(target_type, str):
            resolved = self._resolve_string_type(target_type, globalns)
            if resolved is not None:
                target_type = resolved
        target_type = self._unwrap_annotated(target_type)

        if target_type is inspect.Parameter.empty and not marker.dependency:  # ty:ignore[unresolved-attribute]
            raise ValueError(f"Parameter {name} has Depends() but no type hint.")

        # Use marker.dependency if provided, otherwise use target_type
        dependency_target = marker.dependency or target_type  # ty:ignore[unresolved-attribute]
        
        # Determine scope - use marker's scope if specified, otherwise look up from registration
        if marker.scope:  # ty:ignore[unresolved-attribute]
            scope = marker.scope  # ty:ignore[unresolved-attribute]
        else:
            # Fall back to registered scope, checking both dependency_target and target_type
            # Use the dependency_target first (what we're actually resolving), then fall back to target_type
            scope = self._scope.get(dependency_target, self._scope.get(target_type, "singleton" if marker.use_cache else "function"))  # ty:ignore[unresolved-attribute]

        # Create cache key for request/function scopes
        # Include tags in cache key to differentiate tagged dependencies
        cache_key = (dependency_target, tag_set) if tag_set else dependency_target

        # Function scope - always create new instance
        if scope == "function" or not marker.use_cache:  # ty:ignore[unresolved-attribute]
            # Bypass all caching - always create new instance
            if marker.dependency:  # ty:ignore[unresolved-attribute]
                return await self._call_with_injection(marker.dependency, _resolution_stack)  # ty:ignore[unresolved-attribute]
            # Resolve from annotation without caching
            factory = self._get_factory(target_type, tag_set)
            return await self._call_with_injection(factory, _resolution_stack)

        # Request scope - check request cache
        if scope == "request":
            if cache_key in self._request_cache:
                return self._request_cache[cache_key]

            # Create and cache in request scope
            if marker.dependency:  # ty:ignore[unresolved-attribute]
                instance = await self.resolve(marker.dependency, _resolution_stack, tags=tag_set)  # ty:ignore[unresolved-attribute]
            else:
                instance = await self.resolve(target_type, _resolution_stack, tags=tag_set)

            self._request_cache[cache_key] = instance
            return instance

        # Singleton scope - use normal container resolution (default behavior)
        if marker.dependency:  # ty:ignore[unresolved-attribute]
            # Resolve via container to support registration, singletons, and overrides
            return await self.resolve(marker.dependency, _resolution_stack, tags=tag_set)  # ty:ignore[unresolved-attribute]

        return await self.resolve(target_type, _resolution_stack, tags=tag_set)

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[Container]:
        """Context manager for container lifecycle with cleanup support.

        Usage:
            async with container.lifespan():
                # Container ready with cleanup tracking
                instance = await container.resolve(SomeType)
            # All generators cleaned up
        """
        async with AsyncExitStack() as stack:
            self._cleanup_stack = stack
            try:
                # Run startup hooks
                for hook in self._startup_hooks:
                    if asyncio.iscoroutinefunction(hook):
                        await hook()
                    else:
                        hook()

                yield self
            finally:
                # Run shutdown hooks
                for hook in self._shutdown_hooks:
                    if asyncio.iscoroutinefunction(hook):
                        await hook()
                    else:
                        hook()

                self._cleanup_stack = None

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
    """Get or create the global default container.

    On first call, this will:
    1. Create a new Container instance
    2. Load providers from dependency_provider decorator registry (lazy, on first resolve)

    Returns:
        The global container instance.
    """
    global _default_container
    if _default_container is None:
        _default_container = Container()
    return _default_container


def reset_container() -> None:
    """Reset the global default container."""
    global _default_container
    if _default_container:
        _default_container.clear()
    _default_container = None


__all__ = ("Container", "ResolutionResult", "get_container", "reset_container")
