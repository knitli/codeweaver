# sourcery skip: no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Initialize the CodeWeaver Server (all background services)."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from fastmcp import FastMCP
from pydantic import ConfigDict, DirectoryPath, Field, NonNegativeInt, PrivateAttr, computed_field
from pydantic.dataclasses import dataclass
from starlette.middleware import Middleware as ASGIMiddleware

from codeweaver import __version__ as version
from codeweaver.common.registry import ModelRegistry, ProviderRegistry, ServicesRegistry
from codeweaver.common.statistics import SessionStatistics
from codeweaver.common.telemetry.client import PostHogClient
from codeweaver.common.utils import elapsed_time_to_human_readable, get_project_path, lazy_import
from codeweaver.config.settings import CodeWeaverSettings
from codeweaver.core.types.dataclasses import DATACLASS_CONFIG, DataclassSerializationMixin
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.sentinel import Unset
from codeweaver.engine.failover import VectorStoreFailoverManager
from codeweaver.engine.indexer import Indexer
from codeweaver.exceptions import InitializationError
from codeweaver.mcp.state import CwMcpHttpState
from codeweaver.providers.provider import Provider as Provider
from codeweaver.server.health.health_service import HealthService
from codeweaver.server.management import ManagementServer


if TYPE_CHECKING:
    from codeweaver.common.http_pool import HttpClientPool
    from codeweaver.common.utils import LazyImport
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT

# lazy imports for default factory functions
get_provider_registry: LazyImport[Callable[[], ProviderRegistry]] = lazy_import(
    "codeweaver.common.registry.provider", "get_provider_registry"
)
get_services_registry: LazyImport[Callable[[], ServicesRegistry]] = lazy_import(
    "codeweaver.common.registry.services", "get_services_registry"
)
get_model_registry: LazyImport[Callable[[], ModelRegistry]] = lazy_import(
    "codeweaver.common.registry.models", "get_model_registry"
)
get_session_statistics: LazyImport[Callable[[], SessionStatistics]] = lazy_import(
    "codeweaver.common.statistics", "get_session_statistics"
)
get_settings: LazyImport[Callable[[], CodeWeaverSettings]] = lazy_import(
    "codeweaver.config.settings", "get_settings"
)

_logger = logging.getLogger(__name__)
BRACKET_PATTERN: re.Pattern[str] = re.compile("\\[.+\\]")


# ================================================
# *     CodeWeaver Application State and Health
# ================================================


@dataclass(order=True, kw_only=True, config=DATACLASS_CONFIG | ConfigDict(extra="forbid"))
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
        CodeWeaverSettings | None,
        Field(default_factory=get_settings, description="CodeWeaver configuration settings"),
    ]
    config_path: Annotated[
        Path | None, Field(default=None, description="Path to the configuration file, if any")
    ]
    project_path: Annotated[
        DirectoryPath,
        Field(default_factory=get_project_path, description="Path to the project root"),
    ]
    provider_registry: Annotated[
        ProviderRegistry,
        Field(
            default_factory=get_provider_registry,
            description="Provider registry for dynamic provider management",
        ),
    ]
    services_registry: Annotated[
        ServicesRegistry,
        Field(
            default_factory=get_services_registry,
            description="Service registry for managing available services",
        ),
    ]
    model_registry: Annotated[
        ModelRegistry,
        Field(
            default_factory=get_model_registry,
            description="Model registry for managing AI and embedding/reranking models",
        ),
    ]
    statistics: Annotated[
        SessionStatistics,
        Field(
            default_factory=get_session_statistics,
            description="Session statistics and performance tracking",
        ),
    ]
    indexer: Annotated[
        Indexer | None, Field(description="Indexer instance for background indexing")
    ] = None
    health_service: Annotated[
        HealthService | None, Field(description="Health service instance", exclude=True)
    ] = None
    failover_manager: Annotated[
        VectorStoreFailoverManager | None,
        Field(description="Failover manager instance", exclude=True),
    ] = None
    startup_time: NonNegativeInt = Field(default_factory=lambda: int(time.time()))
    startup_stopwatch: NonNegativeInt = Field(default_factory=lambda: int(time.monotonic()))
    management_server: Annotated[
        ManagementServer | None,
        Field(
            description="Management HTTP server instance. The Management Server is a lightweight uvicorn server that provides HTTP endpoints for status checking and similar functionality.",
            exclude=True,
        ),
    ] = None  # type: ignore[valid-type]

    middleware_stack: tuple[ASGIMiddleware, ...] = Field(
        default_factory=tuple,
        description="Optional HTTP middleware stack to CodeWeaver's management and http mcp servers.",
    )

    telemetry: Annotated[PostHogClient | None, PrivateAttr(default=None)]

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
        """Post-initialization to set the global state reference."""
        self._tasks = []
        global _state
        _state = self

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        # Each of the values that are BasedModel or DataclassSerializationMixin have their own filters
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            # We'd need to make broader use of the Unset sentinel for that to work well
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


