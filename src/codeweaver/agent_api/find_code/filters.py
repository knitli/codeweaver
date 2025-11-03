# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Post-search filtering utilities.

This module provides functions for filtering search results based on
various criteria such as test file inclusion and language focus.
"""

from __future__ import annotations

from codeweaver.core.chunks import CodeChunk, SearchResult


def filter_test_files(candidates: list[SearchResult], *, include_tests: bool) -> list[SearchResult]:
    """Filter out test files if include_tests is False.

    Args:
        candidates: List of search results to filter
        include_tests: Whether to include test files

    Returns:
        Filtered list of search results

    Note:
        This is a basic implementation using path name heuristics.
        Future versions will use repo metadata to properly tag test files.
    """
    if include_tests:
        return candidates

    return [c for c in candidates if not (c.file_path and "test" in str(c.file_path).lower())]


def filter_by_languages(
    candidates: list[SearchResult], focus_languages: tuple[str, ...] | None
) -> list[SearchResult]:
    """Filter search results to only include specified languages.

    Args:
        candidates: List of search results to filter
        focus_languages: Optional tuple of language names to include

    Returns:
        Filtered list of search results
    """
    if not focus_languages:
        return candidates

    langs = set(focus_languages)
    return [
        c
        for c in candidates
        if (
            isinstance(c.content, CodeChunk)
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
    return filter_by_languages(
        filter_test_files(candidates, include_tests=include_tests), focus_languages=focus_languages
    )


__all__ = ("apply_filters", "filter_by_languages", "filter_test_files")
