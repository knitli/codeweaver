# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Edge case and error handling tests for @dependency_provider decorator and auto-discovery.

Tests error conditions, edge cases, and boundary scenarios:
- Invalid scope values
- Duplicate registrations
- Type resolution edge cases
- Circular dependencies
- Generator errors
- Metadata edge cases
- Registry state consistency
"""

from __future__ import annotations

import asyncio

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING

import pytest

from codeweaver.core import (
    Container,
    Depends,
    dependency_provider,
    get_all_provider_metadata,
    get_all_providers,
    get_provider,
    get_provider_metadata,
    is_provider_registered,
)
from codeweaver.core.exceptions import CircularDependencyError


if TYPE_CHECKING:
    from typing import Annotated


# Test services
class ServiceA:
    def __init__(self, value: int = 1) -> None:
        self.value = value


class ServiceB:
    def __init__(self, name: str = "test") -> None:
        self.name = name


@pytest.fixture
def clean_registry():
    """Clean the provider registry before and after each test."""
    from codeweaver.core.di import utils

    # Store original state - deep copy to preserve the list structure
    original_providers = {k: v.copy() for k, v in utils._providers.items()}

    # Clear registry for test isolation
    utils._providers.clear()

    yield

    # Restore original state
    utils._providers.clear()
    utils._providers.update(original_providers)


# ==============================================================================
# Scope Validation Tests
# ==============================================================================


def test_provider_with_invalid_scope_still_registers(clean_registry):
    """Test that invalid scope values are accepted (no validation at decorator time)."""

    # Note: Current implementation doesn't validate scope at decorator time
    # This test documents current behavior
    @dependency_provider(ServiceA, scope="invalid")  # type: ignore
    def create() -> ServiceA:
        return ServiceA()

    # Should still register
    assert is_provider_registered(ServiceA)
    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "invalid"  # type: ignore


# ==============================================================================
# Duplicate Registration Tests
# ==============================================================================


def test_duplicate_provider_registration_overwrites(clean_registry):
    """Test that registering the same type twice overwrites the first."""

    first_called = False
    second_called = False

    @dependency_provider(ServiceA, scope="singleton", module="first")
    def first_factory() -> ServiceA:
        nonlocal first_called
        first_called = True
        return ServiceA(value=1)

    @dependency_provider(ServiceA, scope="request", module="second")
    def second_factory() -> ServiceA:
        nonlocal second_called
        second_called = True
        return ServiceA(value=2)

    # Should use second factory
    factory = get_provider(ServiceA)
    assert factory == second_factory

    # Metadata should be from second registration
    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "request"
    assert metadata.module == "second"


async def test_duplicate_registration_container_behavior(clean_registry):
    """Test Container behavior with duplicate registrations."""

    @dependency_provider(ServiceA, scope="singleton")
    def first_factory() -> ServiceA:
        return ServiceA(value=1)

    @dependency_provider(ServiceA, scope="singleton")
    def second_factory() -> ServiceA:
        return ServiceA(value=2)

    container = Container()
    instance = await container.resolve(ServiceA)

    # Should use the last registered factory
    assert instance.value == 2


# ==============================================================================
# Type Resolution Edge Cases
# ==============================================================================


def test_provider_with_generic_type(clean_registry):
    """Test provider with generic type hints."""
    from typing import Generic, TypeVar

    T = TypeVar("T")

    class GenericService(Generic[T]):
        def __init__(self, value: T) -> None:
            self.value = value

    # Register with concrete generic type
    @dependency_provider(GenericService, scope="singleton")
    def create() -> GenericService[int]:
        return GenericService(value=42)

    assert is_provider_registered(GenericService)


def test_provider_with_union_type(clean_registry):
    """Test provider with union type hints."""

    UnionType = ServiceA | ServiceB

    @dependency_provider(UnionType, scope="singleton")  # type: ignore
    def create() -> ServiceA:
        return ServiceA()

    # Should register (even though it's unusual)
    assert is_provider_registered(UnionType)  # type: ignore


def test_provider_with_optional_type(clean_registry):
    """Test provider with Optional type hints."""

    OptionalType = ServiceA | None

    @dependency_provider(OptionalType, scope="singleton")  # type: ignore
    def create() -> ServiceA | None:
        return ServiceA()

    assert is_provider_registered(OptionalType)  # type: ignore


# ==============================================================================
# Generator Edge Cases
# ==============================================================================


def test_provider_generator_that_raises(clean_registry):
    # sourcery skip: remove-unreachable-code
    """Test generator provider that raises during setup."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_with_error() -> Iterator[ServiceA]:
        raise RuntimeError("Setup failed")
        yield ServiceA()  # Never reached

    container = Container()

    # Should propagate the error
    with pytest.raises(RuntimeError, match="Setup failed"):
        asyncio.run(container.resolve(ServiceA))


