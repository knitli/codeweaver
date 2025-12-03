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
import contextlib

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple

from cyclopts import App, Parameter
from pydantic import FilePath, PositiveInt
from typing_extensions import TypeIs

from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.cli.utils import get_settings_map_for
from codeweaver.common.utils.lazy_importer import lazy_import
from codeweaver.core.types.sentinel import Unset
from codeweaver.daemon import check_daemon_health, spawn_daemon_process


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types.dictview import DictView

_display: StatusDisplay = get_display()
app = App("start", help="Start CodeWeaver background services.")


class NetworkConfig(NamedTuple):
    """Network configuration for CodeWeaver services."""

    management_host: str
    management_port: int
    mcp_host: str | None
    mcp_port: int | None


def _get_settings_map() -> DictView[CodeWeaverSettingsDict]:
    """Get the current settings map."""
    from codeweaver.config.settings import get_settings_map

    return get_settings_map()


async def are_services_running(management_host: str, management_port: int) -> bool:
    """Check if background services are running via management server.

    Args:
        management_host: Host to check.
        management_port: Port to check.

    Returns:
        True if services are running, False otherwise.
    """
    return await check_daemon_health(management_host, management_port)


def _start_daemon_background(
    display: StatusDisplay,
    project: Path,
    management_host: str,
    management_port: int,
    mcp_host: str,
    mcp_port: int,
    config_file: Path | None = None,
) -> bool:
    """Start the CodeWeaver daemon as a background process.

    Args:
        display: Status display for output
        project: Optional project directory path
        management_host: Host for management server
        management_port: Port for management server
        mcp_host: Host for MCP HTTP server
        mcp_port: Port for MCP HTTP server
        config_file: Optional configuration file path

    Returns:
        True if daemon was started successfully, False otherwise.
    """
    success = spawn_daemon_process(
        project=project,
        management_host=management_host,
        management_port=management_port,
        mcp_host=mcp_host,
        mcp_port=mcp_port,
        config_file=config_file,
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
    project_path: Path,
    mcp_host: str,
    mcp_port: PositiveInt,
    management_host: str,
    management_port: PositiveInt,
    *,
    start_mcp_http_server: bool = True,  # Start MCP HTTP server for stdio proxy support
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Start background services and optionally MCP HTTP server.

    By default, starts both the management server (port 9329) and MCP HTTP server
    (port 9328) to support stdio proxy connections.
    """
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.server.lifespan import background_services_lifespan
    from codeweaver.server.management import ManagementServer

    statistics = get_session_statistics()

    # Use background_services_lifespan (the new Phase 1 implementation)
    async with background_services_lifespan(
        settings=lazy_import("codeweaver.config.settings", "get_settings")._resolve()(),
        statistics=statistics,
        status_display=display,
        verbose=verbose,
        debug=debug,
    ) as background_state:
        management_server = ManagementServer(background_state)
        await management_server.start(host=management_host, port=management_port)

        display.print_success("Background services started successfully")
        display.print_info(
            f"Management server: http://{management_host}:{management_port}", prefix="🌐"
        )

        # Start MCP HTTP server if requested (needed for stdio proxy)
        mcp_server_task = None
        if start_mcp_http_server:
            from codeweaver.mcp.server import create_http_server

            mcp_state = await create_http_server(
                host=mcp_host, port=mcp_port, verbose=verbose, debug=debug
            )
            display.print_info(f"MCP HTTP server: http://{mcp_host}:{mcp_port}/mcp/", prefix="🔌")

            # Start MCP HTTP server as background task
            mcp_server_task = asyncio.create_task(
                mcp_state.app.run_http_async(**mcp_state.run_args)
            )

        try:
            if tasks_to_wait := [t for t in [management_server.server_task, mcp_server_task] if t]:
                # Create a task that monitors the shutdown event
                async def wait_for_shutdown() -> None:
                    """Wait for shutdown signal from management API."""
                    from codeweaver.server.management import ManagementServer as MgmtServer

                    # Wait on the event instead of busy-waiting with sleep
                    if MgmtServer._shutdown_event is not None:
                        await MgmtServer._shutdown_event.wait()
                        display.print_info("Shutdown requested via management API")

                shutdown_task = asyncio.create_task(wait_for_shutdown())

                # Wait for either server tasks to complete or shutdown request
                _, pending = await asyncio.wait(
                    [*tasks_to_wait, shutdown_task], return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
            else:
                # Shouldn't happen: no server tasks set
                raise RuntimeError(
                    "No server tasks were created. This should not happen; please check server startup logic."
                )
        except (KeyboardInterrupt, asyncio.CancelledError):
            display.print_warning("Shutting down background services...")
        finally:
            if mcp_server_task and not mcp_server_task.done():
                mcp_server_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await mcp_server_task
            await management_server.stop()


def get_network_settings() -> NetworkConfig:
    """Get network configuration from settings."""
    settings_map = _get_settings_map()

    management_host = (
        settings_map["management_host"]
        if settings_map["management_host"] is not Unset
        else "127.0.0.1"
    )
    management_port = (
        settings_map["management_port"] if settings_map["management_port"] is not Unset else 9329
    )
    if (mcp_http_server := settings_map["mcp_server"]) is not Unset:
        mcp_host = mcp_http_server.get("host", "127.0.0.1")
        mcp_port = mcp_http_server.get("port", 9328)
    else:
        mcp_host = "127.0.0.1"
        mcp_port = 9328
    return NetworkConfig(
        management_host=management_host,
        management_port=management_port,
        mcp_host=mcp_host,
        mcp_port=mcp_port,
    )


def _is_valid_host(host: Any) -> TypeIs[str]:
    """Check if the provided host is a valid hostname or IP address."""
    if not isinstance(host, str):
        return False
    import socket

    try:
        socket.gethostbyname(host)
    except OSError:
        return False
    else:
        return True


def _is_valid_port(port: Any) -> TypeIs[PositiveInt]:
    """Check if the provided port is within the valid range (1-65535)."""
    return isinstance(port, int) and 1 <= port <= 65535


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
    management_host: Annotated[
        str | None, Parameter(help="Management server host. Default is 127.0.0.1. (localhost)")
    ] = None,
    management_port: Annotated[
        PositiveInt | None, Parameter(help="Management server port. Default is 9329.")
    ] = None,
    mcp_host: Annotated[
        str | None, Parameter(help="MCP server host. Default is 127.0.0.1. (localhost)")
    ] = None,
    mcp_port: Annotated[
        PositiveInt | None, Parameter(help="MCP server port. Default is 9328.")
    ] = None,
    verbose: Annotated[
        bool, Parameter(name=["--verbose", "-v"], help="Enable verbose logging with timestamps")
    ] = False,
    debug: Annotated[bool, Parameter(name=["--debug", "-d"], help="Enable debug logging")] = False,
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
    settings_map = get_settings_map_for(config_file=config_file, project_path=project)
    display = _display
    error_handler = CLIErrorHandler(display, verbose=verbose, debug=debug)
    network_config = get_network_settings()
    management_host = management_host or network_config.management_host
    management_port = management_port or network_config.management_port
    mcp_host = mcp_host or network_config.mcp_host
    mcp_port = mcp_port or network_config.mcp_port
    if (
        not _is_valid_host(management_host)
        or not _is_valid_host(mcp_host)
        or not _is_valid_port(management_port)
        or not _is_valid_port(mcp_port)
    ):
        display.print_error("Invalid host or port provided. Please check your inputs.")
        return
    get_project_path = lazy_import("codeweaver.common.utils.git", "get_project_path")
    project = (
        project or project_path
        if (project_path := settings_map.get("project_path")) is not Unset
        else get_project_path._resolve()()
    )
    if not project and isinstance(project, Path) and project.exists():
        display.print_warning(
            "No valid project directory found. Please provide a path using --project."
        )
        return
    try:
        display.print_command_header("start", "Start Background Services")

        # Check if already running (use the specified host/port for accurate check)
        if await are_services_running(management_host, management_port):
            display.print_warning("Background services already running")
            display.print_info(
                f"Management server: http://{management_host}:{management_port}", prefix="🌐"
            )
            return

        if foreground:
            # Foreground mode: run in current terminal
            display.print_info("Starting CodeWeaver daemon in foreground...")
            display.print_info("Press Ctrl+C to stop", prefix="⚠️")

            await start_cw_services(
                display,
                project_path=project,
                management_host=management_host,
                management_port=management_port,
                mcp_host=mcp_host,
                mcp_port=mcp_port,
                verbose=verbose,
                debug=debug,
            )
        else:
            # Background mode (default): spawn detached process
            display.print_info("Starting CodeWeaver daemon in background...")
            display.print_info("Use 'cw stop' to stop the daemon", prefix="💡")

            success = _start_daemon_background(
                display,
                project=project,
                management_host=management_host,
                management_port=management_port,
                mcp_host=mcp_host,
                mcp_port=mcp_port,
                config_file=config_file,
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
                display.print_info(
                    f"Management server: http://{management_host}:{management_port}", prefix="🌐"
                )
                mcp_port_val = mcp_port
                mcp_host_val = mcp_host
                display.print_info(
                    f"MCP HTTP server: http://{mcp_host_val}:{mcp_port_val}/mcp/", prefix="🔌"
                )
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
        bool, Parameter(name=["--uninstall", "-u"], help="Remove the installed service")
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
