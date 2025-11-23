# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Internal helper utilities for the core package."""

from __future__ import annotations

from pathlib import Path


TEST_FILE_PATTERNS = ["*.test.*", "*.spec.*", "test/**/*", "spec/**/*"]

_tooling_dirs: set[Path] | None = None


def truncate_text(text: str, max_length: int = 100, ellipsis: str = "...") -> str:
    """
    Truncate text to a maximum length, adding an ellipsis if truncated.

    Args:
        text: The input text to truncate.
        max_length: The maximum allowed length of the text (default: 100).
        ellipsis: The string to append if truncation occurs (default: "...").

    Returns:
        The truncated text if it exceeds max_length, otherwise the original text.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(ellipsis)] + ellipsis


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


__all__ = ("TEST_FILE_PATTERNS", "get_tooling_dirs", "truncate_text")
