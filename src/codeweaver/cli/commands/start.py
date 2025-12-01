# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Start command for CodeWeaver background services.

Starts background services (indexing, file watching, health monitoring, telemetry)
independently of the MCP server. Supports both daemon (background) and foreground modes.
"""

from __future__ import annotations

import asyncio
import os
import sys

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from cyclopts import App, Parameter
from pydantic import FilePath, PositiveInt

from codeweaver.cli.daemon import DaemonManager, setup_signal_handlers
from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.core.types.sentinel import Unset


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types.dictview import DictView

_display: StatusDisplay = get_display()
app = App("start", help="Start CodeWeaver background services.")


def _get_settings_map() -> DictView[CodeWeaverSettingsDict]:
    """Get the current settings map."""
    from codeweaver.config.settings import get_settings_map

    return get_settings_map()


def _get_pid_file_path() -> Path:
    """Get the PID file path for daemon tracking."""
    from codeweaver.config.paths import get_codeweaver_home

    return get_codeweaver_home() / "background_services.pid"


async def are_services_running() -> bool:
    """Check if background services are running via management server."""
    try:
        import httpx
    except ImportError:
        return False

    settings_map = _get_settings_map()
    mgmt_host = (
        settings_map["management_host"]
        if settings_map["management_host"] is not Unset
        else "127.0.0.1"
    )
    mgmt_port = (
        settings_map["management_port"] if settings_map["management_port"] is not Unset else 9329
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{mgmt_host}:{mgmt_port}/health", timeout=2.0)
            return response.status_code == 200
    except Exception:
        return False


async def start_cw_services(
    display: StatusDisplay,
    daemon_manager: DaemonManager,
    config_path: Path | None = None,
    project_path: Path | None = None,
    *,
    start_mcp_http_server: bool = False,  # Currently unused, reserved for future
    mcp_host: str | None = None,
    mcp_port: PositiveInt | None = None,
) -> None:
    """Start background services using the new lifespan architecture."""
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.config.settings import get_settings
    from codeweaver.server.lifespan import background_services_lifespan
    from codeweaver.server.management import ManagementServer

    # Setup signal handlers for graceful shutdown
    def cleanup() -> None:
        daemon_manager.remove_pid_file()

    setup_signal_handlers(cleanup)

    # Load settings
    settings = get_settings()
    if config_path:
        settings.config_file = config_path  # type: ignore
    if project_path:
        settings.project_path = project_path

    statistics = get_session_statistics()

    # Use background_services_lifespan (the new Phase 1 implementation)
    async with background_services_lifespan(
        settings=settings,
        statistics=statistics,
        status_display=display,
        verbose=False,
        debug=False,
    ) as background_state:
        # Start management server
        mgmt_host = getattr(settings, "management_host", "127.0.0.1")
        mgmt_port = getattr(settings, "management_port", 9329)

        management_server = ManagementServer(background_state)
        await management_server.start(host=mgmt_host, port=mgmt_port)

        display.print_success("Background services started successfully")
        display.print_info(
            f"Management server: http://{mgmt_host}:{mgmt_port}", prefix="🌐"
        )

        try:
            # Keep services running until interrupted
            if management_server.server_task:
                await management_server.server_task
            else:
                # Wait indefinitely if task not set (shouldn't happen)
                await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            display.print_warning("Shutting down background services...")
        finally:
            await management_server.stop()
            daemon_manager.remove_pid_file()


@app.default
async def start(
    config_file: Annotated[
        FilePath | None,
        Parameter(
            name=["--config-file", "-c"],
            help="Path to CodeWeaver configuration file, only needed if not using defaults.",
        ),
    ] = None,
    project: Annotated[
        Path | None,
        Parameter(
            name=["--project", "-p"],
            help="Path to project directory. CodeWeaver will attempt to auto-detect if not provided.",
        ),
    ] = None,
    *,
    no_daemon: bool = False,
    management_host: str = "127.0.0.1",
    management_port: PositiveInt = 9329,
    start_mcp_http_server: bool = False,
    mcp_host: str | None = None,
    mcp_port: PositiveInt | None = None,
) -> None:
    """Start CodeWeaver background services.

    By default, runs in daemon mode (background). Use --no-daemon to run in foreground.

    Starts:
    - Indexer (semantic search engine)
    - FileWatcher (real-time index updates)
    - HealthService (system monitoring)
    - Statistics and Telemetry (if enabled)
    - Management server (HTTP on port 9329 by default)

    Background services run independently of the MCP server.
    The MCP server will auto-start these if needed.

    Management endpoints available at http://127.0.0.1:9329 (by default):
    - /health - Health check
    - /status - Indexing status
    - /state - CodeWeaver state
    - /metrics - Statistics and metrics
    - /version - Version information

    Args:
        config_file: Path to configuration file
        project: Path to project directory
        no_daemon: Run in foreground instead of daemon mode
        management_host: Management server host
        management_port: Management server port
        start_mcp_http_server: Reserved for future use
        mcp_host: Reserved for future use
        mcp_port: Reserved for future use
    """
    display = _display
    error_handler = CLIErrorHandler(display, verbose=False, debug=False)
    pid_file_path = _get_pid_file_path()
    daemon_manager = DaemonManager(pid_file_path)

    try:
        display.print_command_header("start", "Start Background Services")

        # Check if already running using DaemonManager
        if daemon_manager.is_running():
            display.print_warning("Background services already running")
            pid = daemon_manager.get_pid()
            if pid:
                display.print_info(f"Process ID: {pid}", prefix="📋")
            display.print_info(f"Management server: http://{management_host}:{management_port}", prefix="🌐")
            return

        # Daemon mode (default)
        if not no_daemon:
            display.print_info("Starting CodeWeaver background services in daemon mode...")
            display.print_info(f"PID file: {pid_file_path}", prefix="📁")

            # Fork and daemonize
            pid = os.fork()
            if pid > 0:
                # Parent process
                # Wait briefly for child to start
                await asyncio.sleep(1)

                # Verify child process started
                if daemon_manager.is_running():
                    child_pid = daemon_manager.get_pid()
                    display.print_success(f"Background services started successfully (PID: {child_pid})")
                    display.print_info(f"Management server: http://{management_host}:{management_port}", prefix="🌐")
                    display.print_info("Use 'cw stop' to stop background services", prefix="ℹ️")
                else:
                    display.print_error("Failed to start background services")
                    sys.exit(1)
                return

            # Child process continues here
            # Detach from parent environment
            os.setsid()

            # Write PID file
            daemon_manager.write_pid()

            # Continue with service startup (no display output in daemon mode)
            # Create new display that won't interfere with daemon
            from codeweaver.cli.ui import NullDisplay
            daemon_display = NullDisplay()

            await start_cw_services(
                daemon_display,
                daemon_manager,
                config_path=config_file,
                project_path=project,
            )

        # Foreground mode (--no-daemon)
        else:
            display.print_info("Starting CodeWeaver background services in foreground mode...")
            display.print_info("Press Ctrl+C to stop", prefix="⚠️")

            await start_cw_services(
                display,
                daemon_manager,
                config_path=config_file,
                project_path=project,
            )

    except KeyboardInterrupt:
        # Already handled in start_cw_services
        pass
    except Exception as e:
        error_handler.handle_error(e, "Start command", exit_code=1)


if __name__ == "__main__":
    display = _display
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)
    try:
        app()
    except Exception as e:
        error_handler.handle_error(e, "Start command", exit_code=1)
