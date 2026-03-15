# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Initialize the CodeWeaver Server (all background services)."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastmcp import FastMCP
from pydantic import DirectoryPath, Field, NonNegativeInt, PrivateAttr, computed_field
from starlette.middleware import Middleware as ASGIMiddleware

from codeweaver import __version__ as version
from codeweaver.core import (
    AnonymityConversion,
    DataclassSerializationMixin,
    InitializationError,
    ProgressReporter,
    RichConsoleProgressReporter,
    SessionStatistics,
    StatisticsDep,
    TelemetryService,
    elapsed_time_to_human_readable,
    get_container,
    get_project_path,
    get_settings,
)
from codeweaver.core.config.settings_type import CodeWeaverSettingsType
from codeweaver.core.constants import (
    DEFAULT_MANAGEMENT_PORT,
    INDEXER_WINDDOWN_TIMEOUT,
    LOCALHOST,
    ONE,
)
from codeweaver.engine.services.failover_service import FailoverService
from codeweaver.engine.services.indexing_service import IndexingService
from codeweaver.providers import HttpClientPool
from codeweaver.server.config import CodeWeaverSettings
from codeweaver.server.health.health_service import HealthService
from codeweaver.server.management import ManagementServer
from codeweaver.server.mcp.state import CwMcpHttpState


if TYPE_CHECKING:
    from codeweaver.core import AnonymityConversion, FilteredKeyT

_logger = logging.getLogger(__name__)

BRACKET_PATTERN: re.Pattern[str] = re.compile("\\\\\\[.+\\\\]")


def _get_statistics(stats: StatisticsDep) -> SessionStatistics:
    """Dependency injector helper to get session statistics."""
    return stats


@dataclass(order=True, kw_only=True)
class CodeWeaverState(DataclassSerializationMixin):
    """Application state for CodeWeaver server.

    A few important notes about CodeWeaverState and the codeweaver server more broadly:
    - An instance of CodeWeaverState and its server **must be associated with a unique project path**, which includes the project path's subdirectories. We currently don't *check* for this uniqueness, but failing to honor it may result in instability and, in some cases, data destruction. Specifically, if multiple server instances are started with overlapping or identical project paths, they may concurrently access and modify the same files or directories, leading to race conditions, file corruption, or loss of data. Additionally, port conflicts between instances can cause unexpected behavior or crashes. To avoid these risks, always ensure that each server instance has a unique project path and does not share directories with other instances. If you have suggestions for enforcing this uniqueness, please open an issue or PR!
    - CodeWeaverState is a singleton per CodeWeaver server instance. You should not create multiple instances of CodeWeaverState within the same server process.
    - If you need to run multiple CodeWeaver server instances (for different projects), you need to ensure that each instance has its own process, and that each instance's ports do not conflict (both the mcp port if using http/streamable-http transport for mcp, and the management server port).

    CodeWeaver was intended to run as a dedicated server for a single project/repo at a time, so these constraints are in place to ensure stability and data integrity. If you have a use case that requires multiple projects in the same process, please open an issue to discuss it.

    We do think there may be a need for us to support multiple projects in the same process in the future, but it will require significant changes and is not currently on our roadmap.
    """

    initialized: Annotated[
        bool, Field(description="Indicates if the server has been initialized")
    ] = False
    settings: Annotated[
        CodeWeaverSettingsType | None,
        Field(default_factory=get_settings, description="CodeWeaver configuration settings"),
    ]
    config_path: Annotated[
        Path | None, Field(default=None, description="Path to the configuration file, if any")
    ]
    project_path: Annotated[
        DirectoryPath,
        Field(default_factory=get_project_path, description="Path to the project root"),
    ]
    statistics: Annotated[
        SessionStatistics,
        Field(
            default_factory=_get_statistics,
            description="Session statistics and performance tracking",
        ),
    ]
    indexer: Annotated[
        IndexingService | None,
        Field(description="IndexingService instance for background indexing"),
    ] = None
    health_service: Annotated[
        HealthService | None, Field(description="Health service instance", exclude=True)
    ] = None
    failover_manager: Annotated[
        FailoverService | None, Field(description="Failover service instance", exclude=True)
    ] = None
    startup_time: NonNegativeInt = int(time.time())
    startup_stopwatch: NonNegativeInt = int(time.monotonic())
    management_server: Annotated[
        ManagementServer | None,
        Field(
            description="Management HTTP server instance. The Management Server is a lightweight uvicorn server that provides HTTP endpoints for status checking and similar functionality.",
            exclude=True,
        ),
    ] = None
    middleware_stack: tuple[ASGIMiddleware, ...] = Field(
        default_factory=tuple,
        description="Optional HTTP middleware stack to CodeWeaver's management and http mcp servers.",
    )
    telemetry: Annotated[TelemetryService | None, PrivateAttr(default=None)]
    http_pool: Annotated[
        HttpClientPool | None,
        Field(
            default=None,
            description="Shared HTTP client pool for provider connections (Voyage, Cohere, etc.)",
            exclude=True,
        ),
    ] = None
    _mcp_http_server: Annotated[FastMCP[CwMcpHttpState] | None, PrivateAttr()] = None
    _tasks: Annotated[list[asyncio.Task] | None, PrivateAttr(default_factory=list)] = None

    def __post_init__(self) -> None:
        """Post-initialization."""
        self._tasks = []

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core import AnonymityConversion, FilteredKey

        return {
            FilteredKey("config_path"): AnonymityConversion.BOOLEAN,
            FilteredKey("project_path"): AnonymityConversion.HASH,
        }

    @computed_field
    @property
    def request_count(self) -> NonNegativeInt:
        """Computed field for the number of requests handled by the server."""
        return self.statistics.total_requests if self.statistics else 0

    @computed_field
    def uptime_seconds(self) -> NonNegativeInt:
        """Computed field for the server uptime in seconds."""
        return int(time.monotonic() - self.startup_stopwatch)

    @computed_field
    def human_uptime(self) -> str:
        """Computed field for the server uptime in human-readable format."""
        return elapsed_time_to_human_readable(self.uptime_seconds())

    @property
    def mcp_http_server(self) -> FastMCP[CwMcpHttpState] | None:
        """Get the MCP HTTP server instance."""
        return self._mcp_http_server


