# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Utilities for detecting and determining the environment."""

from __future__ import annotations

import importlib
import logging
import os
import sys

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from pydantic import NonNegativeInt

from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.provider import Provider
from codeweaver.core.utils.filesystem import get_project_path
from codeweaver.core.utils.lazy_import import LazyImport, lazy_import


logger = logging.getLogger(__name__)

if importlib.util.find_spec("rich") is not None:
    from rich.console import Console
else:
    type Console = object

if TYPE_CHECKING:
    if importlib.util.find_spec("codeweaver.server") is not None:
        from codeweaver.server import CodeWeaverSettings, CodeWeaverSettingsDict
    else:
        type CodeWeaverSettings = object
        type CodeWeaverSettingsDict = Mapping[str, object]

console: LazyImport[Console] = lazy_import("rich.console", "Console")


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
            if k in {"VSCODE_GIT_IPC_HANDLE", "VSSCODE_INJECTION", "VSCODE_IPC_HOOK_CLI"}
            if v and v not in {"0", "false", "False", ""}
        )
        or os.environ.get("TERM_PROGRAM") == "vscode"
    )


def we_are_in_jetbrains() -> bool:
    """Detect if we are running inside a JetBrains IDE."""
    env = os.environ
    return env.get("TERMINAL_EMULATOR") == "JetBrains-JediTerm"


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


def resolve_project_root() -> Path:
    """Resolve the project root directory."""
    from codeweaver.server import get_settings_map

    settings_map = get_settings_map()
    if isinstance(settings_map.get("project_path"), Path):
        return settings_map["project_path"]

    return get_project_path()


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
            relative_path = path.relative_to(resolve_project_root())
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
    from codeweaver.core import get_user_config_dir
    from codeweaver.server import get_settings_map

    settings_map = get_settings_map()
    project_path = (
        settings_map["project_path"]
        if isinstance(settings_map["project_path"], Path)
        else resolve_project_root()
    )
    user_config_dir = get_user_config_dir()
    repo_paths = [
        project_path / f"{config_path}.{ext}"
        for config_path in (
            "codeweaver.test.local",
            "codeweaver.test",
            ".codeweaver.test.local",
            ".codeweaver.test",
            "codeweaver/codeweaver.test.local",
            "codeweaver/codeweaver.test",
            "codeweaver/config.test.local",
            "codeweaver/config.test",
            ".codeweaver/codeweaver.test.local",
            ".codeweaver/codeweaver.test",
            ".config/codeweaver/test.local",
            ".config/codeweaver/test",
            ".config/codeweaver/config.test.local",
            ".config/codeweaver/config.test",
            ".config/codeweaver/codeweaver.test.local",
            ".config/codeweaver/codeweaver.test",
        )
        for ext in ("toml", "yaml", "yml", "json")
    ]
    repo_paths.extend([
        user_config_dir / f"codeweaver.{ext}" for ext in ("toml", "yaml", "yml", "json")
    ])
    env_config = os.environ.get("CODEWEAVER_CONFIG_FILE")
    if (
        env_config
        and (env_path := Path(env_config)).exists()
        and env_path.is_file()
        and env_path not in repo_paths
        and env_path.suffix.lstrip(".") in {"toml", "yaml", "yml", "json"}
    ):
        repo_paths.append(env_path)
    return tuple(repo_paths)


def is_codeweaver_config_path(path: Path) -> bool:
    """Check if the given path is a CodeWeaver configuration file path."""
    return any(path.samefile(config_path) for config_path in get_codeweaver_config_paths())


def _set_settings_for_config(config_file: Path) -> CodeWeaverSettings:
    """Set the global settings based on the given config file."""
    from codeweaver.server import get_settings

    return get_settings(config_file=config_file)


def _set_project_path(project_path: Path) -> DictView[CodeWeaverSettingsDict]:
    """Set the global project path."""
    if importlib.util.find_spec("code-weaver-server") is None:
        raise ImportError("codeweaver_server module is not available.")
    from codeweaver.server import CodeWeaverSettingsDict, get_settings_map, update_settings

    return cast(
        DictView[CodeWeaverSettingsDict],
        update_settings(**(dict(get_settings_map()) | {"project_path": project_path})),
    )  # ty:ignore[invalid-return-type]


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


__all__ = (
    "detect_root_package",
    "format_file_link",
    "get_codeweaver_config_paths",
    "get_possible_env_vars",
    "get_terminal_width",
    "in_ide",
    "is_codeweaver_config_path",
    "is_tty",
    "resolve_project_root",
    "we_are_in_jetbrains",
    "we_are_in_vscode",
)
