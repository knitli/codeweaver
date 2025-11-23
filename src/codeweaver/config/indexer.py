# sourcery skip: name-type-suffix
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Indexing configuration settings for CodeWeaver.

Settings for `codeweaver.engine.indexer.indexer.Indexer`, `codeweaver.engine.watcher.watcher.FileWatcher`, and related components.
"""

from __future__ import annotations

import contextlib
import logging
import re

from collections.abc import Callable
from functools import cache, cached_property
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    NamedTuple,
    NotRequired,
    TypedDict,
    cast,
    overload,
)

from fastmcp.server.middleware import MiddlewareContext
from pydantic import DirectoryPath, Field, FilePath, PrivateAttr, computed_field

from codeweaver.core.file_extensions import DEFAULT_EXCLUDED_DIRS, DEFAULT_EXCLUDED_EXTENSIONS
from codeweaver.core.types.models import BasedModel
from codeweaver.core.types.sentinel import UNSET, Unset


if TYPE_CHECKING:
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types import DictView
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion

logger = logging.getLogger(__name__)

BRACKET_PATTERN: re.Pattern[str] = re.compile("\\[.+\\]")

_init: bool = True

# ===========================================================================
# *          Rignore and File Filter Settings
# ===========================================================================


class RignoreSettings(TypedDict, total=False):
    """Settings for the rignore library.

    Maps to parameters of rignore.Walker. See https://pypi.org/project/rignore/

    Key parameters:
    - path: Root directory to walk
    - ignore_hidden: If True, ignore hidden files/directories (starting with .)
    - read_git_ignore: If True, respect .gitignore files
    - read_ignore_files: If True, respect .ignore files (ripgrep-style)
    - overrides: Glob patterns for whitelist/ignore. Plain patterns whitelist,
                 patterns starting with ! ignore (e.g., "**/.github/**" whitelists,
                 "!**/node_modules/**" ignores)
    - should_exclude_entry: Callback returning True to exclude a path
    """

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
    overrides: NotRequired[list[str]]
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
    _index_cache_dir: NotRequired[Path | None]
    include_github_dir: NotRequired[bool]
    include_tooling_dirs: NotRequired[bool]
    rignore_options: NotRequired[RignoreSettings | Unset]
    only_index_on_command: NotRequired[bool]


@overload
def _get_settings(*, view: Literal[False]) -> CodeWeaverSettings | None: ...
@overload
def _get_settings(*, view: Literal[True]) -> DictView[CodeWeaverSettingsDict] | None: ...
def _get_settings(
    *, view: bool = False
) -> CodeWeaverSettings | DictView[CodeWeaverSettingsDict] | None:
    """Get the current CodeWeaver settings."""
    if view:
        from codeweaver.config.settings import get_settings_map

        return get_settings_map()
    from codeweaver.config.settings import get_settings

    return get_settings()


def _get_project_name() -> str:
    """Get the current project name from settings."""
    # Avoid circular dependency: check if settings exist without triggering initialization
    if globals().get("_init", False) is False and (settings := _get_settings(view=False)):
        with contextlib.suppress(AttributeError, ValueError):
            if (
                hasattr(settings, "project_name")
                and settings.project_name
                and not isinstance(settings.project_name, Unset)
            ):
                return cast(str, settings.project_name)
            if hasattr(settings, "project_path") and not isinstance(settings.project_path, Unset):
                return cast(Path, settings.project_path).name
            if hasattr(settings, "project_name") and not isinstance(settings.project_name, Unset):
                return cast(str, settings.project_name)
    with contextlib.suppress(Exception):
        from codeweaver.common.utils.git import get_project_path

        project_name = get_project_path().name
        globals()["_init"] = False
        return project_name
    return "your_project_name"


def get_storage_path() -> DirectoryPath:
    """Get the default storage directory for index and checkpoint data."""
    from codeweaver.common.utils import get_user_config_dir

    return Path(get_user_config_dir()) / ".indexes"


def _resolve_globs(path_string: str, repo_root: Path) -> set[Path]:
    """Resolve glob patterns in a path string."""
    if "*" in path_string or "?" in path_string or BRACKET_PATTERN.search(path_string):
        return set(repo_root.glob(path_string))
    if (path := (repo_root / path_string)) and path.exists():
        return {path} if path.is_file() else set(path.glob("**/*"))
    return set()


@cache
def _get_known_extensions() -> set[str]:
    """Get a set of known file extensions for the watcher."""
    from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage
    from codeweaver.core.metadata import get_ext_lang_pairs

    return (
        {ext.ext.lower() for ext in get_ext_lang_pairs()}
        | {ext.lower() for lang in SemanticSearchLanguage for ext in lang.extensions}  # ty: ignore[not-iterable]
        | {ext.lower() for lang in ConfigLanguage for ext in lang.extensions}
    )


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
        excluded_files = settings.get("excludes", set())
        for exclude in excluded_files:
            if exclude:
                excludes |= _resolve_globs(exclude, repo_root)
        excludes -= specifically_included_files
        other_files -= excludes
        other_files -= {None, Path(), Path("./"), Path("./.")}
        excludes -= {None, Path(), Path("./"), Path("./.")}
        return FilteredPaths(frozenset(other_files), frozenset(excludes))


class IndexerSettings(BasedModel):
    """Settings for indexing and file filtering.

    ## How File Filtering Works

    CodeWeaver uses the `rignore` library (a Python wrapper for Rust's `ignore` crate) to
    efficiently walk directories while respecting various ignore rules. The filtering
    happens in this order:

    1. **Override patterns** (highest priority): Whitelist patterns for tooling dirs,
       ignore patterns for excluded dirs (note: any positive whitelist here -- meaning not beginning with a `!` -- is treated as an *only* -- files not matching them will be ignored entirely.)
    2. **Ignore files**: .gitignore, .ignore, .git/info/exclude, global gitignore
    3. **Hidden files**: Files/dirs starting with . are ignored by default
    4. **Extension filter**: Only files with known extensions are included

    ## Default Behavior

    With default settings, CodeWeaver will:
    - Respect .gitignore files (including parent directories and global gitignore)
    - Ignore hidden files and directories
    - Include .github, .circleci, and common tooling dirs (.vscode, .claude, etc.)
    - Exclude common build/cache dirs (node_modules, __pycache__, .git, etc.)
    - Only index files with known extensions (~360 supported file types)

    ## Key Settings

    - `use_gitignore`: Respect .gitignore rules (default: True)
    - `ignore_hidden`: Ignore hidden files/dirs (default: True)
    - `include_tooling_dirs`: Whitelist common tooling dirs despite ignore_hidden (default: True)
    - `excludes`: Additional directories to exclude (default: common build/cache dirs)
    - `excluded_extensions`: File extensions to exclude (default: binaries, media, etc.)

    ## Path Resolution

    All paths should be relative to the project root. CodeWeaver deconflicts paths:
    - Files in `forced_includes` are always included, even if they match excludes
    - Tooling directories are whitelisted via overrides, still respecting .gitignore
    - The `excludes` list is converted to ignore patterns
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
        bool,
        Field(
            description="""Whether to use .gitignore for filtering. Enabled by default and strongly recommended. Disabling would cause CodeWeaver to index your entire git history, including all ignored files, which is usually not desired. We can't think of a use case where you'd want this disabled, but it's here if you need it."""
        ),
    ] = True
    use_other_ignore_files: Annotated[
        bool,
        Field(
            description="""Whether to read any `.ignore` files (besides .gitignore) for filtering"""
        ),
    ] = True
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
            description="""Other kwargs to pass to `rignore`. See <https://pypi.org/project/rignore/>. By default we set same_file_system to True."""
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
            description=r"""\
            Path to store index data locally. The default is in your user configuration directory (like ~/.config/codeweaver/.indexes or c:\Users\your_username\AppData\Roaming\codeweaver\.indexes\).  If not set, CodeWeaver will use the default path.

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
            self.forced_includes |= {"**/.github/**", "**/.circleci/**"}
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
        # with the validation and serialization alias, `_index_cache_dir` maps to `_index_cache_dir`
        if not self._index_cache_dir:
            path = self._index_cache_dir
            # Get the parent directory (cache_dir should be a directory, not a file)
            dir_path = path.parent if path and path.is_file() else path or get_storage_path()
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
            self._index_cache_dir = dir_path
        return self._index_cache_dir

    @computed_field
    @property
    def storage_file(self) -> FilePath:
        """Effective storage file path for index data."""
        project_name = _get_project_name()
        if self._index_cache_dir:
            return self._index_cache_dir / f"{project_name}_index.json"
        return self.cache_dir / f"{project_name}_index.json"

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
        """Convert IndexerSettings to kwargs for rignore.Walker.

        This method configures rignore to:
        1. Include hidden files (ignore_hidden=False) so we can selectively include tooling dirs
        2. Exclude unwanted hidden directories via override ignore patterns
        3. Exclude configured directories via override ignore patterns
        4. Filter to only known file extensions via should_exclude_entry
        5. Filter hidden files not in tooling directories via should_exclude_entry

        Note: We set ignore_hidden=False because ignore_hidden=True would prevent the
        walker from even visiting tooling directories like .github and .vscode. Instead,
        we use the filter to exclude unwanted hidden files/directories.
        """
        rignore_settings = RignoreSettings(
            ignore_hidden=False,  # Let walker visit hidden dirs, filter handles exclusion
            read_git_ignore=True,
            # NOTE: We intentionally don't set max_filesize here because it causes
            # rignore to bypass the filter callback for files. Users can set it via
            # rignore_options if they need filesize filtering (at the cost of extension
            # filtering not working properly).
            same_file_system=True,
        ) | ({} if isinstance(self.rignore_options, Unset) else self.rignore_options)

        if project_path is None:
            # Try to get from global settings without triggering recursion
            _settings = _get_settings(view=True)
            if (
                _settings is not None
                and _settings["project_path"]
                and not isinstance(_settings["project_path"], Unset)
            ):
                project_path = _settings["project_path"]
            else:
                # Fallback to our method for trying to identify it directly
                # this finds the git root or uses the current working directory as a last resort
                from codeweaver.common.utils.git import get_project_path

                project_path = get_project_path()
        rignore_settings["path"] = project_path

        # Configure .gitignore and other ignore file reading
        rignore_settings["read_ignore_files"] = self.use_other_ignore_files
        rignore_settings["read_git_ignore"] = self.use_gitignore

        # Build override patterns - ONLY ignore patterns (with ! prefix)
        overrides: list[str] = []

        # Add exclude patterns (directories to ignore)
        for exclude in self.excludes:
            exclude_str = str(exclude)
            # Skip if it's whitelisted by forced_includes
            if exclude_str in {str(p) for p in self.forced_includes}:
                continue
            # Add as ignore pattern (! prefix)
            if "/" in exclude_str or "*" in exclude_str:
                # Already a glob pattern
                overrides.append(f"!{exclude_str}")
            else:
                # Directory name - make it a glob
                overrides.append(f"!**/{exclude_str}/**")

        rignore_settings["overrides"] = overrides

        # Set the filter for extension checking AND hidden file handling
        rignore_settings["should_exclude_entry"] = self.filter

        return RignoreSettings(rignore_settings)

    @cached_property
    def hidden_tool_paths(self) -> set[str]:
        """Get common hidden tooling paths to consider for forced-includes."""
        from codeweaver.core.file_extensions import COMMON_LLM_TOOLING_PATHS, COMMON_TOOLING_PATHS

        result: set[str] = set()
        for tool in COMMON_TOOLING_PATHS:
            for path_str in tool[1]:
                path = Path(path_str) if isinstance(path_str, str) else path_str
                # Include hidden paths that aren't files with extensions
                if (
                    str(path).startswith(".") or path.name.startswith(".")
                ) and "." not in path.name[1:]:
                    result.add(str(path))

        for tool in COMMON_LLM_TOOLING_PATHS:
            for path_str in tool[1]:
                path = Path(path_str) if isinstance(path_str, str) else path_str
                if (
                    str(path).startswith(".") or path.name.startswith(".")
                ) and "." not in path.name[1:]:
                    result.add(str(path))

        return result

    def construct_filter(self) -> Callable[[Path], bool]:  # noqa: C901 # it is what it is
        """Construct the filter function for rignore's `should_exclude_entry` parameter.

        Returns a function that returns True for paths that should be EXCLUDED.

        This filter:
        1. Allows directories to pass through (rignore handles dir filtering)
        2. Allows files in whitelisted tooling directories
        3. Excludes hidden files not in tooling directories (when ignore_hidden=True)
        4. Excludes files with explicitly excluded extensions
        5. Excludes files with extensions not in our known extensions list
        """
        known_extensions = _get_known_extensions()
        excluded_extensions = {
            ext if ext.startswith(".") else f".{ext}" for ext in self.excluded_extensions
        }

        # Build set of tooling directory names for fast lookup
        tooling_dirs: set[str] = set()
        if self.include_github_dir:
            tooling_dirs.update({".github", ".circleci"})
        if self.include_tooling_dirs:
            tooling_dirs.update(self.hidden_tool_paths)

        double_suffix_extensions = tuple({ext for ext in known_extensions if ext.count(".") > 1})

        # Cache for seen extensions to avoid repeated lookups
        seen: dict[str, bool] = {}

        def filter_func(path: Path | str) -> bool:
            """Return True to EXCLUDE the path, False to INCLUDE it."""
            path_obj = Path(path) if isinstance(path, str) else path

            # Allow directories to pass through - rignore handles directory filtering
            # via ignore rules and overrides
            if path_obj.is_dir():
                # But exclude hidden dirs that aren't tooling dirs
                if self.ignore_hidden:
                    name = path_obj.name
                    if name.startswith(".") and name not in tooling_dirs:
                        return True  # Exclude this hidden directory
                return False

            # Check if file is in a tooling directory (allow hidden files in tooling dirs)
            in_tooling_dir = any(part in tooling_dirs for part in path_obj.parts)

            # Exclude hidden files not in tooling directories
            if self.ignore_hidden and not in_tooling_dir and path_obj.name.startswith("."):
                return True  # Exclude hidden file

            ext = (
                next((ex for ex in double_suffix_extensions if path_obj.name.endswith(ex)), None)
                or path_obj.suffix
                or path_obj.name
            ).lower()

            # Check cache first
            if ext in seen:
                return seen[ext]

            # Check if extension is in excluded list
            if ext in excluded_extensions:
                seen[ext] = True
                return True

            # Check if extension is in known extensions list
            # Also check the full filename for extensionless files like Makefile
            if ext in known_extensions or path_obj.name in known_extensions:
                seen[ext] = False
                return False

            # Unknown extension - exclude by default
            # CodeWeaver only indexes known file types
            seen[ext] = True
            return True

        return filter_func

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