async def _cleanup_state(
    state: CodeWeaverState,
    indexing_task: asyncio.Task | None,
    progress_reporter: ProgressReporter,
    *,
    verbose: bool = False,
) -> None:
    """Clean up application state and shutdown services.

    Args:
        state: Application state
        indexing_task: Background indexing task to cancel
        progress_reporter: ProgressReporter instance for user-facing output
        verbose: Whether to show verbose output
    """
    progress_reporter.report_status("Saving state...", extra={"end": ""})
    if indexing_task and (not indexing_task.done()):
        indexing_task.cancel()
        try:
            await asyncio.wait_for(indexing_task, timeout=INDEXER_WINDDOWN_TIMEOUT)
            if verbose:
                _logger.info("Background indexing stopped gracefully")
        except TimeoutError:
            _logger.warning(
                "Background indexing did not stop within %d seconds, forcing shutdown",
                INDEXER_WINDDOWN_TIMEOUT,
            )
        except asyncio.CancelledError:
            if verbose:
                _logger.info("Background indexing stopped")
    if state.telemetry and state.telemetry.enabled:
        try:
            from codeweaver.core.telemetry import capture_session_event

            duration_seconds = time.time() - state.startup_time
            await capture_session_event(
                state.statistics,
                version=version,
                setup_success=state.initialized,
                setup_attempts=ONE,
                config_errors=None,
                duration_seconds=duration_seconds,
            )
        except Exception:
            logging.getLogger(__name__).exception("Error capturing session telemetry event")
        try:
            state.telemetry.end_session()
        except Exception:
            logging.getLogger(__name__).exception("Error shutting down telemetry client")
    if state.http_pool:
        try:
            await state.http_pool.close_all()
            if verbose:
                _logger.info("Closed HTTP client pools")
        except Exception:
            logging.getLogger(__name__).exception("Error closing HTTP client pools")
    if verbose:
        _logger.info("Exiting CodeWeaver lifespan context manager...")
    progress_reporter.report_status("✓")
    progress_reporter.report_status("Goodbye!")
    state.initialized = False


