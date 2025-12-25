# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Multiprocessing and process utilities."""

from __future__ import annotations

import contextlib
import logging
import os
import platform
import sys

from contextlib import contextmanager
from functools import cache
from importlib.util import find_spec
from typing import TYPE_CHECKING

from pydantic import PositiveInt


if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)


def python_version() -> tuple[str, str, str]:
    """Get the current Python version tuple.

    Returns:
        Python version tuple
    """
    return platform.python_version_tuple()


def get_cpu_count() -> PositiveInt:
    """Get the number of CPUs available on the system.

    NOTE: For most use cases, use `effective_cpu_count` instead to account for cgroup and other resource limits.

    Returns:
        Number of CPUs as a positive integer
    """
    # we can't use a trinary here because it will error if they're running 3.12
    if python_version() >= ("3", "13", "0"):  # noqa: SIM108
        cpu_func = os.process_cpu_count  # ty: ignore[unresolved-attribute]
    else:
        cpu_func = os.cpu_count
    return cpu_func()  # ty: ignore[invalid-return-type]


def effective_cpu_count() -> PositiveInt:
    """Get the effective number of CPUs available, considering cgroup limits.

    Returns:
        Effective number of CPUs as a positive integer
    """
    if not find_spec("psutil"):
        return _wsl_count(get_cpu_count())
    import psutil

    cpu_count = get_cpu_count()
    cgroup_limits = psutil.Process().cpu_affinity()
    effective_count = min(len(cgroup_limits), cpu_count)  # type: ignore[arg-type]
    # WSL reports full CPU count, but will sometimes hang or crash if all are used
    return _wsl_count(effective_count)


def _wsl_count(count: PositiveInt) -> PositiveInt:
    """Adjust CPU count for WSL environments.

    Most users run WSL with default settings, which exposes all host CPUs to the WSL instance. If we actually try to use all CPUs, WSL can hang or crash. To avoid this, we halve the CPU count in WSL environments.

    Args:
        count: Original CPU count

    Returns:
        Adjusted CPU count for WSL environments
    """
    from codeweaver.core import is_wsl

    return max(int(count / 2), 1) if is_wsl() else count


@cache
def asyncio_or_uvloop() -> object:
    """Set uvloop as the event loop policy if available and appropriate."""
    if (
        sys.platform not in {"win32", "cygwin", "wasi", "ios"}
        and platform.python_implementation() == "CPython"
        and find_spec("uvloop") is not None
    ):
        import uvloop

        return uvloop
    import asyncio

    return asyncio


@contextmanager
def low_priority() -> Generator[None, None, None]:
    """Context manager to run code at low process priority.

    Lowers the process priority (nice value on Unix, below-normal on Windows)
    for resource-intensive operations like embedding generation. This prevents
    the indexing process from starving other system processes.

    Priority is automatically restored when exiting the context.

    Example:
        with low_priority():
            await embed_all_chunks(chunks)

    Yields:
        None
    """
    original_nice: int | None = None
    original_priority_class: int | None = None

    try:
        import psutil

        process = psutil.Process()

        if sys.platform == "win32":
            # Windows: Use priority classes
            original_priority_class = process.nice()
            # BELOW_NORMAL_PRIORITY_CLASS = 0x4000
            process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            logger.debug("Set process priority to BELOW_NORMAL")
        else:
            # Unix: Use nice value (higher = lower priority)
            original_nice = process.nice()
            # Set nice to 10 (low priority, but not lowest)
            # Range is -20 (highest) to 19 (lowest)
            new_nice = min(original_nice + 10, 19)
            process.nice(new_nice)
            logger.debug("Set process nice value to %d (was %d)", new_nice, original_nice)

    except ImportError:
        logger.debug("psutil not available, running at normal priority")
    except (psutil.AccessDenied, OSError) as e:
        logger.debug("Could not set process priority: %s", e)

    try:
        yield
    finally:
        # Restore original priority
        with contextlib.suppress(Exception):
            if original_nice is not None or original_priority_class is not None:
                import psutil

                process = psutil.Process()

                if sys.platform == "win32" and original_priority_class is not None:
                    process.nice(original_priority_class)
                    logger.debug("Restored process priority class")
                elif original_nice is not None:
                    process.nice(original_nice)
                    logger.debug("Restored process nice value to %d", original_nice)


@contextmanager
def very_low_priority() -> Generator[None, None, None]:
    """Context manager to run code at very low process priority.

    Sets the absolute lowest priority (nice 19 on Unix, IDLE_PRIORITY_CLASS on Windows)
    for background operations like backup syncing that should never interfere with
    normal system operation.

    Priority is automatically restored when exiting the context.

    Example:
        with very_low_priority():
            await sync_to_backup_store(chunks)

    Yields:
        None
    """
    original_nice: int | None = None
    original_priority_class: int | None = None

    try:
        import psutil

        process = psutil.Process()

        if sys.platform == "win32":
            # Windows: Use IDLE priority class (lowest)
            original_priority_class = process.nice()
            process.nice(psutil.IDLE_PRIORITY_CLASS)
            logger.debug("Set process priority to IDLE")
        else:
            # Unix: Set to absolute lowest (nice 19)
            original_nice = process.nice()
            process.nice(19)
            logger.debug("Set process nice value to 19 (was %d)", original_nice)

    except ImportError:
        logger.debug("psutil not available, running at normal priority")
    except (psutil.AccessDenied, OSError) as e:
        logger.debug("Could not set process priority: %s", e)

    try:
        yield
    finally:
        # Restore original priority
        with contextlib.suppress(Exception):
            if original_nice is not None or original_priority_class is not None:
                import psutil

                process = psutil.Process()

                if sys.platform == "win32" and original_priority_class is not None:
                    process.nice(original_priority_class)
                    logger.debug("Restored process priority class")
                elif original_nice is not None:
                    process.nice(original_nice)
                    logger.debug("Restored process nice value to %d", original_nice)


def get_optimal_workers(task_type: str = "cpu") -> int:
    """Get optimal number of worker threads/processes for a task type.

    Args:
        task_type: Type of task - "cpu" for CPU-bound, "io" for I/O-bound

    Returns:
        Recommended number of workers
    """
    cpu_count = effective_cpu_count()

    return min(cpu_count * 2, 16) if task_type == "io" else max(cpu_count - 1, 1)


__all__ = ("asyncio_or_uvloop", "get_optimal_workers", "low_priority", "very_low_priority")
