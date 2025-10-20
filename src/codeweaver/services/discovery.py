"""File discovery service with rignore integration."""

from __future__ import annotations

import contextlib

from pathlib import Path
from typing import TYPE_CHECKING

import rignore

from codeweaver._data_structures import DiscoveredFile
from codeweaver.exceptions import IndexingError
from codeweaver.language import SemanticSearchLanguage


if TYPE_CHECKING:
    from codeweaver._common import DictView
    from codeweaver.settings_types import CodeWeaverSettingsDict
TEST_FILE_PATTERNS = ["*.test.*", "*.spec.*", "test/**/*", "spec/**/*"]


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
        self._language_extensions = SemanticSearchLanguage.extension_map()

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
                self.settings["project_root"],
                max_filesize=max_file_size or self.settings["max_file_size"],
                case_insensitive=True,
                read_git_ignore=read_git_ignore
                if read_git_ignore in (True, False)
                else self.settings["filter_settings"].use_gitignore,
                read_ignore_files=read_ignore_files
                or self.settings["filter_settings"].use_other_ignore_files,
                # in all but this narrow case below below, ignore_hidden_files is False
                # otherwise we need to resolve whether to include .github/ and tooling dirs before we can discard other hidden files
                ignore_hidden=bool(
                    self.settings["filter_settings"].ignore_hidden_files
                    and self.settings["filter_settings"].include_github_dir is False
                    and self.settings["filter_settings"].include_tooling_dirs is False
                ),
                additional_ignore_paths=extra_ignores,
            )
            with contextlib.suppress(ValueError):
                discovered.extend(
                    file_path.relative_to(self.settings["project_root"]) for file_path in walker
                )

        except Exception as e:
            raise IndexingError(
                f"Failed to discover files in {self.settings['project_root']}",
                details={"error": str(e)},
                suggestions=[
                    "Check that the project root exists and is readable",
                    "Verify that rignore can access the directory",
                ],
            ) from e
        else:
            return sorted(discovered)

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


__all__ = ("FileDiscoveryService",)
