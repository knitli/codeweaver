# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Comprehensive tests for @dependency_provider decorator functionality.

Tests the decorator's core functionality including:
- Function registration with explicit types
- Class self-registration patterns
- Scope handling (singleton, request, function)
- Generator detection (sync and async)
- Metadata storage and retrieval
- Thread safety
- Error cases
"""

from __future__ import annotations

import asyncio
import threading

from collections.abc import AsyncIterator, Iterator

import pytest

from codeweaver.core import (
    ProviderMetadata,
    dependency_provider,
    get_all_provider_metadata,
    get_all_providers,
    get_provider,
    get_provider_metadata,
    is_provider_registered,
)


# Test fixtures
class ServiceA:
    """Simple service for testing."""

    def __init__(self, value: int = 1) -> None:
        self.value = value


class ServiceB:
    """Another service for testing."""

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
# Function Registration Tests
# ==============================================================================


def test_provider_function_registration_explicit_type(clean_registry):
    """Test @dependency_provider decorator with function and explicit type."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_service() -> ServiceA:
        return ServiceA(value=42)

    # Verify registration
    assert is_provider_registered(ServiceA)
    factory = get_provider(ServiceA)
    assert factory == create_service

    # Verify metadata
    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "singleton"
    assert not metadata.is_generator
    assert not metadata.is_async_generator


def test_provider_async_function_registration(clean_registry):
    """Test @dependency_provider decorator with async function."""

    @dependency_provider(ServiceA, scope="request")
    async def create_service_async() -> ServiceA:
        await asyncio.sleep(0)  # Simulate async work
        return ServiceA(value=100)

    # Verify registration
    assert is_provider_registered(ServiceA)
    factory = get_provider(ServiceA)
    assert factory == create_service_async

    # Verify metadata
    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "request"
    assert not metadata.is_generator
    assert not metadata.is_async_generator


def test_provider_function_with_module_metadata(clean_registry):
    """Test @dependency_provider decorator with module metadata."""

    @dependency_provider(ServiceA, scope="function", module="test.module")
    def create_service() -> ServiceA:
        return ServiceA()

    # Verify metadata includes module
    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.module == "test.module"
    assert metadata.scope == "function"


# ==============================================================================
# Class Self-Registration Tests
# ==============================================================================


def test_provider_class_self_registration_no_type_arg(clean_registry):
    """Test @dependency_provider decorator on class without explicit type argument."""

    @dependency_provider(scope="singleton")
    class AutoService:
        def __init__(self) -> None:
            self.auto = True

    # Verify registration
    assert is_provider_registered(AutoService)
    factory = get_provider(AutoService)
    assert factory == AutoService

    # Verify metadata
    metadata = get_provider_metadata(AutoService)
    assert metadata is not None
    assert metadata.scope == "singleton"


def test_provider_class_self_registration_with_type_arg(clean_registry):
    """Test @dependency_provider decorator on class with explicit type argument."""

    @dependency_provider(ServiceA, scope="request")
    class ServiceAImpl:
        """Implementation of ServiceA interface."""

        def __init__(self) -> None:
            self.value = 999

    # Verify registration maps interface to implementation
    assert is_provider_registered(ServiceA)
    factory = get_provider(ServiceA)
    assert factory == ServiceAImpl

    # Verify metadata
    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "request"


def test_provider_class_with_dependencies(clean_registry):
    """Test @dependency_provider decorator on class that has dependencies."""

    @dependency_provider(scope="singleton")
    class ComplexService:
        def __init__(self, value: int = 42, name: str = "test") -> None:
            self.value = value
            self.name = name

    # Verify registration
    assert is_provider_registered(ComplexService)
    metadata = get_provider_metadata(ComplexService)
    assert metadata is not None
    assert metadata.scope == "singleton"


# ==============================================================================
# Scope Tests
# ==============================================================================


def test_provider_singleton_scope(clean_registry):
    """Test provider with singleton scope."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_singleton() -> ServiceA:
        return ServiceA()

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "singleton"


def test_provider_request_scope(clean_registry):
    """Test provider with request scope."""

    @dependency_provider(ServiceB, scope="request")
    def create_request_scoped() -> ServiceB:
        return ServiceB()

    metadata = get_provider_metadata(ServiceB)
    assert metadata is not None
    assert metadata.scope == "request"


def test_provider_function_scope(clean_registry):
    """Test provider with function scope."""

    @dependency_provider(ServiceA, scope="function")
    def create_function_scoped() -> ServiceA:
        return ServiceA()

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "function"


def test_provider_default_scope_is_singleton(clean_registry):
    """Test that default scope is singleton when not specified."""

    @dependency_provider(ServiceA)
    def create_default() -> ServiceA:
        return ServiceA()

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "singleton"


# ==============================================================================
# Generator Detection Tests
# ==============================================================================


def test_provider_sync_generator_detection(clean_registry):
    """Test detection of synchronous generator functions."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_with_cleanup() -> Iterator[ServiceA]:
        service = ServiceA()
        yield service
        # Cleanup code would go here

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.is_generator
    assert not metadata.is_async_generator


