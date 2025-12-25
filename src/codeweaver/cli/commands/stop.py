# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Stop command for CodeWeaver background services.

Gracefully stops background services via the management server API.
"""

from __future__ import annotations

from typing import Annotated

from codeweaver_daemon import check_daemon_health, request_daemon_shutdown, wait_for_daemon_shutdown
from cyclopts import App, Parameter
from pydantic import PositiveInt

from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.config.settings import get_settings_map
from codeweaver.core.types.sentinel import Unset


_display: StatusDisplay = get_display()
app = App("stop", help="Stop CodeWeaver background services.")


def _get_default_host_port() -> tuple[str, int]:
    """Get default management host/port from settings."""
    settings_map = get_settings_map()
    mgmt_host = (
        settings_map["management_host"]
        if settings_map["management_host"] is not Unset
        else "127.0.0.1"
    )
    mgmt_port = (
        settings_map["management_port"] if settings_map["management_port"] is not Unset else 9329
    )
    return mgmt_host, mgmt_port


@app.default
async def stop(
    management_host: Annotated[
        str | None,
        Parameter(
            name=["--management-host"],
            help="Management server host (default: from settings or 127.0.0.1)",
        ),
    ] = None,
    management_port: Annotated[
        PositiveInt | None,
        Parameter(
            name=["--management-port"],
            help="Management server port (default: from settings or 9329)",
        ),
    ] = None,
    *,
    timeout: Annotated[  # noqa: ASYNC109  # acceptable for a command line argument
        float,
        Parameter(name=["--timeout", "-t"], help="Maximum time to wait for shutdown (seconds)"),
    ] = 30.0,
) -> None:
    """Stop CodeWeaver background services.

    Requests graceful shutdown via the management server API, then waits
    for the daemon to terminate. This triggers the normal shutdown sequence:
    - Stopping background indexing
    - Flushing statistics
    - Closing connections
    - Cleanup of resources

    Examples:
        cw stop                    # Stop with default settings
        cw stop --timeout 60       # Wait up to 60 seconds for shutdown
    """
    display = _display
    error_handler = CLIErrorHandler(display, verbose=False, debug=False)

    # Resolve host/port
    default_host, default_port = _get_default_host_port()
    host = management_host or default_host
    port = management_port or default_port

    try:
        display.print_command_header("stop", "Stop Background Services")

        # Check if services are running
        if not await check_daemon_health(host, port):
            display.print_warning("Background services not running")
            display.print_info("Nothing to stop")
            return

        display.print_info("Requesting daemon shutdown...")

        # Request shutdown via management API
        if not await request_daemon_shutdown(host, port, timeout_at=10.0):
            display.print_error("Failed to request shutdown")
            display.print_info("The daemon may not be responding. You can try:", prefix="💡")
            display.print_info("  - Check logs: journalctl --user -u codeweaver.service")
            display.print_info("  - Force stop: pkill -f 'codeweaver start'")
            return

        display.print_info("Waiting for daemon to shut down...")

        # Wait for shutdown to complete
        if await wait_for_daemon_shutdown(host, port, max_wait_seconds=timeout):
            display.print_success("CodeWeaver daemon stopped successfully")
        else:
            display.print_warning(f"Daemon did not shut down within {timeout} seconds")
            display.print_info("The daemon may still be shutting down. You can:", prefix="💡")
            display.print_info("  - Wait and check: cw status")
            display.print_info("  - Force stop: pkill -f 'codeweaver start'")

    except Exception as e:
        error_handler.handle_error(e, "Stop command", exit_code=1)


if __name__ == "__main__":
    display = _display
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)
    try:
        app()
    except Exception as e:
        error_handler.handle_error(e, "Stop command", exit_code=1)
