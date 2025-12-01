# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Start command for CodeWeaver background services.

Starts background services (indexing, file watching, health monitoring, telemetry)
independently of the MCP server. By default, runs as a background daemon.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from cyclopts import App, Parameter
from pydantic import FilePath, PositiveInt

from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.common.utils.procs import (
    get_daemon_status,
    get_pid_file_path,
    remove_pid_file,
    write_pid_file,
)
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


async def start_cw_services_foreground(
    display: StatusDisplay,
    config_path: Path | None = None,
    project_path: Path | None = None,
    *,
    management_host: str = "127.0.0.1",
    management_port: PositiveInt = 9329,
) -> None:
    """Start background services in the foreground (blocking).

    This is used when --no-daemon is specified.
    """
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.config.settings import get_settings
    from codeweaver.server.lifespan import background_services_lifespan
    from codeweaver.server.management import ManagementServer

    # Write PID file for foreground mode too (for stop command compatibility)
    write_pid_file()

    # Load settings
    settings = get_settings()
    if config_path:
        settings.config_file = config_path  # type: ignore
    if project_path:
        settings.project_path = project_path

    statistics = get_session_statistics()

    try:
        # Use background_services_lifespan (the new Phase 1 implementation)
        async with background_services_lifespan(
            settings=settings,
            statistics=statistics,
            status_display=display,
            verbose=False,
            debug=False,
        ) as background_state:
            # Start management server
            mgmt_host = getattr(settings, "management_host", management_host)
            mgmt_port = getattr(settings, "management_port", management_port)

            management_server = ManagementServer(background_state)
            await management_server.start(host=mgmt_host, port=mgmt_port)

            display.print_success("Background services started successfully")
            display.print_info(f"Management server: http://{mgmt_host}:{mgmt_port}", prefix="🌐")

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
    finally:
        # Clean up PID file on exit
        remove_pid_file()


def start_daemon_process(
    display: StatusDisplay,
    config_path: Path | None = None,
    project_path: Path | None = None,
    *,
    management_host: str = "127.0.0.1",
    management_port: PositiveInt = 9329,
) -> tuple[bool, int | None]:
    """Start background services as a daemon process.

    Spawns a new Python process that runs the services in the background.

    Args:
        display: StatusDisplay instance for output.
        config_path: Optional path to config file.
        project_path: Optional path to project directory.
        management_host: Host for management server.
        management_port: Port for management server.

    Returns:
        Tuple of (success, pid). pid is the daemon process ID if successful.
    """
    # Build the command to run the daemon
    cmd = [
        sys.executable,
        "-m",
        "codeweaver.cli.commands.start",
        "--_daemon-child",
    ]

    if config_path:
        cmd.extend(["--config-file", str(config_path)])
    if project_path:
        cmd.extend(["--project", str(project_path)])
    cmd.extend(["--management-host", management_host])
    cmd.extend(["--management-port", str(management_port)])

    try:
        # Use subprocess.Popen to spawn a detached process
        # DEVNULL for stdin/stdout/stderr to fully detach from terminal
        if sys.platform == "win32":
            # Windows: Use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS
            creation_flags = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
            )
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
                start_new_session=True,
            )
        else:
            # Unix: Use start_new_session and double-fork pattern via preexec_fn
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        # Give the process a moment to start
        import time

        time.sleep(1.0)

        # Check if process is still running
        if process.poll() is None:
            # Process is running, write PID file
            write_pid_file(process.pid)
            display.print_success(f"Daemon started with PID {process.pid}")
            return True, process.pid
        else:
            display.print_error(f"Daemon process exited with code {process.returncode}")
            return False, None

    except Exception as e:
        display.print_error(f"Failed to start daemon: {e}")
        return False, None


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
    no_daemon: Annotated[
        bool,
        Parameter(
            name=["--no-daemon"],
            help="Run in foreground instead of as a background daemon. Attach to current shell.",
        ),
    ] = False,
    management_host: Annotated[
        str,
        Parameter(
            name=["--management-host"],
            help="Host for the management HTTP server.",
        ),
    ] = "127.0.0.1",
    management_port: Annotated[
        PositiveInt,
        Parameter(
            name=["--management-port"],
            help="Port for the management HTTP server.",
        ),
    ] = 9329,
    _daemon_child: Annotated[
        bool,
        Parameter(
            name=["--_daemon-child"],
            help="Internal flag: indicates this is a daemon child process.",
            show=False,
        ),
    ] = False,
) -> None:
    """Start CodeWeaver background services.

    By default, starts services as a background daemon that continues running
    after the terminal is closed. Use --no-daemon to run in the foreground
    and attach to the current shell.

    Services started:
    - Indexer (semantic search engine)
    - FileWatcher (real-time index updates)
    - HealthService (system monitoring)
    - Statistics and Telemetry (if enabled)
    - Management server (HTTP on port 9329 by default)

    Management endpoints available at http://127.0.0.1:9329 (by default):
    - /health - Health check
    - /status - Indexing status
    - /state - CodeWeaver state
    - /metrics - Statistics and metrics
    - /version - Version information

    To stop the daemon, run: cw stop
    """
    display = _display
    error_handler = CLIErrorHandler(display, verbose=False, debug=False)

    try:
        # If this is the daemon child process, run in foreground mode
        if _daemon_child:
            # This is the spawned daemon process - run services directly
            await start_cw_services_foreground(
                display,
                config_path=config_file,
                project_path=project,
                management_host=management_host,
                management_port=management_port,
            )
            return

        display.print_command_header("start", "Start Background Services")

        # Check if already running
        is_running, existing_pid = get_daemon_status()
        if is_running and existing_pid:
            display.print_warning(f"Background services already running (PID {existing_pid})")
            display.print_info(f"Management server: http://{management_host}:{management_port}", prefix="🌐")
            display.print_info("To stop: cw stop")
            return

        # Check via HTTP as well (in case PID file is stale)
        if await are_services_running():
            display.print_warning("Background services already running")
            display.print_info(f"Management server: http://{management_host}:{management_port}", prefix="🌐")
            display.print_info("To stop: cw stop")
            # Clean up stale PID file if exists
            pid_file = get_pid_file_path()
            if pid_file.exists():
                remove_pid_file()
                write_pid_file(os.getpid())  # Best effort to track
            return

        if no_daemon:
            # Foreground mode
            display.print_info("Starting CodeWeaver background services in foreground mode...")
            display.print_info("Press Ctrl+C to stop", prefix="⚠️")
            await start_cw_services_foreground(
                display,
                config_path=config_file,
                project_path=project,
                management_host=management_host,
                management_port=management_port,
            )
        else:
            # Daemon mode (default)
            display.print_info("Starting CodeWeaver background services as daemon...")
            success, pid = start_daemon_process(
                display,
                config_path=config_file,
                project_path=project,
                management_host=management_host,
                management_port=management_port,
            )

            if success:
                display.print_info(
                    f"Management server: http://{management_host}:{management_port}", prefix="🌐"
                )
                display.print_info("To stop: cw stop")
                display.print_info("To check status: cw status")
            else:
                display.print_error("Failed to start daemon. Try --no-daemon for more details.")

    except KeyboardInterrupt:
        display.print_warning("Interrupted")
    except Exception as e:
        error_handler.handle_error(e, "Start command", exit_code=1)


if __name__ == "__main__":
    display = _display
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)
    try:
        app()
    except Exception as e:
        error_handler.handle_error(e, "Start command", exit_code=1)
