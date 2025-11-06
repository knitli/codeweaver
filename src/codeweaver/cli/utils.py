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
    if isinstance(settings_map.get("project_root"), Path):
        return settings_map["project_root"]
    from codeweaver.common.utils.git import get_project_path

    return get_project_path()


def is_tty() -> bool:
    """Check if the output is a TTY."""
    console: Console = globals()["console"]._resolve()()
    return console.is_terminal and console.file.isatty()


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
