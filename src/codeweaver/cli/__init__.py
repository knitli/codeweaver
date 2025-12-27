# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CLI interface for CodeWeaver."""

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    # Import everything for IDE and type checker support
    # These imports are never executed at runtime, only during type checking
    from codeweaver.cli.__main__ import app, console, main
    from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CLIErrorHandler": (__spec__.parent, "ui"),
    "StatusDisplay": (__spec__.parent, "ui"),
    "app": (__spec__.parent, "__main__"),
    "console": (__spec__.parent, "__main__"),
    "get_display": (__spec__.parent, "ui"),
    "main": (__spec__.parent, "__main__"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = ("CLIErrorHandler", "StatusDisplay", "app", "console", "get_display", "main")


def __dir__() -> list[str]:
    return list(__all__)


if __name__ == "__main__":
    from codeweaver.cli.__main__ import main

    main()
