# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The indexer service for managing and querying indexed data."""
# import contextlib

# with contextlib.suppress(ImportError):
# from watchfiles import watch
# TODO: register with providers registry

from __future__ import annotations

import contextlib
import logging

from collections.abc import Callable, Sequence
from pathlib import Path
from time import sleep
from typing import Annotated, Any, ClassVar, Unpack, cast, overload

import rignore
import watchfiles

from pydantic import PrivateAttr
from watchfiles.main import Change, FileChange

from codeweaver.config.settings import CodeWeaverSettingsDict, RignoreSettings
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.file_extensions import (
    CODE_FILES_EXTENSIONS,
    CONFIG_FILE_LANGUAGES,
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_EXTENSIONS,
    DOC_FILES_EXTENSIONS,
)
from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage
from codeweaver.core.stores import BlakeStore
from codeweaver.core.types.dictview import DictView


logger = logging.getLogger(__name__)


class DefaultFilter(watchfiles.DefaultFilter):
    """A default filter that ignores common unwanted files and directories."""

    def __init__(
        self,
        *,
        ignore_dirs: Sequence[str | Path] = cast(Sequence[str], DEFAULT_EXCLUDED_DIRS),
        ignore_entity_patterns: Sequence[str] | None = None,
        ignore_paths: Sequence[str | Path] | None = None,
    ) -> None:
        """A default filter that ignores common unwanted files and directories."""
        super().__init__(
            ignore_dirs=ignore_dirs,  # type: ignore
            ignore_entity_patterns=ignore_entity_patterns,
            ignore_paths=ignore_paths,
        )


class ExtensionFilter(DefaultFilter):
    """Filter files by extension on top of the default directory/path ignores."""

    def __init__(
        self,
        extensions: Sequence[str],
        ignore_paths: Sequence[str | Path] = cast(Sequence[str], set(DEFAULT_EXCLUDED_DIRS)),
    ) -> None:
        """Initialize the extension filter.

        Args:
            extensions: Extensions (with dot) to include.
            ignore_paths: Additional paths/directories to exclude.
        """
        self._ignore_paths = ignore_paths
        self.extensions: tuple[str, ...] = (
            extensions if isinstance(extensions, tuple) else tuple(extensions)
        )
        self.__slots__ = (*super().__slots__, "extensions")
        super().__init__()

    def __call__(self, change: Change, path: str) -> bool:
        """Return True when path ends with allowed extensions and passes base filter."""
        return path.endswith(self.extensions) and super().__call__(change, path)


class DefaultExtensionFilter(ExtensionFilter):
    """Filter with a default excluded extension set augmented by provided ones."""

    def __init__(
        self,
        extensions: Sequence[str] = cast(Sequence[str], DEFAULT_EXCLUDED_EXTENSIONS),
        ignore_paths: Sequence[str | Path] = cast(Sequence[str], set(DEFAULT_EXCLUDED_DIRS)),
    ) -> None:
        """Initialize the default extension filter with sensible defaults."""
        self._ignore_paths = ignore_paths
        self.extensions: tuple[str, ...] = (
            extensions if isinstance(extensions, tuple) else tuple(extensions)
        )
        self.__slots__ = (*super().__slots__, "extensions", "_ignore_paths")
        super().__init__(extensions=extensions, ignore_paths=ignore_paths)

    def __call__(self, change: Change, path: str) -> bool:
        """Return True when path ends with allowed extensions and passes base filter."""
        return path.endswith(self.extensions) and super().__call__(change, path)


CodeFilter = DefaultExtensionFilter(
    tuple(pair.ext for pair in CODE_FILES_EXTENSIONS if pair.language not in CONFIG_FILE_LANGUAGES)
    + tuple(SemanticSearchLanguage.code_extensions())
)

ConfigFilter = DefaultExtensionFilter(
    cast(
        Sequence[str],
        {pair.ext for pair in CODE_FILES_EXTENSIONS if pair.language in CONFIG_FILE_LANGUAGES}
        | set(iter(ConfigLanguage.all_extensions())),
    )
)

DocsFilter = DefaultExtensionFilter(tuple(pair.ext for pair in DOC_FILES_EXTENSIONS))


