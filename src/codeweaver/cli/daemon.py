# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Claude (AI Assistant)
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Daemon process management utilities for background services.

Provides PID file management, process daemonization, and signal handling
for CodeWeaver background services.
"""

from __future__ import annotations

import os
import signal
import sys

from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable


class DaemonManager:
    """Manages daemon process lifecycle with PID file tracking.

    Provides functionality to:
    - Track daemon process via PID file
    - Daemonize processes (fork, detach, redirect I/O)
    - Signal daemon processes
    - Validate daemon status

    Args:
        pid_file_path: Path to PID file for tracking daemon process
    """

    def __init__(self, pid_file_path: Path) -> None:
        """Initialize daemon manager with PID file path."""
        self.pid_file_path = pid_file_path

    def is_running(self) -> bool:
        """Check if daemon is running based on PID file and process existence.

        Returns:
            True if daemon process is running, False otherwise
        """
        pid = self.get_pid()
        if pid is None:
            return False

        # Validate process exists
        try:
            # Send signal 0 to check if process exists (doesn't actually send signal)
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            # Process doesn't exist, clean up stale PID file
            self.remove_pid_file()
            return False
        except PermissionError:
            # Process exists but we don't have permission to signal it
            # Assume it's running
            return True

    def get_pid(self) -> int | None:
        """Read PID from file if it exists.

        Returns:
            PID as integer if file exists and is valid, None otherwise
        """
        if not self.pid_file_path.exists():
            return None

        try:
            pid_str = self.pid_file_path.read_text().strip()
            return int(pid_str)
        except (ValueError, OSError):
            # Invalid PID file, remove it
            self.remove_pid_file()
            return None

    def write_pid(self, pid: int | None = None) -> None:
        """Write PID to file.

        Args:
            pid: Process ID to write. If None, uses current process ID.
        """
        if pid is None:
            pid = os.getpid()

        # Ensure directory exists
        self.pid_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write PID to file
        self.pid_file_path.write_text(str(pid))

    def remove_pid_file(self) -> None:
        """Remove PID file (cleanup)."""
        try:
            self.pid_file_path.unlink(missing_ok=True)
        except OSError:
            # Ignore errors during cleanup
            pass

    def send_signal(self, sig: signal.Signals) -> bool:
        """Send signal to daemon process.

        Args:
            sig: Signal to send (e.g., signal.SIGTERM)

        Returns:
            True if signal sent successfully, False otherwise
        """
        pid = self.get_pid()
        if pid is None:
            return False

        try:
            os.kill(pid, sig)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def daemonize(
        self,
        *,
        redirect_stdout: Path | None = None,
        redirect_stderr: Path | None = None,
    ) -> None:
        """Fork and detach process to run as daemon.

        Implements double-fork pattern to properly daemonize process:
        1. First fork creates child process
        2. Parent exits, child becomes orphan (adopted by init)
        3. Child creates new session (setsid)
        4. Second fork ensures process cannot acquire controlling terminal
        5. Redirect standard file descriptors

        Args:
            redirect_stdout: Path to redirect stdout (default: /dev/null)
            redirect_stderr: Path to redirect stderr (default: /dev/null)

        Raises:
            OSError: If fork fails
        """
        # First fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent process exits
                sys.exit(0)
        except OSError as e:
            raise OSError(f"First fork failed: {e}") from e

        # Decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                # First child exits
                sys.exit(0)
        except OSError as e:
            raise OSError(f"Second fork failed: {e}") from e

        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()

        # Redirect stdin to /dev/null
        with open("/dev/null") as dev_null:
            os.dup2(dev_null.fileno(), sys.stdin.fileno())

        # Redirect stdout
        if redirect_stdout:
            redirect_stdout.parent.mkdir(parents=True, exist_ok=True)
            with open(redirect_stdout, "a") as stdout_file:
                os.dup2(stdout_file.fileno(), sys.stdout.fileno())
        else:
            with open("/dev/null", "a") as dev_null:
                os.dup2(dev_null.fileno(), sys.stdout.fileno())

        # Redirect stderr
        if redirect_stderr:
            redirect_stderr.parent.mkdir(parents=True, exist_ok=True)
            with open(redirect_stderr, "a") as stderr_file:
                os.dup2(stderr_file.fileno(), sys.stderr.fileno())
        else:
            with open("/dev/null", "a") as dev_null:
                os.dup2(dev_null.fileno(), sys.stderr.fileno())


def setup_signal_handlers(
    cleanup_callback: Callable[[], None] | None = None,
) -> None:
    """Install signal handlers for graceful shutdown.

    Args:
        cleanup_callback: Optional callback to run on shutdown signals
    """

    def handle_shutdown(signum: int, frame: object) -> None:
        """Handle shutdown signals."""
        if cleanup_callback:
            cleanup_callback()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
