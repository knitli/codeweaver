# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for provider registry API functions.

Tests all public API functions from codeweaver.core:
- dependency_provider() decorator
- get_provider()
- get_provider_metadata()
- is_provider_registered()
- get_all_providers()
- get_all_provider_metadata()

The DI system uses @dependency_provider to register factories,
and the Container automatically loads and resolves them.
"""

from __future__ import annotations

import pytest

from codeweaver.core import (
    dependency_provider,
    get_all_provider_metadata,
    get_all_providers,
    get_provider,
    get_provider_metadata,
    is_provider_registered,
)


# Test fixtures
class ServiceA:
    """Simple test service."""

    def __init__(self, value: int = 42) -> None:
        self.value = value


class ServiceB:
    """Another test service."""

    def __init__(self, name: str = "test") -> None:
        self.name = name


class ServiceC:
    """Third test service."""


@pytest.fixture
def clean_registry():
    """Clean the provider registry before and after each test."""
    from codeweaver.core.di import utils

    # Store original state - deep copy to preserve the list structure
    original_providers = {k: v.copy() for k, v in utils._providers.items()}

    yield

    # Restore original state
    utils._providers.clear()
    utils._providers.update(original_providers)


# ==============================================================================
# get_provider() Tests
# ==============================================================================


def test_get_provider_returns_registered_factory(clean_registry):
    """Test that get_provider returns the registered factory function."""

    @dependency_provider(ServiceA)
    def create_service() -> ServiceA:
        return ServiceA(value=100)

    factory = get_provider(ServiceA)
    assert factory == create_service


def test_get_provider_returns_registered_class(clean_registry):
    """Test that get_provider returns registered class for self-registration."""

    @dependency_provider(scope="singleton")
    class SelfRegisteredService:
        pass

    factory = get_provider(SelfRegisteredService)
    assert factory == SelfRegisteredService


def test_get_provider_raises_key_error_for_unregistered(clean_registry):
    """Test that get_provider raises KeyError for unregistered types."""

    class UnregisteredService:
        pass

    with pytest.raises(KeyError, match="No provider registered for type"):
        get_provider(UnregisteredService)


def test_get_provider_with_multiple_registrations(clean_registry):
    """Test get_provider with multiple registered providers."""

    @dependency_provider(ServiceA)
    def create_a() -> ServiceA:
        return ServiceA()

    @dependency_provider(ServiceB)
    def create_b() -> ServiceB:
        return ServiceB()

    # Each should return its own factory
    assert get_provider(ServiceA) == create_a
    assert get_provider(ServiceB) == create_b


# ==============================================================================
# get_provider_metadata() Tests
# ==============================================================================


def test_get_provider_metadata_returns_metadata(clean_registry):
    """Test that get_provider_metadata returns correct metadata."""

    @dependency_provider(ServiceA, scope="request", module="test.module")
    def create_service() -> ServiceA:
        return ServiceA()

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "request"
    assert metadata.module == "test.module"
    assert not metadata.is_generator
    assert not metadata.is_async_generator


def test_get_provider_metadata_returns_none_for_unregistered(clean_registry):
    """Test that get_provider_metadata returns None for unregistered types."""

    class UnregisteredService:
        pass

    metadata = get_provider_metadata(UnregisteredService)
    assert metadata is None


def test_get_provider_metadata_with_generator(clean_registry):
    """Test get_provider_metadata correctly identifies generators."""
    from collections.abc import Iterator

    @dependency_provider(ServiceA)
    def create_with_cleanup() -> Iterator[ServiceA]:
        service = ServiceA()
        yield service
        # cleanup

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.is_generator
    assert not metadata.is_async_generator


def test_get_provider_metadata_with_async_generator(clean_registry):
    """Test get_provider_metadata correctly identifies async generators."""
    from collections.abc import AsyncIterator

    @dependency_provider(ServiceA)
    async def create_with_async_cleanup() -> AsyncIterator[ServiceA]:
        service = ServiceA()
        yield service
        # async cleanup

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.is_async_generator
    assert not metadata.is_generator


# ==============================================================================
# is_provider_registered() Tests
# ==============================================================================


def test_is_provider_registered_returns_true_for_registered(clean_registry):
    """Test that is_provider_registered returns True for registered types."""

    @dependency_provider(ServiceA)
    def create() -> ServiceA:
        return ServiceA()

    assert is_provider_registered(ServiceA)


def test_is_provider_registered_returns_false_for_unregistered(clean_registry):
    """Test that is_provider_registered returns False for unregistered types."""

    class UnregisteredService:
        pass

    assert not is_provider_registered(UnregisteredService)


def test_is_provider_registered_after_multiple_registrations(clean_registry):
    """Test is_provider_registered with multiple providers."""

    @dependency_provider(ServiceA)
    def create_a() -> ServiceA:
        return ServiceA()

    @dependency_provider(ServiceB)
    def create_b() -> ServiceB:
        return ServiceB()

    assert is_provider_registered(ServiceA)
    assert is_provider_registered(ServiceB)
    assert not is_provider_registered(ServiceC)


# ==============================================================================
# get_all_providers() Tests
# ==============================================================================


def test_get_all_providers_returns_empty_dict_when_empty(clean_registry):
    """Test that get_all_providers returns empty dict when no providers."""
    providers = get_all_providers()
    assert isinstance(providers, dict)
    assert len(providers) == 0


def test_get_all_providers_returns_all_registered(clean_registry):
    """Test that get_all_providers returns all registered providers."""

    @dependency_provider(ServiceA)
    def create_a() -> ServiceA:
        return ServiceA()

    @dependency_provider(ServiceB)
    def create_b() -> ServiceB:
        return ServiceB()

    providers = get_all_providers()
    assert len(providers) == 2
    assert ServiceA in providers
    assert ServiceB in providers
    assert providers[ServiceA] == create_a
    assert providers[ServiceB] == create_b


def test_get_all_providers_returns_copy_not_reference(clean_registry):
    """Test that get_all_providers returns a copy of the registry."""

    @dependency_provider(ServiceA)
    def create() -> ServiceA:
        return ServiceA()

    providers1 = get_all_providers()
    providers2 = get_all_providers()

    # Should be equal but different objects
    assert providers1 == providers2
    assert providers1 is not providers2

    # Modifying returned dict shouldn't affect registry
    providers1[ServiceB] = lambda: ServiceB()
    assert ServiceB not in get_all_providers()


def test_get_all_providers_with_overwritten_registration(clean_registry):
    """Test get_all_providers when a provider is overwritten."""

    @dependency_provider(ServiceA)
    def first_factory() -> ServiceA:
        return ServiceA(value=1)

    @dependency_provider(ServiceA)
    def second_factory() -> ServiceA:
        return ServiceA(value=2)

    providers = get_all_providers()
    # Should have the latest registration only
    assert len(providers) == 1
    assert providers[ServiceA] == second_factory


# ==============================================================================
# get_all_provider_metadata() Tests
# ==============================================================================


def test_get_all_provider_metadata_returns_empty_dict_when_empty(clean_registry):
    """Test that get_all_provider_metadata returns empty dict when no providers."""
    metadata = get_all_provider_metadata()
    assert isinstance(metadata, dict)
    assert len(metadata) == 0


def test_get_all_provider_metadata_returns_all_metadata(clean_registry):
    """Test that get_all_provider_metadata returns all metadata."""

    @dependency_provider(ServiceA, scope="singleton", module="module.a")
    def create_a() -> ServiceA:
        return ServiceA()

    @dependency_provider(ServiceB, scope="request", module="module.b")
    def create_b() -> ServiceB:
        return ServiceB()

    metadata = get_all_provider_metadata()
    assert len(metadata) == 2
    assert ServiceA in metadata
    assert ServiceB in metadata

    # Verify metadata content
    assert metadata[ServiceA].scope == "singleton"
    assert metadata[ServiceA].module == "module.a"
    assert metadata[ServiceB].scope == "request"
    assert metadata[ServiceB].module == "module.b"


def test_get_all_provider_metadata_returns_copy(clean_registry):
    """Test that get_all_provider_metadata returns a copy."""

    @dependency_provider(ServiceA)
    def create() -> ServiceA:
        return ServiceA()

    metadata1 = get_all_provider_metadata()
    metadata2 = get_all_provider_metadata()

    assert metadata1 == metadata2
    assert metadata1 is not metadata2


# ==============================================================================
# Container Resolution Tests (replaces create_provider_factory)
# ==============================================================================


@pytest.mark.asyncio
async def test_container_resolves_registered_provider(clean_registry):
    """Test that container can resolve a registered provider."""
    from codeweaver.core import Container

    @dependency_provider(ServiceA)
    def create() -> ServiceA:
        return ServiceA(value=100)

    container = Container()
    instance = await container.resolve(ServiceA)
    assert isinstance(instance, ServiceA)
    assert instance.value == 100


@pytest.mark.asyncio
async def test_container_resolves_self_registered_class(clean_registry):
    """Test that container resolves self-registered classes."""
    from codeweaver.core import Container

    @dependency_provider(scope="singleton")
    class SelfRegisteredService:
        def __init__(self):
            self.value = 42

    container = Container()
    instance = await container.resolve(SelfRegisteredService)
    assert isinstance(instance, SelfRegisteredService)
    assert instance.value == 42


@pytest.mark.asyncio
async def test_container_caches_singletons(clean_registry):
    """Test that singleton scope caches instances."""
    from codeweaver.core import Container

    call_count = 0

    @dependency_provider(ServiceA, scope="singleton")
    def create() -> ServiceA:
        nonlocal call_count
        call_count += 1
        return ServiceA(value=call_count)

    container = Container()
    instance1 = await container.resolve(ServiceA)
    instance2 = await container.resolve(ServiceA)

    # Should be the same instance
    assert instance1 is instance2
    assert call_count == 1  # Factory called only once


@pytest.mark.asyncio
async def test_container_respects_function_scope(clean_registry):
    """Test that function scope creates new instances each time."""
    from codeweaver.core import Container

    call_count = 0

    @dependency_provider(ServiceA, scope="function")
    def create() -> ServiceA:
        nonlocal call_count
        call_count += 1
        return ServiceA(value=call_count)

    container = Container()
    instance1 = await container.resolve(ServiceA)
    instance2 = await container.resolve(ServiceA)

    # Should be different instances
    assert instance1 is not instance2
    assert call_count == 2  # Factory called twice
    assert instance1.value == 1
    assert instance2.value == 2


@pytest.mark.asyncio
async def test_container_resolves_multiple_types(clean_registry):
    """Test container with multiple registered providers."""
    from codeweaver.core import Container

    @dependency_provider(ServiceA)
    def create_a() -> ServiceA:
        return ServiceA(value=1)

    @dependency_provider(ServiceB)
    def create_b() -> ServiceB:
        return ServiceB(name="test")

    container = Container()
    instance_a = await container.resolve(ServiceA)
    instance_b = await container.resolve(ServiceB)

    assert isinstance(instance_a, ServiceA)
    assert isinstance(instance_b, ServiceB)
    assert instance_a.value == 1
    assert instance_b.name == "test"


# ==============================================================================
# API Consistency Tests
# ==============================================================================


def test_api_functions_are_consistent(clean_registry):
    """Test that all API functions work consistently together."""

    @dependency_provider(ServiceA, scope="request", module="test")
    def create() -> ServiceA:
        return ServiceA()

    # is_provider_registered should return True
    assert is_provider_registered(ServiceA)

    # get_provider should return the factory
    factory = get_provider(ServiceA)
    assert factory == create

    # get_provider_metadata should return metadata
    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "request"

    # get_all_providers should include it
    all_providers = get_all_providers()
    assert ServiceA in all_providers
    assert all_providers[ServiceA] == create

    # get_all_provider_metadata should include it
    all_metadata = get_all_provider_metadata()
    assert ServiceA in all_metadata
    assert all_metadata[ServiceA] == metadata


def test_api_functions_handle_empty_registry(clean_registry):
    """Test that API functions handle empty registry correctly."""
    # get_all_providers should return empty dict
    assert get_all_providers() == {}

    # get_all_provider_metadata should return empty dict
    assert get_all_provider_metadata() == {}

    # is_provider_registered should return False
    assert not is_provider_registered(ServiceA)

    # get_provider_metadata should return None
    assert get_provider_metadata(ServiceA) is None

    # get_provider should raise
    with pytest.raises(KeyError):
        get_provider(ServiceA)


# ==============================================================================
# Error Handling Tests
# ==============================================================================


def test_get_provider_error_message_includes_type_name(clean_registry):
    """Test that get_provider error includes the type name."""

    class MyCustomService:
        pass

    with pytest.raises(KeyError, match="MyCustomService"):
        get_provider(MyCustomService)


def test_api_functions_with_none_type():
    """Test that API functions handle None type gracefully."""
    # These should raise or return sensible values, not crash

    # is_provider_registered with None
    assert not is_provider_registered(None)  # type: ignore

    # get_provider_metadata with None
    metadata = get_provider_metadata(None)  # type: ignore
    assert metadata is None


# ==============================================================================
# Integration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_full_workflow_register_and_retrieve(clean_registry):
    """Test complete workflow: register provider and use all API functions."""
    from codeweaver.core import Container

    # Step 1: Register provider
    @dependency_provider(ServiceA, scope="singleton", module="integration.test")
    def create_service() -> ServiceA:
        return ServiceA(value=999)

    # Step 2: Verify registration
    assert is_provider_registered(ServiceA)

    # Step 3: Get factory
    factory = get_provider(ServiceA)
    assert factory == create_service

    # Step 4: Get metadata
    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "singleton"
    assert metadata.module == "integration.test"

    # Step 5: Resolve via container
    container = Container()
    instance = await container.resolve(ServiceA)
    assert isinstance(instance, ServiceA)
    assert instance.value == 999

    # Step 6: Verify in bulk retrieval
    all_providers = get_all_providers()
    assert ServiceA in all_providers

    all_metadata = get_all_provider_metadata()
    assert ServiceA in all_metadata


def test_api_functions_after_provider_overwrite(clean_registry):
    """Test API functions after overwriting a provider."""

    @dependency_provider(ServiceA, scope="singleton")
    def first_factory() -> ServiceA:
        return ServiceA(value=1)

    # Overwrite
    @dependency_provider(ServiceA, scope="request")
    def second_factory() -> ServiceA:
        return ServiceA(value=2)

    # All API functions should reflect the latest registration
    assert is_provider_registered(ServiceA)
    assert get_provider(ServiceA) == second_factory

    metadata = get_provider_metadata(ServiceA)
    assert metadata is not None
    assert metadata.scope == "request"

    all_providers = get_all_providers()
    assert all_providers[ServiceA] == second_factory
