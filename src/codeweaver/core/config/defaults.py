"""User-extensible default value system."""

import importlib
import os

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from codeweaver.core.config.envs import environment_variables


if TYPE_CHECKING and importlib.util.find_spec("codeweaver.providers") is not None:
    from codeweaver.providers import ProviderSettingsDict
else:
    ProviderSettingsDict = dict[str, Any]


def _get_provider_defaults() -> ProviderSettingsDict:
    """Get built-in default providers."""
    if importlib.util.find_spec("codeweaver.providers") is not None:
        from codeweaver.providers import get_profile

        return get_profile("recommended", "local")
    return {}


def env_defaults() -> ProviderSettingsDict:
    """Get default values from environment variables.

    Returns:
        A dict of config keys to default values from env vars.
    """
    defaults: ProviderSettingsDict = {}
    for key, var_info in environment_variables().items():
        if (env_value := os.getenv(var_info.env)) is not None:
            defaults[key] = env_value  # ty:ignore[invalid-key]
    return defaults


DEFAULTS = {"primary.embedding.model": _get_provider_defaults().get("primary.embedding.model")}

_default_providers: dict[str, list[Callable[[], Any | None]]] = {}

_KNOWN_KEYS: frozenset[str] = frozenset({
    "primary.embedding.dimension",
    "primary.embedding.datatype",
    "primary.embedding.model",
    "primary.embedding.provider",
    "primary.sparse_embedding.datatype",
    "primary.sparse_embedding.model",
    "primary.sparse_embedding.provider",
    "primary.reranking.model",
    "primary.reranking.provider",
    "primary.vector_store.provider",
    "primary.vector_store.url",
    "project_path",
    "config_path",
})
"""This is really just here to document known config keys for default providers.
Users can register defaults for any key, but these are the ones we know about. It's not used
programmatically anywhere.

Tagged paths start with their tag; currently only "primary" and "backup" are possible.
"""


def register_default_provider(key: str, provider: Callable[[], Any | None]) -> None:
    """Register a default value provider for a config key.

    Providers are called in registration order. First non-None value wins.

    Args:
        key: Config key like "primary.embedding.dimension"
        provider: Callable that returns the default value or None

    Example:
        ```python
        # Register a custom default dimension
        register_default_provider("primary.embedding.dimension", lambda: 768)

        # Register with conditional logic
        register_default_provider(
            "primary.embedding.datatype", lambda: "float16" if has_gpu() else "uint8"
        )
        ```
    """
    if key not in _default_providers:
        _default_providers[key] = []
    _default_providers[key].append(provider)


def get_default(key: str) -> Any | None:
    """Get a default value by calling registered providers.

    Args:
        key: Config key to get default for.

    Returns:
        First non-None value from registered providers, or None.
    """
    for provider in _default_providers.get(key, []):
        if (value := provider()) is not None:
            return value
    return None


def clear_defaults() -> None:
    """Clear all registered default providers.

    Primarily for testing.
    """
    _default_providers.clear()


__all__ = ("clear_defaults", "get_default", "register_default_provider")