@asynccontextmanager
async def lifespan(
    app: ManagementServer[CodeWeaverState],
    settings: CodeWeaverSettings | None,
    statistics: SessionStatistics | None = None,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> AsyncIterator[CodeWeaverState]:
    """Context manager for application lifespan with proper initialization.

    Args:
        app: application instance
        settings: Configuration settings
        statistics: Session statistics instance
        verbose: Enable verbose logging
        debug: Enable debug logging
    """
    progress_reporter = RichConsoleProgressReporter()
    server_host = getattr(app, "host", LOCALHOST) if hasattr(app, "host") else LOCALHOST
    server_port = (
        getattr(app, "port", DEFAULT_MANAGEMENT_PORT)
        if hasattr(app, "port")
        else DEFAULT_MANAGEMENT_PORT
    )
    progress_reporter.report_status(f"Server: http://{server_host}:{server_port}")
    progress_reporter.report_status("Built with FastMCP (https://gofastmcp.com)", level="debug")

    if verbose or debug:
        _logger.info("Entering lifespan context manager...")

    # Bootstrap settings via DI system implicitly when resolving state
    # But if passed explicitly (e.g. tests), we might want to respect that.
    # For now, we assume standard DI flow.

    container = get_container()

    if settings:
        container.override(CodeWeaverSettingsType, settings)

    # Register core singletons if provided explicitly
    # (Note: settings and statistics might need to be overridden in container if passed here,
    # but standard flow resolves them from container)

    try:
        # Resolve the entire state graph
        # This triggers factories in codeweaver.server.dependencies
        # which injects IndexingService, HealthService, etc.
        state = await container.resolve(CodeWeaverState)
    except Exception as e:
        raise InitializationError(
            "Failed to resolve CodeWeaverState. Check configuration and dependencies.",
            details={"error": str(e)},
        ) from e

    if not isinstance(state, CodeWeaverState):
        raise InitializationError(
            "CodeWeaverState should be an instance of CodeWeaverState, but isn't. Something is wrong. Please report this issue.",
            details={"state": state},
        )

    # Initialize telemetry if not already done by factory (it's currently done in factory if configured)
    if not state.telemetry:
        from codeweaver.core import TelemetryService

        state.telemetry = TelemetryService.from_settings(state.settings)

    if state.telemetry and state.telemetry.enabled:
        # Start session with simplified metadata (provider registry is gone,
        # so we'd need to inspect providers manually if we want that data,
        # or rely on what's available)
        state.telemetry.start_session({"codeweaver_version": version})

    indexing_task = None
    async with container.lifespan():
        try:
            if verbose or debug:
                _logger.info("Ensuring services set up...")
            from codeweaver.server.background_services import run_background_indexing

            # Note: run_background_indexing resolves FileWatchingService internally or we pass it?
            # Existing code passed state.
            indexing_task = asyncio.create_task(
                run_background_indexing(state, progress_reporter, verbose=verbose, debug=debug)
            )

            progress_reporter.report_status("Health checks...")
            if state.health_service:
                health_response = await state.health_service.get_health_response()
                vs_status = health_response.services.vector_store.status
                status_icon = {"up": "✅", "down": "❌", "degraded": "⚠️"}.get(vs_status, vs_status)
                progress_reporter.report_status(f"Vector store (Qdrant): {status_icon}")

                if vs_status in ("down", "degraded") and (not (verbose or debug)):
                    progress_reporter.report_status(
                        "  Unable to connect. Continuing with sparse-only search.", level="warning"
                    )
                    progress_reporter.report_status(
                        "  To enable semantic search: docker run -p 6333:6333 qdrant/qdrant",
                        level="warning",
                    )
                elif vs_status in ("down", "degraded"):
                    _logger.warning(
                        "Failed to connect to Qdrant. Check configuration and ensure Qdrant is running."
                    )

                emb_status = health_response.services.embedding_provider.status
                emb_model = health_response.services.embedding_provider.model
                status_icon = {"up": "✅", "down": "❌", "degraded": "⚠️"}.get(
                    emb_status, emb_status
                )
                progress_reporter.report_status(
                    f"Embeddings (Voyage AI): {status_icon} ({emb_model})"
                )

                sparse_prov = health_response.services.sparse_embedding.provider
                sparse_status = health_response.services.sparse_embedding.status
                status_icon = {"up": "✅", "down": "❌", "degraded": "⚠️"}.get(
                    sparse_status, sparse_status
                )
                progress_reporter.report_status(f"Sparse embeddings ({sparse_prov}): {status_icon}")

            progress_reporter.report_status("Ready for connections.")
            if verbose or debug:
                _logger.info("Lifespan start actions complete, server initialized.")
            state.initialized = True
            yield state
        except Exception:
            state.initialized = False
            raise
        finally:
            await _cleanup_state(state, indexing_task, progress_reporter, verbose=verbose or debug)


__all__ = ("BRACKET_PATTERN", "CodeWeaverState", "lifespan")
