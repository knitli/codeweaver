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
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any
from fastmcp import FastMCP
from pydantic import ConfigDict, DirectoryPath, Field, NonNegativeInt, PrivateAttr, computed_field
from pydantic.dataclasses import dataclass
from starlette.middleware import Middleware as ASGIMiddleware
from codeweaver import __version__ as version
from codeweaver.core import DATACLASS_CONFIG, AnonymityConversion, DataclassSerializationMixin, InitializationError, SessionStatistics, Unset, elapsed_time_to_human_readable, get_container, get_project_path
from codeweaver.core import Provider as Provider
from codeweaver.engine import Indexer, VectorStoreFailoverManager
from codeweaver.providers import HttpClientPool
from codeweaver.server.config import CodeWeaverSettings
from codeweaver.server.health.health_service import HealthService
from codeweaver.server.management import ManagementServer
from codeweaver.server.mcp import CwMcpHttpState
if TYPE_CHECKING:
    from codeweaver.core import AnonymityConversion, FilteredKeyT
_logger = logging.getLogger(__name__)
BRACKET_PATTERN: re.Pattern[str] = re.compile('\\[.+\\]')

@dataclass(order=True, kw_only=True, config=DATACLASS_CONFIG | ConfigDict(extra='forbid'))
class CodeWeaverState(DataclassSerializationMixin):
    """Application state for CodeWeaver server.

    A few important notes about CodeWeaverState and the codeweaver server more broadly:
    - An instance of CodeWeaverState and its server **must be associated with a unique project path**, which includes the project path's subdirectories. We currently don't *check* for this uniqueness, but failing to honor it may result in instability and, in some cases, data destruction. Specifically, if multiple server instances are started with overlapping or identical project paths, they may concurrently access and modify the same files or directories, leading to race conditions, file corruption, or loss of data. Additionally, port conflicts between instances can cause unexpected behavior or crashes. To avoid these risks, always ensure that each server instance has a unique project path and does not share directories with other instances. If you have suggestions for enforcing this uniqueness, please open an issue or PR!
    - CodeWeaverState is a singleton per CodeWeaver server instance. You should not create multiple instances of CodeWeaverState within the same server process.
    - If you need to run multiple CodeWeaver server instances (for different projects), you need to ensure that each instance has its own process, and that each instance's ports do not conflict (both the mcp port if using http/streamable-http transport for mcp, and the management server port).

    CodeWeaver was intended to run as a dedicated server for a single project/repo at a time, so these constraints are in place to ensure stability and data integrity. If you have a use case that requires multiple projects in the same process, please open an issue to discuss it.

    We do think there may be a need for us to support multiple projects in the same process in the future, but it will require significant changes and is not currently on our roadmap.
    """
    initialized: Annotated[bool, Field(description='Indicates if the server has been initialized')] = False
    settings: Annotated[CodeWeaverSettings | None, Field(default_factory=get_settings, description='CodeWeaver configuration settings')]
    config_path: Annotated[Path | None, Field(default=None, description='Path to the configuration file, if any')]
    project_path: Annotated[DirectoryPath, Field(default_factory=get_project_path, description='Path to the project root')]
    statistics: Annotated[SessionStatistics, Field(default_factory=get_session_statistics, description='Session statistics and performance tracking')]
    indexer: Annotated[Indexer | None, Field(description='Indexer instance for background indexing')] = None
    health_service: Annotated[HealthService | None, Field(description='Health service instance', exclude=True)] = None
    failover_manager: Annotated[VectorStoreFailoverManager | None, Field(description='Failover manager instance', exclude=True)] = None
    startup_time: NonNegativeInt = Field(default_factory=lambda: int(time.time()))
    startup_stopwatch: NonNegativeInt = Field(default_factory=lambda: int(time.monotonic()))
    management_server: Annotated[ManagementServer | None, Field(description='Management HTTP server instance. The Management Server is a lightweight uvicorn server that provides HTTP endpoints for status checking and similar functionality.', exclude=True)] = None
    middleware_stack: tuple[ASGIMiddleware, ...] = Field(default_factory=tuple, description="Optional HTTP middleware stack to CodeWeaver's management and http mcp servers.")
    telemetry: Annotated[TelemetryService | None, PrivateAttr(default=None)]
    http_pool: Annotated[HttpClientPool | None, Field(default=None, description='Shared HTTP client pool for provider connections (Voyage, Cohere, etc.)', exclude=True)] = None
    _mcp_http_server: Annotated[FastMCP[CwMcpHttpState] | None, PrivateAttr()] = None
    _tasks: Annotated[list[asyncio.Task] | None, PrivateAttr(default_factory=list)] = None

    def __post_init__(self) -> None:
        """Post-initialization to set the global state reference."""
        self._tasks = []
        global _state
        _state = self

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core import AnonymityConversion, FilteredKey
        return {FilteredKey('config_path'): AnonymityConversion.BOOLEAN, FilteredKey('project_path'): AnonymityConversion.HASH}

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
        try:
            import asyncio
        except Exception as e:
            raise InitializationError('CodeWeaverState has not been initialized yet. Ensure the server is properly set up before accessing the state.') from e
        else:
            return asyncio.run(get_container().resolve(CodeWeaverState))
    return _state

