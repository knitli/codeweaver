# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Start command for CodeWeaver background services.

Starts background services (indexing, file watching, health monitoring, telemetry)
independently of the MCP server.
"""

from __future__ import annotations

import asyncio

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from cyclopts import App, Parameter
from pydantic import FilePath, PositiveInt

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
                with asyncio.suppress(asyncio.CancelledError):
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
    management_host: str = "127.0.0.1",
    management_port: PositiveInt = 9329,
    mcp_host: str | None = None,
    mcp_port: PositiveInt | None = None,
) -> None:
    """Start CodeWeaver daemon with background services and MCP HTTP server.

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

        # Check if already running
        if await are_services_running():
            display.print_warning("Background services already running")
            display.print_info("Management server: http://127.0.0.1:9329", prefix="🌐")
            return

        display.print_info("Starting CodeWeaver daemon...")
        display.print_info("Press Ctrl+C to stop", prefix="⚠️")

        await start_cw_services(
            display,
            config_path=config_file,
            project_path=project,
            mcp_host=mcp_host,
            mcp_port=mcp_port,
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
