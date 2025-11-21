# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Multiprocessing and process utilities."""

from __future__ import annotations

import contextlib
import logging
import sys

from contextlib import contextmanager
from functools import cache
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)


@cache
def asyncio_or_uvloop() -> object:
    """Set uvloop as the event loop policy if available and appropriate."""
    import platform

    from importlib.util import find_spec

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


def get_optimal_workers(task_type: str = "cpu") -> int:
    """Get optimal number of worker threads/processes for a task type.

    Args:
        task_type: Type of task - "cpu" for CPU-bound, "io" for I/O-bound

    Returns:
        Recommended number of workers
    """
    import os

    cpu_count = os.cpu_count() or 4

    if task_type == "io":
        # I/O bound tasks can use more workers
        return min(cpu_count * 2, 32)
    # CPU bound tasks should match core count
    # Leave one core free for system responsiveness
    return max(cpu_count - 1, 1)


__all__ = ("asyncio_or_uvloop", "get_optimal_workers", "low_priority")