def _get_health_service() -> HealthService:
    """Get the health service instance."""
    state = get_state()
    return HealthService(statistics=state.statistics, indexer=state.indexer, startup_stopwatch=state.startup_stopwatch)

async def _cleanup_state(state: CodeWeaverState, indexing_task: asyncio.Task | None, status_display: Any, *, verbose: bool=False) -> None:
    """Clean up application state and shutdown services.

    Args:
        state: Application state
        indexing_task: Background indexing task to cancel
        status_display: StatusDisplay instance for user-facing output
        verbose: Whether to show verbose output
    """
    status_display.print_shutdown_start()
    if indexing_task and (not indexing_task.done()):
        indexing_task.cancel()
        try:
            await asyncio.wait_for(indexing_task, timeout=7.0)
            if verbose:
                _logger.info('Background indexing stopped gracefully')
        except TimeoutError:
            _logger.warning('Background indexing did not stop within 7 seconds, forcing shutdown')
        except asyncio.CancelledError:
            if verbose:
                _logger.info('Background indexing stopped')
    if state.telemetry and state.telemetry.enabled:
        try:
            from codeweaver.core import capture_session_event
            duration_seconds = time.time() - state.startup_time
            capture_session_event(state.statistics, version=version, setup_success=state.initialized, setup_attempts=1, config_errors=None, duration_seconds=duration_seconds)
        except Exception:
            logging.getLogger(__name__).exception('Error capturing session telemetry event')
        try:
            state.telemetry.end_session()
        except Exception:
            logging.getLogger(__name__).exception('Error shutting down telemetry client')
    if state.http_pool:
        try:
            await state.http_pool.close_all()
            if verbose:
                _logger.info('Closed HTTP client pools')
        except Exception:
            logging.getLogger(__name__).exception('Error closing HTTP client pools')
    if verbose:
        _logger.info('Exiting CodeWeaver lifespan context manager...')
    status_display.print_shutdown_complete()
    state.initialized = False

