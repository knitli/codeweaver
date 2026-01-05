"""Tests for config resolution system."""

import pytest

from codeweaver.core.config.registry import clear_configurables, register_configurable
from codeweaver.core.config.resolver import resolve_all_configs
from codeweaver.core.di import get_container


class MockConfigurable:
    """Mock configurable component for testing."""

    def __init__(self) -> None:
        self.resolved_values = {}
        self.dependencies_called = False
        self.apply_called = False

    def config_dependencies(self) -> dict[str, type]:
        """Return empty dependencies for testing."""
        self.dependencies_called = True
        return {}

    async def apply_resolved_config(self, **resolved) -> None:
        """Track that apply was called."""
        self.apply_called = True
        self.resolved_values = resolved


class MockDependentConfigurable:
    """Mock configurable that depends on another."""

    def __init__(self) -> None:
        self.resolved_values = {}

    def config_dependencies(self) -> dict[str, type]:
        """Return dependencies."""
        return {"mock": MockConfigurable}

    async def apply_resolved_config(self, **resolved) -> None:
        """Store resolved values."""
        self.resolved_values = resolved


@pytest.fixture(autouse=True)
def _cleanup():
    """Clean up after each test."""
    yield
    clear_configurables()
    get_container().clear()


def test_configurable_component_protocol():
    """Test that ConfigurableComponent protocol works."""
    mock = MockConfigurable()

    # Should have the required methods
    assert hasattr(mock, "config_dependencies")
    assert hasattr(mock, "apply_resolved_config")

    # Should be callable
    assert callable(mock.config_dependencies)
    assert callable(mock.apply_resolved_config)


@pytest.mark.asyncio
async def test_resolve_all_configs_empty():
    """Test resolve_all_configs with no configurables."""
    # Should not raise an error
    await resolve_all_configs()


@pytest.mark.asyncio
async def test_resolve_all_configs_no_dependencies():
    """Test resolve_all_configs with configurable that has no dependencies."""
    mock = MockConfigurable()
    register_configurable(mock)

    await resolve_all_configs()

    # Should have called config_dependencies but not apply (no resolved values)
    assert mock.dependencies_called
    assert not mock.apply_called


@pytest.mark.asyncio
async def test_resolve_all_configs_with_dependencies():
    """Test resolve_all_configs with actual dependencies."""
    # Create and register provider
    provider = MockConfigurable()
    container = get_container()
    container.register(MockConfigurable, lambda: provider, singleton=True)

    # Create dependent configurable
    dependent = MockDependentConfigurable()
    register_configurable(dependent)

    await resolve_all_configs()

    # Should have resolved the dependency
    assert "mock" in dependent.resolved_values
    assert dependent.resolved_values["mock"] is provider


@pytest.mark.asyncio
async def test_resolve_all_configs_missing_dependency():
    """Test resolve_all_configs when dependency is not available."""
    # Create dependent without registering the dependency
    dependent = MockDependentConfigurable()
    register_configurable(dependent)

    # Should not raise - should gracefully skip missing dependencies
    await resolve_all_configs()

    # Should have empty resolved values (dependency not available)
    assert dependent.resolved_values == {}


@pytest.mark.asyncio
async def test_resolve_all_configs_multiple_configurables():
    """Test resolve_all_configs with multiple configurables."""
    mock1 = MockConfigurable()
    mock2 = MockConfigurable()

    register_configurable(mock1)
    register_configurable(mock2)

    await resolve_all_configs()

    # Both should have been processed
    assert mock1.dependencies_called
    assert mock2.dependencies_called
