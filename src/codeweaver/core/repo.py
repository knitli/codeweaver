# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Heuristic-based repository environment and topography detection."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import cached_property
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal, Self, TypedDict, cast

from pydantic import DirectoryPath, Field, computed_field
from pydantic.dataclasses import dataclass

from codeweaver.core.file_extensions import COMMON_TOOLING_PATHS, TEST_DIR_NAMES
from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage
from codeweaver.core.types.aliases import FilteredKeyT, LiteralStringT
from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.models import DATACLASS_CONFIG, DataclassSerializationMixin


if TYPE_CHECKING:
    from codeweaver.core.types import AnonymityConversion


type PathOrFalse = Path | Literal[False]
"""A return type that can either be a Path or False."""


class DirectoryPurpose(str, BaseEnum):
    """Enum for common directory purposes in a repository."""

    APPS = "apps"
    """Applications or app directory, or similar workspaces like 'crates'."""
    BACKEND = "backend"
    """Backend or server directory."""
    BUILD = "build"
    """Build artifacts or output directory."""
    CI = "ci"
    """Continuous integration configuration directory."""
    DOCS = "docs"
    """Documentation or examples directory."""
    FRONTEND = "frontend"
    """Frontend/ui or client directory."""
    INFRA = "infra"
    """Infrastructure or cloud-related directory."""
    LIB = "libraries"
    """Library or shared code directory."""
    LLM_TOOLS = "llm_tools"
    """LLM (Large Language Model) tools directory."""
    SCRIPTS = "scripts"
    """Scripts or automation tools directory."""
    SRC = "source code"
    """Source code directory."""
    SUB_REPO = "sub-repository"
    """Sub-repository or module directory. (These are what is inside `APPS`)"""
    TESTS = "tests"
    """Tests directory, including fixtures."""
    TOOLING = "tooling"
    """Developer tooling or similar tool configuration (linting, formatting, cli tools). Not scripts/automation tools, which are `SCRIPTS`."""

    __slots__ = ()

    @property
    def alias(self) -> tuple[str, ...]:
        """Get alternative names for the directory purpose.

        (Should it be `aliases`? Yes. But that's a classmethod for `BaseEnum` that relies on this being 'alias`.)

        Returns:
            A tuple of alternative names.
        """
        aliases: dict[DirectoryPurpose, tuple[str, ...]] = {
            DirectoryPurpose.APPS: (
                "app",
                "applications",
                "application",
                "crates",
                "modules",
                "packages",
                "services",
                "pkgs",
                "mods",
                "workspaces",
                "pkgspaces",
                "svcs",
            ),
            DirectoryPurpose.BACKEND: ("back-end",),
            DirectoryPurpose.BUILD: (),
            DirectoryPurpose.CI: (
                ".github",
                ".circleci",
                ".ci",
                "ci",
                "cd",
                ".cd",
                "ci-cd",
                ".ci-cd",
                "ci_cd",
                ".ci_cd",
            ),
            DirectoryPurpose.DOCS: ("documentation", "examples", "doc"),
            DirectoryPurpose.FRONTEND: ("front-end", "ui", "web", "www"),
            DirectoryPurpose.INFRA: ("infrastructure",),
            DirectoryPurpose.LIB: ("library", "libs", "libraries"),
            DirectoryPurpose.SCRIPTS: ("bin", "bins", "tools", ".tools"),
            DirectoryPurpose.SRC: ("source", "Sources", "Source"),
            DirectoryPurpose.SUB_REPO: (),  # found heuristically
            DirectoryPurpose.TESTS: (*TEST_DIR_NAMES, "fixtures"),
            DirectoryPurpose.TOOLING: tuple(
                str(path)
                for paths in COMMON_TOOLING_PATHS
                for path in paths[1]
                if "." not in str(path)[1:] or "/" not in str(path)
            ),
        }
        return aliases.get(self, ())

    @property
    def validator(self) -> Callable[[Path], bool]:
        """Get the validator function for the directory purpose.

        Returns:
            A callable that takes a Path and returns True if it matches the purpose.
        """
        raise NotImplementedError("DirectoryPurpose.validator must be implemented per member.")

    @classmethod
    def validators(cls) -> MappingProxyType[DirectoryPurpose, Callable[[Path], bool]]:
        """Each member has its own validator to assess membership."""
        return MappingProxyType({member: member.validator for member in cls})


