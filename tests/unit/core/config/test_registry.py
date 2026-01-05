"""Tests for configurable component registry."""

import pytest

from codeweaver.core.config.registry import (
    clear_configurables,
    get_configurable_components,
    register_configurable,
)


class MockConfigurable:
    """Mock configurable for testing."""

    def config_dependencies(self) -> dict[str, type]:
        return {}

    async def apply_resolved_config(self, **resolved) -> None:
        pass


@pytest.fixture(autouse=True)
def _cleanup():
    """Clean up registry after each test."""
    yield
    clear_configurables()


def test_register_configurable():
    """Test registering a configurable component."""
    mock = MockConfigurable()
    register_configurable(mock)

    components = get_configurable_components()
    assert len(components) == 1
    assert mock in components


def test_register_configurable_duplicate():
    """Test that duplicate registration is prevented."""
    mock = MockConfigurable()
    register_configurable(mock)
    register_configurable(mock)  # Register again

    components = get_configurable_components()
    assert len(components) == 1  # Should only be registered once


def test_get_configurable_components_returns_copy():
    """Test that get_configurable_components returns a copy."""
    mock = MockConfigurable()
    register_configurable(mock)

    components1 = get_configurable_components()
    components2 = get_configurable_components()

    # Should be equal but not the same object
    assert components1 == components2
    assert components1 is not components2


def test_clear_configurables():
    """Test clearing the registry."""
    mock1 = MockConfigurable()
    mock2 = MockConfigurable()

    register_configurable(mock1)
    register_configurable(mock2)

    assert len(get_configurable_components()) == 2

    clear_configurables()

    assert len(get_configurable_components()) == 0


def test_multiple_configurables():
    """Test registering multiple different configurables."""
    mock1 = MockConfigurable()
    mock2 = MockConfigurable()
    mock3 = MockConfigurable()

    register_configurable(mock1)
    register_configurable(mock2)
    register_configurable(mock3)

    components = get_configurable_components()
    assert len(components) == 3
    assert mock1 in components
    assert mock2 in components
    assert mock3 in components
