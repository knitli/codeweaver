# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CLI interface for CodeWeaver."""

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.common.utils.lazy_importer import create_lazy_getattr


if TYPE_CHECKING:
    # Import everything for IDE and type checker support
    # These imports are never executed at runtime, only during type checking
    from codeweaver.cli.__main__ import app, console, main
    from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
    from codeweaver.cli.utils import (
        format_file_link,
        get_codeweaver_config_paths,
        in_ide,
        is_tty,
        is_wsl,
        we_are_in_jetbrains,
        we_are_in_vscode,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CLIErrorHandler": (__spec__.parent, "ui"),
    "StatusDisplay": (__spec__.parent, "ui"),
    "app": (__spec__.parent, "__main__"),
    "console": (__spec__.parent, "__main__"),
    "format_file_link": (__spec__.parent, "utils"),
    "get_codeweaver_config_paths": (__spec__.parent, "utils"),
    "get_display": (__spec__.parent, "ui"),
    "in_ide": (__spec__.parent, "utils"),
    "is_tty": (__spec__.parent, "utils"),
    "is_wsl": (__spec__.parent, "utils"),
    "main": (__spec__.parent, "__main__"),
    "we_are_in_jetbrains": (__spec__.parent, "utils"),
    "we_are_in_vscode": (__spec__.parent, "utils"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "CLIErrorHandler",
    "StatusDisplay",
    "app",
    "console",
    "format_file_link",
    "get_codeweaver_config_paths",
    "get_display",
    "in_ide",
    "is_tty",
    "is_wsl",
    "main",
    "we_are_in_jetbrains",
    "we_are_in_vscode",
)


def __dir__() -> list[str]:
    return list(__all__)


if __name__ == "__main__":
    from codeweaver.cli.__main__ import main

    main()