_state: CodeWeaverState | None = None


def get_state() -> CodeWeaverState:
    """Get the current application state."""
    global _state
    if _state is None:
        raise InitializationError(
            "CodeWeaverState has not been initialized yet. Ensure the server is properly set up before accessing the state."
        )
    return _state


def _get_health_service() -> HealthService:
    """Get the health service instance."""
    state = get_state()

    return HealthService(
        provider_registry=state.provider_registry,
        statistics=state.statistics,
        indexer=state.indexer,
        startup_stopwatch=state.startup_stopwatch,
    )


async def _cleanup_state(
    state: CodeWeaverState,
    indexing_task: asyncio.Task | None,
    status_display: Any,
    *,
    verbose: bool = False,
) -> None:
    """Clean up application state and shutdown services.

    Args:
        state: Application state
        indexing_task: Background indexing task to cancel
        status_display: StatusDisplay instance for user-facing output
        verbose: Whether to show verbose output
    """
    # Show clean shutdown message
    status_display.print_shutdown_start()

    # Cancel background indexing with timeout
    if indexing_task and not indexing_task.done():
        indexing_task.cancel()
        try:
            # Wait up to 7 seconds for graceful shutdown
            await asyncio.wait_for(indexing_task, timeout=7.0)
            if verbose:
                _logger.info("Background indexing stopped gracefully")
        except TimeoutError:
            _logger.warning("Background indexing did not stop within 7 seconds, forcing shutdown")
            # Task is already cancelled, just move on
        except asyncio.CancelledError:
            if verbose:
                _logger.info("Background indexing stopped")

    # Capture session telemetry event before shutdown
    if state.telemetry and state.telemetry.enabled:
        try:
            from codeweaver.common.telemetry.events import capture_session_event

            # Calculate session duration
            duration_seconds = time.time() - state.startup_time

            # Capture session event with statistics
            capture_session_event(
                state.statistics,
                version=version,
                setup_success=state.initialized,
                setup_attempts=1,  # TODO: track actual attempts
                config_errors=None,  # TODO: track config errors
                duration_seconds=duration_seconds,
            )
        except Exception:
            logging.getLogger(__name__).exception("Error capturing session telemetry event")

        # End telemetry session (closes context and flushes events)
        try:
            state.telemetry.end_session()
        except Exception:
            logging.getLogger(__name__).exception("Error shutting down telemetry client")

    # Close HTTP client pools to release connections
    if state.http_pool:
        try:
            await state.http_pool.close_all()
            if verbose:
                _logger.info("Closed HTTP client pools")
        except Exception:
            logging.getLogger(__name__).exception("Error closing HTTP client pools")

    if verbose:
        _logger.info("Exiting CodeWeaver lifespan context manager...")

    status_display.print_shutdown_complete()
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
    from codeweaver.cli.ui import StatusDisplay

    # Create StatusDisplay for clean user-facing output
    status_display = StatusDisplay()

    # Print clean header (not in verbose mode, as this is always shown)
    server_host = getattr(app, "host", "127.0.0.1") if hasattr(app, "host") else "127.0.0.1"
    server_port = getattr(app, "port", 9329) if hasattr(app, "port") else 9329
    status_display.print_header(host=server_host, port=server_port)

    if verbose or debug:
        _logger.info("Entering lifespan context manager...")

    if settings is None:
        settings = get_settings._resolve()()
    if isinstance(settings.project_path, Unset):
        settings.project_path = get_project_path()

    state = _initialize_cw_state(settings, statistics)

    if not isinstance(state, CodeWeaverState):
        raise InitializationError(
            "CodeWeaverState should be an instance of CodeWeaverState, but isn't. Something is wrong. Please report this issue.",
            details={"state": state},
        )

    indexing_task = None

    try:
        if verbose or debug:
            _logger.info("Ensuring services set up...")
        from codeweaver.server.background_services import run_background_indexing

        # Start background indexing task
        indexing_task = asyncio.create_task(
            run_background_indexing(state, status_display, verbose=verbose, debug=debug)
        )

        # Perform health checks and display results
        status_display.print_step("Health checks...")

        if state.health_service:
            health_response = await state.health_service.get_health_response()

            # Vector store health with degraded handling
            vs_status = health_response.services.vector_store.status
            status_display.print_health_check("Vector store (Qdrant)", vs_status)

            # Show helpful message for degraded/down vector store
            if vs_status in ("down", "degraded") and not (verbose or debug):
                status_display.console.print(
                    "  [dim]Unable to connect. Continuing with sparse-only search.[/dim]"
                )
                status_display.console.print(
                    "  [dim]To enable semantic search: docker run -p 6333:6333 qdrant/qdrant[/dim]"
                )
            elif vs_status in ("down", "degraded"):
                _logger.warning(
                    "Failed to connect to Qdrant. Check configuration and ensure Qdrant is running."
                )

            # Embeddings health
            status_display.print_health_check(
                "Embeddings (Voyage AI)",
                health_response.services.embedding_provider.status,
                model=health_response.services.embedding_provider.model,
            )

            # Sparse embeddings health
            status_display.print_health_check(
                f"Sparse embeddings ({health_response.services.sparse_embedding.provider})",
                health_response.services.sparse_embedding.status,
            )
        if not state.failover_manager:
            state.failover_manager = VectorStoreFailoverManager()
        status_display.print_ready()

        if verbose or debug:
            _logger.info("Lifespan start actions complete, server initialized.")
        state.initialized = True
        yield state
    except Exception:
        state.initialized = False
        raise
    finally:
        await _cleanup_state(state, indexing_task, status_display, verbose=verbose or debug)


