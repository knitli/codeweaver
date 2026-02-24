# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Utilities for detecting and determining the environment."""

from __future__ import annotations

import contextlib
import importlib
import logging
import os
import sys

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from lateimport import LateImport, lateimport
from pydantic import NonNegativeInt, PositiveInt

from codeweaver.core.constants import (
    ENV_EXPLICIT_FALSE_VALUES,
    ENV_JETBRAINS_INDICATOR,
    ENV_VSCODE_INDICATORS,
    LOCALHOST_URL,
)
from codeweaver.core.types.provider import Provider
from codeweaver.core.utils.checks import has_package


logger = logging.getLogger(__name__)

if importlib.util.find_spec("rich") is not None:
    from rich.console import Console
else:
    type Console = object

if TYPE_CHECKING:
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType

console: LateImport[Console] = lateimport("rich.console", "Console")


def is_tty() -> bool:
    """Check if the output is a TTY in an interactive terminal."""
    return sys.stdout.isatty() if hasattr(sys, "stdout") and sys.stdout else False


def we_are_in_vscode() -> bool:
    """Detect if we are running inside VSCode."""
    env = os.environ
    return (
        any(
            v
            for k, v in env.items()
            if k in ENV_VSCODE_INDICATORS
            if v and v not in ENV_EXPLICIT_FALSE_VALUES
        )
        or os.environ.get("TERM_PROGRAM") == "vscode"
    )


def we_are_in_jetbrains() -> bool:
    """Detect if we are running inside a JetBrains IDE."""
    env = os.environ
    return env.get(ENV_JETBRAINS_INDICATOR) == "JetBrains-JediTerm"


def in_ide() -> bool:
    """Detect if we are running inside an IDE."""
    return we_are_in_vscode() or we_are_in_jetbrains()


def _check_env_var(var_name: str) -> str | None:
    """Check if an environment variable is set and return its value, or None if not set."""
    return os.getenv(var_name)


def get_possible_env_vars() -> tuple[tuple[str, str], ...] | None:
    """Get a tuple of any resolved environment variables for all providers."""
    env_vars = sorted({item[1][0] for item in Provider.all_envs()})
    found_vars = tuple(
        (var, value) for var in env_vars if (value := _check_env_var(var)) is not None
    )
    return found_vars or None


def get_terminal_width() -> int:
    """Get the terminal width."""
    fallback = 120 if in_ide() else 80
    try:
        import shutil

        size = shutil.get_terminal_size(fallback=(fallback, 24))
    except Exception:
        return fallback
    else:
        return size.columns


def format_file_link(file_path: str | Path, line: NonNegativeInt | None = None) -> str:
    """Format a file link for IDEs that support it (VSCode, JetBrains)."""
    path = Path(file_path) if isinstance(file_path, str) else file_path
    if we_are_in_vscode():
        formatted_line = f":{line!s}" if line is not None else ""
        return f"file://{path.absolute()!s}{formatted_line}"
    if we_are_in_jetbrains():
        try:
            from codeweaver.core.utils.filesystem import get_project_path

            relative_path = path.relative_to(get_project_path())
        except ValueError:
            relative_path = path
        return (
            f'File "{relative_path!s}", line {line!s}'
            if line is not None
            else f'File "{relative_path!s}"'
        )
    return f"{path.absolute()!s}:{line!s}" if line is not None else f"{path.absolute()!s}"


def get_codeweaver_config_paths() -> tuple[Path, ...]:
    """Get all possible CodeWeaver configuration file paths."""
    from codeweaver.core.config.core_settings import get_possible_config_paths

    return tuple(get_possible_config_paths())


def is_codeweaver_config_path(path: Path) -> bool:
    """Check if the given path is a CodeWeaver configuration file path."""
    return any(path.samefile(config_path) for config_path in get_codeweaver_config_paths())


def _set_settings_for_config(config_file: Path) -> CodeWeaverSettingsType:
    """Set the global settings based on the given config file."""
    from codeweaver.core.config.loader import get_settings

    return get_settings(config_file=config_file)


def _set_project_path(project_path: Path) -> CodeWeaverSettingsType:
    """Set the global project path."""
    from codeweaver.core.config import get_settings

    settings = get_settings()
    settings.project_path = project_path
    return settings


