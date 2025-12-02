# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Start command for CodeWeaver background services.

Starts background services (indexing, file watching, health monitoring, telemetry)
independently of the MCP server.

By default, the daemon runs in the background. Use --foreground to run in the
current terminal session.
"""

from __future__ import annotations

import asyncio

from pathlib import Path
from typing import TYPE_CHECKING, Annotated
import contextlib
from cyclopts import App, Parameter
from pydantic import FilePath, PositiveInt

from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.core.types.sentinel import Unset
from codeweaver.daemon import (
    check_daemon_health,
    spawn_daemon_process,
)


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types.dictview import DictView

_display: StatusDisplay = get_display()
app = App("start", help="Start CodeWeaver background services.")


def _get_settings_map() -> DictView[CodeWeaverSettingsDict]:
    """Get the current settings map."""
    from codeweaver.config.settings import get_settings_map

    return get_settings_map()


async def are_services_running(
    management_host: str | None = None,
    management_port: int | None = None,
) -> bool:
    """Check if background services are running via management server.

    Args:
        management_host: Host to check. If None, uses settings or defaults to 127.0.0.1
        management_port: Port to check. If None, uses settings or defaults to 9329

    Returns:
        True if services are running, False otherwise.
    """
    # Use provided values or fall back to settings/defaults
    if management_host is None or management_port is None:
        settings_map = _get_settings_map()
        if management_host is None:
            management_host = (
                settings_map["management_host"]
                if settings_map["management_host"] is not Unset
                else "127.0.0.1"
            )
        if management_port is None:
            management_port = (
                settings_map["management_port"]
                if settings_map["management_port"] is not Unset
                else 9329
            )

    return await check_daemon_health(management_host, management_port)


def _start_daemon_background(
    display: StatusDisplay,
    config_file: Path | None = None,
    project: Path | None = None,
    management_host: str = "127.0.0.1",
    management_port: int = 9329,
    mcp_host: str | None = None,
    mcp_port: int | None = None,
) -> bool:
    """Start the CodeWeaver daemon as a background process.

    Args:
        display: Status display for output
        config_file: Optional configuration file path
        project: Optional project directory path
        management_host: Host for management server
        management_port: Port for management server
        mcp_host: Host for MCP HTTP server
        mcp_port: Port for MCP HTTP server

    Returns:
        True if daemon was started successfully, False otherwise.
    """
    success = spawn_daemon_process(
        config_file=config_file,
        project=project,
        management_host=management_host,
        management_port=management_port,
        mcp_host=mcp_host,
        mcp_port=mcp_port,
    )
    if not success:
        display.print_error("Failed to start daemon process")
    return success


async def _wait_for_daemon_healthy(
    display: StatusDisplay,
    management_host: str = "127.0.0.1",
    management_port: int = 9329,
    max_wait_seconds: float = 30.0,
    check_interval: float = 0.5,
) -> bool:
    """Wait for the daemon to become healthy.

    Args:
        display: Status display for output
        management_host: Host of management server
        management_port: Port of management server
        max_wait_seconds: Maximum time to wait
        check_interval: Interval between health checks

    Returns:
        True if daemon became healthy, False if timeout.
    """
    elapsed = 0.0
    while elapsed < max_wait_seconds:
        await asyncio.sleep(check_interval)
        elapsed += check_interval

        if await check_daemon_health(management_host, management_port):
            return True

    return False


async def start_cw_services(
    display: StatusDisplay,
    config_path: Path | None = None,
    project_path: Path | None = None,
    *,
    start_mcp_http_server: bool = True,  # Start MCP HTTP server for stdio proxy support
    mcp_host: str | None = None,
    mcp_port: PositiveInt | None = None,
) -> None:
    """Start background services and optionally MCP HTTP server.

    By default, starts both the management server (port 9329) and MCP HTTP server
    (port 9328) to support stdio proxy connections.
    """
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.config.settings import get_settings
    from codeweaver.server.lifespan import background_services_lifespan
    from codeweaver.server.management import ManagementServer

    # Load settings
    settings = get_settings()
    if config_path:
        settings.config_file = config_path  # type: ignore
    if project_path:
        settings.project_path = project_path

    statistics = get_session_statistics()

    # Resolve MCP server host/port
    _mcp_host = mcp_host or getattr(settings, "mcp_host", "127.0.0.1")
    _mcp_port = mcp_port or getattr(settings, "mcp_port", 9328)

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

        # Start MCP HTTP server if requested (needed for stdio proxy)
        mcp_server_task = None
        if start_mcp_http_server:
            from codeweaver.mcp.server import create_http_server

            mcp_state = await create_http_server(
                host=_mcp_host, port=_mcp_port, verbose=False, debug=False
            )
            display.print_info(
                f"MCP HTTP server: http://{_mcp_host}:{_mcp_port}/mcp/", prefix="🔌"
            )

            # Start MCP HTTP server as background task
            mcp_server_task = asyncio.create_task(
                mcp_state.app.run_http_async(**mcp_state.run_args)
            )

        try:
            # Keep services running until interrupted
            tasks_to_wait = [t for t in [management_server.server_task, mcp_server_task] if t]
            if tasks_to_wait:
                await asyncio.gather(*tasks_to_wait)
            else:
                # Shouldn't happen: no server tasks set
                raise RuntimeError("No server tasks were created. This should not happen; please check server startup logic.")
        except (KeyboardInterrupt, asyncio.CancelledError):
            display.print_warning("Shutting down background services...")
        finally:
            if mcp_server_task and not mcp_server_task.done():
                mcp_server_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await mcp_server_task
            await management_server.stop()


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
    foreground: Annotated[
        bool,
        Parameter(
            name=["--foreground", "-f"],
            help="Run daemon in foreground (blocks terminal). Default is to run in background.",
        ),
    ] = False,
    management_host: str = "127.0.0.1",
    management_port: PositiveInt = 9329,
    mcp_host: str | None = None,
    mcp_port: PositiveInt | None = None,
) -> None:
    """Start CodeWeaver daemon with background services and MCP HTTP server.

    By default, starts the daemon in the background and returns immediately.
    Use --foreground to run in the current terminal session.

    Starts:
    - Indexer (semantic search engine)
    - FileWatcher (real-time index updates)
    - HealthService (system monitoring)
    - Statistics and Telemetry (if enabled)
    - Management server (HTTP on port 9329 by default)
    - MCP HTTP server (HTTP on port 9328 by default)

    The MCP HTTP server is required for stdio transport. When you run
    `codeweaver server` (stdio mode), it proxies to the daemon's HTTP server.

    Management endpoints available at http://127.0.0.1:9329 (by default):
    - /health - Health check
    - /status - Indexing status
    - /state - CodeWeaver state
    - /metrics - Statistics and metrics
    - /version - Version information

    MCP HTTP server available at http://127.0.0.1:9328/mcp/ (by default).
    """
    display = _display
    error_handler = CLIErrorHandler(display, verbose=False, debug=False)

    try:
        display.print_command_header("start", "Start Background Services")

        # Check if already running (use the specified host/port for accurate check)
        if await are_services_running(management_host, management_port):
            display.print_warning("Background services already running")
            display.print_info(f"Management server: http://{management_host}:{management_port}", prefix="🌐")
            return

        if foreground:
            # Foreground mode: run in current terminal
            display.print_info("Starting CodeWeaver daemon in foreground...")
            display.print_info("Press Ctrl+C to stop", prefix="⚠️")

            await start_cw_services(
                display,
                config_path=config_file,
                project_path=project,
                mcp_host=mcp_host,
                mcp_port=mcp_port,
            )
        else:
            # Background mode (default): spawn detached process
            display.print_info("Starting CodeWeaver daemon in background...")

            success = _start_daemon_background(
                display,
                config_file=config_file,
                project=project,
                management_host=management_host,
                management_port=management_port,
                mcp_host=mcp_host,
                mcp_port=mcp_port,
            )

            if not success:
                display.print_error("Failed to start daemon process")
                return

            # Wait for daemon to become healthy
            display.print_info("Waiting for daemon to start...")
            healthy = await _wait_for_daemon_healthy(
                display,
                management_host=management_host,
                management_port=management_port,
                max_wait_seconds=30.0,
                check_interval=0.5,
            )

            if healthy:
                display.print_success("CodeWeaver daemon started successfully")
                display.print_info(f"Management server: http://{management_host}:{management_port}", prefix="🌐")
                mcp_port_val = mcp_port or 9328
                mcp_host_val = mcp_host or "127.0.0.1"
                display.print_info(f"MCP HTTP server: http://{mcp_host_val}:{mcp_port_val}/mcp/", prefix="🔌")
                display.print_info("Stop with: cw stop", prefix="💡")
            else:
                display.print_error("Daemon started but did not become healthy within 30 seconds")
                display.print_info("Check logs or try: cw start --foreground")

    except KeyboardInterrupt:
        # Already handled in start_cw_services
        pass
    except Exception as e:
        error_handler.handle_error(e, "Start command", exit_code=1)


@app.command
def persist(
    project: Annotated[
        Path | None,
        Parameter(
            name=["--project", "-p"],
            help="Path to project directory. CodeWeaver will attempt to auto-detect if not provided.",
        ),
    ] = None,
    *,
    enable: Annotated[
        bool,
        Parameter(
            name=["--enable", "-e"],
            help="Enable and start the service immediately (Linux/macOS only)",
        ),
    ] = True,
    uninstall: Annotated[
        bool,
        Parameter(
            name=["--uninstall", "-u"],
            help="Remove the installed service",
        ),
    ] = False,
) -> None:
    """Install CodeWeaver as a persistent system service.

    This is an alias for `cw init service`. It configures CodeWeaver to start
    automatically when you log in.

    **Linux (systemd):**
    Creates a user systemd service at ~/.config/systemd/user/codeweaver.service

    **macOS (launchd):**
    Creates a user launch agent at ~/Library/LaunchAgents/li.knit.codeweaver.plist

    **Windows:**
    Provides instructions for setting up with NSSM or Task Scheduler.

    Examples:
        cw start persist                 # Install and enable service
        cw start persist --no-enable     # Install without enabling
        cw start persist --uninstall     # Remove the service
    """
    # Delegate to init service command
    from codeweaver.cli.commands.init import service as init_service

    init_service(project=project, enable=enable, uninstall=uninstall)


if __name__ == "__main__":
    display = _display
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)
    try:
        app()
    except Exception as e:
        error_handler.handle_error(e, "Start command", exit_code=1)
