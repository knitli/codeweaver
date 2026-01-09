# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Test provider auto-discovery integration with Container.

Tests that the @provider decorator integrates with Container to automatically
register providers without manual registration calls.
"""

from __future__ import annotations

import pytest

from codeweaver.core import Container, get_all_providers, provider


# Test fixtures
class SimpleService:
    """A simple service for testing."""

    def __init__(self) -> None:
        self.value = 42


class DependentService:
    """A service that depends on SimpleService."""

    def __init__(self, simple: SimpleService) -> None:
        self.simple = simple


@pytest.fixture
def clean_registry():
    """Clean the provider registry before and after each test."""
    from codeweaver.core import utils

    # Store original state
    original_providers = utils._providers.copy()
    original_metadata = utils._provider_metadata.copy()

    yield

    # Restore original state
    utils._providers.clear()
    utils._providers.update(original_providers)
    utils._provider_metadata.clear()
    utils._provider_metadata.update(original_metadata)


def test_provider_decorator_registers_in_utils_registry(clean_registry):
    """Test that @provider decorator adds providers to utils registry."""

    @provider(SimpleService, scope="singleton")
    def create_simple() -> SimpleService:
        return SimpleService()

    # Verify provider is in the registry
    providers = get_all_providers()
    assert SimpleService in providers
    assert providers[SimpleService] == create_simple


async def test_container_loads_providers_on_first_resolve(clean_registry):
    """Test that Container loads providers from registry on first resolve."""

    @provider(SimpleService, scope="singleton")
    def create_simple() -> SimpleService:
        return SimpleService()

    container = Container()

    # Before first resolve, providers should not be loaded
    assert not container._providers_loaded

    # First resolve should load providers
    instance = await container.resolve(SimpleService)
    assert container._providers_loaded

    # Verify instance is correct
    assert isinstance(instance, SimpleService)
    assert instance.value == 42


async def test_provider_scope_respected_by_container(clean_registry):
    """Test that provider scope metadata is respected by Container."""

    call_count = 0

    @provider(SimpleService, scope="singleton")
    def create_simple() -> SimpleService:
        nonlocal call_count
        call_count += 1
        return SimpleService()

    container = Container()

    # Singleton should only be created once
    instance1 = await container.resolve(SimpleService)
    instance2 = await container.resolve(SimpleService)

    assert instance1 is instance2
    assert call_count == 1  # Only created once


def test_provider_metadata_stored_correctly(clean_registry):
    """Test that provider metadata is stored with correct attributes."""
    from codeweaver.core import get_provider_metadata

    @provider(SimpleService, scope="request", module="test_module")
    def create_simple() -> SimpleService:
        return SimpleService()

    metadata = get_provider_metadata(SimpleService)
    assert metadata is not None
    assert metadata.scope == "request"
    assert metadata.module == "test_module"
    assert not metadata.is_generator
    assert not metadata.is_async_generator


def test_provider_generator_detection(clean_registry):
    """Test that generator functions are detected in metadata."""
    from collections.abc import AsyncIterator

    from codeweaver.core import get_provider_metadata

    @provider(SimpleService, scope="singleton")
    async def create_simple() -> AsyncIterator[SimpleService]:
        service = SimpleService()
        yield service
        # Cleanup would happen here

    metadata = get_provider_metadata(SimpleService)
    assert metadata is not None
    assert metadata.is_async_generator
    assert not metadata.is_generator


def test_container_clear_resets_provider_loading_flag():
    """Test that Container.clear() resets the provider loading flag."""
    container = Container()

    # Trigger provider loading
    container._load_providers()
    assert container._providers_loaded

    # Clear should reset the flag
    container.clear()
    assert not container._providers_loaded


async def test_multiple_containers_each_load_providers(clean_registry):
    """Test that each Container instance loads providers independently."""

    @provider(SimpleService, scope="singleton")
    def create_simple() -> SimpleService:
        return SimpleService()

    container1 = Container()
    container2 = Container()

    # Both containers should load providers
    instance1 = await container1.resolve(SimpleService)
    instance2 = await container2.resolve(SimpleService)

    assert container1._providers_loaded
    assert container2._providers_loaded

    # Instances should be different (different container singletons)
    assert instance1 is not instance2


async def test_provider_without_explicit_type(clean_registry):
    """Test @provider decorator with class self-registration."""

    @provider(scope="singleton")
    class AutoService:
        def __init__(self) -> None:
            self.auto = True

    container = Container()
    instance = await container.resolve(AutoService)

    assert isinstance(instance, AutoService)
    assert instance.auto


def test_container_loads_providers_only_once():
    """Test that _load_providers is idempotent."""
    container = Container()

    # Load providers multiple times
    container._load_providers()
    container._load_providers()
    container._load_providers()

    # Should only load once
    assert container._providers_loaded


def test_provider_registration_is_thread_safe(clean_registry):
    """Test that provider registration handles concurrent access safely."""
    import threading

    results = []

    def register_provider():
        @provider(SimpleService, scope="singleton")
        def create_simple() -> SimpleService:
            return SimpleService()

        results.append(True)

    # Start multiple threads registering providers
    threads = [threading.Thread(target=register_provider) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # All threads should complete successfully
    assert len(results) == 10

    # Registry should have the provider (only one, not duplicates)
    providers = get_all_providers()
    assert SimpleService in providers
