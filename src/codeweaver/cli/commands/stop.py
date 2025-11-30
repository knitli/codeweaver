# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Stop command for CodeWeaver background services.

Gracefully stops background services using signal-based shutdown.
"""

from __future__ import annotations

import os
import signal

from cyclopts import App

from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.config.settings import get_settings_map


_display: StatusDisplay = get_display()
app = App("stop", help="Stop CodeWeaver background services.")


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


async def stop_background_services() -> None:
    """Stop background services gracefully using signal."""
    # Use signal-based shutdown (more secure than HTTP endpoint)
    os.kill(os.getpid(), signal.SIGTERM)


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

    try:
        display.print_command_header("stop", "Stop Background Services")

        # Check if services are running
        if not await is_services_running():
            display.print_warning("Background services not running")
            display.print_info("Nothing to stop")
            return

        display.print_info("Stopping background services...")
        await stop_background_services()

    except Exception as e:
        error_handler.handle_error(e, "Stop command", exit_code=1)


if __name__ == "__main__":
    display = _display
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)
    try:
        app()
    except Exception as e:
        error_handler.handle_error(e, "Stop command", exit_code=1)
