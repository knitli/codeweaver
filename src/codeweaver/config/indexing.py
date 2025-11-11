# sourcery skip: name-type-suffix
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Indexing configuration settings for CodeWeaver.

Settings for `codeweaver.engine.indexer.Indexer`, `codeweaver.engine.indexer.FileWatcher`, and related components.
"""

from __future__ import annotations

import contextlib
import logging
import re

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple, NotRequired, TypedDict

from fastmcp.server.middleware import MiddlewareContext
from pydantic import DirectoryPath, Field, FilePath, PrivateAttr, computed_field

from codeweaver.core.file_extensions import DEFAULT_EXCLUDED_DIRS, DEFAULT_EXCLUDED_EXTENSIONS
from codeweaver.core.types.models import BasedModel
from codeweaver.core.types.sentinel import UNSET, Unset


if TYPE_CHECKING:
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion

logger = logging.getLogger(__name__)

BRACKET_PATTERN: re.Pattern[str] = re.compile("\\[.+\\]")

_init: bool = True

# ===========================================================================
# *          Rignore and File Filter Settings
# ===========================================================================


class RignoreSettings(TypedDict, total=False):
    """Settings for the rignore library."""

    path: NotRequired[Path]
    ignore_hidden: NotRequired[bool]
    read_ignore_files: NotRequired[bool]
    read_parents_ignores: NotRequired[bool]
    read_git_ignore: NotRequired[bool]
    read_global_git_ignore: NotRequired[bool]
    read_git_exclude: NotRequired[bool]
    require_git: NotRequired[bool]
    additional_ignores: NotRequired[list[str]]
    additional_ignore_paths: NotRequired[list[str]]
    max_depth: NotRequired[int]
    max_filesize: NotRequired[int]
    follow_links: NotRequired[bool]
    case_insensitive: NotRequired[bool]
    same_file_system: NotRequired[bool]
    should_exclude_entry: NotRequired[Callable[[Path], bool]]


class IndexerSettingsDict(TypedDict, total=False):
    """A serialized `IndexerSettings` object."""

    forced_includes: NotRequired[frozenset[str | Path]]
    excludes: NotRequired[frozenset[str | Path]]
    excluded_extensions: NotRequired[frozenset[str]]
    use_gitignore: NotRequired[bool]
    use_other_ignore_files: NotRequired[bool]
    ignore_hidden: NotRequired[bool]
    index_storage_path: NotRequired[Path | None]
    include_github_dir: NotRequired[bool]
    include_tooling_dirs: NotRequired[bool]
    rignore_options: NotRequired[RignoreSettings | Unset]
    only_index_on_command: NotRequired[bool]


def _get_settings() -> CodeWeaverSettings | None:
    """Get the current CodeWeaver settings."""
    from codeweaver.config.settings import get_settings

    return get_settings()


def _get_project_name() -> str:
    """Get the current project name from settings."""
    # Avoid circular dependency: check if settings exist without triggering initialization
    if globals().get("_init", False) is False:
        settings = _get_settings()
        if settings is not None:
            with contextlib.suppress(AttributeError, ValueError):
                if (
                    hasattr(settings, "project_name")
                    and settings.project_name
                    and not isinstance(settings.project_name, Unset)
                ):
                    return settings.project_name
                if hasattr(settings, "project_path") and not isinstance(
                    settings.project_path, Unset
                ):
                    return settings.project_path.name
                if hasattr(settings, "project_name") and not isinstance(
                    settings.project_name, Unset
                ):
                    return settings.project_name
    with contextlib.suppress(Exception):
        from codeweaver.common.utils.git import get_project_path

        project_name = get_project_path().name
        globals()["_init"] = False
        return project_name
    return "your_project_name"


def get_storage_path() -> Path:
    """Get the default storage path for index data."""
    from codeweaver.common.utils import get_user_config_dir

    return Path(get_user_config_dir()) / f"{_get_project_name()}_index.json"


def _resolve_globs(path_string: str, repo_root: Path) -> set[Path]:
    """Resolve glob patterns in a path string."""
    if "*" in path_string or "?" in path_string or BRACKET_PATTERN.search(path_string):
        return set(repo_root.glob(path_string))
    if (path := (repo_root / path_string)) and path.exists():
        return {path} if path.is_file() else set(path.glob("**/*"))
    return set()


class FilteredPaths(NamedTuple):
    """Tuple of included and excluded file paths."""

    includes: frozenset[Path]
    excludes: frozenset[Path]

    @classmethod
    async def from_settings(cls, indexing: IndexerSettings, repo_root: Path) -> FilteredPaths:
        """Resolve included and excluded files based on filter settings.

        Resolves glob patterns for include and exclude paths, filtering includes for excluded extensions.

        If a file is specifically included in the `forced_includes`, it will not be excluded even if it matches an excluded extension or excludes.

        "Specifically included" means that it was defined directly in the `forced_includes`, and **not** as a glob pattern.

        This constructor is async so that it can resolve quietly in the background without slowing initialization.
        """
        settings = indexing.model_dump(mode="python")
        other_files: set[Path] = set()
        specifically_included_files = {
            Path(file)
            for file in settings.get("forced_includes", set())
            if file
            and "*" not in file
            and ("?" not in file)
            and Path(file).exists()
            and Path(file).is_file()
        }
        for include in settings.get("forced_includes", set()):
            other_files |= _resolve_globs(include, repo_root)
        for ext in settings.get("excluded_extensions", set()):
            if not ext:
                continue
            ext = ext.lstrip("*?[]")
            ext = ext if ext.startswith(".") else f".{ext}"
            other_files -= {
                file
                for file in other_files
                if file.suffix == ext and file not in specifically_included_files
            }
        excludes: set[Path] = set()
        excluded_files = settings.get("excluded_files", set())
        for exclude in excluded_files:
            if exclude:
                excludes |= _resolve_globs(exclude, repo_root)
        excludes |= specifically_included_files
        other_files -= {
            exclude for exclude in excludes if exclude not in specifically_included_files
        }
        other_files -= {None, Path(), Path("./"), Path("./.")}
        excludes -= {None, Path(), Path("./"), Path("./.")}
        return FilteredPaths(frozenset(other_files), frozenset(excludes))


class IndexerSettings(BasedModel):
    """Settings for indexing and file filtering.

    ## Path Resolution and Deconfliction

    Any configured paths or path patterns should be relative to the project root directory.

    CodeWeaver deconflicts paths in the following ways:
    - If a file is specifically defined in `forced_includes`, it will always be included, even if it matches an exclude pattern.
      - This doesn't apply if it is defined in `forced_includes` with a glob pattern that matches an excluded file (by extension or glob/path).
      - This also doesn't apply to directories.
    - Other filters like `use_gitignore`, `use_other_ignore_files`, and `ignore_hidden` will apply to all files **not in `forced_includes`**.
      - Files in `forced_includes`, including files defined from glob patterns, will *not* be filtered by these settings.
    - if `include_github_dir` is True (default), the glob `**/.github/**` will be added to `forced_includes`.
    - if `include_tooling_dirs` is True (default and recommended), common hidden tooling directories will be included *if they aren't .gitignored* (assuming `use_gitignore` is enabled, which is default). Any gitignored files will be excluded. This includes directories like `.vscode`, `.idea`, but also more specialized ones like `.moon`, `.husky`, and LLM-specific ones like `.codeweaver`, `.claude`, `.codex`, `.roo`, and more.
    """

    forced_includes: Annotated[
        frozenset[str | Path],
        Field(
            description="""Directories, files, or [glob patterns](https://docs.python.org/3/library/pathlib.html#pathlib-pattern-language) to include in search and indexing. This is a set of strings, so you can use glob patterns like `**/src/**` or `**/*.py` to include directories or files."""
        ),
    ] = frozenset()
    excludes: Annotated[
        frozenset[str | Path],
        Field(
            description="""Directories, files, or [glob patterns](https://docs.python.org/3/library/pathlib.html#pathlib-pattern-language) to exclude from search and indexing. This is a set of strings, so you can use glob patterns like `**/node_modules/**` or `**/*.log` to exclude directories or files. You don't need to provide gitignored paths here if `use_gitignore` is enabled (default)."""
        ),
    ] = DEFAULT_EXCLUDED_DIRS
    excluded_extensions: Annotated[
        frozenset[str], Field(description="""File extensions to exclude from search and indexing""")
    ] = DEFAULT_EXCLUDED_EXTENSIONS
    use_gitignore: Annotated[
        bool, Field(description="""Whether to use .gitignore for filtering. Enabled by default.""")
    ] = True
    use_other_ignore_files: Annotated[
        bool,
        Field(
            description="""Whether to read *other* ignore files (besides .gitignore) for filtering"""
        ),
    ] = False
    ignore_hidden: Annotated[
        bool,
        Field(description="""Whether to ignore hidden files (starting with .) for filtering"""),
    ] = True
    include_github_dir: Annotated[
        bool,
        Field(
            description="""Whether to include the .github directory in search and indexing. Because the .github directory is hidden, it wouldn't be included in default settings. Most people want to include it for work on GitHub Actions, workflows, and other GitHub-related files. Note: this setting will also include `.circleci` if present. Any subdirectories or files within `.github` or `.circleci` that are gitignored will still be excluded."""
        ),
    ] = True
    include_tooling_dirs: Annotated[
        bool,
        Field(
            description="""Whether to include common hidden tooling directories in search and indexing. This is enabled by default and recommended for most users. Still respects .gitignore rules, so any gitignored files will be excluded."""
        ),
    ] = True
    rignore_options: Annotated[
        RignoreSettings | Unset,
        Field(
            description="""Other kwargs to pass to `rignore`. See <https://pypi.org/project/rignore/>. By default we set max_filesize to 5MB and same_file_system to True."""
        ),
    ] = UNSET

    only_index_on_command: Annotated[
        bool,
        Field(
            description="""Disabled by default and usually **not recommended**. This setting disables background indexing, requiring you to manually trigger indexing by command or program call. CodeWeaver uses background indexing to ensure it always has an accurate view of the codebase, so disabling this can severely impact the quality of results. We expose this setting for troubleshooting, debugging, and some isolated use cases where codeweaver may be orchestrated externally or supplied with data from other sources."""
        ),
    ] = False

    _index_cache_dir: Annotated[
        Path | None,
        Field(
            description=rf"""\
            Path to store index data locally. The default is in your user configuration directory (like ~/.config/codeweaver/{_get_project_name()}_index.json or c:\Users\your_username\AppData\Roaming\codeweaver\your_project_name_index.json).  If not set, CodeWeaver will use the default path.

            Developer Note: We set the default lazily after initialization to avoid circular import issues. Internally, we use the `cache_dir` property to get the effective storage path. We recommend you do too if you need to programmatically access this value. We only keep this field public for user configuration.
            """,
            exclude=False,
            serialization_alias="index_storage_path",
            validation_alias="index_storage_path",
        ),
    ] = None

    _inc_exc_set: Annotated[bool, PrivateAttr()] = False

    def model_post_init(self, _context: MiddlewareContext[Any] | None = None, /) -> None:
        """Post-initialization processing."""
        self._inc_exc_set = False
        if self.include_github_dir:
            self.forced_includes |= {"**/.github/**"}
        if self.include_tooling_dirs:
            from codeweaver.core.file_extensions import (
                COMMON_LLM_TOOLING_PATHS,
                COMMON_TOOLING_PATHS,
            )

            file_endings = {
                ".json",
                ".yaml",
                ".yml",
                ".toml",
                ".lock",
                ".sbt",
                ".properties",
                ".js",
                ".ts",
                ".cmd",
                ".xml",
            }

            tooling_dirs = {
                path
                for tool in COMMON_TOOLING_PATHS
                for path in tool[1]
                if Path(path).name.startswith(".")
                or (str(path).startswith(".") and Path(path).suffix not in file_endings)
            } | {
                path
                for tool in COMMON_LLM_TOOLING_PATHS
                for path in tool[1]
                if Path(path).name.startswith(".")
                or (str(path).startswith(".") and Path(path).suffix not in file_endings)
            }
            self.forced_includes |= {f"**/{directory}/**" for directory in tooling_dirs}

    @computed_field
    @property
    def cache_dir(self) -> DirectoryPath:
        """Effective storage directory for index data."""
        path = self._index_cache_dir or get_storage_path()
        # Get the parent directory (cache_dir should be a directory, not a file)
        dir_path = path.parent
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    @computed_field
    @property
    def storage_file(self) -> FilePath:
        """Effective storage file path for index data."""
        if self._index_cache_dir:
            return self._index_cache_dir
        project_name = _get_project_name()
        self._index_cache_dir = self.cache_dir / f"{project_name}_index.json"
        return self._index_cache_dir

    @computed_field
    @property
    def inc_exc_set(self) -> bool:
        """Whether includes and excludes have been set."""
        return self._inc_exc_set

    @computed_field
    @property
    def checkpoint_file(self) -> FilePath:
        """Path to the checkpoint file for indexing progress."""
        return self.cache_dir / "indexing_checkpoint.json"

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types.aliases import FilteredKey

        return {
            FilteredKey("_index_cache_dir"): AnonymityConversion.HASH,
            FilteredKey("additional_ignores"): AnonymityConversion.COUNT,
            FilteredKey("cache_dir"): AnonymityConversion.HASH,
            FilteredKey("checkpoint_file"): AnonymityConversion.HASH,
            FilteredKey("excluded_extensions"): AnonymityConversion.COUNT,
            FilteredKey("excludes"): AnonymityConversion.COUNT,
            FilteredKey("forced_includes"): AnonymityConversion.COUNT,
            FilteredKey("storage_file"): AnonymityConversion.HASH,
        }

    async def set_inc_exc(self, project_path: Path) -> None:
        """Set that includes and excludes have been configured."""
        self.forced_includes, self.excludes = await FilteredPaths.from_settings(self, project_path)
        self._inc_exc_set = True

    def _as_settings(self, project_path: Path | None = None) -> RignoreSettings:
        """Convert self, either as an instance or as a serialized python dictionary, to kwargs for rignore."""
        rignore_settings = RignoreSettings(
            ignore_hidden=False, read_git_ignore=True, max_filesize=5_000_000, same_file_system=True
        ) | ({} if isinstance(self.rignore_options, Unset) else self.rignore_options)
        if project_path is None:
            # Try to get from global settings without triggering recursion
            _settings = _get_settings()
            if (
                _settings is not None
                and hasattr(_settings, "project_path")
                and not isinstance(_settings.project_path, Unset)
            ):
                project_path = _settings.project_path
            else:
                # Fallback to our method for trying to identify it directly
                # this finds the git root or uses the current working directory as a last resort
                from codeweaver.common.utils.git import get_project_path

                project_path = get_project_path()
        rignore_settings["path"] = project_path
        rignore_settings["ignore_hidden"] = bool(
            self.ignore_hidden and not self.include_github_dir and not self.include_tooling_dirs
        )
        rignore_settings["read_ignore_files"] = self.use_other_ignore_files
        rignore_settings["read_git_ignore"] = self.use_gitignore
        rignore_settings["additional_ignore_paths"] = [
            str(p) for p in self.excludes if not any(char for char in ("*?[]") if char in str(p))
        ]
        rignore_settings["additional_ignores"] = [
            str(p)
            for p in self.excludes
            if str(p) not in rignore_settings["additional_ignore_paths"]
        ]
        rignore_settings["should_exclude_entry"] = self.filter
        return RignoreSettings(rignore_settings)

    def construct_filter(self) -> Callable[[Path], bool]:
        """Constructs the filter function for rignore's `should_exclude_entry` parameter.

        Returns *True* for paths that should **not** be included (i.e., excluded paths).
        """

        def filter_func(settings: IndexerSettings, path: Path | str) -> bool:
            """Default filter function that respects forced includes and other settings."""
            path_obj = Path(path) if isinstance(path, str) else path
            if settings.ignore_hidden and (
                settings.include_github_dir or settings.include_tooling_dirs
            ):
                # We need to check for .github/ and tooling dirs first
                if settings.include_github_dir and (
                    path_obj.match("**/.github/**") or path_obj.match("**/.circleci/**")
                ):
                    return False
                if settings.include_tooling_dirs:
                    from codeweaver.core.file_extensions import (
                        COMMON_LLM_TOOLING_PATHS,
                        COMMON_TOOLING_PATHS,
                    )

                    # filter for tooling dirs that are hidden (i.e., start with .)
                    if {
                        p
                        for p in {
                            path
                            for tool in COMMON_TOOLING_PATHS
                            for path in tool[1]
                            if path_obj.match(f"**/{path}/**")
                        }
                        | {
                            path
                            for tool in COMMON_LLM_TOOLING_PATHS
                            for path in tool[1]
                            if path_obj.match(f"**/{path}/**")
                        }
                        if p
                        and (
                            (str(p).startswith(".") or p.name.startswith("."))
                            and ("." not in p.name[1:] or "." not in p.parts[0][1:])
                        )
                    }:
                        return False
                return True
            return False

        return partial(filter_func, self)

    @property
    def filter(self) -> Callable[[Path], bool]:
        """Cached property for the filter function."""
        return self.construct_filter()

    def to_settings(self) -> RignoreSettings:
        """Serialize to `RignoreSettings`."""
        return self._as_settings()


DefaultIndexerSettings = IndexerSettingsDict(
    IndexerSettings().model_dump(exclude_none=True, exclude_computed_fields=True)  # type: ignore
)

__all__ = ("DefaultIndexerSettings", "IndexerSettings")
