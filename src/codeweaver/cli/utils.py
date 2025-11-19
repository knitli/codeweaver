# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Common CLI utilities."""

from __future__ import annotations

import os

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import NonNegativeInt

from codeweaver.common.utils.lazy_importer import LazyImport, lazy_import


if TYPE_CHECKING:
    from rich.console import Console


console: LazyImport[Console] = lazy_import("rich.console", "Console")


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


def resolve_project_root() -> Path:
    """Resolve the project root directory."""
    from codeweaver.config.settings import get_settings_map

    settings_map = get_settings_map()
    if isinstance(settings_map.get("project_path"), Path):
        return settings_map["project_path"]
    from codeweaver.common.utils.git import get_project_path

    return get_project_path()


def is_tty() -> bool:
    """Check if the output is a TTY in an interactive terminal."""
    console: Console = globals()["console"]._resolve()()
    return console.is_terminal and console.file.isatty() and console.is_interactive


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
    from codeweaver.common.utils import get_user_config_dir
    from codeweaver.config.settings import get_settings_map

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
            "codeweaver",
            ".codeweaver",
            ".codeweaver.local",
            "codeweaver.local",
            ".codeweaver/codeweaver",
            ".codeweaver/codeweaver.local",
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


def is_wsl() -> bool:
    """Check if running inside Windows Subsystem for Linux (WSL)."""
    return "microsoft" in (release := os.uname().release.lower()) or "wsl" in release


__all__ = (
    "format_file_link",
    "get_codeweaver_config_paths",
    "get_terminal_width",
    "in_ide",
    "is_codeweaver_config_path",
    "is_tty",
    "is_wsl",
    "resolve_project_root",
    "we_are_in_jetbrains",
    "we_are_in_vscode",
)
