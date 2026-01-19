# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Core dependency types and factories."""

from __future__ import annotations

import asyncio
import importlib
import os

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from pydantic import DirectoryPath

from codeweaver.core import TelemetryService
from codeweaver.core._logging import get_rich_console
from codeweaver.core.config._logging import DefaultLoggingSettings, LoggingSettingsDict
from codeweaver.core.di.depends import INJECTED, depends
from codeweaver.core.di.utils import dependency_provider
from codeweaver.core.types.aliases import BlakeKey
from codeweaver.core.types.sentinel import Unset
from codeweaver.core.types.settings_model import get_possible_config_paths
from codeweaver.core.ui_protocol import (
    NoOpProgressReporter,
    ProgressReporter,
    RichConsoleProgressReporter,
)
from codeweaver.core.utils.filesystem import get_git_branch, get_project_path


if TYPE_CHECKING:
    from codeweaver.core.config.telemetry import TelemetrySettings
    from codeweaver.core.config.types import CodeWeaverSettingsDict
    from codeweaver.core.statistics import SessionStatistics
    from codeweaver.core.types.dictview import DictView


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


async def bootstrap_settings(config_file: Path | None = None) -> CodeWeaverSettingsType:
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

    await asyncio.sleep(0)
    config_file = (
        config_file or Path(env)
        if (env := os.environ.get("CODEWEAVER_CONFIG_FILE")) is not None
        else None
    )

    if (
        config_file
        and config_file.exists()
        and config_file in await asyncio.to_thread(get_possible_config_paths)
    ):
        # let pydantic_settings handle loading from the file if it's in a standard location
        config_file = None
    SettingsEnvVars.from_defaults().register_values()

    config_file = config_file if config_file and config_file.exists() else _resolve_config_file()
    return await asyncio.to_thread(get_settings, config_file=config_file)  # ty:ignore[invalid-return-type]


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


type SettingsDep = Annotated[
    CodeWeaverSettingsType, depends(bootstrap_settings, scope="singleton", tags={"settings"})
]

type NoneDep = Annotated[None, depends(lambda: None, use_cache=True, scope="singleton")]


@dependency_provider(DictView[CodeWeaverSettingsDict])
def _get_settings_map(settings: SettingsDep = INJECTED) -> DictView[CodeWeaverSettingsDict]:
    """Marker for providing a DictView of the current settings."""
    from codeweaver.core.types.dictview import DictView

    return DictView(settings.model_dump())


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


@dependency_provider(ProgressReporter, scope="singleton")
def _create_progress_reporter(settings: SettingsDep = INJECTED) -> ProgressReporter:
    """Factory for progress reporter.

    Returns:
        - NoOpProgressReporter for testing
        - RichConsoleProgressReporter for server/daemon (uses Rich Console)
        - CLI can override with StatusDisplay implementation
    """
    from codeweaver.core.utils.environment import is_tty

    console = get_rich_console()
    if is_tty():
        return RichConsoleProgressReporter(console=console)

    # Default: no-op (e.g., testing)
    return NoOpProgressReporter()


type ProgressReporterDep = Annotated[ProgressReporter, depends(_create_progress_reporter)]


async def _get_canonical_project_path(settings: SettingsDep = INJECTED) -> DirectoryPath:
    await asyncio.sleep(0)  # Yield control to the event loop
    return (
        settings.project_path  # ty:ignore[invalid-return-type]
        if settings.project_path is not Unset
        else await asyncio.to_thread(get_project_path)
    )


type ResolvedProjectPathDep = Annotated[DirectoryPath, depends(_get_canonical_project_path)]


async def _get_canonical_project_name(
    settings: SettingsDep = INJECTED, project_path: ResolvedProjectPathDep = INJECTED
) -> str:
    await asyncio.sleep(0)  # Yield control to the event loop
    return (
        settings.project_name  # ty:ignore[invalid-return-type]
        if settings.project_name is not Unset
        else project_path.name
    )


type ResolvedProjectNameDep = Annotated[str, depends(_get_canonical_project_name)]


async def _get_resolved_project_path_hash(
    project_path: ResolvedProjectPathDep = INJECTED,
) -> BlakeKey:
    from codeweaver.core.utils import get_blake_hash

    await asyncio.sleep(0)  # Yield control to the event loop
    return await asyncio.to_thread(get_blake_hash, str(project_path.absolute()))  # ty:ignore[invalid-argument-type]


type ResolvedProjectPathHashDep = Annotated[BlakeKey, depends(_get_resolved_project_path_hash)]


async def _get_resolved_git_branch(project_path: ResolvedProjectPathDep = INJECTED) -> str:
    """Get the git branch for the given project path. Always returns a string.

    If the branch can't be found, it return an empty string.
    """
    await asyncio.sleep(0)  # Yield control to the event loop
    return await asyncio.to_thread(get_git_branch, project_path)


type ResolvedGitBranchDep = Annotated[str, depends(_get_resolved_git_branch)]


async def _create_telemetry_service(settings: TelemetrySettingsDep = INJECTED) -> TelemetryService:
    from codeweaver.core.telemetry.client import TelemetryService

    return TelemetryService(
        api_key=settings.posthog_project_key,
        host=str(settings.posthog_host),
        enabled=not settings.disable_telemetry,
    )


type TelemetryServiceDep = Annotated[TelemetryService, depends(_create_telemetry_service)]


__all__ = (
    "CodeWeaverSettingsType",
    "LoggingSettingsDep",
    "NoneDep",
    "ProgressReporterDep",
    "ResolvedGitBranchDep",
    "ResolvedProjectNameDep",
    "ResolvedProjectPathDep",
    "ResolvedProjectPathHashDep",
    "SettingsDep",
    "StatisticsDep",
    "TelemetryServiceDep",
    "TelemetrySettingsDep",
    "bootstrap_settings",
)