@dataclass(config=DATACLASS_CONFIG)
class RepoDirectory(DataclassSerializationMixin):
    """Representation of a directory in the repository with its purpose.

    `RepoDirectory` also have detailed properties that are lazily evaluated, and helper methods for working with directories.
    """

    path: DirectoryPath
    """The path to the directory."""

    purpose: Annotated[DirectoryPurpose, Field(description="The main purpose of the directory.")]

    _files: Sequence[Path] | None = None
    """Cache of files in the directory."""

    _subdirectories: Sequence[Path] | None = None
    """Cache of subdirectories in the directory."""

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {
            FilteredKey("path"): AnonymityConversion.HASH,
            FilteredKey("_files"): AnonymityConversion.COUNT,
            FilteredKey("_subdirectories"): AnonymityConversion.COUNT,
        }


class RepoChecklistDict(TypedDict):
    """A dictionary representation of the RepoChecklist dataclass.

    Keys are the attribute names of RepoChecklist, and values are their corresponding types. Used for type hinting in methods that return mixed types.
    """

    has_src_dir: PathOrFalse
    has_lib_dir: PathOrFalse
    has_tests_dir: PathOrFalse
    has_fixtures_dir: PathOrFalse
    has_parent_named_dir: PathOrFalse
    has_apps_dir: PathOrFalse
    has_docs_dir: PathOrFalse
    has_packages_dir: PathOrFalse
    has_frontend_dir: PathOrFalse
    has_backend_dir: PathOrFalse
    has_modules_dir: PathOrFalse
    has_infra_dir: PathOrFalse
    has_scripts_dir: PathOrFalse
    has_bin_dir: PathOrFalse
    has_tools_dir: PathOrFalse
    has_build_dir: PathOrFalse
    has_ci_dir: PathOrFalse
    has_circleci_dir: PathOrFalse
    has_github_dir: PathOrFalse
    has_jenkins_file: PathOrFalse
    has_gitlab_file: PathOrFalse
    has_context_dir: PathOrFalse
    has_examples_dir: PathOrFalse
    has_migrations_dir: PathOrFalse
    has_notebooks_dir: PathOrFalse
    has_data_dir: PathOrFalse
    tooling: tuple[tuple[str, Path], ...]
    llm_tooling: tuple[tuple[str, Path], ...]
    config_files: tuple[tuple[str, Path], ...]
    language_specific_files: tuple[tuple[str, Path], ...]


