# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
The `watch` package wraps the `watchfiles` library to provide file system monitoring
capabilities integrated with CodeWeaver's indexing engine. It includes classes for
watching files, logging watch events, and tracking indexing progress using Rich.
"""

from __future__ import annotations


parent = __spec__.parent or "codeweaver.engine.watcher"

# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.engine.watcher._logging import (
        WatchfilesLogManager,
        normalize_and_validate_patterns,
    )
    from codeweaver.engine.watcher.progress import IndexingProgressUI
    from codeweaver.engine.watcher.types import FileChange, WatchfilesArgs
    from codeweaver.engine.watcher.watch_filters import (
        DefaultExtensionFilter,
        DefaultFilter,
        ExtensionFilter,
        IgnoreFilter,
        ResolvedProjectPathDep,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DefaultExtensionFilter": (__spec__.parent, "watch_filters"),
    "DefaultFilter": (__spec__.parent, "watch_filters"),
    "ExtensionFilter": (__spec__.parent, "watch_filters"),
    "IgnoreFilter": (__spec__.parent, "watch_filters"),
    "ResolvedProjectPathDep": (__spec__.parent, "watch_filters"),
    "WatchfilesArgs": (__spec__.parent, "types"),
    "WatchfilesLogManager": (__spec__.parent, "_logging"),
    "IndexingProgressUI": (__spec__.parent, "progress"),
    "normalize_and_validate_patterns": (__spec__.parent, "_logging"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "DefaultExtensionFilter",
    "DefaultFilter",
    "ExtensionFilter",
    "FileChange",
    "IgnoreFilter",
    "IndexingProgressUI",
    "MappingProxyType",
    "ResolvedProjectPathDep",
    "WatchfilesArgs",
    "WatchfilesLogManager",
    "normalize_and_validate_patterns",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
