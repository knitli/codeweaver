# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""User interface components for clean status display."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.cli.ui.error_handler import CLIErrorHandler
    from codeweaver.cli.ui.interaction import (
        RichUserInteraction,
        UserInteraction,
        UserInteractionDep,
    )
    from codeweaver.cli.ui.status_display import (
        AtomicAwareBarColumn,
        AtomicAwareCountColumn,
        AtomicAwarePercentColumn,
        AtomicAwareSeparatorColumn,
        IndexingProgress,
        StatusDisplay,
        get_display,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AtomicAwareBarColumn": (__spec__.parent, "status_display"),
    "AtomicAwareCountColumn": (__spec__.parent, "status_display"),
    "AtomicAwarePercentColumn": (__spec__.parent, "status_display"),
    "AtomicAwareSeparatorColumn": (__spec__.parent, "status_display"),
    "IndexingProgress": (__spec__.parent, "status_display"),
    "StatusDisplay": (__spec__.parent, "status_display"),
    "CLIErrorHandler": (__spec__.parent, "error_handler"),
    "handle_keyboard_interrupt_gracefully": (__spec__.parent, "error_handler"),
    "get_display": (__spec__.parent, "status_display"),
    "RichUserInteraction": (__spec__.parent, "interaction"),
    "UserInteraction": (__spec__.parent, "interaction"),
    "UserInteractionDep": (__spec__.parent, "interaction"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "AtomicAwareBarColumn",
    "AtomicAwareCountColumn",
    "AtomicAwarePercentColumn",
    "AtomicAwareSeparatorColumn",
    "CLIErrorHandler",
    "IndexingProgress",
    "RichUserInteraction",
    "StatusDisplay",
    "UserInteraction",
    "UserInteractionDep",
    "get_display",
    "handle_keyboard_interrupt_gracefully",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
