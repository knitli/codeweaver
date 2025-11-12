"""File change filters based on file extensions."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar, Unpack, cast, overload

import rignore
import watchfiles

from watchfiles import Change, DefaultFilter

from codeweaver.config.indexing import RignoreSettings
from codeweaver.config.types import CodeWeaverSettingsDict
from codeweaver.core.file_extensions import (
    CODE_FILES_EXTENSIONS,
    CONFIG_FILE_LANGUAGES,
    DEFAULT_EXCLUDED_DIRS,
    DOC_FILES_EXTENSIONS,
)
from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage
from codeweaver.core.types import Unset


logger = logging.getLogger(__name__)


class ExtensionFilter(DefaultFilter):
    """Filter files by extension on top of the default directory/path ignores."""

    __slots__ = ("extensions",)

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
        super().__init__()

    def __call__(self, change: Change, path: str) -> bool:
        """Return True when path ends with allowed extensions and passes base filter."""
        return path.endswith(self.extensions) and super().__call__(change, path)


class DefaultExtensionFilter(ExtensionFilter):
    """Filter with a default excluded extension set augmented by provided ones."""

    __slots__ = ("_ignore_paths",)

    def __init__(
        self,
        extensions: Sequence[str] = cast(
            Sequence[str],
            {pair.ext for pair in CODE_FILES_EXTENSIONS if pair.language in CONFIG_FILE_LANGUAGES}
            | set(iter(ConfigLanguage.all_extensions())),
        ),
        ignore_paths: Sequence[str | Path] = cast(Sequence[str], set(DEFAULT_EXCLUDED_DIRS)),
    ) -> None:
        """Initialize the default extension filter with sensible defaults."""
        self._ignore_paths = ignore_paths
        self.extensions: tuple[str, ...] = (
            extensions if isinstance(extensions, tuple) else tuple(extensions)
        )
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

    __slots__: ClassVar[tuple[str, ...]] = (
        *watchfiles.DefaultFilter.__slots__,
        "_walker",
        "_allowed_complete",
        "_allowed",
    )

    _walker: Walker
    _allowed: set[Path]
    _allowed_complete: bool

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
                raise ValueError(
                    "You must provide either settings or a walker. We need to know what to ignore!"
                )
            if base_path is None:
                raise ValueError(
                    "You must provide a base path if you don't provide a walker instance."
                )
            self._walker = rignore.walk(path=base_path, **cast(dict[str, Any], settings))  # type: ignore
        self._allowed = set()
        self._allowed_complete = False
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
        # If we have a complete set of allowed paths, we can use it
        if self._allowed_complete and (not is_new or path in self._allowed):
            if delete and path in self._allowed:
                self._allowed.remove(path)
                return True
            return False if delete else path in self._allowed
        # Otherwise, we need to walk until we find it or exhaust the walker
        if delete:
            with contextlib.suppress(KeyError):
                self._allowed.remove(path)
                return True
            # It's either not in allowed or it doesn't matter because we're deleting
            return False
        try:
            # Iterate through walker until we find the path or exhaust it
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
        cls, settings: CodeWeaverSettingsDict | None = None
    ) -> IgnoreFilter[rignore.Walker]:
        """Create an IgnoreFilter instance from settings."""
        # we actually need the full object here
        from codeweaver.common.utils.git import get_project_path
        from codeweaver.config.indexing import DefaultIndexerSettings, IndexerSettings
        from codeweaver.config.settings import get_settings

        settings = settings or get_settings()
        index_settings = (
            settings.indexing
            if isinstance(settings.indexing, IndexerSettings)
            else IndexerSettings.model_validate(DefaultIndexerSettings)
        )
        if not index_settings.inc_exc_set:
            # Check if there's already a running event loop
            try:
                asyncio.get_running_loop()
                # If we're here, there's a running loop
                # We can't await here since from_settings is not async, so skip for now
                logger.debug(
                    "Cannot set inc_exc in Indexer.from_settings: already in async context. Will be set lazily when indexer is used."
                )
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                _ = asyncio.run(
                    index_settings.set_inc_exc(
                        get_project_path()
                        if isinstance(settings.project_path, Unset)
                        else settings.project_path
                    )
                )
        walker = rignore.Walker(
            **(index_settings.to_settings())  # type: ignore
        )
        return cls(
            walker=walker,
            base_path=get_project_path()
            if isinstance(settings.project_path, Unset)
            else settings.project_path,
        )

    @property
    def walker(self) -> rignore.Walker:
        """Return the underlying rignore walker used by this filter."""
        return self._walker


__all__ = (
    "CodeFilter",
    "ConfigFilter",
    "DefaultExtensionFilter",
    "DefaultFilter",
    "DocsFilter",
    "ExtensionFilter",
    "IgnoreFilter",
)
