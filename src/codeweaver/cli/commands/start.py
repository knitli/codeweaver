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
import time

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from cyclopts import App, Parameter
from pydantic import FilePath, PositiveInt

from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.common.registry import ModelRegistry, ProviderRegistry, ServicesRegistry
from codeweaver.common.telemetry.client import PostHogClient
from codeweaver.common.utils import get_project_path
from codeweaver.core.types.sentinel import Unset
from codeweaver.engine.indexer import Indexer


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
    start_mcp_http_server: bool = False,
    mcp_host: str | None = None,
    mcp_port: PositiveInt | None = None,
) -> None:
    """Start background services (indexer, watcher, health, management server)."""
    from codeweaver import __version__ as version
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.config.settings import get_settings
    from codeweaver.server.health.health_service import HealthService
    from codeweaver.server.server import CodeWeaverState, _run_background_indexing

    # Load settings
    settings = get_settings()
    if project_path:
        settings.project_path = project_path
    elif isinstance(settings.project_path, Unset):
        settings.project_path = get_project_path()

    # Initialize telemetry
    telemetry_client = PostHogClient.from_settings()

    # Get singletons
    provider_registry = ProviderRegistry()
    statistics = get_session_statistics()

    # Create CodeWeaverState
    cw_state = CodeWeaverState(
        initialized=False,
        settings=settings,
        statistics=statistics,
        project_path=get_project_path()
        if isinstance(settings.project_path, Unset)
        else settings.project_path,
        config_path=config_path,
        provider_registry=provider_registry,
        services_registry=ServicesRegistry(),
        model_registry=ModelRegistry(),
        health_service=None,
        failover_manager=None,
        telemetry=telemetry_client,
        indexer=Indexer.from_settings(),
    )

    # Initialize health service
    cw_state.health_service = HealthService(
        provider_registry=provider_registry,
        statistics=statistics,
        indexer=cw_state.indexer,
        failover_manager=cw_state.failover_manager,
        startup_time=time.time(),
    )

    # Start telemetry session
    if telemetry_client and telemetry_client.enabled:
        telemetry_client.start_session({
            "codeweaver_version": version,
            "index_backend": "qdrant",
            "mode": "background_services",
        })

    # Start background indexing
    indexing_task = asyncio.create_task(
        _run_background_indexing(cw_state, settings, display, verbose=False, debug=False)
    )

    display.print_success("Background services started successfully")
    display.print_info(
        f"Management server: http://127.0.0.1:{settings.management_port}", prefix="🌐"
    )

    # Keep services running until interrupted
    try:
        # Wait for indexing task to complete or be cancelled
        await indexing_task
    except asyncio.CancelledError:
        display.print_warning("Background services cancelled...")
    except KeyboardInterrupt:
        display.print_warning("Shutting down background services...")
        indexing_task.cancel()
        try:
            await asyncio.wait_for(indexing_task, timeout=5.0)
        except (asyncio.CancelledError, TimeoutError):
            pass
    finally:
        cw_state.initialized = False


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
    start_mcp_http_server: bool = False,
    mcp_host: str | None = None,
    mcp_port: PositiveInt | None = None,
) -> None:
    """Start CodeWeaver background services.

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

        display.print_info("Starting CodeWeaver background services...")
        display.print_info("Press Ctrl+C to stop", prefix="⚠️")

        await start_cw_services(display, config_path=config_file, project_path=project)

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