class IgnoreFilter[Walker: rignore.Walker](watchfiles.DefaultFilter):
    """
    A filter that uses rignore to exclude files based on .gitignore and other rules.

    `IgnoreFilter` can be initialized with either:
    - An `rignore.Walker` instance, which is a pre-configured walker that
      applies ignore rules.
    - A `base_path` and `settings` dictionary to create a new `rignore.Walker`.

    The filter checks if a file should be included based on the rules defined
    in the walker. It caches results to avoid redundant checks for previously
    seen paths.
    """

    _walker: Walker
    _allowed: ClassVar[set[Path]] = set()
    _allowed_complete: bool = False

    @overload
    def __init__(self, *, base_path: None, settings: None, walker: rignore.Walker) -> None: ...
    @overload
    def __init__(
        self, *, base_path: Path, walker: None = None, **settings: Unpack[RignoreSettings]
    ) -> None: ...
    def __init__(  # type: ignore
        self,
        *,
        base_path: Path | None = None,
        walker: Walker | None = None,
        settings: RignoreSettings | None = None,
    ) -> None:
        """Initialize the IgnoreFilter with either rignore settings or a pre-configured walker."""
        self.__slots__ = (*super().__slots__, "_walker", "_allowed_complete", "_allowed")
        if not walker and not (settings and base_path):
            self = type(self).from_settings()
            return
        if walker and settings:
            # favor walker if both are provided
            logger.warning("Both settings and walker provided; using walker.")
        if walker:
            self._walker = walker
        else:
            if settings is None:
                raise ValueError("You must provide either settings or a walker.")
            if base_path is None:
                raise ValueError("Base path must be provided if walker is not.")
            if (
                (filter_present := settings.pop("filter", None))
                and callable(filter_present)
                and settings.get("should_exclude_entry") is None
            ) or not callable(settings.get("should_exclude_entry")):
                settings |= {"should_exclude_entry": filter_present}  # type: ignore
            self._walker = rignore.walk(path=base_path, **cast(dict[str, Any], settings))  # type: ignore
        super().__init__()

    def __call__(self, change: Change, path: str) -> bool:
        """Determine if a file should be included based on rignore rules."""
        p = Path(path)
        match change:
            case Change.deleted:
                return self._walkable(p, is_new=False, delete=True)
            case Change.added:
                return self._walkable(p, is_new=True, delete=False)
            case Change.modified:
                return self._walkable(p, is_new=False, delete=False)

    def _walkable(self, path: Path, *, is_new: bool = False, delete: bool = False) -> bool:
        """Check if a path is walkable (not ignored) using the rignore walker.

        Stores previously seen paths to avoid redundant checks.

        This method still returns True for deleted files to allow cleanup of indexed data.
        """
        if self._allowed_complete and (not is_new or path in self._allowed):
            if delete and path in self._allowed:
                self._allowed.remove(path)
                return True
            return False if delete else path in self._allowed
        if delete:
            with contextlib.suppress(KeyError):
                self._allowed.remove(path)
                return True
            # It's either not in allowed or it doesn't matter because we're deleting
            return False
        try:
            for p in self._walker:
                # it's a set, so we add regardless of whether it's already there
                self._allowed.add(p)
                if p and p.samefile(str(path)):
                    return True
        except StopIteration:
            self._allowed_complete = True
        return False

    @classmethod
    def from_settings(
        cls, settings: DictView[CodeWeaverSettingsDict] | None = None
    ) -> IgnoreFilter[rignore.Walker]:
        """Create an IgnoreFilter instance from settings."""
        from codeweaver.config.settings import get_settings_map

        settings = settings or get_settings_map()
        filter_settings = settings["filter_settings"].to_settings()
        return cls(base_path=None, settings=None, walker=rignore.walk(**filter_settings))

    @property
    def walker(self) -> rignore.Walker:
        """Return the underlying rignore walker used by this filter."""
        return self._walker