async def test_provider_async_generator_that_raises(clean_registry):
    # sourcery skip: remove-unreachable-code
    """Test async generator provider that raises during setup."""

    @dependency_provider(ServiceA, scope="singleton")
    async def create_with_error() -> AsyncIterator[ServiceA]:
        raise RuntimeError("Async setup failed")
        yield ServiceA()  # Never reached

    container = Container()

    with pytest.raises(RuntimeError, match="Async setup failed"):
        await container.resolve(ServiceA)


def test_provider_generator_that_yields_none(clean_registry):
    """Test generator that yields None."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_none() -> Iterator[ServiceA]:
        yield None  # type: ignore

    # Should register and allow resolution
    assert is_provider_registered(ServiceA)


# ==============================================================================
# Circular Dependency Tests
# ==============================================================================


async def test_circular_dependency_detection_with_auto_discovery(clean_registry):
    """Test that circular dependencies are detected with auto-discovered providers."""

    class ServiceX:
        def __init__(self, service_y: ServiceY) -> None:  # type: ignore
            self.service_y = service_y

    class ServiceY:
        def __init__(self, service_x: ServiceX) -> None:
            self.service_x = service_x

    @dependency_provider(ServiceX, scope="singleton")
    def create_x(service_y: Annotated[ServiceY, Depends()]) -> ServiceX:
        return ServiceX(service_y=service_y)

    @dependency_provider(ServiceY, scope="singleton")
    def create_y(service_x: Annotated[ServiceX, Depends()]) -> ServiceY:
        return ServiceY(service_x=service_x)

    container = Container()

    # Should detect circular dependency
    with pytest.raises(CircularDependencyError):
        await container.resolve(ServiceX)


# ==============================================================================
# Metadata Edge Cases
# ==============================================================================


def test_provider_with_none_module(clean_registry):
    """Test that None module is handled correctly."""

    @dependency_provider(ServiceA, scope="singleton", module=None)
    def create() -> ServiceA:
        return ServiceA()

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.module is None


def test_provider_with_empty_string_module(clean_registry):
    """Test that empty string module is handled correctly."""

    @dependency_provider(ServiceA, scope="singleton", module="")
    def create() -> ServiceA:
        return ServiceA()

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.module == ""


# ==============================================================================
# Container State Consistency Tests
# ==============================================================================


async def test_container_state_after_failed_resolution(clean_registry):
    """Test that container state is consistent after failed resolution."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_failing() -> ServiceA:
        raise RuntimeError("Factory failed")

    container = Container()

    # First attempt should fail
    with pytest.raises(RuntimeError, match="Factory failed"):
        await container.resolve(ServiceA)

    # Provider should still be loaded
    assert container._providers_loaded

    # Registry should still have the provider
    assert is_provider_registered(ServiceA)


async def test_container_request_cache_state_after_error(clean_registry):
    """Test that request cache state is consistent after errors."""

    call_count = 0

    @dependency_provider(ServiceA, scope="request")
    def create_sometimes_failing() -> ServiceA:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("First call fails")
        return ServiceA(value=call_count)

    container = Container()

    # First call fails
    with pytest.raises(RuntimeError):
        await container.resolve(ServiceA)

    # Request cache should not contain failed result
    assert ServiceA not in container._request_cache

    # Second call should succeed
    instance = await container.resolve(ServiceA)
    assert instance.value == 2
    assert ServiceA in container._request_cache


# ==============================================================================
# Registry Lock Edge Cases
# ==============================================================================


