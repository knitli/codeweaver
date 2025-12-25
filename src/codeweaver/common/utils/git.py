# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Git and Path related utilities."""

from __future__ import annotations

# ruff: noqa: S603
import contextlib
import shutil
import subprocess

from pathlib import Path
from typing import cast

from codeweaver.core.types import Sentinel, SentinelName
from codeweaver.core.utils import get_git_branch as get_git_branch
from codeweaver.core.utils import get_project_path as get_project_path
from codeweaver.core.utils import in_codeweaver_clone as in_codeweaver_clone
from codeweaver.core.utils import is_git_dir as is_git_dir
from codeweaver.core.utils import set_relative_path as set_relative_path
from codeweaver.core.utils import try_git_rev_parse as try_git_rev_parse


# ===========================================================================
# *                            Git/Path Utilities
# ===========================================================================


class Missing(Sentinel):
    """Sentinel for missing values."""


MISSING: Missing = Missing(name=SentinelName("MISSING"), module_name=__name__)


def has_git() -> bool:
    """Check if git is installed and available."""
    git = shutil.which("git")
    if not git:
        return False
    # Verify git command works
    output = subprocess.run([git, "--version"], capture_output=True, check=False)
    return output.returncode == 0


def _get_git_dir(directory: Path) -> Path | Missing:
    """Get the .git directory of a git repository."""
    if not is_git_dir(directory):
        try:
            directory = get_project_path()
        except FileNotFoundError:
            return MISSING
        if not is_git_dir(directory):
            return MISSING
    return directory


def get_git_revision(directory: Path) -> str | Missing:
    """Get the SHA-1 of the HEAD of a git repository."""
    git_dir = _get_git_dir(directory)
    if git_dir is MISSING:
        return MISSING
    directory = cast(Path, git_dir)
    if has_git():
        git = shutil.which("git")
        if not git:
            return MISSING
        with contextlib.suppress(subprocess.CalledProcessError):
            output = subprocess.run(
                [git, "rev-parse", "--short", "HEAD"], cwd=directory, capture_output=True, text=True
            )
            return output.stdout.strip()
    return MISSING


def _get_branch_from_origin(directory: Path) -> str | Missing:
    """Get the branch name from the origin remote."""
    git = shutil.which("git")
    if not git:
        return MISSING
    with contextlib.suppress(subprocess.CalledProcessError):
        output = subprocess.run(
            [git, "rev-parse", "--abbrev-ref", "origin/HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
        )
        branch = output.stdout.strip().removeprefix("origin/")
        # Return the full branch name after removing "origin/" prefix
        # This handles both simple names like "main" and complex ones like "feature/my-feature"
        return branch or MISSING
    return MISSING


__all__ = (
    "get_git_branch",
    "get_git_revision",
    "get_project_path",
    "has_git",
    "in_codeweaver_clone",
    "is_git_dir",
    "set_relative_path",
)