def detect_root_package() -> Literal["server", "engine", "provider", "core"]:
    """Detect which package should be root based on what's installed.

    Priority (highest to lowest):
    1. code-weaver-server (full installation)
    2. code-weaver-engine (indexing/chunking only)
    3. code-weaver-providers (providers only)
    4. core (minimal - logging/telemetry only)

    Returns:
        The package type that should serve as root settings
    """
    # Check in priority order - highest level package wins
    if importlib.util.find_spec("codeweaver.server") is not None:
        logger.debug("Detected server package - using CodeWeaverSettings")
        return "server"

    if importlib.util.find_spec("codeweaver.engine") is not None:
        logger.debug("Detected engine package - using CodeWeaverEngineSettings")
        return "engine"

    if importlib.util.find_spec("codeweaver.providers") is not None:
        logger.debug("Detected providers package - using CodeWeaverProviderSettings")
        return "provider"

    logger.debug("Only core package detected - using CodeWeaverCoreSettings")
    return "core"


def settings_type_for_root_package(
    root_package: Literal["server", "engine", "provider", "core"],
) -> type[CodeWeaverSettingsType]:
    """Get the settings type for the given root package."""
    match root_package:
        case "server":
            from codeweaver.server.config.settings import CodeWeaverSettings

            return CodeWeaverSettings
        case "engine":
            from codeweaver.engine.config.root_settings import CodeWeaverEngineSettings

            return CodeWeaverEngineSettings
        case "provider":
            from codeweaver.providers.config.root_settings import CodeWeaverProviderSettings

            return CodeWeaverProviderSettings
        case "core":
            from codeweaver.core.config.core_settings import CodeWeaverCoreSettings

            return CodeWeaverCoreSettings


async def _check_ports(port_search: tuple[int, ...]) -> int | None:
    async def _endpoint(port: int):
        return f"{LOCALHOST_URL}:{port}/healthz"

    if has_package("codeweaver.providers"):
        from codeweaver.providers.http_pool import get_http_pool

        client = await get_http_pool().get_client("qdrant_probe")
    else:
        import httpx

        client = httpx.AsyncClient()

    async with client:
        for port in port_search:
            try:
                response = await client.get(await _endpoint(port), timeout=0.2)
                if response.status_code == 200:
                    return port
            except httpx.RequestError:
                continue
    return None


async def _try_qdrant_client(port: int) -> bool:
    from qdrant_client import AsyncQdrantClient

    response = None
    with contextlib.suppress(Exception):
        client = AsyncQdrantClient(url=f"{LOCALHOST_URL}:{port}")
        response = await client.get_collections()
    return bool(response)


async def find_qdrant_instance(port_search: tuple[int, ...] | None = None) -> PositiveInt | None:
    """Attempt to find the port of a local qdrant instance."""
    port_search = port_search or (
        6333,
        6334,
        6335,
        6336,
        8080,
        8000,
        4321,
        *range(3000, 6333),
        *range(6337, 9000),
    )
    if (found_port := await _check_ports(port_search)) and await _try_qdrant_client(found_port):
        return found_port
    if (idx := port_search.index(found_port)) + 1 < len(port_search):
        return await find_qdrant_instance(port_search=port_search[idx + 1 :])
    return None


async def qdrant_instance_live_at_port(port: int) -> bool:
    """Check if a Qdrant instance is live at the given port."""
    return await _try_qdrant_client(port)


def get_codeweaver_prefix() -> str:
    """Return the codeweaver terminal prefix."""
    if is_tty():
        if "truecolor" in os.environ.get("TERM", "").lower():
            return """\033[38;2;181;108;48;m[codeweaver]\033[0m"""
        return "\033[38;5;131m[codeweaver]\033[0m"
    return "[codeweaver]"


__all__ = (
    "detect_root_package",
    "find_qdrant_instance",
    "format_file_link",
    "get_codeweaver_config_paths",
    "get_codeweaver_prefix",
    "get_possible_env_vars",
    "get_terminal_width",
    "in_ide",
    "is_codeweaver_config_path",
    "is_tty",
    "qdrant_instance_live_at_port",
    "settings_type_for_root_package",
    "we_are_in_jetbrains",
    "we_are_in_vscode",
)
