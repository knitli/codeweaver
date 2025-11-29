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
from typing import Annotated

from cyclopts import App, Parameter
from pydantic import FilePath

from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.common.registry import ModelRegistry, ProviderRegistry, ServicesRegistry
from codeweaver.common.telemetry.client import PostHogClient
from codeweaver.common.utils import get_project_path
from codeweaver.config.settings import get_settings, get_settings_map
from codeweaver.core.types.sentinel import Unset
from codeweaver.engine.indexer import Indexer


_display: StatusDisplay = get_display()
app = App("start", help="Start CodeWeaver background services.")


async def is_services_running() -> bool:
    """Check if background services are running via management server."""
    try:
        import httpx
    except ImportError:
        return False

    settings_map = get_settings_map()
    mgmt_host = settings_map.get("server", {}).get("management_host", "127.0.0.1")
    mgmt_port = settings_map.get("server", {}).get("management_port", 9329)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{mgmt_host}:{mgmt_port}/health", timeout=2.0)
            return response.status_code == 200
    except Exception:
        return False


async def start_background_services(
    display: StatusDisplay,
    config_path: Path | None = None,
    project_path: Path | None = None,
) -> None:
    """Start background services (indexer, watcher, health, management server)."""
    from codeweaver import __version__ as version
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.server.background.state import BackgroundState
    from codeweaver.server.health_service import HealthService
    from codeweaver.server.server import _run_background_indexing

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
    startup_time = time.time()

    # Create BackgroundState
    background_state = BackgroundState(
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
        startup_time=startup_time,
    )

    # Initialize health service
    background_state.health_service = HealthService(
        provider_registry=provider_registry,
        statistics=statistics,
        indexer=background_state.indexer,
        failover_manager=background_state.failover_manager,
        startup_time=startup_time,
    )

    # Initialize background services
    await background_state.initialize()

    # Start telemetry session
    if telemetry_client and telemetry_client.enabled:
        telemetry_client.start_session({
            "codeweaver_version": version,
            "index_backend": "qdrant",
            "mode": "background_services",
        })

    # Start background indexing
    indexing_task = asyncio.create_task(
        _run_background_indexing(
            background_state, settings, display, verbose=False, debug=False
        )
    )
    background_state.background_tasks.add(indexing_task)

    display.print_success("Background services started successfully")
    display.print_info(
        f"Management server: http://127.0.0.1:{settings.server.management_port}",
        prefix="🌐"
    )

    # Keep services running until interrupted
    try:
        await background_state.shutdown_event.wait()
    except KeyboardInterrupt:
        display.print_warning("Shutting down background services...")
    finally:
        await background_state.shutdown()


@app.default
async def start(
    config: Annotated[
        FilePath | None,
        Parameter(name=["--config", "-c"], help="Path to CodeWeaver configuration file"),
    ] = None,
    project: Annotated[
        Path | None, Parameter(name=["--project", "-p"], help="Path to project directory")
    ] = None,
) -> None:
    """Start CodeWeaver background services.

    Starts:
    - Indexer (semantic search engine)
    - FileWatcher (real-time index updates)
    - HealthService (system monitoring)
    - Statistics (telemetry collection)
    - Management server (HTTP on port 9329)

    Background services run independently of the MCP server.
    The MCP server will auto-start these if needed.

    Management endpoints available at http://127.0.0.1:9329:
    - /health - Health check
    - /status - Indexing status
    - /metrics - Statistics and metrics
    - /version - Version information
    """
    display = _display
    error_handler = CLIErrorHandler(display, verbose=False, debug=False)

    try:
        display.print_command_header("start", "Start Background Services")

        # Check if already running
        if await is_services_running():
            display.print_warning("Background services already running")
            display.print_info("Management server: http://127.0.0.1:9329", prefix="🌐")
            return

        display.print_info("Starting CodeWeaver background services...")
        display.print_info("Press Ctrl+C to stop", prefix="⚠️")

        await start_background_services(display, config_path=config, project_path=project)

    except KeyboardInterrupt:
        # Already handled in start_background_services
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