def test_provider_async_generator_detection(clean_registry):
    """Test detection of asynchronous generator functions."""

    @dependency_provider(ServiceB, scope="singleton")
    async def create_with_async_cleanup() -> AsyncIterator[ServiceB]:
        service = ServiceB()
        yield service
        # Async cleanup code would go here
        await asyncio.sleep(0)

    metadata = get_provider_metadata(ServiceB)
    assert metadata is not None
    assert metadata.is_async_generator
    assert not metadata.is_generator


def test_provider_regular_function_not_generator(clean_registry):
    """Test that regular functions are not marked as generators."""

    @dependency_provider(ServiceA, scope="function")
    def create_regular() -> ServiceA:
        return ServiceA()

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert not metadata.is_generator
    assert not metadata.is_async_generator


# ==============================================================================
# Metadata Storage and Retrieval Tests
# ==============================================================================


def test_get_provider_metadata_returns_correct_data(clean_registry):
    """Test that get_provider_metadata returns complete and correct data."""

    @dependency_provider(ServiceA, scope="request", module="my.module")
    async def create() -> AsyncIterator[ServiceA]:
        yield ServiceA()

    metadata = get_provider_metadata(ServiceA)
    assert isinstance(metadata, ProviderMetadata)
    assert metadata.scope == "request"
    assert metadata.module == "my.module"
    assert metadata.is_async_generator
    assert not metadata.is_generator


def test_get_provider_metadata_returns_none_for_unregistered(clean_registry):
    """Test that get_provider_metadata returns None for unregistered types."""

    class UnregisteredService:
        pass

    metadata = get_provider_metadata(UnregisteredService)
    assert metadata is None