def _initialize_cw_state(
    settings: CodeWeaverSettings | None = None, statistics: SessionStatistics | None = None
) -> CodeWeaverState:
    """Initialize application state if not already present."""
    from codeweaver.common.http_pool import HttpClientPool

    resolved_settings = settings or get_settings._resolve()()

    # Initialize HTTP client pool for connection reuse
    http_pool = HttpClientPool.get_instance()
    _logger.debug("Initialized HTTP client pool for provider connections")

    state = CodeWeaverState(  # type: ignore
        initialized=False,
        # for lazy imports, we need to call resolve() to get the function/object and then call it
        settings=resolved_settings,
        statistics=statistics or get_session_statistics._resolve()(),
        project_path=get_project_path()
        if isinstance(resolved_settings.project_path, Unset)
        else resolved_settings.project_path,
        config_path=None
        if isinstance(resolved_settings.config_file, Unset)
        else resolved_settings.config_file,
        provider_registry=get_provider_registry._resolve()(),
        services_registry=get_services_registry._resolve()(),
        model_registry=get_model_registry._resolve()(),
        # middleware stack is for ASGIMiddleware; we haven't integrated this yet
        middleware_stack=(),
        health_service=None,  # Initialize as None, will be set after CodeWeaverState construction
        failover_manager=None,  # Initialize as None, will be set after CodeWeaverState construction
        telemetry=PostHogClient.from_settings(),
        http_pool=http_pool,
        indexer=Indexer.from_settings(),
    )
    state.health_service = _get_health_service()
    # Start telemetry session with metadata
    if state.telemetry and state.telemetry.enabled:
        state.telemetry.start_session({
            "codeweaver_version": version,
            "vector_store": vector_store_provider
            if (
                vector_store_provider := state.provider_registry.get_provider_enum_for(
                    "vector_store"
                )
            )
            else "Qdrant",
            "embedding_provider": embedding_provider_provider
            if (
                embedding_provider_provider := state.provider_registry.get_provider_enum_for(
                    "embedding"
                )
            )
            else "Voyage",
            "sparse_embedding_provider": sparse_embedding_provider
            if (
                sparse_embedding_provider := state.provider_registry.get_provider_enum_for(
                    "sparse_embedding"
                )
            )
            else "None",
            "reranking_provider": reranking_provider
            if (reranking_provider := state.provider_registry.get_provider_enum_for("reranking"))
            else "None",
        })

    return state


__all__ = ("CodeWeaverState", "get_state", "lifespan")
