# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Post-search filtering utilities.

This module provides functions for filtering search results based on
various criteria such as test file inclusion and language focus.
"""

from __future__ import annotations

from pathlib import Path

from codeweaver.core import CodeChunk, SearchResult


def _is_test_file(file_path: Path) -> bool:
    """Check if a file is a test file using filename and directory name heuristics.

    Checks only the filename and immediate parent directory name to avoid
    false positives when the project itself is located under a path containing
    the word "test" (e.g., pytest temp directories like
    /tmp/pytest-of-user/pytest-123/test_my_project/test_codebase/auth.py).

    Args:
        file_path: Path to check

    Returns:
        True if the file appears to be a test file
    """
    name = file_path.name.lower()
    # Filename heuristics: test_*.py, *_test.py, *_spec.py, *_tests.py
    if name.startswith("test_") or name.endswith(("_test.py", "_tests.py", "_spec.py")):
        return True
    # Check if immediately inside a test directory
    parent_name = file_path.parent.name.lower()
    return parent_name in ("test", "tests", "spec", "specs", "__tests__")


def filter_test_files(candidates: list[SearchResult]) -> list[SearchResult]:
    """Filter out test files if include_tests is False.

    Args:
        candidates: List of search results to filter

    Returns:
        Filtered list of search results

    Note:
        This is a basic implementation using path name heuristics.
        Future versions will use repo metadata to properly tag test files.
    """
    return [c for c in candidates if not (c.file_path and _is_test_file(c.file_path))]


def filter_by_languages(
    candidates: list[SearchResult], focus_languages: tuple[str, ...]
) -> list[SearchResult]:
    """Filter search results to only include specified languages.

    Args:
        candidates: List of search results to filter
        focus_languages: tuple of language names to include

    Returns:
        Filtered list of search results
    """
    langs = set(focus_languages)
    return [
        c
        for c in candidates
        if (
            c
            and isinstance(c.content, CodeChunk)
            and c.content.language
            and str(c.content.language) in langs
        )
    ]


def apply_filters(
    candidates: list[SearchResult],
    *,
    include_tests: bool = False,
    focus_languages: tuple[str, ...] | None = None,
) -> list[SearchResult]:
    """Apply all configured filters to search results.

    Args:
        candidates: List of search results to filter
        include_tests: Whether to include test files
        focus_languages: Optional tuple of language names to include

    Returns:
        Filtered list of search results
    """
    # we don't need to filter anything
    if not focus_languages and include_tests:
        return candidates
    # if include_tests is True, only filter by languages (if any)
    if include_tests:
        if not focus_languages:
            return candidates
        return filter_by_languages(candidates, focus_languages=focus_languages)
    # include_tests is False: always filter test files; optionally filter by language
    if not focus_languages:
        return filter_test_files(candidates)
    return filter_test_files(filter_by_languages(candidates, focus_languages=focus_languages))


__all__ = ("apply_filters", "filter_by_languages", "filter_test_files")
