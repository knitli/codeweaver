# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The indexer service for managing and querying indexed data."""
# import contextlib

# with contextlib.suppress(ImportError):
# from watchfiles import watch
# TODO: implement file watcher
# TODO: register with providers registry

from collections.abc import Sequence
from pathlib import Path

import rignore
import watchfiles


type WatchfilesAwatch = watchfiles.awatch | None


class IgnoreFilter[Walker](watchfiles.DefaultFilter):
    ignore_dirs: Sequence[str]


class FileWatcher[WatchfilesAwatch]:
    """Main file watcher class. Wraps watchfiles.awatch."""

    _watch: watchfiles.awatch
    _allow_filter: rignore.Walker

    def __init__(self, base_path: Path) -> None:
        self._allow_filter = rignore.Walker(
            base_path,
            ignore_hidden=True,
            read_git_ignore=True,
            max_filesize=1024 * 1024 * 5,
            same_file_system=True,
        )

        self._watch = watchfiles.awatch(base_path)

    def default_filter(self, path: Path) -> bool:
        """Default filter function to exclude unwanted files."""


__all__ = ("FileWatcher",)
