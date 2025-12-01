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
from typing import TYPE_CHECKING

from pydantic import PositiveInt


if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

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
    try:
        import psutil

        cpu_count = get_cpu_count()
        cgroup_limits = psutil.Process().cpu_affinity()
        effective_count = min(len(cgroup_limits), cpu_count)  # type: ignore[arg-type]
        # WSL reports full CPU count, but will sometimes hang or crash if all are used
        return _wsl_count(effective_count)
    except ImportError:
        return _wsl_count(get_cpu_count())


def _wsl_count(count: PositiveInt) -> PositiveInt:
    """Adjust CPU count for WSL environments.

    Args:
        count: Original CPU count

    Returns:
        Adjusted CPU count for WSL environments
    """
    from codeweaver.common.utils.checks import is_wsl

    return max(int(count / 2), 1) if is_wsl() else count


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


# ==============================================================================
# Daemon process management
# ==============================================================================

PID_FILE_NAME = "codeweaver.pid"


def get_pid_file_path() -> "Path":
    """Get the path to the CodeWeaver PID file.

    Returns:
        Path to the PID file in the user config directory.
    """
    from pathlib import Path

    from codeweaver.common.utils.utils import get_user_config_dir

    config_dir = get_user_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / PID_FILE_NAME


def write_pid_file(pid: int | None = None) -> "Path":
    """Write the current process PID to the PID file.

    Args:
        pid: Process ID to write. Defaults to current process PID.

    Returns:
        Path to the written PID file.
    """
    pid_file = get_pid_file_path()
    pid_to_write = pid if pid is not None else os.getpid()
    pid_file.write_text(str(pid_to_write))
    logger.debug("Wrote PID %d to %s", pid_to_write, pid_file)
    return pid_file


def read_pid_file() -> int | None:
    """Read the daemon process PID from the PID file.

    Returns:
        The daemon PID if the file exists and contains a valid integer, None otherwise.
    """
    pid_file = get_pid_file_path()
    if not pid_file.exists():
        return None
    try:
        pid_str = pid_file.read_text().strip()
        return int(pid_str)
    except (ValueError, OSError) as e:
        logger.warning("Failed to read PID file %s: %s", pid_file, e)
        return None


def remove_pid_file() -> bool:
    """Remove the PID file.

    Returns:
        True if the file was removed, False if it didn't exist.
    """
    pid_file = get_pid_file_path()
    if pid_file.exists():
        pid_file.unlink()
        logger.debug("Removed PID file %s", pid_file)
        return True
    return False


def is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running.

    Args:
        pid: Process ID to check.

    Returns:
        True if the process is running, False otherwise.
    """
    try:
        import psutil

        if not psutil.pid_exists(pid):
            return False
        # Check process status to exclude zombies
        try:
            proc = psutil.Process(pid)
            return proc.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    except ImportError:
        # Fallback without psutil
        if sys.platform == "win32":
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        else:
            try:
                os.kill(pid, 0)  # Signal 0 checks if process exists
                return True
            except OSError:
                return False


def terminate_process(pid: int, *, timeout: float = 5.0, force: bool = False) -> bool:
    """Terminate a process gracefully with optional force kill.

    Sends SIGTERM first, waits for timeout, then sends SIGKILL if force=True
    and the process is still running.

    Args:
        pid: Process ID to terminate.
        timeout: Seconds to wait for graceful shutdown.
        force: If True, forcefully kill the process after timeout.

    Returns:
        True if the process was terminated, False if it wasn't running.
    """
    import signal
    import time

    if not is_process_running(pid):
        logger.debug("Process %d is not running", pid)
        return False

    try:
        # Send SIGTERM for graceful shutdown
        if sys.platform == "win32":
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(1, False, pid)  # PROCESS_TERMINATE
            if handle:
                kernel32.TerminateProcess(handle, 0)
                kernel32.CloseHandle(handle)
        else:
            os.kill(pid, signal.SIGTERM)

        logger.debug("Sent SIGTERM to process %d", pid)

        # Wait for process to terminate
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            if not is_process_running(pid):
                logger.debug("Process %d terminated gracefully", pid)
                return True
            time.sleep(0.1)

        # Process still running after timeout
        if force and is_process_running(pid):
            logger.warning("Process %d did not terminate, sending SIGKILL", pid)
            if sys.platform != "win32":
                os.kill(pid, signal.SIGKILL)
            # On Windows, TerminateProcess is already forceful
            time.sleep(0.5)
            return not is_process_running(pid)

        return not is_process_running(pid)

    except (OSError, PermissionError) as e:
        logger.error("Failed to terminate process %d: %s", pid, e)
        return False


def get_daemon_status() -> tuple[bool, int | None]:
    """Get the status of the CodeWeaver daemon process.

    Returns:
        Tuple of (is_running, pid). pid is None if not running or PID file doesn't exist.
    """
    pid = read_pid_file()
    if pid is None:
        return False, None
    return is_process_running(pid), pid


__all__ = (
    "asyncio_or_uvloop",
    "get_daemon_status",
    "get_optimal_workers",
    "get_pid_file_path",
    "is_process_running",
    "low_priority",
    "read_pid_file",
    "remove_pid_file",
    "terminate_process",
    "very_low_priority",
    "write_pid_file",
)
