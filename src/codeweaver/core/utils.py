# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# ruff: noqa: S603

"""Internal helper utilities for the core package."""

from __future__ import annotations

import contextlib
import logging
import os
import re
import shutil
import subprocess
import sys
import unicodedata

from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast


if TYPE_CHECKING:
    from pydantic import UUID7
    from pydantic.types import NonNegativeFloat, NonNegativeInt


logger = logging.getLogger(__name__)

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


def ensure_iterable[T](value: Iterable[T] | T) -> Iterable[T]:
    """Ensure the value is iterable.

    Note: If you pass `ensure_iterable` a `Mapping` (like a `dict`), it will yield the keys of the mapping, not its items/values.
    """
    if isinstance(value, Iterable) and not isinstance(value, (bytes | bytearray | str)):
        yield from cast(Iterable[T], value)
    else:
        yield cast(T, value)


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


if sys.version_info < (3, 14):
    from uuid_extensions import uuid7 as uuid7_gen
else:
    from uuid import uuid7 as uuid7_gen


def uuid7() -> UUID7:
    """Generate a new UUID7."""
    from pydantic import UUID7

    return cast(UUID7, uuid7_gen())


@cache
def get_user_config_dir(*, base_only: bool = False) -> Path:
    """Get the user configuration directory based on the operating system."""
    import platform

    if (system := platform.system()) == "Windows":
        config_dir = Path(os.getenv("APPDATA", Path("~\\AppData\\Roaming").expanduser()))
    elif system == "Darwin":
        config_dir = Path.home() / "Library" / "Application Support"
    else:
        config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_dir if base_only else config_dir / "codeweaver"


def elapsed_time_to_human_readable(elapsed_seconds: NonNegativeFloat | NonNegativeInt) -> str:
    """Convert elapsed time between start_time and end_time to a human-readable format."""
    minutes, sec = divmod(int(elapsed_seconds), 60)
    hours, min_ = divmod(minutes, 60)
    days, hr = divmod(hours, 24)
    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}d")
    if hr > 0:
        parts.append(f"{hr}h")
    if min_ > 0:
        parts.append(f"{min_}m")
    parts.append(f"{sec}s")
    return " ".join(parts)


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
    """Is the given directory version-controlled with git?"""
    directory = directory or Path.cwd()
    git_path = directory / ".git"
    return git_path.is_dir() or git_path.is_file() if git_path.exists() else False


def _root_path_checks_out(path: Path) -> bool:
    """Check if the given path is a valid git repository root."""
    return path.is_dir() and is_git_dir(path)


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
        "CodeWeaver requires a git repository to determine the project root."
    )
    raise FileNotFoundError(msg)


def get_project_path(root_path: Path | None = None) -> Path:
    """Get the root directory of the project."""
    if (
        root_path is None
        and (git_root := try_git_rev_parse())
        and (git_root.is_dir() and is_git_dir(git_root))
    ):
        return git_root
    if isinstance(root_path, Path) and root_path.is_dir() and is_git_dir(root_path):
        return root_path

    if (env_path := os.environ.get("CODEWEAVER_PROJECT_PATH")) and (
        path := Path(env_path)
    ).is_dir():
        return path

    return _walk_up_to_git_root(root_path)


def set_relative_path(path: Path | str | None, base_path: Path | None = None) -> Path | None:
    """Validates a path and makes it relative to the project root if the path is absolute."""
    if path is None:
        return None
    path_obj = Path(path).resolve()
    if not path_obj.is_absolute():
        return path_obj

    try:
        base_path = (base_path or get_project_path()).resolve()
    except FileNotFoundError:
        return path_obj

    try:
        return path_obj.relative_to(base_path)
    except ValueError:
        return path_obj


def has_git() -> bool:
    """Check if git is installed and available."""
    git = shutil.which("git")
    if not git:
        return False
    # Verify git command works
    output = subprocess.run([git, "--version"], capture_output=True, check=False)
    return output.returncode == 0


