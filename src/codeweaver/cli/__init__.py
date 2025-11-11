# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CLI interface for CodeWeaver."""

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    # Import everything for IDE and type checker support
    # These imports are never executed at runtime, only during type checking
    from codeweaver.cli.__main__ import app, console, main
    from codeweaver.cli.utils import (
        format_file_link,
        in_ide,
        is_tty,
        we_are_in_jetbrains,
        we_are_in_vscode,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "app": (__spec__.parent, "__main__"),
    "console": (__spec__.parent, "__main__"),
    "main": (__spec__.parent, "__main__"),
    "format_file_link": (__spec__.parent, "utils"),
    "in_ide": (__spec__.parent, "utils"),
    "is_tty": (__spec__.parent, "utils"),
    "we_are_in_jetbrains": (__spec__.parent, "utils"),
    "we_are_in_vscode": (__spec__.parent, "utils"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the semantic package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = (
    "app",
    "console",
    "format_file_link",
    "in_ide",
    "is_tty",
    "main",
    "we_are_in_jetbrains",
    "we_are_in_vscode",
)


def __dir__() -> list[str]:
    return list(__all__)
