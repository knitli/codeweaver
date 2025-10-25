# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Git and Path related utilities."""

from __future__ import annotations

# ruff: noqa: S607
import contextlib
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


MISSING: Missing = Missing(SentinelName("Missing"), "<MISSING>")


def try_git_rev_parse() -> Path | None:
    """Attempt to use git to get the root directory of the current git repository."""
    if not has_git():
        return None
    git = shutil.which("git")
    with contextlib.suppress(subprocess.CalledProcessError):
        output = subprocess.run(
            ["rev-parse", "--show-superproject-working-tree", "--show-toplevel", "|", "head", "-1"],
            executable=git,
            capture_output=True,
            text=True,
        )
        return Path(output.stdout.strip())
    return None


def is_git_dir(directory: Path | None = None) -> bool:
    """Is the given directory version-controlled with git?"""
    directory = directory or Path.cwd()
    if (git_dir := (directory / ".git")) and git_dir.exists():
        return git_dir.is_dir()
    return False


def _walk_down_to_git_root(path: Path | None = None) -> Path:
    """Walk up the directory tree until a .git directory is found."""
    path = path or Path.cwd()
    if path.is_file():
        path = path.parent
    while path != path.parent:
        if is_git_dir(path):
            return path
        path = path.parent
    raise FileNotFoundError("No .git directory found in the path hierarchy.")


def _root_path_checks_out(root_path: Path) -> bool:
    """Check if the root path is valid."""
    return root_path.is_dir() and is_git_dir(root_path)


def get_project_root(root_path: Path | None = None) -> Path:
    """Get the root directory of the project."""
    return (
        root_path
        if isinstance(root_path, Path) and _root_path_checks_out(root_path)
        else _walk_down_to_git_root(root_path)
    )  # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType]


def set_relative_path(path: Path | str | None) -> Path | None:
    """Validates a path and makes it relative to the project root if the path is absolute."""
    if path is None:
        return None
    path_obj = Path(path)
    if not path_obj.is_absolute():
        return path_obj

    base_path = get_project_root()
    return path_obj.relative_to(base_path)


def has_git() -> bool:
    """Check if git is installed and available."""
    git = shutil.which("git")
    if not git:
        return False
    with contextlib.suppress(subprocess.CalledProcessError):
        output = subprocess.run(
            ["--version"], executable=git, stderr=subprocess.STDOUT, capture_output=True
        )
        return output.returncode == 0
    return False


def _get_git_dir(directory: Path) -> Path | Missing:
    """Get the .git directory of a git repository."""
    if not is_git_dir(directory):
        with contextlib.suppress(FileNotFoundError):
            directory = get_project_root() or Path.cwd()
        if not directory or not is_git_dir(directory):
            return MISSING
    return directory


def get_git_revision(directory: Path) -> str | Missing:
    """Get the SHA-1 of the HEAD of a git repository.

    TODO: (big one): This is a precursor for future functionality. We'd like to be able to associate indexes and other artifacts with a specific git commit. Because there's nothing worse than an Agent working from a totally different context than the one you expect. We need to track changes across commits, branches, etc. This is a first step. We'll need to figure out how manage partial indexes, diffs, etc. later.
    """
    git_dir = _get_git_dir(directory)
    if git_dir is MISSING:
        return MISSING
    directory = cast(Path, git_dir)
    if has_git():
        git = shutil.which("git")
        with contextlib.suppress(subprocess.CalledProcessError):
            output = subprocess.run(
                ["rev-parse", "--short", "HEAD"],
                executable=git,
                cwd=directory,
                capture_output=True,
                text=True,
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
            ["rev-parse", "--abbrev-ref", "origin/HEAD"],
            executable=git,
            cwd=directory,
            capture_output=True,
            text=True,
        )
        branch = output.stdout.strip().removeprefix("origin/")
        if branch and "/" in branch:
            return branch.split("/", 1)[1]
        if branch:
            return branch
    return MISSING


def get_git_branch(directory: Path) -> str | Missing:
    """Get the current branch name of a git repository."""
    git_dir = _get_git_dir(directory)
    if git_dir is MISSING:
        return MISSING
    directory = cast(Path, git_dir)
    if has_git():
        git = shutil.which("git")
        with contextlib.suppress(subprocess.CalledProcessError):
            output = subprocess.run(
                ["rev-parse", "--abbrev-ref", "HEAD"],
                executable=git,
                cwd=directory,
                capture_output=True,
                text=True,
            )
            if branch := output.stdout.strip():
                return branch if branch != "HEAD" else _get_branch_from_origin(directory)
            if branch is MISSING:
                return "detached"
    return MISSING


def in_codeweaver_clone(path: Path) -> bool:
    """Check if the current repo is CodeWeaver."""
    return (
        "codeweaver" in str(path).lower()
        or "code-weaver" in str(path).lower()
        or bool((rev_dir := try_git_rev_parse()) and "codeweaver" in rev_dir.name.lower())
    )  # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType]


__all__ = (
    "MISSING",
    "Missing",
    "get_git_branch",
    "get_git_revision",
    "get_project_root",
    "has_git",
    "in_codeweaver_clone",
    "is_git_dir",
    "set_relative_path",
)