@dataclass(config=DATACLASS_CONFIG)
class RepoChecklist(DataclassSerializationMixin):
    """A checklist-style representation of repository structure.

    The attribute names aren't 1-for-1 to directory names. For example, `has_src_dir` indicates a directory named `src` or `source`.
    """

    # core repo directories
    has_src_dir: PathOrFalse
    has_lib_dir: PathOrFalse
    has_tests_dir: PathOrFalse
    """Can be 'test(s)', 'spec(s)', or '__test(s)__'."""
    has_fixtures_dir: PathOrFalse
    has_parent_named_dir: PathOrFalse
    """Indicates the presence of a directory named after the parent directory, common for some languages as the source code root (Python is one, though src is more common these days)."""

    # monorepo indicators
    has_apps_dir: PathOrFalse
    has_docs_dir: PathOrFalse
    has_packages_dir: PathOrFalse
    has_frontend_dir: PathOrFalse
    has_backend_dir: PathOrFalse
    has_modules_dir: PathOrFalse
    has_infra_dir: PathOrFalse

    # tooling and utility directories
    has_scripts_dir: PathOrFalse
    has_bin_dir: PathOrFalse
    has_tools_dir: PathOrFalse
    has_build_dir: PathOrFalse

    # ci_cd directories
    has_ci_dir: PathOrFalse
    has_circleci_dir: PathOrFalse
    has_github_dir: PathOrFalse

    has_jenkins_file: PathOrFalse
    has_gitlab_file: PathOrFalse

    # docs
    has_docs_dir: PathOrFalse
    has_context_dir: PathOrFalse

    # data and examples
    has_examples_dir: PathOrFalse
    has_migrations_dir: PathOrFalse
    has_notebooks_dir: PathOrFalse
    has_data_dir: PathOrFalse

    # common tooling files and directories
    tooling: tuple[tuple[str, Path], ...]
    llm_tooling: tuple[tuple[str, Path], ...]

    # configuration files
    config_files: tuple[tuple[str, Path], ...]
    language_specific_files: tuple[tuple[str, Path], ...]

    _children: dict[Path, RepoChecklist] | None = None
    """Cache of child RepoChecklist instances for subdirectories."""

    # Directory name variants for common directories with alternate naming conventions
    _DIR_VARIANTS: ClassVar[MappingProxyType[str, set[str]]] = MappingProxyType({
        "apps": {"apps", "app", "applications", "application", "crates"},
        "ci": {"ci", ".ci", "cd", ".cd", "ci-cd", ".ci-cd", ".ci_cd", "ci_cd"},
        "lib": {"lib", "library", "libs", "libraries"},
        "tests": {*TEST_DIR_NAMES},
        "src": {"src", "source"},
        "packages": {"packages", "pkg", "pkgs"},
        "modules": {"modules", "mod", "mods", "workspaces", "pkgspaces", "services", "svcs"},
    })

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("_children"): AnonymityConversion.COUNT,
            FilteredKey("tooling"): AnonymityConversion.DISTRIBUTION,
            FilteredKey("llm_tooling"): AnonymityConversion.DISTRIBUTION,
            FilteredKey("config_files"): AnonymityConversion.DISTRIBUTION,
            FilteredKey("language_specific_files"): AnonymityConversion.DISTRIBUTION,
        }

    @classmethod
    def _any_exists(cls, self_instance: Self) -> bool:
        """Check if any directory attributes are present in the checklist.

        Args:
            self_instance: An instance of RepoChecklist.

        Returns:
            True if any directory attributes are present, False otherwise.
        """
        return any(
            (attr.startswith("has_") and getattr(self_instance, attr) is not False)
            or (
                attr in ("tooling", "llm_tooling", "config_files", "language_specific_files")
                and getattr(self_instance, attr)
            )
            for attr in cls.__dataclass_fields__
        )

    @staticmethod
    def _attr_name(attr: str) -> str:
        if (
            attr.startswith("has_")
            and attr.endswith("_dir")
            and not any(
                name for name in ("github", "gitlab", "circleci", "jenkins") if name in attr
            )
        ):
            return attr[4:-4]
        return attr

    @classmethod
    def _find_directory_variant(
        cls, base_name: str, root_level_dir_names: set[str], project_path: Path
    ) -> Path | None:
        """Find a directory matching one of the known variants for a base name.

        Args:
            base_name: The base name to look for (e.g., 'tests', 'ci', 'src', 'lib').
            root_level_dir_names: Set of directory names at the project root.
            project_path: The project root path.

        Returns:
            The path to the matching directory, or None if not found.
        """
        if base_name not in cls._DIR_VARIANTS:
            return None

        variants = cls._DIR_VARIANTS[base_name]
        return next(
            (
                project_path / d
                for d in root_level_dir_names
                if d in variants and (project_path / d).exists()
            ),
            None,
        )

    @classmethod
    def _determine_root_attrs(
        cls, dir_checks: set[str], project_path: Path, root_level_dir_names: set[str]
    ) -> RepoChecklistDict:
        """Determine which root-level directories are present.

        Returns a mapping of dataclass attribute name -> value. Values may be:
        - Path | False for directory/file presence flags
        - tuple[...] for tooling/config collections assigned later
        """
        # ensure the dict can hold mixed value types (Path|False and tuples)
        attrs: RepoChecklistDict = RepoChecklistDict(**{  # type: ignore[missing-typed-dict-key]
            key: False if key.startswith("has_") else () for key in cls.__dataclass_fields__
        })  # type: ignore # it doesn't infer the keys
        for name in dir_checks:
            if name in root_level_dir_names:
                attrs[f"has_{name}_dir"] = project_path / name  # ty: ignore[invalid-key]
            elif name == "parent_named" and (
                (project_path / project_path.name).is_dir()
                or any(
                    n
                    for n in root_level_dir_names
                    if n in project_path.name or project_path.name in n
                )
            ):
                attrs["has_parent_named_dir"] = (
                    (project_path / project_path.name)
                    if (project_path / project_path.name).is_dir()
                    else cast(
                        PathOrFalse,
                        next(
                            (
                                project_path / n
                                for n in root_level_dir_names
                                if n in project_path.name or project_path.name in n
                            ),
                            False,
                        ),
                    )
                )
            elif name in cls._DIR_VARIANTS and (
                found_dir := cls._find_directory_variant(name, root_level_dir_names, project_path)
            ):
                attrs[f"has_{name}_dir"] = found_dir  # ty: ignore[invalid-key]
        return attrs

    @staticmethod
    def _gather_tooling_paths(
        files: Sequence[Path],
        project_path: Path,
        common_tooling_paths: tuple[tuple[LiteralStringT, tuple[Path, ...]], ...],
    ) -> tuple[tuple[str, Path], ...]:
        """Gather common tooling paths from the repository files."""
        tooling_paths: list[tuple[str, Path]] = []
        for tool_name, possible_paths in common_tooling_paths:
            for rel_path in possible_paths:
                abs_path = project_path / rel_path
                if abs_path.exists() and abs_path in files:
                    tooling_paths.append((tool_name, abs_path))
                    break  # don't check more paths, but we stay in the outer loop
        return tuple(tooling_paths)

    @staticmethod
    def _gather_llm_tooling_paths(
        files: Sequence[Path],
        project_path: Path,
        common_llm_tooling_paths: tuple[tuple[LiteralStringT, tuple[Path, ...]], ...],
    ) -> tuple[tuple[str, Path], ...]:
        """Gather common LLM tooling paths from the repository files."""
        llm_tooling_paths: list[tuple[str, Path]] = []
        for tool_name, possible_paths in common_llm_tooling_paths:
            if valid_paths := (
                project_path / rel_path
                for rel_path in possible_paths
                if (project_path / rel_path).exists() and (project_path / rel_path) in files
            ):
                llm_tooling_paths.extend((tool_name, path) for path in valid_paths)
        return tuple(llm_tooling_paths)

    @classmethod
    async def from_files(cls, files: Sequence[Path], project_path: Path) -> Self:
        """Create a RepoChecklist from a list of file paths.

        Args:
            files: A sequence of file paths in the repository.
            project_path: The root directory of the project.

        Returns:
            An instance of RepoChecklist with detected directories and files.
        """
        from codeweaver.core.file_extensions import COMMON_LLM_TOOLING_PATHS, COMMON_TOOLING_PATHS

        root_level_dir_names: set[str] = {
            f.name for f in files if f.parent == project_path and f.is_dir()
        }
        dir_checks = {
            cls._attr_name(attr)
            for attr in cls.__dataclass_fields__
            if attr.startswith("has_") and attr.endswith("_dir")
        }
        root_dir_attrs = cls._determine_root_attrs(dir_checks, project_path, root_level_dir_names)
        root_dir_attrs["has_gitlab_file"] = (
            project_path / ".gitlab-ci.yml"
            if (project_path / ".gitlab-ci.yml").exists()
            else cast(PathOrFalse, False)
        )
        root_dir_attrs["has_jenkins_file"] = (
            project_path / "Jenkinsfile"
            if (project_path / "Jenkinsfile").exists()
            else cast(PathOrFalse, False)
        )

        root_dir_attrs["tooling"] = cls._gather_tooling_paths(
            files, project_path, COMMON_TOOLING_PATHS
        )
        root_dir_attrs["llm_tooling"] = cls._gather_llm_tooling_paths(
            files, project_path, COMMON_LLM_TOOLING_PATHS
        )
        # configuration files
        config_files: list[tuple[str, Path]] = []
        for language in SemanticSearchLanguage:
            if language.config_files:
                config_files.extend(
                    (
                        cfg.language_type.variable
                        if cfg.language_type != ConfigLanguage.SELF
                        else language.variable,
                        cfg.path,
                    )
                    for cfg in language.config_files
                    if cfg.exists()
                )
        for language in ConfigLanguage:
            if language == ConfigLanguage.SELF:
                continue
            for ext in language.extensions:
                config_files.extend(
                    (language.variable, path)
                    for path in project_path.rglob(f"*{ext}")
                    if path in files and path.exists()
                )
        configs = [
            cfg
            for cfg in config_files
            if cfg[1] not in (path for _, path in root_dir_attrs["tooling"])
            or cfg[1] not in (path for _, path in root_dir_attrs["llm_tooling"])
        ]
        root_dir_attrs["config_files"] = tuple(configs)
        root_dir_attrs["language_specific_files"] = ()  # not implemented yet
        instance = cls(**root_dir_attrs)
        children = {
            app: await RepoChecklist.from_files(
                [f for f in files if str(app) in str(f)], project_path
            )
            for app in instance.apps
            if instance.apps
        }
        instance._children = {
            app: child
            for app, child in children.items()
            if child and cls._any_exists(child)  # type: ignore
        }
        return instance

    @property
    def as_dict(self) -> RepoChecklistDict:
        """Get a dictionary representation of the RepoChecklist.

        Returns:
            A dictionary with attribute names as keys and their values.
        """
        return RepoChecklistDict(**{  # ty: ignore[missing-typed-dict-key]
            field: getattr(self, field) for field in self.__dataclass_fields__
        })

    @property
    def paths(self) -> Sequence[Path]:
        """Get all paths represented in the checklist.

        Returns:
            A sequence of Path objects for all detected directories and files.
        """
        paths: list[Path] = []
        for field in self.__dataclass_fields__:
            value = getattr(self, field)
            if isinstance(value, Path):
                paths.append(value)
            elif isinstance(value, tuple):
                paths.extend(
                    item[1]
                    for item in value  # type: ignore
                    if isinstance(item, tuple)
                    and len(cast(tuple[str, Path], item)) == 2
                    and isinstance(item[1], Path)
                )
        return paths

    @property
    def is_monorepo(self) -> bool:
        """Determine if the repository is likely a monorepo.

        Returns:
            True if the repository has monorepo indicators, False otherwise.
        """
        return bool(
            self.has_apps_dir
            or self.has_packages_dir
            or self.has_modules_dir
            or (
                sum(
                    bool(dir_attr)
                    for dir_attr in [
                        self.has_frontend_dir,
                        self.has_backend_dir,
                        self.has_infra_dir,
                    ]
                )
                >= 2
            )
        )

    @computed_field
    @cached_property
    def primary_source_dir(self) -> Path | None:
        """Get the primary source directory for the repository.

        Returns:
            The primary source directory path if it exists, None otherwise.
        """
        # One monorepo structure is to have a core src or lib with multiple apps/packages/etc.
        if (
            self.is_monorepo
            and (src_dir := self.has_src_dir or self.has_lib_dir)
            and len([d for d in src_dir.iterdir() if d.is_dir()]) > 1
        ):
            return src_dir
        if self.is_monorepo:
            return None
        for attr in ["has_src_dir", "has_parent_named_dir", "has_lib_dir"]:
            dir_path = getattr(self, attr)
            if dir_path is not False:
                return dir_path
        return None

    @computed_field
    @cached_property
    def apps(self) -> Sequence[Path]:
        """Get the application directories in a monorepo structure.

        Naively assumes that directories under 'apps', 'packages', 'modules', 'src', or 'lib' are applications.

        Returns:
            A sequence of Paths representing application directories.
        """
        app_dirs: list[Path] = []
        for attr in [
            "has_apps_dir",
            "has_packages_dir",
            "has_modules_dir",
            "has_src_dir",
            "has_lib_dir",
        ]:
            dir_path = getattr(self, attr)
            if dir_path is not False:
                app_dirs.extend(d for d in dir_path.iterdir() if d.is_dir())
        return app_dirs


__all__ = ("DirectoryPurpose", "PathOrFalse", "RepoChecklist", "RepoChecklistDict", "RepoDirectory")
