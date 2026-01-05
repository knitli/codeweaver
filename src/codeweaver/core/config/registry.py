"""Registry for configurable components."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.core.config.resolver import ConfigurableComponent


_configurable_components: list[ConfigurableComponent] = []


def register_configurable(component: ConfigurableComponent) -> None:
    """Register a component for config resolution.

    Args:
        component: Component implementing ConfigurableComponent protocol.
    """
    if component not in _configurable_components:
        _configurable_components.append(component)


def get_configurable_components() -> list[ConfigurableComponent]:
    """Get all registered configurable components.

    Returns:
        Copy of the registered components list.
    """
    return _configurable_components.copy()


def clear_configurables() -> None:
    """Clear all registered components.

    Primarily for testing - ensures clean state between tests.
    """
    _configurable_components.clear()


__all__ = ("clear_configurables", "get_configurable_components", "register_configurable")
