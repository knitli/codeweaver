"""Core dependency types and factories."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from codeweaver.core.di import depends
from codeweaver.core.types import get_config_locations


def _resolve_config_file() -> Path | None:
    if (declared_env := os.getenv("CODEWEAVER_CONFIG_FILE")) is not None:
        return Path(declared_env)
    for path in get_config_locations():
        if path.exists():
            return path
    return None


# Import for decorator
from codeweaver.core.di import dependency_provider

if TYPE_CHECKING:
    from codeweaver.core.types.settings_model import BaseCodeWeaverSettings


def bootstrap_settings():
    """Bootstrap global settings as DI root.

    Auto-detects the appropriate settings class based on installed packages
    (server, engine, provider, or core) and returns it as BaseCodeWeaverSettings.

    This is the DI system's entry point - settings are created once at startup
    and all other providers can inject them via:
        settings: BaseCodeWeaverSettings = INJECTED

    Returns:
        The appropriate settings instance for the current installation
    """
    from codeweaver.core.config.loader import get_settings

    config_file = _resolve_config_file()
    return get_settings(config_file=config_file)


# Register factory after definition (import here to avoid circular dependency at module top)
from codeweaver.core.types.settings_model import BaseCodeWeaverSettings

dependency_provider(BaseCodeWeaverSettings, scope="singleton")(bootstrap_settings)


type SettingsDep = Annotated[BaseCodeWeaverSettings, depends(bootstrap_settings)]


type NoneDep = Annotated[None, depends(lambda: None, use_cache=True, scope="singleton")]

__all__ = (
    "NoneDep",
    "SettingsDep",
    "bootstrap_settings",
)
