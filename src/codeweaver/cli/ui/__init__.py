# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""User interface components for clean status display."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.cli.ui.error_handler import CLIErrorHandler
    from codeweaver.cli.ui.status_display import IndexingProgress, StatusDisplay, get_display


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CLIErrorHandler": (__spec__.parent, "error_handler"),
    "IndexingProgress": (__spec__.parent, "status_display"),
    "StatusDisplay": (__spec__.parent, "status_display"),
    "get_display": (__spec__.parent, "status_display"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = ("CLIErrorHandler", "IndexingProgress", "StatusDisplay", "get_display")


def __dir__() -> list[str]:
    return list(__all__)
