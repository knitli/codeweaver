# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Types used in engine base modules."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any, Literal, NotRequired, Required, TypedDict

from watchfiles import Change


type FileChange = tuple[Change, str]


class WatchfilesArgs(TypedDict, total=False):
    """Arguments for watchfiles module."""

    paths: Required[Sequence[Path | str]]
    """Paths to watch for changes."""
    target: Required[str | Callable[..., Any]]
    """Function or command to run when changes are detected. If the target is a function, it can access the file changes with the `WATCHFILES_CHANGES` environment variable (json)."""
    args: NotRequired[tuple[Any, ...]]
    """Arguments to pass to the target function."""
    kwargs: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the target function."""
    target_type: NotRequired[Literal["function", "command", "auto"]]  # default 'auto'
    """Type of target: 'function', 'command', or 'auto' to detect automatically. Function is a python callable, command is a shell command string."""
    callback: NotRequired[
        Awaitable[Callable[[set[FileChange], Any], Any]]
        | Callable[[set[FileChange], Any], Any]
        | None
    ]
    """Function to call on reload, which is called with the file changes and the target's return value."""
    # NOTE: `watchfiles.arun_process` is incorrectly typed without `Awaitable` in its signature, but the docstring and implementation indicate it can be async. (maybe because Awaitable wasn't in stdlib when the type stubs were written?)
    watch_filter: NotRequired[Callable[[Change | str], bool] | None]
    """Function to filter which file changes should be acted upon. Can also use a `watchfiles.BaseFilter` subclass. `None` means no filtering. The default filter, `watchfiles.DefaultFilter`, ignores standard gitignore subjects for python projects like `__pycache__`, `.git`, `.venv`.

    CodeWeaver uses its own custom filter, which wraps `rignore` to provide the same filtering as we use on the file indexer. You can set its behavior with the `indexing` configuration options."""
    grace_period: NotRequired[float]  # default 0.0
    """Time in seconds to wait after the first change is detected before acting on it."""
    debounce: NotRequired[int]  # default 1_600
    """Maximum time in *milliseconds* to wait before grouping changes and yielding them."""
    step: NotRequired[int]  # default 50
    """Time to wait for new changes in *milliseconds* before yielding grouped changes."""
    debug: NotRequired[bool | None]  # default None
    """Enable debug logging for Watchfiles if True, disable if False, use global setting if None."""
    recursive: NotRequired[bool]  # default True
    """Whether to watch directories recursively."""
    ignore_permission_denied: NotRequired[bool]  # default False
    """Whether to ignore permission denied errors."""

    __all__ = ("FileChange", "WatchfilesArgs")
