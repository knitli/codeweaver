# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Registry for configurable components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal


if TYPE_CHECKING:
    from codeweaver.core.config.resolver import ConfigurableComponent, ConfigurationValue


_configurable_components: list[ConfigurableComponent] = []
_configurable_values: list[ConfigurationValue] = []


def register_configurable(component: ConfigurableComponent | ConfigurationValue) -> None:
    """Register a component for config resolution.

    Args:
        component: Component implementing ConfigurableComponent protocol or a ConfigurationValue.
    """
    if isinstance(component, ConfigurationValue):
        _configurable_values.append(component)
    else:
        _configurable_components.append(component)


def get_configurable_components() -> list[ConfigurableComponent]:
    """Get all registered configurable components.

    Returns:
        Copy of the registered components list.
    """
    return _configurable_components.copy()


def get_configurable_values() -> list[ConfigurationValue]:
    """Get all registered configurable values.

    Returns:
        Copy of the registered configuration values list.
    """
    return _configurable_values.copy()


def clear_configurables() -> None:
    """Clear all registered components.

    Primarily for testing - ensures clean state between tests.
    """
    _configurable_components.clear()
    _configurable_values.clear()


def create_configuration_value(
    resolver_key: str,
    value: Any,
    source: Literal["env", "constant", "profile", "coded_default"],
    *,
    tagged: bool = False,
) -> ConfigurationValue:
    """Helper to create a ConfigurationValue instance.

    Args:
        resolver_key: Key used by the config resolver.
        value: The actual value.
        source: Source of the value.
        tagged: Whether the value is tagged (e.g., "primary.embedding")

    Returns:
        ConfigurationValue instance.
    """
    from codeweaver.core.config.resolver import ConfigurationValue

    return ConfigurationValue(resolver_key=resolver_key, value=value, source=source, tagged=tagged)


__all__ = (
    "clear_configurables",
    "create_configuration_value",
    "get_configurable_components",
    "get_configurable_values",
    "register_configurable",
)
