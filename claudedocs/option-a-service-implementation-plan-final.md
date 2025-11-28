<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Option A: Service Architecture - Implementation Plan (FINAL)

> **Revision History**:
> - **v1**: Initial plan with server/background services separation
> - **v2**: Updated for CLI UX improvements and management server separation
> - **v3 (FINAL)**: Corrected middleware architecture, simplified state management, refined based on architecture review

> **Latest Update**: Document revised based on comprehensive architecture review:
> - **Middleware Correction**: Use FastMCP middleware (not Starlette) for telemetry and state access
> - **State Management**: Repurpose existing AppState as BackgroundState (minimal disruption)
> - **Configuration**: Background service settings in ServerSettings (not IndexerSettings)
> - **Management Server**: Direct route registration (reuse existing handlers)
> - **Information Flow**: Clarified that existing patterns already handle all required data flows

## Executive Summary

**Goal**: Separate CodeWeaver's background processes (indexing, file watching) from the MCP protocol layer, enabling full stdio support and proper process lifecycle management.

**Architectural Approach**: Same-process separation with clear boundaries, designed to evolve to separate-process architecture if needed.

**Timeline**: 3-4 weeks for alpha.2 release
**Breaking Changes**: Minimal - primarily internal architecture refactoring
**Benefits**:
- Full stdio support (not read-only)
- Clean separation of concerns (protocol vs. business logic)
- Foundation for future separate-process deployment
- Proper lifecycle management for background tasks
- Maintains CodeWeaver's ONE TOOL principle

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  CodeWeaver MCP Server Process (FastMCP + Starlette)   │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  MCP Protocol Layer (FastMCP)                      │ │
│  │  - Handles MCP protocol (HTTP or stdio)            │ │
│  │  - Port 9328 (HTTP mode only)                      │ │
│  │  - Exposes ONE TOOL: find_code()                   │ │
│  │  - FastMCP Middleware Stack:                       │ │
│  │    * StatisticsMiddleware (telemetry)              │ │
│  │    * ErrorHandlingMiddleware                       │ │
│  │    * RateLimitingMiddleware                        │ │
│  │  - No observability endpoints here                 │ │
│  └────────────────────────────────────────────────────┘ │
│         ↓ Access via global getter: get_background_state()
│  ┌────────────────────────────────────────────────────┐ │
│  │  Management Server (Always HTTP - Port 9329)       │ │
│  │  - Independent of MCP transport choice             │ │
│  │  - /health, /status, /metrics, /version            │ │
│  │  - /settings, /state                               │ │
│  │  - Available for stdio and HTTP MCP modes          │ │
│  │  - Runs via separate uvicorn instance              │ │
│  │  - Started automatically with background services  │ │
│  │  - Reuses handlers from app_bindings.py            │ │
│  └────────────────────────────────────────────────────┘ │
│         ↓ Both access BackgroundState via app.state     │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Background Services Layer (BackgroundState)       │ │
│  │  - Renamed from AppState (minimal disruption)      │ │
│  │  - ProviderRegistry (singleton)                    │ │
│  │  - IndexerService (file watching + indexing)       │ │
│  │  - HealthService (monitoring)                      │ │
│  │  - SessionStatistics (telemetry)                   │ │
│  │  - VectorStoreFailoverManager (resilience)         │ │
│  │  - ManagementServer (reference)                    │ │
│  │  - background_tasks: set[asyncio.Task]             │ │
│  │  - shutdown_event: asyncio.Event                   │ │
│  │  - Managed via Starlette lifespan                  │ │
│  └────────────────────────────────────────────────────┘ │
│         ↓ Providers                                     │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Provider Layer (ProviderRegistry)                 │ │
│  │  - Indexer (core indexing engine)                  │ │
│  │  - VectorStore (Qdrant)                            │ │
│  │  - Embedder (Voyage AI)                            │ │
│  │  - Sparse Embedder (local SPLADE)                  │ │
│  │  - Reranker                                        │ │
│  │  - FailoverManager (resilience)                    │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
         ↑ MCP Protocol (HTTP:9328 or stdio)
┌────────┴────────────┐
│  MCP Clients        │   Monitoring: http://127.0.0.1:9329
│  - Claude Desktop   │   (health, status, metrics)
│  - Cursor           │
│  - Continue         │
└─────────────────────┘
```

**Key Principles**:
1. **Constitutional Compliance**: ONE TOOL (`find_code`) exposed to agents
2. **Pattern Reuse**: Leverage existing AppState → rename to BackgroundState
3. **Same-Process First**: Clear boundaries, evolve to separate-process if needed
4. **Cross-Platform**: HTTP-first (Unix sockets deferred to later phase)
5. **Immutability**: Frozen models, get_settings_map() for read-only access
6. **Transport Independence**: Management endpoints always available (stdio or HTTP)
7. **FastMCP Middleware**: Use FastMCP middleware for MCP protocol concerns, not Starlette

---

## Information Flow Architecture

### Data Flow 1: Telemetry (find_code → telemetry service)

**Status**: ✅ Already implemented correctly

**Implementation**: FastMCP `StatisticsMiddleware` (existing)

```python
# src/codeweaver/middleware/statistics.py (EXISTING - NO CHANGES NEEDED)

