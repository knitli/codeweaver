# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Component settings dependency definitions."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING, Annotated

from pydantic import DirectoryPath

from codeweaver.core.di.depends import depends
from codeweaver.core.di.utils import dependency_provider
from codeweaver.core.types.service_cards import ServiceCard


if TYPE_CHECKING:
    from codeweaver.core.dependencies.core_settings import CodeWeaverSettingsType


def _global_settings() -> CodeWeaverSettingsType:
    from codeweaver.core.dependencies.utils import ensure_settings_initialized
    from codeweaver.core.di.container import get_container

    ensure_settings_initialized()
    container = get_container()
    return container.resolve("CodeWeaverSettingsType")


@dependency_provider(
    tuple[ServiceCard, ...], scope="singleton", collection=True, tags=["service_cards", "providers"]
)
def _get_service_cards() -> tuple[ServiceCard, ...]:
    from codeweaver.core.types.service_cards import get_service_cards

    return get_service_cards()


type ServiceCardsDep = Annotated["tuple[ServiceCard, ...]", depends(_get_service_cards)]


from codeweaver.core.config.telemetry import TelemetrySettings


@dependency_provider(TelemetrySettings, scope="singleton")
def _get_telemetry_settings() -> TelemetrySettings:
    settings = _global_settings()
    return settings.telemetry


type TelemetrySettingsDep = Annotated[TelemetrySettings, depends(_get_telemetry_settings)]


from codeweaver.core.config._logging import LoggingSettingsDict


@dependency_provider(LoggingSettingsDict, scope="singleton")
def _get_logging_settings() -> LoggingSettingsDict:
    settings = _global_settings()
    return settings.logging


type LoggingSettingsDep = Annotated[LoggingSettingsDict, depends(_get_logging_settings)]


@dependency_provider(logging.Logger, scope="singleton")
def _get_logger() -> logging.Logger:
    from codeweaver.core._logging import setup_logger

    settings = _get_logging_settings()
    return setup_logger(**settings)  # ty:ignore[unknown-argument]


type LoggerDep = Annotated[logging.Logger, depends(_get_logger)]


import asyncio
import contextlib


async def _get_canonical_project_path() -> DirectoryPath:
    await asyncio.sleep(0)  # Yield control to the event loop
    with contextlib.suppress(ImportError):
        settings = _global_settings()
        if settings and settings.project_path:
            return settings.project_path
    from codeweaver.core.utils.filesystem import get_project_path

    loop = asyncio.get_running_loop()
    return await loop.to_thread(get_project_path)


type ResolvedProjectPathDep = Annotated[DirectoryPath, depends(_get_canonical_project_path)]


async def _get_canonical_project_name() -> str:
    await asyncio.sleep(0)  # Yield control to the event loop
    settings = _global_settings()
    if settings.project_name:
        return settings.project_name
    return (await _get_canonical_project_path()).name


type ResolvedProjectNameDep = Annotated[str, depends(_get_canonical_project_name)]


from codeweaver.core.types.aliases import BlakeKey
from codeweaver.core.utils.filesystem import get_git_branch


async def _get_resolved_project_path_hash() -> BlakeKey:
    await asyncio.sleep(0)  # Yield control to the event loop
    project_path = await _get_canonical_project_path()
    directory = str(project_path).encode("utf-8")

    loop = asyncio.get_running_loop()
    return await loop.to_thread(directory, project_path)


type ResolvedProjectPathHashDep = Annotated[BlakeKey, depends(_get_resolved_project_path_hash)]


async def _get_resolved_git_branch() -> str:
    """Get the git branch for the given project path. Always returns a string.

    If the branch can't be found, it return an empty string.
    """
    await asyncio.sleep(0)  # Yield control to the event loop
    project_path = await _get_canonical_project_path()

    loop = asyncio.get_running_loop()
    return await loop.to_thread(get_git_branch, project_path)


type ResolvedGitBranchDep = Annotated[str, depends(_get_resolved_git_branch)]


__all__ = (
    "LoggerDep",
    "LoggingSettingsDep",
    "ResolvedGitBranchDep",
    "ResolvedProjectNameDep",
    "ResolvedProjectPathDep",
    "ResolvedProjectPathHashDep",
    "ServiceCardsDep",
    "TelemetrySettingsDep",
)
