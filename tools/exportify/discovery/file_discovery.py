#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""File discovery service for lazy import system.

Discovers Python files in source trees with:
- Recursive directory walking
- .gitignore respect
- Pattern filtering (include/exclude)
- __pycache__ exclusion
"""

from __future__ import annotations

import fnmatch
import re

from pathlib import Path
from re import Pattern


class FileDiscovery:
    """Discover Python files in source tree."""

    def __init__(self, *, respect_gitignore: bool = True):
        """Initialize file discovery.

        Args:
            respect_gitignore: Whether to respect .gitignore patterns
        """
        self.respect_gitignore = respect_gitignore
        self._gitignore_patterns: list[Pattern] = []

    def discover_python_files(
        self,
        root: Path,
        *,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[Path]:
        """Find all Python files in directory tree.

        Args:
            root: Root directory to search
            include_patterns: Glob patterns to include (e.g., ["*.py"])
            exclude_patterns: Glob patterns to exclude (e.g., ["*_test.py"])

        Returns:
            Sorted list of Python file paths

        Example:
            >>> discovery = FileDiscovery()
            >>> files = discovery.discover_python_files(Path("src"))
            >>> len(files)
            347
        """
        if self.respect_gitignore:
            self._load_gitignore(root)

        python_files = []

        # Use rglob to recursively find all .py files
        for py_file in root.rglob("*.py"):
            # Skip __pycache__ directories
            if "__pycache__" in py_file.parts:
                continue

            # Skip if gitignored
            if self.respect_gitignore and self._is_ignored(py_file, root):
                continue

            # Apply include patterns (if specified)
            if include_patterns and not any(
                fnmatch.fnmatch(py_file.name, pattern) for pattern in include_patterns
            ):
                continue

            # Apply exclude patterns
            if exclude_patterns and any(
                fnmatch.fnmatch(py_file.name, pattern) for pattern in exclude_patterns
            ):
                continue

            python_files.append(py_file)

        return sorted(python_files)

    def _load_gitignore(self, root: Path) -> None:
        """Load .gitignore patterns.

        Args:
            root: Root directory to search for .gitignore
        """
        gitignore_file = root / ".gitignore"
        if not gitignore_file.exists():
            return

        patterns = []
        for line in gitignore_file.read_text().splitlines():
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Convert gitignore pattern to regex
            # Simplified conversion - handles common cases
            # For full gitignore support, could use gitignore-parser library

            # Escape special regex characters except * and ?
            pattern = line.replace(".", r"\.")

            # Convert gitignore wildcards to regex
            pattern = pattern.replace("**", "<<<DOUBLESTAR>>>")  # Placeholder
            pattern = pattern.replace("*", "[^/]*")  # * matches anything except /
            pattern = pattern.replace("<<<DOUBLESTAR>>>", ".*")  # ** matches anything
            pattern = pattern.replace("?", ".")  # ? matches single char

            # If pattern doesn't start with /, it can match at any level
            # Otherwise it's anchored to the root
            pattern = f"(^|.*/){pattern}$" if not pattern.startswith("/") else f"^{pattern[1:]}$"

            # Compile regex
            try:
                patterns.append(re.compile(pattern))
            except re.error:
                # Skip invalid patterns
                continue

        self._gitignore_patterns = patterns

    def _is_ignored(self, path: Path, root: Path) -> bool:
        """Check if path matches any gitignore pattern.

        Args:
            path: Path to check
            root: Root directory (for relative path calculation)

        Returns:
            True if path should be ignored
        """
        # Get path relative to root
        try:
            relative = path.relative_to(root)
        except ValueError:
            # Path is not relative to root
            return False

        relative_str = str(relative)

        # Check against all patterns
        return any(pattern.match(relative_str) for pattern in self._gitignore_patterns)


__all__ = ["FileDiscovery"]
