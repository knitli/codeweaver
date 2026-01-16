# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Core dependency types and factories."""

from __future__ import annotations

import importlib
import os

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from pydantic import DirectoryPath

from codeweaver.core import LoggingSettingsDict
from codeweaver.core.config import DefaultLoggingSettings
from codeweaver.core.di import INJECTED, dependency_provider, depends
from codeweaver.core.types import Unset, get_possible_config_paths
from codeweaver.core.utils import get_project_path


if TYPE_CHECKING:
    from codeweaver.core.config.telemetry import TelemetrySettings
    from codeweaver.core.statistics import SessionStatistics


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


def bootstrap_settings(config_file: Path | None = None) -> CodeWeaverSettingsType:
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
    return get_settings(config_file=config_file)  # ty:ignore[invalid-return-type]


if importlib.util.find_spec("codeweaver.server"):
    from codeweaver.server.config.settings import CodeWeaverSettings

    type CodeWeaverSettingsType = CodeWeaverSettings

elif importlib.util.find_spec("codeweaver.engine"):
    from codeweaver.engine.config.root_settings import CodeWeaverEngineSettings

    type CodeWeaverSettingsType = CodeWeaverEngineSettings

elif importlib.util.find_spec("codeweaver.providers"):
    from codeweaver.providers.config.root_settings import CodeWeaverProviderSettings

    type CodeWeaverSettingsType = CodeWeaverProviderSettings

else:
    from codeweaver.core.config.core_settings import CodeWeaverCoreSettings

    type CodeWeaverSettingsType = CodeWeaverCoreSettings


dependency_provider(CodeWeaverSettingsType, scope="singleton")(bootstrap_settings)  # ty:ignore[no-matching-overload]


type SettingsDep = Annotated[CodeWeaverSettingsType, depends(bootstrap_settings)]

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


@dependency_provider(TelemetrySettings, scope="singleton")
def _get_telemetry_settings(settings: SettingsDep = INJECTED) -> TelemetrySettings:
    from codeweaver.core.config import TelemetrySettings

    return (
        settings.telemetry if settings.telemetry is not Unset else TelemetrySettings()  # ty:ignore[invalid-return-type]
    )  # ty:ignore[invalid-return-type]


type TelemetrySettingsDep = Annotated[TelemetrySettings, depends(_get_telemetry_settings)]


@dependency_provider(LoggingSettingsDict, scope="singleton")
def _get_logging_settings(settings: SettingsDep = INJECTED) -> LoggingSettingsDict:
    return (
        settings.logging  # type: ignore[return-value]
        if settings.logging is not Unset
        else DefaultLoggingSettings
    )  # type: ignore[return-value]


type LoggingSettingsDep = Annotated[LoggingSettingsDict, depends(_get_logging_settings)]


def _get_canonical_project_path(settings: SettingsDep = INJECTED) -> DirectoryPath:
    return settings.project_path if settings.project_path is not Unset else get_project_path()  # ty:ignore[invalid-return-type]


type ResolvedProjectPathDep = Annotated[DirectoryPath, depends(_get_canonical_project_path)]


def _get_canonical_project_name(settings: SettingsDep = INJECTED) -> str:
    return (
        settings.project_name  # ty:ignore[invalid-return-type]
        if settings.project_name is not Unset
        else _get_canonical_project_path.name
    )


type ResolvedProjectNameDep = Annotated[str, depends(_get_canonical_project_name)]

__all__ = (
    "CodeWeaverSettingsType",
    "NoneDep",
    "ResolvedProjectNameDep",
    "ResolvedProjectPathDep",
    "SettingsDep",
    "StatisticsDep",
    "TelemetrySettingsDep",
    "bootstrap_settings",
)