@asynccontextmanager
async def lifespan(app: ManagementServer[CodeWeaverState], settings: CodeWeaverSettings | None, statistics: SessionStatistics | None=None, *, verbose: bool=False, debug: bool=False) -> AsyncIterator[CodeWeaverState]:
    """Context manager for application lifespan with proper initialization.

    Args:
        app: application instance
        settings: Configuration settings
        statistics: Session statistics instance
        verbose: Enable verbose logging
        debug: Enable debug logging
    """
    from codeweaver.cli import StatusDisplay
    status_display = StatusDisplay()
    server_host = getattr(app, 'host', '127.0.0.1') if hasattr(app, 'host') else '127.0.0.1'
    server_port = getattr(app, 'port', 9329) if hasattr(app, 'port') else 9329
    status_display.print_header(host=server_host, port=server_port)
    if verbose or debug:
        _logger.info('Entering lifespan context manager...')
    if settings is None:
        settings = get_settings._resolve()()
    if isinstance(settings.project_path, Unset):
        settings.project_path = get_project_path()
    state = await _initialize_cw_state(settings, statistics)
    if not isinstance(state, CodeWeaverState):
        raise InitializationError("CodeWeaverState should be an instance of CodeWeaverState, but isn't. Something is wrong. Please report this issue.", details={'state': state})
    indexing_task = None
    async with get_container().lifespan():
        try:
            if verbose or debug:
                _logger.info('Ensuring services set up...')
            from codeweaver.server.background_services import run_background_indexing
            indexing_task = asyncio.create_task(run_background_indexing(state, status_display, verbose=verbose, debug=debug))
            status_display.print_step('Health checks...')
            if state.health_service:
                health_response = await state.health_service.get_health_response()
                vs_status = health_response.services.vector_store.status
                status_display.print_health_check('Vector store (Qdrant)', vs_status)
                if vs_status in ('down', 'degraded') and (not (verbose or debug)):
                    status_display.console.print('  [dim]Unable to connect. Continuing with sparse-only search.[/dim]')
                    status_display.console.print('  [dim]To enable semantic search: docker run -p 6333:6333 qdrant/qdrant[/dim]')
                elif vs_status in ('down', 'degraded'):
                    _logger.warning('Failed to connect to Qdrant. Check configuration and ensure Qdrant is running.')
                status_display.print_health_check('Embeddings (Voyage AI)', health_response.services.embedding_provider.status, model=health_response.services.embedding_provider.model)
                status_display.print_health_check(f'Sparse embeddings ({health_response.services.sparse_embedding.provider})', health_response.services.sparse_embedding.status)
            if not state.failover_manager:
                state.failover_manager = VectorStoreFailoverManager()
            status_display.print_ready()
            if verbose or debug:
                _logger.info('Lifespan start actions complete, server initialized.')
            state.initialized = True
            yield state
        except Exception:
            state.initialized = False
            raise
        finally:
            await _cleanup_state(state, indexing_task, status_display, verbose=verbose or debug)

async def _initialize_cw_state(settings: CodeWeaverSettings | None=None, statistics: SessionStatistics | None=None) -> CodeWeaverState:
    """Initialize application state if not already present."""
    from codeweaver.core import get_container
    container = get_container()
    state = await container.resolve(CodeWeaverState)
    if not state.health_service:
        from codeweaver.server.health.health_service import HealthService
        state.health_service = HealthService(provider_registry=state.provider_registry, statistics=state.statistics, indexer=state.indexer, failover_manager=state.failover_manager, startup_stopwatch=float(state.startup_stopwatch))
    if not state.telemetry:
        from codeweaver.core import TelemetryService
        state.telemetry = TelemetryService.from_settings(state.settings)
    if state.telemetry and state.telemetry.enabled:
        state.telemetry.start_session({'codeweaver_version': version, 'vector_store': vector_store_provider if (vector_store_provider := state.provider_registry.get_provider_enum_for('vector_store')) else 'Qdrant', 'embedding_provider': embedding_provider_provider if (embedding_provider_provider := state.provider_registry.get_provider_enum_for('embedding')) else 'Voyage', 'sparse_embedding_provider': sparse_embedding_provider if (sparse_embedding_provider := state.provider_registry.get_provider_enum_for('sparse_embedding')) else 'None', 'reranking_provider': reranking_provider if (reranking_provider := state.provider_registry.get_provider_enum_for('reranking')) else 'None'})
    return state
__all__ = ('CodeWeaverState', 'get_state', 'lifespan')