class StatisticsMiddleware(Middleware):
    """FastMCP middleware to track request statistics and performance metrics."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, CallToolResult],
    ) -> CallToolResult:
        """Handle incoming tool requests and track statistics."""
        start_time = time.perf_counter()
        request_id = context.fastmcp_context.request_id

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Telemetry automatically captured
            self.statistics.add_successful_request(request_id=request_id)
            self.timing_statistics.update(
                "on_call_tool_requests",
                duration_ms,
                tool_or_resource_name=context.message.name
            )

            return result
        except Exception:
            # Track failures
            self.statistics.add_failed_request(request_id=request_id)
            raise
```

**Why this works**:
- FastMCP middleware sees ALL MCP operations (stdio and HTTP)
- Automatically captures timing, success/failure, request IDs
- No code changes needed in find_code tool
- Works across all transports

### Data Flow 2-4: Queries, Results, Status

**Status**: ✅ Already handled via existing patterns

**Implementation**: Global getter + ProviderRegistry

```python
# find_code accesses BackgroundState via global getter
# (No Context injection needed - DI framework planned for future)

async def find_code(
    query: str,
    intent: IntentType | None = None,
    *,
    token_limit: int = 30000,
    focus_languages: tuple[str, ...] | None = None,
) -> FindCodeResponseSummary:
    # Access background state via global getter
    # (same pattern as current get_state())
    from codeweaver.server.background.state import get_background_state

    background_state = get_background_state()

    # Flow 2: Queries to services (via ProviderRegistry)
    indexer = background_state.indexer

    # Flow 3: Results from services (via return values)
    response = await find_code_impl(query, intent, token_limit, focus_languages, indexer)

    # Flow 4: Status information (via HealthService and failover manager)
    if background_state.failover_manager:
        failover_metadata = {
            "failover": {
                "enabled": background_state.failover_manager.backup_enabled,
                "active": background_state.failover_manager.is_failover_active,
            }
        }
        response = response.model_copy(update={"metadata": failover_metadata})

    # SearchEvent telemetry (already implemented in find_code business logic)
    # See: src/codeweaver/agent_api/find_code/__init__.py:387-395
    try:
        from codeweaver.common.telemetry.events import capture_search_event

        capture_search_event(
            response=response,
            query=query,
            intent_type=intent or IntentType.UNDERSTAND,
            strategies=strategies_used,
            execution_time_ms=execution_time_ms,
            tools_over_privacy=tools_over_privacy,
            feature_flags=feature_flags,
        )
    except Exception:
        # Never fail find_code due to telemetry
        logger.debug("Failed to capture search telemetry")

    return response
```

**Why this works**:
- Global `get_background_state()` accessible everywhere (same pattern as current `get_state()`)
- ProviderRegistry provides access to all services
- SearchEvent telemetry already implemented in find_code business logic
- No FastMCP middleware needed for SearchEvent (too specific to find_code)
- DI framework planned for future will replace global getter pattern

**Important Note on Telemetry**:
- **MCP-level timing**: Captured by `StatisticsMiddleware` (FastMCP middleware)
- **SearchEvent telemetry**: Captured in `find_code()` business logic (already implemented at lines 387-395, 408-418)
- SearchEvent has rich context (query, response, intent, strategies, execution time)
- SearchEvent is NOT in middleware because it needs find_code execution context
- No changes needed to telemetry architecture

---

## Phase 1: Background Services Extraction (Week 1-2)

### 1.1 Rename and Extend AppState → BackgroundState

**Rationale**: Current AppState is already 90% background services. Rename it rather than creating a new class.

**File**: `src/codeweaver/server/background/state.py` (NEW - moved from server.py)

```python
"""
Background services state management.

Extracted from existing AppState pattern - manages lifecycle of background
services independent of protocol layer.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from pydantic import ConfigDict, DirectoryPath, Field, NonNegativeInt, PrivateAttr, computed_field
from pydantic.dataclasses import dataclass

from codeweaver.core.types.models import DATACLASS_CONFIG, DataclassSerializationMixin
from codeweaver.common.logging import get_logger

if TYPE_CHECKING:
    from codeweaver.engine.indexer.indexer import Indexer
    from codeweaver.common.health import HealthService
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.common.registry import ProviderRegistry, ServicesRegistry, ModelRegistry
    from codeweaver.providers.failover import VectorStoreFailoverManager
    from codeweaver.common.telemetry.client import PostHogClient
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.core.types import FilteredKeyT, AnonymityConversion

logger = get_logger(__name__)


