# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
The `watch` package wraps the `watchfiles` library to provide file system monitoring
capabilities integrated with CodeWeaver's indexing engine. It includes classes for
watching files, logging watch events, and tracking indexing progress using Rich.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.engine.watcher._logging import WatchfilesLogManager
    from codeweaver.engine.watcher.types import FileChange, WatchfilesArgs
    from codeweaver.engine.watcher.watch_filters import (
        CodeFilter,
        ConfigFilter,
        DefaultExtensionFilter,
        DefaultFilter,
        DocsFilter,
        ExtensionFilter,
        IgnoreFilter,
    )
    from codeweaver.engine.watcher.watcher import FileWatcher

parent = __spec__.parent or "codeweaver.engine.watcher"

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "WatchfilesLogManager": (parent, "_logging"),
    "FileChange": (parent, "types"),
    "WatchfilesArgs": (parent, "types"),
    "CodeFilter": (parent, "watch_filters"),
    "ConfigFilter": (parent, "watch_filters"),
    "DefaultExtensionFilter": (parent, "watch_filters"),
    "DocsFilter": (parent, "watch_filters"),
    "DefaultFilter": (parent, "watch_filters"),
    "ExtensionFilter": (parent, "watch_filters"),
    "IgnoreFilter": (parent, "watch_filters"),
    "FileWatcher": (parent, "watcher"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "CodeFilter",
    "ConfigFilter",
    "DefaultExtensionFilter",
    "DefaultFilter",
    "DocsFilter",
    "ExtensionFilter",
    "FileChange",
    "FileWatcher",
    "IgnoreFilter",
    "WatchfilesArgs",
    "WatchfilesLogManager",
)


def __dir__() -> list[str]:
    return list(__all__)