class Indexer:
    """Main indexer class. Wraps a vector store and parsers."""

    _store: BlakeStore[DiscoveredFile] = PrivateAttr()
    _parsers: Annotated[Sequence[Callable[[Path], Any]], PrivateAttr(default_factory=list)]
    _walker: rignore.Walker | None = PrivateAttr(default=None)

    def __init__(
        self, walker: rignore.Walker | None = None, store: BlakeStore[DiscoveredFile] | None = None
    ) -> None:
        """Initialize the Indexer."""
        self._parsers = []
        self._store = store or BlakeStore[DiscoveredFile](_value_type=DiscoveredFile)
        self._walker = walker

    async def index(self, change: FileChange) -> None:
        """Index a single file based on a watchfiles change event.

        Handles added, modified, and deleted file events. For add/modify, the file is hashed and
        stored if it's an indexable file type. For delete, any indexed entries matching the path are removed.
        """
        try:
            change_type, path_str = change
        except Exception:
            logger.exception("Invalid FileChange tuple received: %r", change)
            return

        path = Path(path_str)

        match change_type:
            case Change.added | Change.modified:
                # Skip non-files quickly
                if not path.exists() or not path.is_file():
                    return
                # Only index files we recognize (code/config/docs) via DiscoveredFile
                discovered_file = DiscoveredFile.from_path(path)
                if not discovered_file or not discovered_file.is_text:
                    return
                # Remove any prior entries for this path (hash may have changed)
                _ = self._remove_path(path)
                # Persist using the discovered file's own content hash as the key
                self._store.set(discovered_file.file_hash, discovered_file)
                logger.debug(
                    "Indexed %s [%s] (%s bytes)",
                    discovered_file.path,
                    discovered_file.ext_kind,
                    discovered_file.size,
                )
            case Change.deleted:
                if removed := self._remove_path(path):
                    logger.debug("Removed %d index entries for deleted path %s", removed, path)
            case _:
                logger.debug("Unhandled change type %s for %s", change_type, path)

    # ---- public helpers ----
    def prime_index(self) -> int:
        """Perform an initial indexing pass using the configured rignore walker.

        Returns the number of files indexed. If no walker was provided, does nothing.
        """
        if not self._walker:
            return 0

        count = 0
        try:
            with contextlib.suppress(StopIteration):
                for p in self._walker:
                    # rignore returns absolute paths typically; ensure it's a file
                    if not p or not p.is_file():
                        continue
                    if discovered_file := DiscoveredFile.from_path(p):
                        _ = self._remove_path(discovered_file.path)
                        self._store.set(discovered_file.file_hash, discovered_file)
                        count += 1
        except Exception:
            logger.exception("Failure during initial indexing pass")
        return count

    # ---- internal helpers ----
    def _remove_path(self, path: Path) -> int:
        """Remove any entries in the store that match the given path. Returns number removed."""
        to_delete: list[Any] = []
        for key, discovered_file in list(self._store.items()):
            try:
                if discovered_file.path.samefile(path):
                    to_delete.append(key)
            except Exception:
                # defensive: malformed entry shouldn't break cleanup
                logger.exception("Error checking stored item for deletion")
                continue
        for key in to_delete:
            self._store.delete(key)
        return len(to_delete)

    @staticmethod
    def keep_alive(alive_time: float = 5000) -> None:
        """A long-lived no-op function suitable as the run target for arun_process.

        We keep the child process alive so arun_process can signal and restart it,
        but all indexing happens in the callback on the main process.
        """
        try:
            while True:
                sleep(alive_time)
        except KeyboardInterrupt:
            # allow graceful stop
            return

    @property
    def is_empty(self) -> bool:
        """Check if the indexer is empty."""
        return len(self._store) == 0


class FileWatcher:
    """Main file watcher class. Wraps watchfiles.awatch."""

    _indexer: Indexer

    def __init__(
        self,
        *paths: str | Path,
        handler: Callable[[set[FileChange]], Any] | None = None,
        file_filter: watchfiles.BaseFilter | None = None,
        walker: rignore.Walker | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the FileWatcher with a path and an optional filter."""
        # If an IgnoreFilter is provided, extract its rignore walker for initial indexing.
        if walker is None and isinstance(file_filter, IgnoreFilter):
            walker = file_filter.walker
        self._indexer = Indexer(walker=walker)
        ff = cast(watchfiles.BaseFilter | None, file_filter)
        self.file_filter = ff
        self.paths = paths
        self.handler = handler or self._default_handler
        watch_kwargs: dict[str, Any] = (
            {
                # Keep a child process alive; do NOT perform indexing in the child process
                # so that state remains in the main process.
                "target": Indexer.keep_alive,
                "target_type": "function",
                "callback": self._default_handler,
                "watch_filter": ff,
                "grace_period": 20,
                "debounce": 200_000,  # milliseconds - we want to avoid rapid re-indexing but not let things go stale, either.
                "step": 15_000,  # milliseconds -- how long to wait for more changes before yielding on changes
                "ignore_permission_denied": True,
            }
            | kwargs
        )
        watch_kwargs["recursive"] = True  # we always want recursive watching
        try:
            # Perform a one-time initial indexing pass if we have a walker
            if initial_count := self._indexer.prime_index():
                logger.info("Initial indexing complete: %d files indexed", initial_count)
            self.watcher = watchfiles.arun_process(*self.paths, **watch_kwargs)
        except Exception:
            logger.exception("Something happened...")
            raise

    async def _default_handler(self, changes: set[FileChange]) -> None:
        """Default may be a strong characterization -- 'placeholder' handler."""
        for change in changes:
            logger.info("File change detected.", extra={"change": change})
            await self._indexer.index(change)

    async def run(self) -> int:
        """Run the file watcher until cancelled. Returns the reload count from arun_process."""
        return await self.watcher  # type: ignore[no-any-return]


__all__ = (
    "CodeFilter",
    "ConfigFilter",
    "DefaultFilter",
    "DocsFilter",
    "ExtensionFilter",
    "FileWatcher",
    "IgnoreFilter",
    "Indexer",
)
