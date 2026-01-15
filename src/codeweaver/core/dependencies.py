# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Core dependency types and factories."""

from __future__ import annotations

import os

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from codeweaver.core.di import depends
from codeweaver.core.types import get_possible_config_paths


def _resolve_config_file() -> Path | None:
    if (declared_env := os.getenv("CODEWEAVER_CONFIG_FILE")) is not None:
        return Path(declared_env)
    return None


# Import for decorator
from codeweaver.core.di import dependency_provider


if TYPE_CHECKING:
    from codeweaver.core.statistics import SessionStatistics
    from codeweaver.core.types.settings_model import BaseCodeWeaverSettings


def _resolve_config_file() -> Path | None:
    """Resolve the configuration file path.

    Checks for the CODEWEAVER_CONFIG_FILE environment variable first,
    then falls back to standard config locations.

    Returns:
        The resolved config file path, or None if not found.
    """
    if (declared_env := os.getenv("CODEWEAVER_CONFIG_FILE")) is not None:
        return Path(declared_env)
    return None


def bootstrap_settings(config_file: Path | None = None) -> BaseCodeWeaverSettings:
    """Bootstrap global settings as DI root.

    Auto-detects the appropriate settings class based on installed packages
    (server, engine, provider, or core) and returns it as BaseCodeWeaverSettings.

    This is the DI system's entry point - settings are created once at startup
    and all other providers can inject them via:
        settings: BaseCodeWeaverSettings = INJECTED

    Returns:
        The appropriate settings instance for the current installation
    """
    from codeweaver.core.config.loader import get_settings  # noqa: I001
    from codeweaver.core.config.envs import SettingsEnvVars

    if config_file and config_file.exists() and config_file in get_possible_config_paths():
        # let pydantic_settings handle loading from the file if it's in a standard location
        config_file = None
    SettingsEnvVars.from_defaults().register_values()

    config_file = config_file if config_file and config_file.exists() else _resolve_config_file()
    return get_settings(config_file=config_file)


# Register factory after definition (import here to avoid circular dependency at module top)
from codeweaver.core.types.settings_model import BaseCodeWeaverSettings


dependency_provider(BaseCodeWeaverSettings, scope="singleton")(bootstrap_settings)


type SettingsDep = Annotated[BaseCodeWeaverSettings, depends(bootstrap_settings)]


type NoneDep = Annotated[None, depends(lambda: None, use_cache=True, scope="singleton")]


@dependency_provider(SessionStatistics, scope="singleton")
def _get_statistics() -> SessionStatistics:
    from codeweaver.core.statistics import SessionStatistics

    return SessionStatistics(
        _successful_request_log=[],
        _failed_request_log=[],
        _successful_http_request_log=[],
        _failed_http_request_log=[],
    )


type StatisticsDep = Annotated[SessionStatistics, depends(_get_statistics)]

__all__ = ("NoneDep", "SettingsDep", "StatisticsDep", "bootstrap_settings")
