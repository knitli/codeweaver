# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Stop command for CodeWeaver background services.

Gracefully stops background services using PID-based process termination.
"""

from __future__ import annotations

from typing import Annotated

from cyclopts import App, Parameter

from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.common.utils.procs import (
    get_daemon_status,
    get_pid_file_path,
    remove_pid_file,
    terminate_process,
)


_display: StatusDisplay = get_display()
app = App("stop", help="Stop CodeWeaver background services.")


async def stop_daemon_process(
    display: StatusDisplay, *, force: bool = False, timeout: float = 10.0
) -> bool:
    """Stop the background daemon process.

    Args:
        display: StatusDisplay instance for output.
        force: If True, forcefully kill the process after timeout.
        timeout: Seconds to wait for graceful shutdown.

    Returns:
        True if the daemon was stopped, False otherwise.
    """
    is_running, pid = get_daemon_status()

    if not is_running or pid is None:
        # Check if there's a stale PID file
        pid_file = get_pid_file_path()
        if pid_file.exists():
            display.print_warning("Found stale PID file, cleaning up...")
            remove_pid_file()
        return False

    display.print_info(f"Found daemon process with PID {pid}")
    display.print_info("Sending shutdown signal...")

    success = terminate_process(pid, timeout=timeout, force=force)

    if success:
        display.print_success(f"Daemon process {pid} terminated successfully")
        remove_pid_file()
        return True
    else:
        display.print_error(f"Failed to terminate daemon process {pid}")
        if not force:
            display.print_info("Try running with --force to forcefully terminate")
        return False


@app.default
async def stop(
    force: Annotated[
        bool,
        Parameter(
            name=["--force", "-f"],
            help="Forcefully terminate the daemon if graceful shutdown fails.",
        ),
    ] = False,
    timeout: Annotated[
        float,
        Parameter(
            name=["--timeout", "-t"],
            help="Seconds to wait for graceful shutdown before giving up or forcing.",
        ),
    ] = 10.0,
) -> None:
    """Stop CodeWeaver background services.

    Gracefully shuts down all background services by sending SIGTERM to the
    daemon process. This triggers the normal shutdown sequence including:
    - Stopping background indexing
    - Flushing statistics
    - Closing connections
    - Cleanup of resources

    Use --force to send SIGKILL if the process doesn't respond to SIGTERM.
    """
    display = _display
    error_handler = CLIErrorHandler(display, verbose=False, debug=False)

    try:
        display.print_command_header("stop", "Stop Background Services")

        stopped = await stop_daemon_process(display, force=force, timeout=timeout)

        if not stopped:
            display.print_warning("Background services are not running")
            display.print_info("Nothing to stop")

    except Exception as e:
        error_handler.handle_error(e, "Stop command", exit_code=1)


if __name__ == "__main__":
    display = _display
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)
    try:
        app()
    except Exception as e:
        error_handler.handle_error(e, "Stop command", exit_code=1)
