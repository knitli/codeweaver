# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Utilities for detecting and determining the environment."""

from __future__ import annotations

import os
import sys

from collections.abc import Mapping
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import NonNegativeInt

from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.provider import Provider
from codeweaver.core.utils.filesystem import get_project_path
from codeweaver.core.utils.lazy_import import LazyImport, lazy_import


if find_spec("rich"):
    from rich.console import Console
else:
    type Console = object

if TYPE_CHECKING:
    if find_spec("codeweaver.config.settings") is not None:
        from codeweaver.config.settings import CodeWeaverSettings
        from codeweaver.config.types import CodeWeaverSettingsDict
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
    from codeweaver.config.settings import get_settings_map

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
    from codeweaver.config.settings import get_settings_map
    from codeweaver.core import get_user_config_dir

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
    from codeweaver.config.settings import get_settings

    return get_settings(config_file=config_file)


def _set_project_path(project_path: Path) -> DictView[CodeWeaverSettingsDict]:
    """Set the global project path."""
    if find_spec("codeweaver.config.settings") is None:
        raise ImportError("codeweaver.config.settings module is not available.")
    from codeweaver.config.settings import get_settings_map, update_settings
    from codeweaver.config.types import CodeWeaverSettingsDict

    return cast(
        DictView[CodeWeaverSettingsDict],
        update_settings(**(dict(get_settings_map()) | {"project_path": project_path})),
    )  # ty:ignore[invalid-return-type]


def get_settings_map_for(
    config_file: Path | None = None, project_path: Path | None = None
) -> DictView[CodeWeaverSettingsDict]:
    """Get the settings map for the given config file."""
    if config_file is not None:
        return _set_settings_for_config(config_file).view  # ty:ignore[unresolved-attribute]
    if project_path is not None:
        return _set_project_path(project_path)
    from codeweaver.config.settings import get_settings_map

    return get_settings_map()  # ty:ignore[invalid-return-type]


__all__ = (
    "format_file_link",
    "get_codeweaver_config_paths",
    "get_possible_env_vars",
    "get_settings_map_for",
    "get_terminal_width",
    "in_ide",
    "is_codeweaver_config_path",
    "is_tty",
    "resolve_project_root",
    "we_are_in_jetbrains",
    "we_are_in_vscode",
)
