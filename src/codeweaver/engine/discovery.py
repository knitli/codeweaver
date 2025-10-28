# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""File discovery service with rignore integration."""

from __future__ import annotations

import contextlib

from pathlib import Path
from typing import TYPE_CHECKING

import rignore

from codeweaver.core.discovery import DiscoveredFile
from codeweaver.exceptions import IndexingError


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types import DictView
TEST_FILE_PATTERNS = ["*.test.*", "*.spec.*", "test/**/*", "spec/**/*"]

_tooling_dirs: set[Path] | None = None


def get_tooling_dirs() -> set[Path]:
    """Get common tooling directories within the project root."""

    def _is_hidden_dir(path: Path) -> bool:
        return bool(str(path).startswith(".") and "." not in str(path)[1:])

    global _tooling_dirs
    if _tooling_dirs is None:
        from codeweaver.core.file_extensions import COMMON_LLM_TOOLING_PATHS, COMMON_TOOLING_PATHS

        tooling_paths = {
            path for tool in COMMON_TOOLING_PATHS for path in tool[1] if _is_hidden_dir(path)
        } | {path for tool in COMMON_LLM_TOOLING_PATHS for path in tool[1] if _is_hidden_dir(path)}
        _tooling_dirs = tooling_paths
    return _tooling_dirs


class FileDiscoveryService:
    """Service for discovering and filtering files in a codebase.

    Integrates with rignore for gitignore support and provides
    language-aware file filtering.
    """

    def __init__(self, settings: DictView[CodeWeaverSettingsDict]) -> None:
        """Initialize file discovery service.

        Args:
            settings: CodeWeaver configuration settings
        """
        self.settings = settings

    async def _discover_files(
        self,
        *,
        include_tests: bool | None = None,
        max_file_size: int | None = None,
        read_git_ignore: bool | None = None,
        read_ignore_files: bool | None = None,
        additional_ignore_paths: list[Path] | None = None,
    ) -> list[Path]:
        """Discover files using rignore integration with filtering.

        Args:
            patterns: Optional file patterns to filter by
            include_tests: Whether to include test files

        Returns:
            List of discovered file paths

        Raises:
            IndexingError: If file discovery fails
        """
        try:
            discovered: list[Path] = []
            additional_ignore_paths = additional_ignore_paths or []
            extra_ignores = [str(path) for path in additional_ignore_paths]
            if not include_tests:
                extra_ignores.extend(TEST_FILE_PATTERNS)
            walker = rignore.walk(
                self.settings["project_path"],
                max_filesize=max_file_size or self.settings["max_file_size"],
                case_insensitive=True,
                read_git_ignore=read_git_ignore
                if read_git_ignore in (True, False)
                else self.settings["indexing"].use_gitignore,
                read_ignore_files=read_ignore_files
                or self.settings["indexing"].use_other_ignore_files,
                # in all but this narrow case defined here, ignore_hidden_files is False
                # otherwise we need to resolve whether to include .github/ and tooling dirs before we can discard other hidden files
                ignore_hidden=bool(
                    self.settings["indexing"].ignore_hidden_files
                    and self.settings["indexing"].include_github_dir is False
                    and self.settings["indexing"].include_tooling_dirs is False
                ),
                additional_ignore_paths=extra_ignores,
            )
            with contextlib.suppress(ValueError):
                discovered.extend(
                    file_path.relative_to(self.settings["project_path"])
                    for file_path in walker
                    if not self._is_filtered(file_path)
                )

        except Exception as e:
            raise IndexingError(
                f"Failed to discover files in {self.settings['project_path']}",
                details={"error": str(e)},
                suggestions=[
                    "Check that the project root exists and is readable",
                    "Verify that rignore can access the directory",
                ],
            ) from e
        else:
            return sorted(discovered)

    def _is_filtered(self, file: Path) -> bool:
        """Filter files based on settings.

        This applies an additional filtering layer after a file is found by rignore.

        We need to be careful about how we assess paths, because they don't have to exist at the project root (like in a monorepo -- we can have deeply nested '.github' or similar directories).

        Args:
            files: Sequence of file paths to filter

        Returns:
            True if the file is not filtered, False otherwise
        """

        def target_dir_in_path(target_dirs: set[Path], path: Path) -> bool:
            """Check if any target directory is in the given path."""
            for part in path.parts:
                if (
                    Path(part) in target_dirs
                    and (parent := next(p for p in target_dirs if Path(part) == p))
                    and parent.is_dir()
                    and parent in path.parents
                ):
                    return True
            return False

        if not self.settings["indexing"].ignore_hidden_files:
            return False
        return bool(
            (
                not self.settings["indexing"].include_github_dir
                and target_dir_in_path({Path(".github"), Path(".circleci")}, file)
            )
            or (
                not self.settings["indexing"].include_tooling_dirs
                and target_dir_in_path(get_tooling_dirs(), file)
            )
        )

    async def get_discovered_files(self) -> tuple[tuple[DiscoveredFile, ...], tuple[Path, ...]]:
        """Get all discovered files and filtered files.

        Returns:
            Tuple of discovered files and filtered files
        """
        files = await self._discover_files()
        discovered_files: list[DiscoveredFile] = []
        filtered_files: list[Path] = []
        for file_path in files:
            if discovered_file := DiscoveredFile.from_path(file_path):
                discovered_files.append(discovered_file)
            else:
                filtered_files.append(file_path)
        return (tuple(discovered_files), tuple(filtered_files))


__all__ = ("FileDiscoveryService", "get_tooling_dirs")