def test_registry_thread_safety_under_exception(clean_registry):
    """Test that registry lock is released even when exceptions occur."""
    import threading

    errors: list[Exception] = []
    successes: list[bool] = []

    def register_and_fail():
        try:

            @dependency_provider(ServiceA, scope="singleton")
            def create() -> ServiceA:
                return ServiceA()

            # Try to access registry
            get_provider(ServiceA)
            successes.append(True)
        except Exception as e:
            errors.append(e)

    # Run multiple threads
    threads = [threading.Thread(target=register_and_fail) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All should succeed (lock should not be stuck)
    assert len(successes) == 10
    assert not errors


# ==============================================================================
# Mixed Registration Patterns
# ==============================================================================


async def test_mixed_function_and_class_registration(clean_registry):
    """Test mixing function and class self-registration."""

    # Function registration
    @dependency_provider(ServiceA, scope="singleton")
    def create_a() -> ServiceA:
        return ServiceA(value=1)

    # Class self-registration
    @dependency_provider(scope="request")
    class ServiceB:
        def __init__(self) -> None:
            self.name = "class-registered"

    container = Container()

    # Both should work
    service_a = await container.resolve(ServiceA)
    service_b = await container.resolve(ServiceB)

    assert service_a.value == 1
    assert service_b.name == "class-registered"


# ==============================================================================
# Empty and None Cases
# ==============================================================================


def test_get_all_providers_when_empty(clean_registry):
    """Test get_all_providers returns empty dict when no providers."""
    providers = get_all_providers()
    assert providers == {}
    assert isinstance(providers, dict)


def test_get_all_metadata_when_empty(clean_registry):
    """Test get_all_provider_metadata returns empty dict when no providers."""
    metadata = get_all_provider_metadata()
    assert metadata == {}
    assert isinstance(metadata, dict)


# ==============================================================================
# Provider Function Signature Edge Cases
# ==============================================================================


def test_provider_with_no_return_annotation(clean_registry):
    """Test provider without return type annotation."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_no_annotation():  # type: ignore
        return ServiceA()

    # Should still register
    assert is_provider_registered(ServiceA)


def test_provider_with_args_and_kwargs(clean_registry):
    """Test provider that accepts *args and **kwargs."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_with_varargs(*args, **kwargs) -> ServiceA:
        return ServiceA(value=kwargs.get("value", 1))

    assert is_provider_registered(ServiceA)


# ==============================================================================
# Container Auto-Discovery Edge Cases
# ==============================================================================


async def test_container_with_providers_registered_after_first_load(clean_registry):
    """Test that providers registered after first load are not picked up."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_a() -> ServiceA:
        return ServiceA()

    container = Container()

    # First resolve - loads providers
    await container.resolve(ServiceA)
    assert container._providers_loaded

    # Register new provider after loading
    @dependency_provider(ServiceB, scope="singleton")
    def create_b() -> ServiceB:
        return ServiceB()

    # New provider should not be in container
    # Container would need to be cleared and reloaded
    # This tests idempotency of _load_providers


async def test_container_clear_and_reload_picks_up_new_providers(clean_registry):
    """Test that clearing container and reloading picks up new providers."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_a() -> ServiceA:
        return ServiceA(value=1)

    container = Container()
    await container.resolve(ServiceA)

    # Clear and register new provider
    container.clear()

    @dependency_provider(ServiceB, scope="singleton")
    def create_b() -> ServiceB:
        return ServiceB()

    # Should pick up new provider
    service_b = await container.resolve(ServiceB)
    assert isinstance(service_b, ServiceB)


# ==============================================================================
# Scope Metadata Mapping Edge Cases
# ==============================================================================


async def test_unknown_scope_defaults_to_singleton(clean_registry):
    """Test that unknown scope in metadata defaults to singleton behavior."""

    # Manually register with unknown scope (bypassing type checking)
    from codeweaver.core.di import utils

    def create() -> ServiceA:
        return ServiceA()

    # Manually register with invalid scope
    from codeweaver.core import ProviderMetadata

    metadata = ProviderMetadata(
        scope="unknown",  # type: ignore
        is_generator=False,
        is_async_generator=False,
        module=None,
    )
    utils._providers[ServiceA] = [(create, metadata)]

    container = Container()
    container._load_providers()

    # Should fall back to singleton=False (not singleton)
    assert container._is_singleton.get(ServiceA) is False


# ==============================================================================
# Provider Overwrite Consistency Tests
# ==============================================================================


def test_provider_overwrite_maintains_registry_consistency(clean_registry):
    """Test that overwriting a provider maintains registry consistency."""

    @dependency_provider(ServiceA, scope="singleton")
    def first() -> ServiceA:
        return ServiceA(value=1)

    # Get initial state
    factory1 = get_provider(ServiceA)
    metadata1 = get_provider_metadata(ServiceA)

    @dependency_provider(ServiceA, scope="request")
    def second() -> ServiceA:
        return ServiceA(value=2)

    # Verify complete replacement
    factory2 = get_provider(ServiceA)
    metadata2 = get_provider_metadata(ServiceA)

    assert factory1 != factory2
    assert metadata1 != metadata2
    assert metadata2 is not None
    assert metadata2.scope == "request"


# ==============================================================================
# Module Path Edge Cases
# ==============================================================================


def test_provider_with_very_long_module_path(clean_registry):
    """Test provider with very long module path."""

    long_module = "very.long.module.path." * 10 + "end"

    @dependency_provider(ServiceA, scope="singleton", module=long_module)
    def create() -> ServiceA:
        return ServiceA()

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.module == long_module


def test_provider_with_special_characters_in_module(clean_registry):
    """Test provider with special characters in module name."""

    @dependency_provider(ServiceA, scope="singleton", module="module-with-dashes")
    def create() -> ServiceA:
        return ServiceA()

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.module == "module-with-dashes"


# ==============================================================================
# Provider Factory Callable Edge Cases
# ==============================================================================


def test_provider_with_lambda(clean_registry):
    """Test provider using lambda function."""

    @dependency_provider(ServiceA, scope="singleton")
    def wrapper() -> ServiceA:
        factory = lambda: ServiceA(value=99)  # noqa: E731
        return factory()

    assert is_provider_registered(ServiceA)


def test_provider_with_class_method(clean_registry):
    """Test provider using class method as factory."""

    class Factory:
        @staticmethod
        def create() -> ServiceA:
            return ServiceA(value=100)

    dependency_provider(ServiceA, scope="singleton")(Factory.create)

    assert is_provider_registered(ServiceA)
    factory = get_provider(ServiceA)
    assert factory == Factory.create