@dataclass(order=True, kw_only=True, config=DATACLASS_CONFIG | ConfigDict(extra="forbid"))
class BackgroundState(DataclassSerializationMixin):
    """
    Background services state (formerly AppState).

    Manages lifecycle of long-running background tasks independent of
    MCP protocol concerns. This is the same as the old AppState, just
    renamed and extended with background task tracking.
    """

    initialized: Annotated[
        bool, Field(description="Indicates if the background services have been initialized")
    ] = False
    settings: Annotated[
        CodeWeaverSettings | None,
        Field(description="CodeWeaver configuration settings"),
    ]
    config_path: Annotated[
        Path | None, Field(default=None, description="Path to the configuration file, if any")
    ]
    project_path: Annotated[
        DirectoryPath,
        Field(description="Path to the project root"),
    ]
    provider_registry: Annotated[
        ProviderRegistry,
        Field(description="Provider registry for dynamic provider management"),
    ]
    services_registry: Annotated[
        ServicesRegistry,
        Field(description="Service registry for managing available services"),
    ]
    model_registry: Annotated[
        ModelRegistry,
        Field(description="Model registry for managing AI and embedding/reranking models"),
    ]
    statistics: Annotated[
        SessionStatistics,
        Field(description="Session statistics and performance tracking"),
    ]
    indexer: Annotated[
        Indexer | None, Field(default=None, description="Indexer instance for background indexing")
    ]
    health_service: Annotated[
        HealthService | None, Field(description="Health service instance", exclude=True)
    ] = None
    failover_manager: Annotated[
        VectorStoreFailoverManager | None,
        Field(description="Failover manager instance", exclude=True),
    ] = None
    startup_time: Annotated[
        float, Field(default_factory=time.time, description="Server startup timestamp")
    ]

    # NEW: Management server reference
    management_server: Annotated[
        ManagementServer | None,
        Field(description="Management HTTP server instance", exclude=True)
    ] = None

    # NEW: Background task tracking
    background_tasks: Annotated[
        set[asyncio.Task],
        Field(default_factory=set, description="Set of running background tasks")
    ] = field(default_factory=set)

    # NEW: Shutdown coordination
    shutdown_event: Annotated[
        asyncio.Event,
        Field(default_factory=asyncio.Event, description="Event to signal shutdown")
    ] = field(default_factory=asyncio.Event)

    telemetry: Annotated[PostHogClient | None, PrivateAttr()] = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("config_path"): AnonymityConversion.BOOLEAN,
            FilteredKey("project_path"): AnonymityConversion.HASH,
        }

    @computed_field
    @property
    def request_count(self) -> NonNegativeInt:
        """Computed field for the number of requests handled by the server."""
        if self.statistics:
            return self.statistics.total_requests + (self.statistics.total_http_requests or 0)
        return 0

    async def initialize(self) -> None:
        """Initialize background services."""
        if self.initialized:
            logger.warning("BackgroundState already initialized")
            return

        try:
            from codeweaver.config.settings import get_settings_map
            from codeweaver.common.registry.provider import ProviderRegistry

            settings_map = get_settings_map()

            # Health service initialization (if not already set)
            if not self.health_service:
                from codeweaver.server.health_service import HealthService
                self.health_service = HealthService(
                    provider_registry=self.provider_registry,
                    statistics=self.statistics,
                    indexer=self.indexer,
                    startup_time=self.startup_time,
                )

            # Failover manager initialization (if not already set)
            if not self.failover_manager:
                from codeweaver.providers.failover import VectorStoreFailoverManager
                self.failover_manager = VectorStoreFailoverManager(
                    registry=self.provider_registry,
                    settings_map=settings_map
                )

            # Initialize and start management server
            # (Always HTTP, independent of MCP transport)
            from codeweaver.server.background.management import ManagementServer

            self.management_server = ManagementServer(background_state=self)

            mgmt_host = settings_map.get("server", {}).get("management_host", "127.0.0.1")
            mgmt_port = settings_map.get("server", {}).get("management_port", 9329)

            await self.management_server.start(host=mgmt_host, port=mgmt_port)

            self.initialized = True
            logger.info("Background services initialized")

        except Exception as e:
            logger.error(f"Failed to initialize background services: {e}")
            raise

    async def start_background_indexing(self) -> None:
        """Start background indexing and file watching."""
        if not self.initialized or not self.indexer:
            raise RuntimeError("BackgroundState not initialized")

        # Create background task for indexing + watching
        task = asyncio.create_task(self._run_background_indexing())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

        logger.info("Background indexing started")

    async def _run_background_indexing(self) -> None:
        """Background task for indexing and file watching."""
        # Implementation delegated to existing _run_background_indexing function
        # from server.py (will be imported here)
        from codeweaver.server.server import _run_background_indexing

        await _run_background_indexing(
            state=self,
            settings=self.settings,
            status_display=...,  # Will need to pass this through
            verbose=False,
            debug=False,
        )

    async def shutdown(self) -> None:
        """Graceful shutdown of background services."""
        logger.info("Shutting down background services")
        self.shutdown_event.set()

        # Stop management server first
        if self.management_server:
            await self.management_server.stop()

        # Cancel all background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete (with timeout)
        if self.background_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.background_tasks, return_exceptions=True),
                    timeout=7.0
                )
            except asyncio.TimeoutError:
                logger.warning("Some background tasks did not stop within 7 seconds")

        logger.info("Background services shut down")


# Global state reference (same pattern as before)
_state: BackgroundState | None = None


def get_background_state() -> BackgroundState:
    """Get the current background state."""
    global _state
    if _state is None:
        raise RuntimeError(
            "BackgroundState has not been initialized yet. "
            "Ensure the server is properly set up before accessing the state."
        )
    return _state
```

### 1.2 Create Management Server

**File**: `src/codeweaver/server/background/management.py` (NEW)

```python
"""
Management HTTP server for observability and monitoring.

Runs independently of MCP transport choice (stdio or HTTP).
Provides health, stats, metrics, and settings endpoints.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route

from codeweaver.common.logging import get_logger

if TYPE_CHECKING:
    from codeweaver.server.background.state import BackgroundState

logger = get_logger(__name__)


class ManagementServer:
    """
    HTTP server for management endpoints.

    Always runs on HTTP (port 9329), independent of MCP transport.
    Provides observability endpoints for monitoring and debugging.

    Reuses existing endpoint handlers from app_bindings.py.
    """

    def __init__(self, background_state: BackgroundState):
        """
        Initialize management server.

        Args:
            background_state: BackgroundState instance for accessing services
        """
        self.background_state = background_state
        self.server: uvicorn.Server | None = None
        self.server_task: asyncio.Task | None = None

    def create_app(self) -> Starlette:
        """
        Create Starlette app with management routes.

        Routes are conditionally registered based on endpoint_settings
        (matching pattern from app_bindings.py).

        IMPORTANT: Reuses existing handlers from app_bindings.py.
        """
        from codeweaver.config.settings import get_settings_map
        from codeweaver.server.app_bindings import (
            health,
            stats_info,
            version_info,
            settings_info,
            state_info,
            favicon,
        )

        settings_map = get_settings_map()
        endpoint_settings = settings_map.get("endpoints", {})

        routes = [
            # Always register favicon (browsers always request it)
            Route("/favicon.ico", favicon, methods=["GET"], include_in_schema=False)
        ]

        # Conditional endpoints (matching app_bindings.py pattern)
        if endpoint_settings.get("enable_health", True):
            routes.append(Route("/health", health, methods=["GET"]))

        if endpoint_settings.get("enable_status", True):
            # Note: status endpoint needs to be created in app_bindings.py
            # For now, reuse health endpoint
            routes.append(Route("/status", health, methods=["GET"]))

        if endpoint_settings.get("enable_metrics", True):
            routes.append(Route("/metrics", stats_info, methods=["GET"]))

        if endpoint_settings.get("enable_version", True):
            routes.append(Route("/version", version_info, methods=["GET"]))

        if endpoint_settings.get("enable_settings", True):
            routes.append(Route("/settings", settings_info, methods=["GET"]))

        if endpoint_settings.get("enable_state", True):
            routes.append(Route("/state", state_info, methods=["GET"]))

        app = Starlette(routes=routes)

        # Attach background state to app for handlers to access
        # Handlers use request.app.state or get_state() global
        app.state.background = self.background_state

        return app

    async def start(self, host: str = "127.0.0.1", port: int = 9329):
        """
        Start management server.

        Args:
            host: Server host (default: 127.0.0.1)
            port: Server port (default: 9329)
        """
        logger.info(f"Starting management server on {host}:{port}")

        app = self.create_app()

        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",  # Quiet logs for management server
            access_log=False  # Use our own logging via @timed_http
        )

        self.server = uvicorn.Server(config)

        # Run in background task
        self.server_task = asyncio.create_task(self.server.serve())

        logger.info(f"Management server ready at http://{host}:{port}")

    async def stop(self):
        """Stop management server gracefully."""
        if self.server:
            logger.info("Stopping management server")
            self.server.should_exit = True

            if self.server_task:
                try:
                    await asyncio.wait_for(self.server_task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Management server did not stop within 5 seconds")

            logger.info("Management server stopped")
```

### 1.3 Update Lifespan Management

**File**: `src/codeweaver/server/lifespan.py` (NEW - extracted from server.py)

```python
"""
Starlette lifespan integration for background services.

