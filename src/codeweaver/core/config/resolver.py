"""Configuration resolution system using DI container."""

from __future__ import annotations

import contextlib

from typing import TYPE_CHECKING, Any, Protocol

from codeweaver.core.di import get_container


if TYPE_CHECKING:
    from codeweaver.core.config.registry import ConfigurableComponent


class ConfigurationSupplier(Protocol):
    """Protocol for supplying configuration instances."""

    async def get_configuration(self) -> Any:
        """Get the configuration instance.

        Returns:
            Configuration instance.
        """
        ...


class ConfigurableComponent(Protocol):
    """Protocol for components participating in config resolution.

    Components implementing this protocol can:
    1. Declare what other configs they depend on
    2. Receive resolved instances and adjust their own config
    """

    def config_dependencies(self) -> dict[str, type]:
        """Return types this config needs to resolve against.

        Returns:
            Dict mapping dependency name to type from DI container.
            Example: {"embedding": EmbeddingProviderSettings}
        """
        ...

    async def apply_resolved_config(self, **resolved: Any) -> None:
        """Apply resolved configuration from dependencies.

        Args:
            **resolved: Resolved dependency instances from DI container.
                       Keys match those from config_dependencies().
        """
        ...


async def resolve_all_configs() -> None:
    """Resolve all configurations across the application.

    This should be called during settings finalization, after all
    configs are initialized but before the application starts.
    """
    from codeweaver.core.config.registry import get_configurable_components

    container = get_container()
    configurables = get_configurable_components()

    for configurable in configurables:
        deps = configurable.config_dependencies()
        resolved = {}

        for dep_name, dep_type in deps.items():
            with contextlib.suppress(AttributeError, KeyError, TypeError, ValueError, ImportError):
                resolved[dep_name] = await container.resolve(dep_type)

        if resolved:
            await configurable.apply_resolved_config(**resolved)


__all__ = ("ConfigurableComponent", "resolve_all_configs")
