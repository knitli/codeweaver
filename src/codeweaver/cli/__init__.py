# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CLI interface for CodeWeaver."""

from __future__ import annotations


if __name__ == "__main__":
    from codeweaver.cli.__main__ import main

    main()

# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.cli.__main__ import ROOT_PACKAGE
    from codeweaver.cli.dependencies import CodeWeaverSettingsType, setup_cli_di
    from codeweaver.cli.ui import MappingProxyType
    from codeweaver.cli.ui.error_handler import CLIErrorHandler, CodeWeaverError
    from codeweaver.cli.ui.status_display import (
        AtomicAwareBarColumn,
        AtomicAwareCountColumn,
        AtomicAwarePercentColumn,
        AtomicAwareSeparatorColumn,
        IndexingProgress,
        StatusDisplay,
    )
    from codeweaver.cli.utils import check_provider_package_available

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ROOT_PACKAGE": (__spec__.parent, "__main__"),
    "AtomicAwareBarColumn": (__spec__.parent, "ui.status_display"),
    "AtomicAwareCountColumn": (__spec__.parent, "ui.status_display"),
    "AtomicAwarePercentColumn": (__spec__.parent, "ui.status_display"),
    "AtomicAwareSeparatorColumn": (__spec__.parent, "ui.status_display"),
    "CodeWeaverError": (__spec__.parent, "ui.error_handler"),
    "CodeWeaverSettingsType": (__spec__.parent, "dependencies"),
    "IndexingProgress": (__spec__.parent, "ui.status_display"),
    "MappingProxyType": (__spec__.parent, "ui"),
    "StatusDisplay": (__spec__.parent, "ui.status_display"),
    "check_provider_package_available": (__spec__.parent, "utils"),
    "CLIErrorHandler": (__spec__.parent, "ui.error_handler"),
    "setup_cli_di": (__spec__.parent, "dependencies"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "ROOT_PACKAGE",
    "AtomicAwareBarColumn",
    "AtomicAwareCountColumn",
    "AtomicAwarePercentColumn",
    "AtomicAwareSeparatorColumn",
    "CLIErrorHandler",
    "CodeWeaverError",
    "CodeWeaverSettingsType",
    "IndexingProgress",
    "MappingProxyType",
    "StatusDisplay",
    "check_provider_package_available",
    "setup_cli_di",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