Manages startup/shutdown of background services using Starlette's
AsyncExitStack pattern.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

from codeweaver.common.logging import get_logger
from codeweaver.server.background.state import BackgroundState

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.common.statistics import SessionStatistics

logger = get_logger(__name__)


@asynccontextmanager
async def combined_lifespan(
    app: FastMCP,
    settings: CodeWeaverSettings | None = None,
    statistics: SessionStatistics | None = None,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> AsyncIterator[None]:
    """
    Unified lifespan context manager for background services + MCP server.

    This replaces the old lifespan() function in server.py.
    Manages both background services and MCP server lifecycle.

    Args:
        app: FastMCP application instance
        settings: Configuration settings
        statistics: Session statistics instance
        verbose: Enable verbose logging
        debug: Enable debug logging
    """
    from codeweaver.cli.ui import StatusDisplay
    from codeweaver.config.settings import get_settings
    from codeweaver.common.utils import get_project_path
    from codeweaver.core.types.sentinel import Unset

    # Create StatusDisplay for clean user-facing output
    status_display = StatusDisplay()

    # Print clean header
    server_host = getattr(app, "host", "127.0.0.1") if hasattr(app, "host") else "127.0.0.1"
    server_port = getattr(app, "port", 9328) if hasattr(app, "port") else 9328
    status_display.print_header(host=server_host, port=server_port)

    if verbose or debug:
        logger.info("Entering combined lifespan context manager...")

    # Load settings if not provided
    if settings is None:
        settings = get_settings()
    if isinstance(settings.project_path, Unset):
        settings.project_path = get_project_path()

    # Initialize BackgroundState (formerly AppState)
    # This is the same initialization as before, just renamed
    from codeweaver.server.server import _initialize_app_state

    # _initialize_app_state returns BackgroundState now
    background_state = _initialize_app_state(app, settings, statistics)

    # Store in app.state for access via Context
    app.state.background = background_state

    indexing_task = None

    try:
        if verbose or debug:
            logger.info("Initializing background services...")

        # Initialize background services
        await background_state.initialize()

        # Start background indexing task
        from codeweaver.server.server import _run_background_indexing

        indexing_task = asyncio.create_task(
            _run_background_indexing(
                background_state, settings, status_display,
                verbose=verbose, debug=debug
            )
        )

        # Perform health checks and display results
        status_display.print_step("Health checks...")

        if background_state.health_service:
            health_response = await background_state.health_service.get_health_response()

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

        status_display.print_ready()

        if verbose or debug:
            logger.info("Lifespan start actions complete, server initialized.")

        background_state.initialized = True

        # Server runs here
        yield

    except Exception:
        background_state.initialized = False
        raise
    finally:
        # Cleanup
        from codeweaver.server.server import _cleanup_state

        await _cleanup_state(background_state, indexing_task, status_display, verbose=verbose or debug)
```

### 1.4 Update MCP Server Integration

**File**: `src/codeweaver/server/mcp_server.py` (UPDATE)

```python
"""
MCP server with background services integration.

Separates protocol layer (FastMCP) from background services layer.

Note: Observability endpoints (/health, /status, /metrics, etc.) are on
the management server (port 9329), not here. This keeps the MCP layer
focused on protocol and the ONE TOOL principle.
"""

from fastmcp import FastMCP, Context

from codeweaver.common.logging import get_logger
from codeweaver.server.lifespan import combined_lifespan
from codeweaver.middleware.statistics import StatisticsMiddleware

logger = get_logger(__name__)


# Create FastMCP app
mcp = FastMCP("CodeWeaver", version="0.1.0-alpha.2")


# Register FastMCP middleware (NOT Starlette middleware)
# StatisticsMiddleware already handles all telemetry correctly
mcp.add_middleware(StatisticsMiddleware())


@mcp.tool()
async def find_code(
    query: str,
    intent: str | None = None,
    *,
    token_limit: int = 30000,
    focus_languages: tuple[str, ...] | None = None,
    context: Context,  # FastMCP automatically injects this
) -> dict:
    """
    Search codebase using semantic similarity.

    This is the ONE TOOL exposed to agents (Constitutional Principle I).

    Args:
        query: Natural language query or code pattern
        intent: Optional intent for specialized search behavior
        token_limit: Maximum tokens in response (default: 30000)
        focus_languages: Optional language filter tuple
        context: MCP context (injected by FastMCP)

    Returns:
        FindCodeResponseSummary as dict with:
        - results: List[SearchResult] with file paths, line numbers, snippets
        - total: Total results found
        - took_ms: Query execution time
        - metadata: Search metadata (intent, filters, etc.)
    """
    # Import actual implementation from app_bindings.py
    # (app_bindings.find_code_tool uses get_state() global to access BackgroundState)
    from codeweaver.server.app_bindings import find_code_tool

    # Delegate to actual implementation
    result = await find_code_tool(
        query=query,
        intent=intent,
        token_limit=token_limit,
        focus_languages=focus_languages,
        context=context
    )

    # Return as dict (FindCodeResponseSummary.model_dump())
    return result.model_dump() if hasattr(result, 'model_dump') else result


# Set lifespan (FastMCP will call this)
mcp._lifespan = combined_lifespan


# Note: Observability endpoints are on the management server (port 9329):
#   - GET /health - Health check with indexing status
#   - GET /status - Indexing and failover status
#   - GET /metrics - Timing statistics and token metrics
#   - GET /version - Version information
#   - GET /settings - Configuration (redacted)
#   - GET /state - Internal state
```

**Key Changes**:
1. ❌ **Removed**: Starlette middleware for state passing
2. ✅ **Kept**: FastMCP `StatisticsMiddleware` for telemetry
3. ✅ **Added**: Context injection for accessing `BackgroundState`
4. ✅ **Simplified**: Direct delegation to `app_bindings.find_code_tool`

---

## Phase 2: Configuration Updates (Week 2)

### 2.1 Update ServerSettings (Not IndexerSettings)

**Rationale**: Background services are server lifecycle concerns, not indexer-specific.

**File**: `src/codeweaver/config/server.py` (UPDATE)

```python
"""
Server configuration (updated for background services architecture).
"""

from pathlib import Path
from typing import Annotated, Literal

from codeweaver.core.types.models import BasedModel, FROZEN_BASEDMODEL_CONFIG
from codeweaver.core.types.sentinel import UNSET, UnsetType


class ServerSettings(BasedModel):
    """
    MCP server settings.

    Includes MCP server, management server, and background service configuration.
    """

    model_config = FROZEN_BASEDMODEL_CONFIG

    # MCP Server (HTTP mode only)
    host: str = "127.0.0.1"
    """MCP server host (use 127.0.0.1 for localhost, 0.0.0.0 for public)."""

    port: int = 9328
    """MCP server port (avoid Qdrant ports 6333-6334)."""

    transport: Literal["streamable-http", "stdio"] = "streamable-http"
    """
    MCP transport protocol.

    - 'streamable-http': HTTP with SSE - recommended
    - 'stdio': Standard IO transport
    """

    # Management Server (Always HTTP)
    management_host: str = "127.0.0.1"
    """Management server host (independent of MCP transport)."""

    management_port: int = 9329
    """Management server port (always HTTP, for health/stats/metrics)."""

    # Background Services
    auto_index_on_startup: bool = True
    """Automatically start indexing on server startup."""

    file_watching_enabled: bool = True
    """Enable file watching for real-time updates."""

    health_check_interval_seconds: int = 30
    """Interval for health checks (seconds)."""

    statistics_enabled: bool = True
    """Enable statistics collection."""

    def _telemetry_keys(self) -> dict | None:
        """No sensitive fields."""
        return None
```

**File**: `config.toml` (UPDATE)

```toml
[server]
# MCP server (HTTP mode - port 9328)
host = "127.0.0.1"
port = 9328
transport = "streamable-http"

# Management server (always HTTP - port 9329)
# Available regardless of MCP transport (stdio or HTTP)
management_host = "127.0.0.1"
management_port = 9329

# Background services
auto_index_on_startup = true
file_watching_enabled = true
health_check_interval_seconds = 30
statistics_enabled = true
```

**Immutability Pattern**:

```python
# ✅ CORRECT: Immutable read-only access (95% of cases)
from codeweaver.config.settings import get_settings_map

settings_map = get_settings_map()  # Returns DictView[CodeWeaverSettingsDict]
auto_index = settings_map["server"]["auto_index_on_startup"]  # bool

# ⚠️ Only when need property/method access:
from codeweaver.config.settings import get_settings

settings = get_settings()  # Returns CodeWeaverSettings (BasedModel)
auto_index = settings.server.auto_index_on_startup  # Property access
```

---

## Phase 3: CLI Commands (Week 2)

### 3.1 Background Services Management

**File**: `src/codeweaver/cli/commands/services.py` (NEW)

```python
"""
Background services management commands.

Manages CodeWeaver's background services (indexing, file watching, telemetry).
"""

from pathlib import Path
from typing import Annotated

import asyncio
import cyclopts
from rich.console import Console

from codeweaver.common.logging import get_logger
from codeweaver.config.settings import get_settings_map

logger = get_logger(__name__)
console = Console()


async def is_services_running() -> bool:
    """Check if background services are running via management server."""
    import httpx

    settings_map = get_settings_map()
    mgmt_host = settings_map.get("server", {}).get("management_host", "127.0.0.1")
    mgmt_port = settings_map.get("server", {}).get("management_port", 9329)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://{mgmt_host}:{mgmt_port}/health",
                timeout=2.0
            )
            return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


