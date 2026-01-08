"""User-extensible default value system."""

from collections.abc import Callable
from typing import Any


_default_providers: dict[str, list[Callable[[], Any | None]]] = {}

_KNOWN_KEYS: frozenset[str] = frozenset({
    "embedding.dimension",
    "embedding.datatype",
    "embedding.model",
    "embedding.provider",
})
"""This is really just here to document known config keys for default providers.
Users can register defaults for any key, but these are the ones we know about. It's not used
programmatically anywhere.
"""


def register_default_provider(key: str, provider: Callable[[], Any | None]) -> None:
    """Register a default value provider for a config key.

    Providers are called in registration order. First non-None value wins.

    Args:
        key: Config key like "embedding.dimension"
        provider: Callable that returns the default value or None

    Example:
        ```python
        # Register a custom default dimension
        register_default_provider("embedding.dimension", lambda: 768)

        # Register with conditional logic
        register_default_provider(
            "embedding.datatype", lambda: "float16" if has_gpu() else "uint8"
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
