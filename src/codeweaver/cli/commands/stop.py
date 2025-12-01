# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Stop command for CodeWeaver background services.

Gracefully stops background services using signal-based shutdown.
"""

from __future__ import annotations

import asyncio
import signal

from pathlib import Path
from cyclopts import App

from codeweaver.cli.daemon import DaemonManager
from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.config.settings import get_settings_map


_display: StatusDisplay = get_display()
app = App("stop", help="Stop CodeWeaver background services.")


def _get_pid_file_path() -> Path:
    """Get the PID file path for daemon tracking."""
    from codeweaver.config.paths import get_codeweaver_home

    return get_codeweaver_home() / "background_services.pid"


async def is_services_running() -> bool:
    """Check if background services are running via management server."""
    try:
        import httpx
    except ImportError:
        return False

    settings_map = get_settings_map()
    mgmt_host = settings_map.get("management_host", "127.0.0.1")
    mgmt_port = settings_map.get("management_port", 9329)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{mgmt_host}:{mgmt_port}/health", timeout=2.0)
            return response.status_code == 200
    except Exception:
        return False


async def stop_background_services(daemon_manager: DaemonManager) -> None:
    """Stop background services gracefully using signal.

    Args:
        daemon_manager: DaemonManager instance for PID tracking

    Raises:
        RuntimeError: If daemon process cannot be found or signaled
    """
    pid = daemon_manager.get_pid()

    if pid is None:
        raise RuntimeError("Cannot find background services process (no PID file)")

    # Send SIGTERM to daemon process (NOT os.getpid()!)
    success = daemon_manager.send_signal(signal.SIGTERM)

    if not success:
        raise RuntimeError(f"Failed to signal process {pid} (process may have already exited)")

    # Wait for process to stop (with timeout)
    max_wait_seconds = 10
    for _ in range(max_wait_seconds * 2):  # Check every 0.5 seconds
        if not daemon_manager.is_running():
            # Process stopped successfully
            daemon_manager.remove_pid_file()
            return

        await asyncio.sleep(0.5)

    # Timeout reached, process still running
    raise RuntimeError(
        f"Background services did not stop within {max_wait_seconds} seconds. "
        f"You may need to manually kill process {pid}"
    )


@app.default
async def stop() -> None:
    """Stop CodeWeaver background services.

    Gracefully shuts down all background services using SIGTERM signal.
    This triggers the normal shutdown sequence including:
    - Stopping background indexing
    - Flushing statistics
    - Closing connections
    - Cleanup of resources
    """
    display = _display
    error_handler = CLIErrorHandler(display, verbose=False, debug=False)
    pid_file_path = _get_pid_file_path()
    daemon_manager = DaemonManager(pid_file_path)

    try:
        display.print_command_header("stop", "Stop Background Services")

        # Check if services are running using DaemonManager
        if not daemon_manager.is_running():
            display.print_warning("Background services not running")
            display.print_info("Nothing to stop")
            return

        pid = daemon_manager.get_pid()
        display.print_info(f"Stopping background services (PID: {pid})...")

        await stop_background_services(daemon_manager)

        display.print_success("Background services stopped successfully")

    except Exception as e:
        error_handler.handle_error(e, "Stop command", exit_code=1)


if __name__ == "__main__":
    display = _display
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)
    try:
        app()
    except Exception as e:
        error_handler.handle_error(e, "Stop command", exit_code=1)