async def start_background_services() -> None:
    """Start background services (indexer, watcher, health, management server)."""
    from codeweaver.server.background.state import BackgroundState

    # Initialize state (same pattern as server startup)
    background_state = BackgroundState(...)  # Initialize with proper params

    await background_state.initialize()
    await background_state.start_background_indexing()

    # Keep services running (until interrupted)
    try:
        await background_state.shutdown_event.wait()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down background services...[/yellow]")
    finally:
        await background_state.shutdown()


async def stop_background_services() -> None:
    """Stop background services gracefully."""
    import signal
    import os

    # Use signal-based shutdown (more secure than HTTP endpoint)
    os.kill(os.getpid(), signal.SIGTERM)


@cyclopts.command
def start(
    config: Annotated[
        Path | None,
        cyclopts.Parameter(help="Path to CodeWeaver configuration file")
    ] = None,
    project: Annotated[
        Path | None,
        cyclopts.Parameter(help="Path to project directory")
    ] = None,
) -> None:
    """
    Start CodeWeaver background services.

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
    if asyncio.run(is_services_running()):
        console.print("[yellow]Background services already running[/yellow]")
        console.print("[dim]Management server: http://127.0.0.1:9329[/dim]")
        return

    console.print("[green]Starting CodeWeaver background services...[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")

    asyncio.run(start_background_services())


@cyclopts.command
def stop() -> None:
    """
    Stop CodeWeaver background services.

    Gracefully shuts down all background services using SIGTERM.
    """
    if not asyncio.run(is_services_running()):
        console.print("[yellow]Background services not running[/yellow]")
        return

    console.print("[yellow]Stopping background services...[/yellow]")
    asyncio.run(stop_background_services())
```

### 3.2 Update Server Command

**File**: `src/codeweaver/cli/commands/server.py` (UPDATE)

```python
"""
MCP server commands (updated for background services architecture).
"""

from pathlib import Path
from typing import Annotated, Literal

import asyncio
import sys
import cyclopts
from rich.console import Console

from codeweaver.common.logging import get_logger
from codeweaver.config.settings import get_settings_map

logger = get_logger(__name__)
console = Console()


@cyclopts.command
def server(
    transport: Annotated[
        Literal["streamable-http", "stdio"],
        cyclopts.Parameter(help="MCP transport protocol")
    ] = "streamable-http",
    host: Annotated[
        str | None,
        cyclopts.Parameter(help="Server host (HTTP only)")
    ] = None,
    port: Annotated[
        int | None,
        cyclopts.Parameter(help="Server port (HTTP only)")
    ] = None,
    no_auto_start: Annotated[
        bool,
        cyclopts.Parameter(help="Don't auto-start background services")
    ] = False,
) -> None:
    """
    Start CodeWeaver MCP server.

    Automatically starts background services if not already running
    (disable with --no-auto-start).

    Transport modes:
    - streamable-http (default): HTTP-based transport
    - stdio: Standard I/O transport (launched per-session by MCP clients)

    Background services (indexing, file watching, telemetry) will auto-start
    unless already running or --no-auto-start is specified.
    """
    settings_map = get_settings_map()

    # Check and potentially start background services
    if not no_auto_start:
        from codeweaver.cli.commands.services import is_services_running, start_background_services

        if not asyncio.run(is_services_running()):
            console.print("[dim]Background services not running, starting...[/dim]")

            # Start services in background thread
            import threading
            services_thread = threading.Thread(
                target=lambda: asyncio.run(start_background_services()),
                daemon=True
            )
            services_thread.start()

            # Wait for initialization
            import time
            time.sleep(2)
            console.print("[green]✓[/green] Background services started")
        else:
            console.print("[dim]Background services already running[/dim]")

    # Start MCP server
    if transport == "streamable-http":
        final_host = host or settings_map["server"]["host"]
        final_port = port or settings_map["server"]["port"]

        console.print(f"[green]Starting MCP server on {final_host}:{final_port}[/green]")
        console.print(f"[dim]Management server: http://127.0.0.1:9329[/dim]")

        from codeweaver.server.mcp_server import mcp

        mcp.run(
            transport="sse",  # FastMCP >= 2.13.1 uses "sse" for streamable-http
            host=final_host,
            port=final_port
        )

    elif transport == "stdio":
        console.print("[green]Starting MCP stdio server[/green]", file=sys.stderr)
        console.print("[dim]Background services auto-started[/dim]", file=sys.stderr)

        from codeweaver.server.mcp_server import mcp

        mcp.run(transport="stdio")

    else:
        console.print(f"[red]Unknown transport: {transport}[/red]", err=True)
        raise SystemExit(1)
```

---

## Phase 4: Testing & Validation (Week 3)

### 4.1 Background Services Tests

**File**: `tests/integration/test_background_services.py`

```python
"""
Integration tests for background services architecture.
"""

import pytest
import asyncio

from codeweaver.server.background.state import BackgroundState


@pytest.mark.asyncio
async def test_background_state_lifecycle():
    """Test background state initialization and shutdown."""
    # Initialize state (formerly AppState)
    state = BackgroundState(...)  # Proper initialization

    assert not state.initialized

    # Initialize services
    await state.initialize()
    assert state.initialized
    assert state.indexer is not None
    assert state.statistics is not None
    assert state.management_server is not None

    # Start background indexing
    await state.start_background_indexing()
    assert len(state.background_tasks) > 0

    # Shutdown
    await state.shutdown()
    assert all(task.done() for task in state.background_tasks)


@pytest.mark.asyncio
async def test_find_code_via_mcp_context():
    """Test find_code tool accesses state via Context injection."""
    from codeweaver.server.mcp_server import mcp
    from fastmcp.testing import get_session_for_test

    async with get_session_for_test(mcp) as session:
        # Call find_code tool
        result = await session.call_tool(
            "find_code",
            arguments={
                "query": "semantic search implementation",
                "token_limit": 10000
            }
        )

        # Should return FindCodeResponseSummary structure
        assert "results" in result
        assert "total" in result
        assert "took_ms" in result


@pytest.mark.asyncio
async def test_statistics_middleware_telemetry():
    """Verify StatisticsMiddleware captures telemetry correctly."""
    from codeweaver.middleware.statistics import StatisticsMiddleware
    from codeweaver.common.statistics import SessionStatistics

    stats = SessionStatistics()
    middleware = StatisticsMiddleware(statistics=stats)

    # Verify middleware is FastMCP middleware (not Starlette)
    from fastmcp.server.middleware.middleware import Middleware
    assert isinstance(middleware, Middleware)

    # Telemetry tracking verified
    assert stats.total_requests == 0

    # After tool call (simulated)
    # stats.total_requests should increment
    # Duration should be tracked


@pytest.mark.asyncio
async def test_management_server_independence():
    """Verify management server works in stdio mode."""
    import httpx

    # Start background services
    state = BackgroundState(...)
    await state.initialize()

    # Management server should be accessible even in stdio mode
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:9329/health")
        assert response.status_code == 200

    await state.shutdown()


@pytest.mark.asyncio
async def test_no_reindex_tool_exposed():
    """Verify reindex is NOT exposed as MCP tool (Constitutional compliance)."""
    from codeweaver.server.mcp_server import mcp

    # Get all registered tools
    tools = [tool.name for tool in mcp.list_tools()]

    # Should only have find_code
    assert "find_code" in tools
    assert "reindex" not in tools
    assert "get_index_status" not in tools

    # ONE TOOL principle
    assert len([t for t in tools if t.startswith("find_")]) == 1
```

---

## Phase 5: Documentation (Week 4)

### 5.1 Architecture Documentation

**File**: `docs/architecture/background-services.md`

```markdown
# Background Services Architecture

## Overview

CodeWeaver separates concerns between:
- **Protocol Layer**: FastMCP handles MCP protocol (HTTP or stdio)
- **Background Services Layer**: Indexing, file watching, health monitoring
- **Provider Layer**: Vector stores, embedders, indexers (via ProviderRegistry)

## Key Architecture Changes

### State Management

**Before (alpha.1)**:
- Single `AppState` class managed everything
- Tightly coupled to MCP server lifecycle

**After (alpha.2)**:
- `BackgroundState` (renamed from `AppState`) manages background services
- Lightweight MCP server accesses `BackgroundState` via Context injection
- Clear separation: protocol ≠ business logic

### Middleware Architecture

**FastMCP Middleware** (Used):
- `StatisticsMiddleware`: Captures ALL MCP operation telemetry
- Works in both stdio and HTTP transports
- Hooks: `on_call_tool`, `on_read_resource`, `on_get_prompt`, etc.

**Starlette Middleware** (NOT Used for MCP concerns):
- Only relevant for HTTP-level concerns (CORS, compression, etc.)
- Does NOT see MCP protocol operations in stdio mode
- NOT used for state passing or telemetry

### Information Flow

```
┌──────────────────────────────────────────────────┐
│  find_code Tool                                  │
│  - Receives query from agent                     │
│  - Accesses BackgroundState via global getter    │
└──────────────────┬───────────────────────────────┘
                   │ get_background_state() (global function)
┌──────────────────▼───────────────────────────────┐
│  BackgroundState                                 │
│  - Indexer (search engine)                       │
│  - ProviderRegistry (services)                   │
│  - HealthService (monitoring)                    │
│  - SessionStatistics (telemetry sink)            │
│  - FailoverManager (resilience)                  │
└──────────────────┬───────────────────────────────┘
                   │ Uses providers
┌──────────────────▼───────────────────────────────┐
│  Provider Layer                                  │
│  - VectorStore (Qdrant)                          │
│  - Embedder (Voyage AI)                          │
│  - Sparse Embedder (SPLADE)                      │
│  - Reranker                                      │
└──────────────────────────────────────────────────┘

Telemetry Flow (parallel):
┌──────────────────────────────────────────────────┐
│  StatisticsMiddleware.on_call_tool()             │
│  - Wraps ALL tool calls                          │
│  - Captures timing, success/failure, metadata    │
│  - Updates SessionStatistics                     │
└──────────────────────────────────────────────────┘
```

### Management Server

**Port 9329** (Always HTTP):
- Independent of MCP transport choice
- Endpoints: `/health`, `/metrics`, `/version`, `/settings`, `/state`
- Reuses handlers from `app_bindings.py`
- Accessible in both stdio and HTTP MCP modes

**Port 9328** (MCP Server, HTTP mode only):
- MCP protocol endpoint
- ONE TOOL: `find_code`
- No custom HTTP endpoints

## Constitutional Compliance

**ONE TOOL for agents**: `find_code()`

Reindexing and status operations are **intentionally not exposed** as MCP tools.
These are CLI-only operations (via `cw index` commands) to prevent agents from
triggering expensive reindex operations.

Rationale: "We kind of intentionally made it hard to order a reindex... It's like
the hard reset on an iPhone -- you only need to know how to do it when you really need it."

## Migration from alpha.1

### Code Changes

```python
# BEFORE (alpha.1)
from codeweaver.server.server import get_state

state = get_state()  # Returns AppState
indexer = state.indexer

# AFTER (alpha.2)
from codeweaver.server.background.state import get_background_state

# Use global getter (same pattern, just renamed)
background_state = get_background_state()  # Returns BackgroundState
indexer = background_state.indexer

# Note: DI framework planned for future will replace global getter pattern
```

### Configuration Changes

```toml
# BEFORE (alpha.1)
[server]
host = "127.0.0.1"
port = 9328

# AFTER (alpha.2)
[server]
# MCP server
host = "127.0.0.1"
port = 9328
transport = "streamable-http"

# Management server (NEW)
management_host = "127.0.0.1"
management_port = 9329

# Background services (NEW)
auto_index_on_startup = true
file_watching_enabled = true
```

### CLI Changes

```bash
# BEFORE (alpha.1)
codeweaver server start

# AFTER (alpha.2)
# Option 1: Start just MCP server (auto-starts services)
codeweaver server

# Option 2: Start services separately
codeweaver start  # Start background services
codeweaver server --no-auto-start  # Start MCP server without auto-start

# Option 3: Check status
codeweaver status  # Shows services + index
codeweaver status --services  # Shows just services
codeweaver status --index  # Shows just index
```

## Deployment Models

### Development (Single Process)
```bash
codeweaver server start
```

### Production (Docker)
```yaml
services:
  codeweaver:
    image: codeweaver:latest
    ports:
      - "9328:9328"  # MCP server
      - "9329:9329"  # Management server
    environment:
      - CODEWEAVER_PROJECT_PATH=/workspace
```

### Production (Systemd - Linux)
```ini
[Unit]
Description=CodeWeaver MCP Server
After=network.target

[Service]
Type=simple
ExecStart=/opt/codeweaver/.venv/bin/codeweaver server
Restart=always

[Install]
WantedBy=multi-user.target
```
```

---

## Migration Checklist (Revised)

### Development Tasks

**Phase 1: State Management**
- [ ] Rename `AppState` → `BackgroundState` in `server/server.py`
- [ ] Move to `src/codeweaver/server/background/state.py`
- [ ] Add `management_server`, `background_tasks`, `shutdown_event` fields
- [ ] Update all imports (`get_state` → `get_background_state`)
- [ ] Add `initialize()` and `shutdown()` methods

**Phase 2: Management Server**
- [ ] Create `ManagementServer` class in `server/background/management.py`
- [ ] Reuse existing endpoint handlers from `app_bindings.py`
- [ ] Test endpoints with background state access

**Phase 3: Lifespan**
- [ ] Create `combined_lifespan()` in `server/lifespan.py`
- [ ] Initialize `BackgroundState`
- [ ] Start background indexing
- [ ] Start management server
- [ ] Attach to `app.state.background`

**Phase 4: MCP Server**
- [ ] Update `mcp_server.py` to use `combined_lifespan`
- [ ] Update `find_code` to access state via Context injection
- [ ] Remove any Starlette middleware for state passing
- [ ] Keep FastMCP `StatisticsMiddleware` for telemetry

**Phase 5: Configuration**
- [ ] Update `ServerSettings` with management ports and background flags
- [ ] Update `config.toml` schema
- [ ] Test immutability patterns with `get_settings_map()`

**Phase 6: CLI**
- [ ] Implement `cw start` command
- [ ] Implement `cw stop` command (signal-based)
- [ ] Update `cw server` (auto-start services)
- [ ] Update `cw status` (services + index)
- [ ] Register commands in `cli/main.py`

### Testing Tasks

- [ ] Test background services lifecycle
- [ ] Test Context injection in `find_code`
- [ ] Verify `StatisticsMiddleware` telemetry capture
- [ ] Test management server in stdio mode
- [ ] Test auto-start behavior
- [ ] Test graceful shutdown
- [ ] Verify ONE TOOL principle (only find_code)
- [ ] Test health endpoints
- [ ] Cross-platform tests (Linux, macOS, Windows, WSL)

### Documentation Tasks

- [ ] Update README with new architecture
- [ ] Document middleware patterns (FastMCP vs Starlette)
- [ ] Document Context injection pattern
- [ ] Document management server separation
- [ ] Document CLI commands
- [ ] Create migration guide from alpha.1

---

## Risk Mitigation

### Middleware Misunderstanding (CRITICAL)

**Risk**: Using Starlette middleware for MCP concerns won't work in stdio mode

**Mitigation**:
- ✅ Use FastMCP middleware (`StatisticsMiddleware`) for telemetry
- ✅ Use Context injection for state access
- ✅ Document difference clearly
- ✅ Integration tests verify both transports

### State Access Pattern

**Risk**: Developers might not know how to access `BackgroundState`

**Mitigation**:
- ✅ Document Context injection pattern clearly
- ✅ Provide examples in docstrings
- ✅ Create helper functions if needed
- ✅ Migration guide shows before/after patterns

### Port Conflicts

**Risk**: Port 9329 conflicts with other services

**Mitigation**:
- ✅ Configurable via `management_port` setting
- ✅ Default 9329 unlikely to conflict
- ✅ Document port usage clearly
- ✅ Startup error handling for port conflicts

---

## Success Metrics

### Functional Requirements

- [ ] **Constitutional Compliance**: ONE TOOL (`find_code`) exposed to agents
- [ ] **Pattern Fidelity**: Uses BasedModel, get_settings_map(), ProviderRegistry
- [ ] **Cross-Platform**: Works on Linux, macOS, Windows, WSL
- [ ] **Lifecycle Management**: Graceful startup/shutdown via Starlette lifespan
- [ ] **Middleware Correctness**: FastMCP middleware for MCP, not Starlette
- [ ] **Context Injection**: State access via Context parameter
- [ ] **Management Server**: Independent HTTP server on port 9329

### Quality Requirements

- [ ] All tests pass on all platforms
- [ ] No regressions from alpha.1
- [ ] Telemetry via `StatisticsMiddleware` works correctly
- [ ] Health checks operational
- [ ] Documentation complete and accurate

### Performance Requirements

- [ ] Startup time: < 30s for initial indexing
- [ ] File watching: Real-time updates (< 2s latency)
- [ ] Memory usage: < 500MB for medium projects (50k LOC)
- [ ] Query latency: < 100ms p50, < 500ms p95

---

## Timeline

**Week 1**: State Management & Lifespan
- Days 1-2: Rename AppState → BackgroundState, add new fields
- Days 3-4: Create ManagementServer, update lifespan
- Day 5: Integration testing

**Week 2**: Configuration & CLI
- Days 1-2: Update ServerSettings, test immutability
- Days 3-4: CLI commands (start, stop, server, status)
- Day 5: End-to-end CLI testing

**Week 3**: Testing & Polish
- Days 1-2: Integration tests for all scenarios
- Days 3-5: Cross-platform testing, performance benchmarks

**Week 4**: Documentation & Release
- Days 1-2: Architecture documentation, migration guide
- Days 3-4: User documentation, examples
- Day 5: Alpha.2 release

---

## Conclusion

This implementation plan:

1. **Repurposes existing AppState** as BackgroundState (minimal disruption)
2. **Uses FastMCP middleware correctly** for telemetry (not Starlette)
3. **Separates management server** (port 9329) from MCP server (port 9328)
4. **Maintains Constitutional compliance** (ONE TOOL principle)
5. **Provides clear migration path** from alpha.1

**Critical Success Factors**:
- Understanding FastMCP middleware vs Starlette middleware
- Using Context injection for state access
- Repurposing AppState rather than creating new class
- Testing both stdio and HTTP transports thoroughly