def test_get_all_provider_metadata_returns_all(clean_registry):
    """Test that get_all_provider_metadata returns all registered metadata."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_a() -> ServiceA:
        return ServiceA()

    @dependency_provider(ServiceB, scope="request")
    def create_b() -> ServiceB:
        return ServiceB()

    all_metadata = get_all_provider_metadata()
    assert len(all_metadata) == 2
    assert ServiceA in all_metadata
    assert ServiceB in all_metadata
    # New API: metadata[Type] = [ProviderMetadata] list
    assert len(all_metadata[ServiceA]) == 1
    assert all_metadata[ServiceA][0].scope == "singleton"
    assert len(all_metadata[ServiceB]) == 1
    assert all_metadata[ServiceB][0].scope == "request"


# ==============================================================================
# Thread Safety Tests
# ==============================================================================


def test_provider_registration_is_thread_safe(clean_registry):
    """Test that concurrent provider registration is thread-safe."""
    results: list[bool] = []
    errors: list[Exception] = []

    def register_provider(service_type: type, value: int):
        try:

            @dependency_provider(service_type, scope="singleton")
            def create() -> type:
                return service_type(value=value)

            results.append(True)
        except Exception as e:
            errors.append(e)

    # Create unique service types for each thread
    service_types = [type(f"Service{i}", (ServiceA,), {}) for i in range(10)]

    # Start multiple threads registering different providers
    threads = [
        threading.Thread(target=register_provider, args=(stype, i))
        for i, stype in enumerate(service_types)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # All threads should complete successfully
    assert len(results) == 10
    assert len(errors) == 0

    # All providers should be registered
    for stype in service_types:
        assert is_provider_registered(stype)


def test_provider_metadata_retrieval_is_thread_safe(clean_registry):
    """Test that concurrent metadata retrieval is thread-safe."""

    @dependency_provider(ServiceA, scope="singleton")
    def create() -> ServiceA:
        return ServiceA()

    results: list[ProviderMetadata | None] = []
    errors: list[Exception] = []

    def get_metadata():
        try:
            metadata = get_provider_metadata(ServiceA)
            results.append(metadata)
        except Exception as e:
            errors.append(e)

    # Start multiple threads reading metadata
    threads = [threading.Thread(target=get_metadata) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # All threads should succeed
    assert len(results) == 20
    assert len(errors) == 0
    assert all(m is not None and m.scope == "singleton" for m in results)


# ==============================================================================
# Error Cases and Edge Cases
# ==============================================================================


def test_get_provider_raises_for_unregistered_type(clean_registry):
    """Test that get_provider raises KeyError for unregistered types."""

    class UnregisteredService:
        pass

    with pytest.raises(KeyError, match="No provider registered"):
        get_provider(UnregisteredService)


def test_is_provider_registered_returns_false_for_unregistered(clean_registry):
    """Test that is_provider_registered returns False for unregistered types."""

    class UnregisteredService:
        pass

    assert not is_provider_registered(UnregisteredService)


def test_provider_overwrites_existing_registration(clean_registry):
    """Test that registering a provider twice overwrites the first."""

    @dependency_provider(ServiceA, scope="singleton")
    def first_factory() -> ServiceA:
        return ServiceA(value=1)

    @dependency_provider(ServiceA, scope="request")
    def second_factory() -> ServiceA:
        return ServiceA(value=2)

    # Second registration should overwrite
    factory = get_provider(ServiceA)
    assert factory == second_factory

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "request"


def test_provider_with_none_module_metadata(clean_registry):
    """Test provider with None module (default)."""

    @dependency_provider(ServiceA)
    def create() -> ServiceA:
        return ServiceA()

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.module is None


# ==============================================================================
# Multiple Provider Tests
# ==============================================================================


def test_multiple_providers_different_types(clean_registry):
    """Test registering multiple providers for different types."""

    @dependency_provider(ServiceA, scope="singleton")
    def create_a() -> ServiceA:
        return ServiceA()

    @dependency_provider(ServiceB, scope="request")
    def create_b() -> ServiceB:
        return ServiceB()

    # Both should be registered
    assert is_provider_registered(ServiceA)
    assert is_provider_registered(ServiceB)

    # Each should have its own factory
    factory_a = get_provider(ServiceA)
    factory_b = get_provider(ServiceB)
    assert factory_a != factory_b

    # Each should have its own metadata
    metadata_a = get_provider_metadata(ServiceA)
    metadata_b = get_provider_metadata(ServiceB)
    assert metadata_a is not None
    assert metadata_b is not None
    assert metadata_a.scope == "singleton"
    assert metadata_b.scope == "request"


def test_get_all_providers_returns_dict(clean_registry):
    """Test that get_all_providers returns a dictionary."""

    @dependency_provider(ServiceA)
    def create_a() -> ServiceA:
        return ServiceA()

    @dependency_provider(ServiceB)
    def create_b() -> ServiceB:
        return ServiceB()

    all_providers = get_all_providers()
    assert isinstance(all_providers, dict)
    assert len(all_providers) == 2
    assert ServiceA in all_providers
    assert ServiceB in all_providers


def test_get_all_providers_returns_copy(clean_registry):
    """Test that get_all_providers returns a copy (not direct reference)."""

    @dependency_provider(ServiceA)
    def create() -> ServiceA:
        return ServiceA()

    providers1 = get_all_providers()
    providers2 = get_all_providers()

    # Should be equal but not the same object
    assert providers1 == providers2
    assert providers1 is not providers2

    # Modifying one shouldn't affect the other
    providers1[ServiceB] = lambda: ServiceB()
    assert ServiceB not in providers2


# ==============================================================================
# Decorator Return Type Tests
# ==============================================================================


def test_provider_decorator_returns_original_function(clean_registry):
    """Test that @dependency_provider returns the original function unchanged."""

    def original_func() -> ServiceA:
        return ServiceA()

    decorated = dependency_provider(ServiceA)(original_func)

    # Should return the same function object
    assert decorated is original_func


def test_provider_decorator_returns_original_class(clean_registry):
    """Test that @dependency_provider returns the original class unchanged."""

    class OriginalClass:
        pass

    # Class self-registration
    decorated = dependency_provider(scope="singleton")(OriginalClass)

    # Should return the same class object
    assert decorated is OriginalClass


# ==============================================================================
# Complex Scenarios
# ==============================================================================


def test_provider_with_complex_return_type(clean_registry):
    """Test provider with complex return types (generators, etc.)."""

    @dependency_provider(ServiceA, scope="singleton")
    async def complex_provider() -> AsyncIterator[ServiceA]:
        # Setup
        service = ServiceA(value=100)
        try:
            yield service
        finally:
            # Cleanup
            pass

    assert is_provider_registered(ServiceA)
    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.is_async_generator


def test_provider_registration_order_independence(clean_registry):
    """Test that registration order doesn't affect retrieval."""

    @dependency_provider(ServiceB, scope="request")
    def create_b() -> ServiceB:
        return ServiceB()

    @dependency_provider(ServiceA, scope="singleton")
    def create_a() -> ServiceA:
        return ServiceA()

    # Both should be retrievable regardless of registration order
    assert get_provider(ServiceA) == create_a
    assert get_provider(ServiceB) == create_b
