# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Git and Path related utilities."""

from __future__ import annotations

# ruff: noqa: S603
import contextlib
import os
import shutil
import subprocess

from pathlib import Path
from typing import cast

from codeweaver.core.types import Sentinel, SentinelName


# ===========================================================================
# *                            Git/Path Utilities
# ===========================================================================


class Missing(Sentinel):
    """Sentinel for missing values."""


MISSING: Missing = Missing(name=SentinelName("MISSING"), module_name=__name__)


def try_git_rev_parse() -> Path | None:
    """Attempt to use git to get the root directory of the current git repository."""
    git = shutil.which("git")
    if not git:
        return None
    with contextlib.suppress(subprocess.CalledProcessError):
        # Try superproject first (for submodules)
        output = subprocess.run(
            [git, "rev-parse", "--show-superproject-working-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        if output.returncode == 0 and output.stdout.strip():
            return Path(output.stdout.strip())

        # Fall back to toplevel
        output = subprocess.run(
            [git, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
        )
        if output.returncode == 0 and output.stdout.strip():
            return Path(output.stdout.strip())
    return None


def is_git_dir(directory: Path | None = None) -> bool:
    """Is the given directory version-controlled with git?

    Handles both regular git repositories (.git is a directory) and
    git worktrees (.git is a file pointing to the worktree location).
    """
    directory = directory or Path.cwd()
    git_path = directory / ".git"
    return git_path.is_dir() or git_path.is_file() if git_path.exists() else False


def _walk_up_to_git_root(path: Path | None = None) -> Path:
    """Walk up the directory tree until a .git directory is found."""
    path = path or Path.cwd()
    if path.is_file():
        path = path.parent
    while path != path.parent:
        if is_git_dir(path):
            return path
        path = path.parent
    msg = (
        "No .git directory found in the path hierarchy.\n"
        "CodeWeaver requires a git repository to determine the project root.\n"
        "Please run this command from within a git repository, or initialize one with: git init"
    )
    raise FileNotFoundError(msg)


def _root_path_checks_out(root_path: Path) -> bool:
    """Check if the root path is valid."""
    return root_path.is_dir() and is_git_dir(root_path)


def get_project_path(root_path: Path | None = None) -> Path:
    """Get the root directory of the project.

    Resolution order:
    1. Try git rev-parse to find the git root (if root_path is None)
    2. If root_path is provided and is a valid git directory, use it
    3. Check CODEWEAVER_PROJECT_PATH environment variable (useful for Docker containers
       where .git may not be present)
    4. Walk up the directory tree to find a .git directory
    """
    if (
        root_path is None
        and (git_root := try_git_rev_parse())
        and (_root_path_checks_out(git_root))
    ):
        return git_root
    if isinstance(root_path, Path) and _root_path_checks_out(root_path):
        return root_path

    # Check for CODEWEAVER_PROJECT_PATH environment variable as fallback
    # This is useful for Docker containers where .git may not be present
    # Note: We intentionally don't require a .git directory here since the
    # primary use case is Docker containers without git repositories
    if (env_path := os.environ.get("CODEWEAVER_PROJECT_PATH")) and (
        path := Path(env_path)
    ).is_dir():
        return path

    return _walk_up_to_git_root(root_path)


def set_relative_path(path: Path | str | None) -> Path | None:
    """Validates a path and makes it relative to the project root if the path is absolute.

    If the path is outside the project root (e.g., test temp files), returns the path as-is.
    """
    if path is None:
        return None
    path_obj = Path(path)
    if not path_obj.is_absolute():
        return path_obj

    try:
        base_path = get_project_path()
    except FileNotFoundError:
        # Not in a git repository, return path as-is
        return path_obj

    try:
        return path_obj.relative_to(base_path)
    except ValueError:
        # Path is outside project root (e.g., /tmp test files)
        # Return as-is to allow testing with temporary directories
        return path_obj


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


def get_git_branch(directory: Path) -> str:
    """Get the current branch name of a git repository."""
    git_dir = _get_git_dir(directory)

    if git_dir is MISSING:
        # Try to get project path
        try:
            directory = get_project_path(directory)
        except FileNotFoundError:
            return "detached"
    else:
        directory = cast(Path, git_dir)

    if not has_git():
        return "detached"

    git = shutil.which("git")
    if not git:
        return "detached"

    with contextlib.suppress(subprocess.CalledProcessError):
        output = subprocess.run(
            [git, "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
        )
        branch = output.stdout.strip()

        # If we got HEAD, try to get origin branch
        if not branch or branch == "HEAD":
            origin_branch = _get_branch_from_origin(directory)
            if origin_branch is not MISSING and origin_branch != "HEAD":
                return cast(str, origin_branch)
            return "detached"

        return branch

    return "detached"


def in_codeweaver_clone(path: Path) -> bool:
    """Check if the current repo is CodeWeaver."""
    return (
        "codeweaver" in str(path).lower()
        or "code-weaver" in str(path).lower()
        or bool((rev_dir := try_git_rev_parse()) and "codeweaver" in rev_dir.name.lower())
    )


__all__ = (
    "get_git_branch",
    "get_git_revision",
    "get_project_path",
    "has_git",
    "in_codeweaver_clone",
    "is_git_dir",
    "set_relative_path",
)