NORMALIZE_FORM = "NFKC"
CONTROL_CHARS = [chr(i) for i in range(0x20) if i not in (9, 10, 13)]
INVISIBLE_CHARS = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", *CONTROL_CHARS)
INVISIBLE_PATTERN = re.compile("|".join(re.escape(c) for c in INVISIBLE_CHARS))
POSSIBLE_PROMPT_INJECTS = (
    r"[<(\|=:]\s*system\s*[>)\|=:]",
    r"[<(\|=:]\s*instruction\s*[>)\|=:]",
    r"\b(?:ignore|disregard|forget|cancel|override|void)\b(?:\s+(?:previous|above|all|prior|earlier|former|before|other|last|everything|this)){0,2}\s*(?:instruct(?:ions?)?|direction(?:s?)?|directive(?:s?)?|command(?:s?)?|request(?:s?)?|order(?:s?)?|message(?:s?)?|prompt(?:s?)?)\b",
)
INJECT_PATTERN = re.compile("|".join(POSSIBLE_PROMPT_INJECTS), re.IGNORECASE)


@cache
def normalize_ext(ext: str) -> str:
    """Normalize a file extension to a standard format. Cached because of hot/repetitive use."""
    return ext.lower().strip() if ext.startswith(".") else f".{ext.lower().strip()}"


def sanitize_unicode(
    text: str | bytes | bytearray,
    normalize_form: Literal["NFC", "NFKC", "NFD", "NFKD"] = NORMALIZE_FORM,
) -> str:
    """Sanitize unicode text by normalizing and removing invisible/control characters."""
    if isinstance(text, bytes | bytearray):
        text = text.decode("utf-8", errors="ignore")
    if not text.strip():
        return ""

    text = unicodedata.normalize(normalize_form, cast(str, text))
    filtered = INVISIBLE_PATTERN.sub("", text)

    matches = list(INJECT_PATTERN.finditer(filtered))
    for match in reversed(matches):
        start, end = match.span()
        logger.warning("Possible prompt injection detected and neutralized: %s", match.group(0))
        replacement = "[[ POSSIBLE PROMPT INJECTION REMOVED ]]"
        filtered = filtered[:start] + replacement + filtered[end:]

    return filtered.strip()


from codeweaver.core.types.aliases import SentinelName
from codeweaver.core.types.sentinel import Sentinel


class Missing(Sentinel):
    """Sentinel for missing values."""


MISSING: Missing = Missing(name=SentinelName("MISSING"), module_name=__name__)


def in_codeweaver_clone(path: Path) -> bool:
    """Check if the current repo is CodeWeaver."""
    return (
        "codeweaver" in str(path).lower()
        or "code-weaver" in str(path).lower()
        or bool((rev_dir := try_git_rev_parse()) and "codeweaver" in rev_dir.name.lower())
    )


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
                [git, "rev-parse", "--short", "HEAD"],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )
            return output.stdout.strip()
    return MISSING


def _get_branch_from_origin(directory: Path) -> str | Missing:
    """Get the branch name from the origin remote."""
    git = shutil.which("git")
    if not git:
        return MISSING
    try:
        output = subprocess.run(
            [git, "rev-parse", "--abbrev-ref", "origin/HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
        branch: str = output.stdout.strip().removeprefix("origin/")
    except Exception:
        return MISSING
    else:
        return branch or MISSING


def get_git_branch(directory: Path) -> str:
    """Get the current branch name of a git repository."""
    if not is_git_dir(directory):
        try:
            directory = get_project_path(directory)
        except Exception:
            return "detached"

    if not shutil.which("git"):
        return "detached"

    git = shutil.which("git")
    try:
        output = subprocess.run(
            [cast(str, git), "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
        branch = output.stdout.strip()

        if not branch or branch == "HEAD":
            origin_branch = _get_branch_from_origin(directory)
            if origin_branch not in ("HEAD", MISSING):
                return cast(str, origin_branch)
            return "detached"
    except Exception:
        return "detached"
    else:
        return branch


__all__ = (
    "MISSING",
    "TEST_FILE_PATTERNS",
    "_get_branch_from_origin",
    "_get_git_dir",
    "_root_path_checks_out",
    "_walk_up_to_git_root",
    "elapsed_time_to_human_readable",
    "ensure_iterable",
    "get_git_branch",
    "get_git_revision",
    "get_project_path",
    "get_tooling_dirs",
    "get_user_config_dir",
    "has_git",
    "in_codeweaver_clone",
    "is_git_dir",
    "normalize_ext",
    "sanitize_unicode",
    "set_relative_path",
    "truncate_text",
    "try_git_rev_parse",
    "uuid7",
)
