<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Option A: Service Architecture - Implementation Plan (REVISED)

> **Revision Notes**: This plan has been updated to align with CodeWeaver's established patterns, idioms, and architectural principles. All discrepancies from the original plan have been addressed.

> **Latest Update**: Document revised to reflect CLI UX improvements and management server separation:
> - **CLI Commands**: New `cw start` / `cw stop` for background services management
> - **Server Auto-Start**: `cw server` now auto-starts background services if not running
> - **Enhanced Status**: `cw status` provides comprehensive system status with filtering options
> - **Management Server (Port 9329)**: All observability endpoints (/health, /status, /metrics, etc.) are now on a separate management server running on port 9329, independent of MCP transport choice
> - **MCP Server (Port 9328)**: Focused solely on MCP protocol and the ONE TOOL (find_code), with no custom HTTP endpoints
> - **ServerSettings**: Added `management_host` and `management_port` fields to support management server configuration
> - **Architecture**: Clarified that management server is always HTTP and available regardless of whether MCP uses stdio or HTTP transport
> - This separation keeps the MCP layer clean and focused on protocol, while observability remains accessible for monitoring

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
│  │  - Routes to background services via Context       │ │
│  │  - No observability endpoints here                 │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Management Server (Always HTTP - Port 9329)       │ │
│  │  - Independent of MCP transport choice             │ │
│  │  - /health, /status, /metrics, /version            │ │
│  │  - /settings, /state                               │ │
│  │  - Available for stdio and HTTP MCP modes          │ │
│  │  - Runs via separate uvicorn instance              │ │
│  │  - Started automatically with background services  │ │
│  └────────────────────────────────────────────────────┘ │
│         ↓ Both access BackgroundState                   │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Background Services Layer                         │ │
│  │  - BackgroundState (lifecycle manager)             │ │
│  │  - IndexerService (file watching + indexing)       │ │
│  │  - HealthService (monitoring)                      │ │
│  │  - Statistics (telemetry)                          │ │
│  │  - Managed via Starlette lifespan                  │ │
│  └────────────────────────────────────────────────────┘ │
│         ↓ Providers                                     │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Provider Layer (ProviderRegistry)                 │ │
│  │  - Indexer (core indexing engine)                  │ │
│  │  - VectorStore (Qdrant)                            │ │
│  │  - Embedder (OpenAI/local)                         │ │
│  │  - FailoverManager (resilience)                    │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
         ↑ MCP Protocol (HTTP:9328 or stdio)
┌────────┴────────────┐
│  MCP Clients        │
│  - Claude Desktop   │   Monitoring: http://127.0.0.1:9329
│  - Cursor           │   (health, status, metrics)
│  - Continue         │
└─────────────────────┘
```

**Key Principles**:
1. **Constitutional Compliance**: ONE TOOL (`find_code`) exposed to agents
2. **Pattern Reuse**: Leverage existing AppState infrastructure
3. **Same-Process First**: Clear boundaries, evolve to separate-process if needed
4. **Cross-Platform**: HTTP-first, Unix socket optional on Unix-like systems
5. **Immutability**: Frozen models, get_settings_map() for read-only access
6. **Transport Independence**: Management endpoints always available (stdio or HTTP)

---

## Phase 1: Background Services Extraction (Week 1-2)

### 1.1 Create Background Services Module

**File**: `src/codeweaver/server/background/__init__.py`

```python
"""
Background services module.

Separates long-running background tasks (indexing, file watching) from
MCP protocol layer.
"""
```

**File**: `src/codeweaver/server/background/management.py`

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
from starlette.responses import JSONResponse
from starlette.routing import Route

from codeweaver.common.logging import get_logger
from codeweaver.common.statistics import timed_http

if TYPE_CHECKING:
    from codeweaver.server.background.state import BackgroundState

logger = get_logger(__name__)


class ManagementServer:
    """
    HTTP server for management endpoints.
    
    Always runs on HTTP (port 9329), independent of MCP transport.
    Provides observability endpoints for monitoring and debugging.
    
    Endpoints mirror existing app_bindings.py custom_route patterns:
    - /health - Health check with indexing status
    - /status - Indexing and failover status
    - /metrics - Timing statistics and token metrics
    - /version - Version information
    - /settings - Configuration (redacts sensitive fields)
    - /state - Internal state (if enabled)
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

    async def health(self, request):
        """
        Health check endpoint.
        
        Matches existing /health endpoint from app_bindings.py.
        """
        from codeweaver.server.app_bindings import health
        
        # health() expects app.state with our BackgroundState
        request.app.state.background = self.background_state
        return await health(request)

    async def status_info(self, request):
        """
        Indexing and failover status endpoint.
        
        Matches existing /status endpoint from app_bindings.py.
        """
        from codeweaver.server.app_bindings import status_info
        
        request.app.state.background = self.background_state
        return await status_info(request)

    async def stats_info(self, request):
        """
        Statistics and metrics endpoint.
        
        Matches existing /metrics endpoint from app_bindings.py.
        """
        from codeweaver.server.app_bindings import stats_info
        
        return await stats_info(request)

    async def version_info(self, request):
        """
        Version information endpoint.
        
        Matches existing /version endpoint from app_bindings.py.
        """
        from codeweaver.server.app_bindings import version_info
        
        return await version_info(request)

    async def settings_info(self, request):
        """
        Settings endpoint (redacts sensitive fields).
        
        Matches existing /settings endpoint from app_bindings.py.
        """
        from codeweaver.server.app_bindings import settings_info
        
        return await settings_info(request)

    async def state_info(self, request):
        """
        Internal state endpoint.
        
        Matches existing /state endpoint from app_bindings.py.
        """
        from codeweaver.server.app_bindings import state_info
        
        request.app.state.background = self.background_state
        return await state_info(request)

    async def favicon(self, request):
        """
        Favicon endpoint.
        
        Matches existing /favicon.ico endpoint from app_bindings.py.
        """
        from codeweaver.server.app_bindings import favicon
        
        return await favicon(request)

    def create_app(self) -> Starlette:
        """
        Create Starlette app with management routes.
        
        Routes are conditionally registered based on endpoint_settings
        (matching pattern from app_bindings.py).
        """
        from codeweaver.config.settings import get_settings_map
        
        settings_map = get_settings_map()
        endpoint_settings = settings_map.get("endpoints", {})

        routes = [
            # Always register favicon (browsers always request it)
            Route("/favicon.ico", self.favicon, methods=["GET"], include_in_schema=False)
        ]

        # Conditional endpoints (matching app_bindings.py pattern)
        if endpoint_settings.get("enable_health", True):
            routes.append(Route("/health", self.health, methods=["GET"]))

        if endpoint_settings.get("enable_status", True):
            routes.append(Route("/status", self.status_info, methods=["GET"]))

        if endpoint_settings.get("enable_metrics", True):
            routes.append(Route("/metrics", self.stats_info, methods=["GET"]))

        if endpoint_settings.get("enable_version", True):
            routes.append(Route("/version", self.version_info, methods=["GET"]))

        if endpoint_settings.get("enable_settings", True):
            routes.append(Route("/settings", self.settings_info, methods=["GET"]))

        if endpoint_settings.get("enable_state", True):
            routes.append(Route("/state", self.state_info, methods=["GET"]))

        return Starlette(routes=routes)

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

**File**: `src/codeweaver/server/background/state.py`

```python
"""
Background services state management.

Extracted from AppState pattern - manages lifecycle of background services
independent of protocol layer.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from pydantic import Field
from pydantic.dataclasses import dataclass

from codeweaver.core.types.models import BasedModel, DataclassSerializationMixin
from codeweaver.common.logging import get_logger

if TYPE_CHECKING:
    from codeweaver.engine.indexer.indexer import Indexer
    from codeweaver.engine.watcher.watcher import FileWatcher
    from codeweaver.common.health import HealthService
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.providers.failover import VectorStoreFailoverManager

logger = get_logger(__name__)


@dataclass
class BackgroundState(DataclassSerializationMixin):
    """
    Background services state.

    Manages lifecycle of long-running background tasks independent of
    MCP protocol concerns. Based on AppState pattern but protocol-agnostic.
    """

    initialized: Annotated[bool, Field(description="""Status of the background services.""")] = False
    indexer: Annotated[Indexer | None, Field(description="""The Indexer singleton""")] = None
    watcher: Annotated[FileWatcher | None, description="""The FileWatcher instance"""] = None
    health_service: Annotated[HealthService | None, Field(description="""The global HealthService instance""")] = None
    failover_manager: Annotated[VectorStoreFailoverManager | None, Field(description="""The fallback handling service""")] = None
    statistics: Annotated[SessionStatistics | None, Field(description="""The global SessionStatistic instance for metrics tracking.""")] = None
    management_server: ManagementServer | None = None
    background_tasks: set[asyncio.Task] = field(default_factory=set)
    shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)
    startup_time: float = field(default_factory=lambda: __import__('time').time())

    async def initialize(self) -> None:
        """Initialize background services."""
        if self.initialized:
            logger.warning("BackgroundState already initialized")
            return

        try:
            from codeweaver.config.settings import get_settings_map
            from codeweaver.common.registry.provider import ProviderRegistry
            from codeweaver.common.health import HealthService
            from codeweaver.common.statistics import SessionStatistics
            from codeweaver.providers.failover import VectorStoreFailoverManager
            from codeweaver.server.background.management import ManagementServer

            settings_map = get_settings_map()

            # Initialize statistics
            self.statistics = SessionStatistics()

            # Initialize provider registry (singleton)
            registry = ProviderRegistry.get_instance()

            # Initialize failover manager
            self.failover_manager = VectorStoreFailoverManager(
                registry=registry,
                settings_map=settings_map
            )

            # Initialize health service
            self.health_service = HealthService(
                registry=registry,
                failover_manager=self.failover_manager
            )

            # Initialize indexer (lazy-loaded via registry)
            from codeweaver.engine.indexer.indexer import Indexer
            self.indexer = await Indexer.from_settings_async()

            # Initialize and start management server
            # (Always HTTP, independent of MCP transport)
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
        try:
            # Prime the index (may take minutes on first run)
            await self.indexer.prime_index()

            # Start file watcher
            from codeweaver.engine.watcher.watcher import FileWatcher
            self.watcher = await FileWatcher.create(
                indexer=self.indexer,
                verbose=False
            )

            # Run watcher until shutdown
            await self.watcher.run()

        except asyncio.CancelledError:
            logger.info("Background indexing cancelled")
            raise
        except Exception as e:
            logger.error(f"Background indexing error: {e}")
            raise

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

        # Cleanup resources
        if self.watcher:
            # FileWatcher cleanup happens in its context managers
            pass

        if self.indexer:
            # Indexer cleanup happens in its context managers
            pass

        logger.info("Background services shut down")
```

**File**: `src/codeweaver/server/background/lifecycle.py`

```python
"""
Starlette lifespan integration for background services.

Manages startup/shutdown of background services using Starlette's
AsyncExitStack pattern.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from codeweaver.common.logging import get_logger
from codeweaver.server.background.state import BackgroundState

if TYPE_CHECKING:
    from starlette.applications import Starlette

logger = get_logger(__name__)


@asynccontextmanager
async def background_lifespan(app: Starlette):
    """
    Starlette lifespan context manager for background services.

    Pattern from fastmcp-deployment-research.md:
    - Startup: Initialize services, start background tasks
    - Yield: Server runs
    - Shutdown: Stop background tasks, cleanup resources
    """
    # Startup
    logger.info("Starting background services lifespan")

    background_state = BackgroundState()

    try:
        # Initialize services
        await background_state.initialize()

        # Start background indexing (non-blocking)
        await background_state.start_background_indexing()

        # Store state in app for access via middleware
        app.state.background = background_state

        logger.info("Background services ready")

        # Server runs here
        yield

    finally:
        # Shutdown
        logger.info("Stopping background services")
        await background_state.shutdown()
        logger.info("Background services stopped")


def wrap_mcp_lifespan(mcp_app, background_lifespan_func):
    """
    Wrap FastMCP lifespan with background services lifespan.

    Combines MCP protocol lifespan with background services lifespan
    using AsyncExitStack pattern.

    Pattern from fastmcp-deployment-research.md.
    """
    from contextlib import AsyncExitStack

    @asynccontextmanager
    async def combined_lifespan(app):
        async with AsyncExitStack() as stack:
            # Enter background services lifespan
            background_ctx = await stack.enter_async_context(
                background_lifespan_func(app)
            )

            # Enter MCP lifespan if exists
            if hasattr(mcp_app, '_lifespan_context'):
                mcp_ctx = await stack.enter_async_context(
                    mcp_app._lifespan_context(app)
                )

            # Both lifespans active
            yield

            # Exit happens automatically via AsyncExitStack

    return combined_lifespan
```

---

### 1.2 Update MCP Server Integration

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
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

from codeweaver.common.logging import get_logger
from codeweaver.server.background.lifecycle import (
    background_lifespan,
    wrap_mcp_lifespan
)

logger = get_logger(__name__)


# Create FastMCP app
mcp = FastMCP("CodeWeaver", version="0.1.0-alpha.2")


class BackgroundStateMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject background state into MCP Context.

    Pattern from fastmcp-deployment-research.md: Bridge app.state to Context.
    """

    async def dispatch(self, request, call_next):
        # Inject background state into request state
        # (FastMCP will make it available via Context parameter)
        request.state.background = request.app.state.background
        request.state.statistics = request.app.state.background.statistics

        response = await call_next(request)
        return response


# Register middleware
mcp.add_middleware(BackgroundStateMiddleware)


@mcp.tool()
async def find_code(
    query: str,
    intent: str | None = None,
    *,
    token_limit: int = 30000,
    focus_languages: tuple[str, ...] | None = None,
    context: Context | None = None,
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
    if not context:
        raise RuntimeError("Context not available")

    # Access background state via context
    background_state = context.request_context.app.state.background

    if not background_state.indexer:
        raise RuntimeError("Indexer not initialized")

    # Import actual implementation from app_bindings.py
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


# Wrap lifespans
mcp._lifespan = wrap_mcp_lifespan(mcp, background_lifespan)


# Note: Observability endpoints are on the management server (port 9329):
#   - GET /health - Health check with indexing status
#   - GET /status - Indexing and failover status
#   - GET /metrics - Timing statistics and token metrics
#   - GET /version - Version information
#   - GET /settings - Configuration (redacted)
#   - GET /state - Internal state
```

---

### 1.3 Update CLI Commands

CodeWeaver uses **cyclopts** (not click) for CLI. Add background services management commands.

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

    background_state = BackgroundState()
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
    """Stop background services via management server shutdown endpoint."""
    import httpx

    settings_map = get_settings_map()
    mgmt_host = settings_map.get("server", {}).get("management_host", "127.0.0.1")
    mgmt_port = settings_map.get("server", {}).get("management_port", 9329)

    try:
        async with httpx.AsyncClient() as client:
            # Trigger graceful shutdown via management API
            response = await client.post(
                f"http://{mgmt_host}:{mgmt_port}/shutdown",
                timeout=5.0
            )
            if response.status_code == 200:
                console.print("[green]✓[/green] Background services stopped")
            else:
                console.print(f"[red]Failed to stop services: {response.text}[/red]", err=True)
    except (httpx.ConnectError, httpx.TimeoutException):
        console.print("[red]Could not connect to management server[/red]", err=True)
        console.print("[dim]Services may not be running[/dim]")


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

    Gracefully shuts down all background services:
    - Indexer
    - FileWatcher
    - HealthService
    - Statistics
    - Management server

    Note: This will also affect any running MCP servers that depend on
    these services.
    """
    if not asyncio.run(is_services_running()):
        console.print("[yellow]Background services not running[/yellow]")
        return

    console.print("[yellow]Stopping background services...[/yellow]")
    asyncio.run(stop_background_services())
```

**File**: `src/codeweaver/cli/commands/server.py` (UPDATE)

```python
"""
MCP server commands (updated for background services architecture).

Uses cyclopts framework following CodeWeaver patterns.
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
    Start CodeWeaver MCP server.

    Automatically starts background services if not already running
    (disable with --no-auto-start).

    The MCP server acts as a transport layer connecting AI assistants
    to CodeWeaver's background services.

    Transport modes:
    - streamable-http (default): HTTP-based transport for persistent connections
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
            # Start services in background task (non-blocking)
            import threading
            services_thread = threading.Thread(
                target=lambda: asyncio.run(start_background_services()),
                daemon=True
            )
            services_thread.start()

            # Wait a moment for services to initialize
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

**File**: `src/codeweaver/cli/commands/status.py` (UPDATE)

```python
"""
Status command (updated for comprehensive system status).
"""

from typing import Annotated

import asyncio
import cyclopts
from rich.console import Console
from rich.table import Table

from codeweaver.common.logging import get_logger

logger = get_logger(__name__)
console = Console()


async def fetch_services_status() -> dict:
    """Fetch background services status from management server."""
    import httpx

    from codeweaver.config.settings import get_settings_map
    settings_map = get_settings_map()

    mgmt_host = settings_map.get("server", {}).get("management_host", "127.0.0.1")
    mgmt_port = settings_map.get("server", {}).get("management_port", 9329)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://{mgmt_host}:{mgmt_port}/status",
                timeout=5.0
            )
            return response.json() if response.status_code == 200 else {}
    except Exception as e:
        logger.debug(f"Failed to fetch services status: {e}")
        return {}


async def fetch_index_status() -> dict:
    """Fetch index status (current behavior)."""
    # Existing index status logic
    from codeweaver.engine.indexer.indexer import Indexer

    indexer = await Indexer.from_settings_async()
    # Return index statistics
    return {
        "indexed_files": indexer.stats.get("files_indexed", 0),
        "total_chunks": indexer.stats.get("chunks_total", 0),
        # ... other index stats
    }


@cyclopts.command
def status(
    services: Annotated[
        bool,
        cyclopts.Parameter(help="Show only background services status")
    ] = False,
    index: Annotated[
        bool,
        cyclopts.Parameter(help="Show only index status")
    ] = False,
    verbose: Annotated[
        bool,
        cyclopts.Parameter(help="Show detailed status information")
    ] = False,
    watch: Annotated[
        bool,
        cyclopts.Parameter(help="Continuously watch status")
    ] = False,
    watch_interval: Annotated[
        int,
        cyclopts.Parameter(help="Seconds between updates in watch mode")
    ] = 5,
) -> None:
    """
    Show CodeWeaver system status.

    Without flags: shows comprehensive status (services, index, health)
    --services: show only background services status
    --index: show only index status (current behavior)
    --watch: continuously monitor status (refresh every watch_interval seconds)
    """
    if services:
        # Services-only status
        services_status = asyncio.run(fetch_services_status())

        table = Table(title="Background Services Status")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")

        for service_name, service_info in services_status.items():
            status_icon = "✓" if service_info.get("running") else "✗"
            table.add_row(service_name, f"{status_icon} {service_info.get('status', 'unknown')}")

        console.print(table)

    elif index:
        # Index-only status (current behavior)
        index_status = asyncio.run(fetch_index_status())

        console.print("[bold]Index Status[/bold]")
        console.print(f"Files indexed: {index_status.get('indexed_files', 0)}")
        console.print(f"Total chunks: {index_status.get('total_chunks', 0)}")
        # ... other index stats

    else:
        # Comprehensive status (default)
        services_status = asyncio.run(fetch_services_status())
        index_status = asyncio.run(fetch_index_status())

        console.print("[bold]CodeWeaver System Status[/bold]\n")

        # Services section
        console.print("[bold cyan]Background Services[/bold cyan]")
        for service_name, service_info in services_status.items():
            status_icon = "✓" if service_info.get("running") else "✗"
            console.print(f"  {status_icon} {service_name}: {service_info.get('status', 'unknown')}")

        console.print()

        # Index section
        console.print("[bold cyan]Index[/bold cyan]")
        console.print(f"  Files indexed: {index_status.get('indexed_files', 0)}")
        console.print(f"  Total chunks: {index_status.get('total_chunks', 0)}")

        if verbose:
            # Additional verbose information
            console.print("\n[bold cyan]Health[/bold cyan]")
            # ... health metrics
```

**File**: `src/codeweaver/cli/main.py` (UPDATE)

Register new commands:

```python
from codeweaver.cli.commands import services

# Add to app
app.command(services.start)
app.command(services.stop)
```

---

## Phase 2: Configuration & Type System Updates (Week 2)

### 2.1 Extend IndexerSettings (Don't Create New Section)

CodeWeaver already has `IndexerSettings`. Extend it instead of creating new `service` section.

**File**: `src/codeweaver/config/indexer.py` (UPDATE)

```python
"""
Indexer configuration (updated for background services).
"""

from pathlib import Path
from typing import Annotated

from codeweaver.core.types.models import BasedModel, FROZEN_BASEDMODEL_CONFIG
from codeweaver.core.types.sentinel import UNSET, UnsetType


class BackgroundServicesSettings(BasedModel):
    """
    Background services configuration.

    Controls behavior of background indexing and file watching.
    """

    model_config = FROZEN_BASEDMODEL_CONFIG

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


class IndexerSettings(BasedModel):
    """
    Indexer settings (extended for background services).
    """

    model_config = FROZEN_BASEDMODEL_CONFIG

    # ... existing fields ...

    background: BackgroundServicesSettings = BackgroundServicesConfig()
    """Background services configuration."""

    def _telemetry_keys(self) -> dict | None:
        """No sensitive fields in indexer settings."""
        return None
```

**File**: `config.toml` (UPDATE)

```toml
[indexer.background]
# Background services configuration
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
auto_index = settings_map["indexer"]["background"]["auto_index_on_startup"]  # bool

# ⚠️ Only when need property/method access or mutation:
from codeweaver.config.settings import get_settings

settings = get_settings()  # Returns CodeWeaverSettings (BasedModel)
auto_index = settings.indexer.background.auto_index_on_startup  # Property access

# ❌ NEVER:
auto_index = settings.get("indexer.background.auto_index_on_startup")  # AttributeError!
```

---

### 2.2 Update Server Settings

**File**: `src/codeweaver/config/server.py` (UPDATE)

```python
"""
Server configuration (updated for cross-platform support).
"""

from pathlib import Path
from typing import Annotated

from codeweaver.core.types.models import BasedModel, FROZEN_BASEDMODEL_CONFIG
from codeweaver.core.types.sentinel import UNSET, UnsetType


class ServerSettings(BasedModel):
    """
    MCP server settings.

    Cross-platform: HTTP-first, Unix socket optional on Unix-like systems.
    """

    model_config = FROZEN_BASEDMODEL_CONFIG

    host: str = "127.0.0.1"
    """MCP server host (use 127.0.0.1 for localhost, 0.0.0.0 for public)."""

    port: int = 9328
    """MCP server port (avoid Qdrant ports 6333-6334)."""

    management_host: str = "127.0.0.1"
    """Management server host (independent of MCP transport)."""

    management_port: int = 9329
    """Management server port (always HTTP, for health/stats/metrics)."""

    unix_socket: Path | UnsetType = UNSET
    """
    Optional Unix socket path (Unix-like systems only).

    Example: /run/codeweaver/server.sock
    Falls back to HTTP if socket unavailable or on Windows.
    """

    transport: str = "streamable-http"
    """
    MCP transport protocol.

    - 'streamable-http': HTTPP (streamable-http) - recommended
    - 'stdio': Standard IO transport
    """

    def _telemetry_keys(self) -> dict | None:
        """No sensitive fields."""
        return None
```

**File**: `config.toml` (UPDATE)

```toml
[server]
# MCP server (HTTP mode only - port 9328)
host = "127.0.0.1"
port = 9328  # NOT 6334 (conflicts with Qdrant)
transport = "sse"

# Management server (always HTTP - port 9329)
# Available regardless of MCP transport (stdio or HTTP)
management_host = "127.0.0.1"
management_port = 9329

# Optional: Unix socket (Linux/macOS only)
# unix_socket = "/run/codeweaver/server.sock"
```

---

## Phase 3: Cross-Platform Support (Week 2-3)

### 3.1 HTTP-First Approach

**Strategy**: HTTP works everywhere. Unix sockets are optional optimization on Unix-like systems.

**File**: `src/codeweaver/server/transport.py` (NEW)

```python
"""
Cross-platform transport detection and selection.
"""

import platform
from pathlib import Path

from codeweaver.common.logging import get_logger

logger = get_logger(__name__)


def is_unix_socket_supported() -> bool:
    """Check if Unix sockets are supported on this platform."""
    return platform.system() in ("Linux", "Darwin")  # Linux, macOS


def select_optimal_transport(
    unix_socket_path: Path | None,
    fallback_to_http: bool = True
) -> tuple[str, str | Path]:
    """
    Select optimal transport for this platform.

    Args:
        unix_socket_path: Desired Unix socket path (or None)
        fallback_to_http: Fall back to HTTP if Unix socket unavailable

    Returns:
        Tuple of (transport_type, connection_path)
        - ("unix", Path) if Unix socket available
        - ("http", "http://host:port") if HTTP fallback

    Raises:
        RuntimeError: If Unix socket unavailable and HTTP fallback disabled
    """
    if unix_socket_path and is_unix_socket_supported():
        if unix_socket_path.exists():
            logger.info(f"Using Unix socket: {unix_socket_path}")
            return ("unix", unix_socket_path)
        else:
            logger.warning(f"Unix socket not found: {unix_socket_path}")

    if not is_unix_socket_supported() and unix_socket_path:
        logger.info(
            f"Unix sockets not supported on {platform.system()}, using HTTP"
        )

    if fallback_to_http:
        from codeweaver.config.settings import get_settings_map
        settings_map = get_settings_map()

        host = settings_map["server"]["host"]
        port = settings_map["server"]["port"]
        url = f"http://{host}:{port}"

        logger.info(f"Using HTTP transport: {url}")
        return ("http", url)

    raise RuntimeError(
        "Unix socket unavailable and HTTP fallback disabled"
    )
```

---

### 3.2 Deployment Configurations

#### Docker Compose (All Platforms)

**File**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  # Vector store
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  # CodeWeaver MCP server (includes background services)
  codeweaver:
    build: .
    command: codeweaver server start --transport http
    ports:
      - "9328:9328"  # MCP server
      - "9329:9329"  # Management server (health, stats, metrics)
    depends_on:
      qdrant:
        condition: service_healthy
    environment:
      - CODEWEAVER_PROJECT_PATH=/workspace
      - CODEWEAVER_VECTOR_STORE_URL=http://qdrant:6333
    volumes:
      - ./workspace:/workspace:ro
      - codeweaver_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9329/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

volumes:
  qdrant_data:
  codeweaver_data:
```

#### Systemd (Linux)

**File**: `deployment/systemd/codeweaver.service`

```ini
[Unit]
Description=CodeWeaver MCP Server
After=network.target

[Service]
Type=simple
User=codeweaver
WorkingDirectory=/opt/codeweaver
ExecStart=/opt/codeweaver/.venv/bin/codeweaver server start --transport http
Restart=always
RestartSec=10

# Environment
Environment="CODEWEAVER_PROJECT_PATH=/path/to/project"
Environment="CODEWEAVER_VECTOR_STORE_URL=http://localhost:6333"

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/codeweaver/data

[Install]
WantedBy=multi-user.target
```

#### Windows Service (Windows)

**File**: `deployment/windows/install-service.ps1`

```powershell
# Windows service installation script
# Uses NSSM (Non-Sucking Service Manager) for service management

$serviceName = "CodeWeaver"
$displayName = "CodeWeaver MCP Server"
$pythonExe = "C:\Program Files\Python311\python.exe"
$codeWeaverPath = "C:\codeweaver"
$appExe = "$codeWeaverPath\.venv\Scripts\codeweaver.exe"

# Install NSSM if not present
if (!(Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "Installing NSSM..."
    choco install nssm -y
}

# Install service
nssm install $serviceName $appExe "server" "start" "--transport" "http"
nssm set $serviceName AppDirectory $codeWeaverPath
nssm set $serviceName DisplayName $displayName
nssm set $serviceName Description "CodeWeaver semantic code search MCP server"

# Set environment variables
nssm set $serviceName AppEnvironmentExtra "CODEWEAVER_PROJECT_PATH=C:\Projects"

# Start service
nssm start $serviceName

Write-Host "CodeWeaver service installed and started"
```

---

## Phase 4: Testing & Validation (Week 3-4)

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
    state = BackgroundState()

    # Not initialized yet
    assert not state.initialized

    # Initialize
    await state.initialize()
    assert state.initialized
    assert state.indexer is not None
    assert state.statistics is not None

    # Start background indexing
    await state.start_background_indexing()

    # Should have background task
    assert len(state.background_tasks) > 0

    # Shutdown
    await state.shutdown()

    # Tasks should be cancelled
    assert all(task.done() for task in state.background_tasks)


@pytest.mark.asyncio
async def test_find_code_via_mcp():
    """Test find_code tool via MCP layer."""
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

### 4.2 Cross-Platform Tests

**File**: `tests/integration/test_cross_platform.py`

```python
"""
Cross-platform transport tests.
"""

import platform
import pytest

from codeweaver.server.transport import (
    is_unix_socket_supported,
    select_optimal_transport
)


def test_unix_socket_detection():
    """Test Unix socket support detection."""
    supported = is_unix_socket_supported()

    if platform.system() in ("Linux", "Darwin"):
        assert supported
    elif platform.system() == "Windows":
        assert not supported


@pytest.mark.asyncio
async def test_http_fallback_on_windows():
    """Test HTTP fallback when Unix socket unavailable."""
    from pathlib import Path

    transport_type, connection_path = select_optimal_transport(
        unix_socket_path=Path("/nonexistent/socket.sock"),
        fallback_to_http=True
    )

    # Should fall back to HTTP
    assert transport_type == "http"
    assert connection_path.startswith("http://")


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="Unix socket test requires Unix-like system"
)
@pytest.mark.asyncio
async def test_unix_socket_preferred():
    """Test Unix socket is preferred when available."""
    from pathlib import Path
    import tempfile

    # Create temp socket file
    with tempfile.NamedTemporaryFile(suffix=".sock") as tf:
        socket_path = Path(tf.name)

        transport_type, connection_path = select_optimal_transport(
            unix_socket_path=socket_path,
            fallback_to_http=True
        )

        # Should use Unix socket
        assert transport_type == "unix"
        assert connection_path == socket_path
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

## Key Principles

### Constitutional Compliance

**ONE TOOL for agents**: `find_code()`

Reindexing and status operations are **intentionally not exposed** as MCP tools.
These are CLI-only operations (via `cw index` commands) to prevent agents from
triggering expensive reindex operations.

Rationale: "We kind of intentionally made it hard to order a reindex... It's like
the hard reset on an iPhone -- you only need to know how to do it when you really need it."

### Pattern Reuse

Background services architecture extracts `BackgroundState` from the existing
`AppState` pattern in `app_bindings.py`. This reuses:
- ProviderRegistry singleton
- HealthService monitoring
- SessionStatistics telemetry
- VectorStoreFailoverManager resilience

### Immutability Philosophy

CodeWeaver is obsessive about immutability:
- `frozen=True` on most BasedModel subclasses
- `MappingProxyType` for read-only dicts
- `frozenset` instead of sets, `tuple` instead of lists
- Sentinel values (`UNSET`) instead of `None`

Settings access pattern:
```python
# ✅ Preferred (95% of cases): Immutable dict-like access
settings_map = get_settings_map()  # Returns DictView[CodeWeaverSettingsDict]
auto_index = settings_map["indexer"]

# ⚠️ Only when need property/method access or mutation
settings = get_settings()  # Returns CodeWeaverSettings (BasedModel)
auto_index = settings.indexer.background.auto_index_on_startup
```

## Architecture Diagram

```
┌─────────────────────────────────────────┐
│  MCP Protocol Layer (FastMCP)           │
│  - Port 9328 (HTTP mode)                │
│  - find_code() tool ONLY                │
│  - No HTTP endpoints (protocol only)    │
└──────────────┬──────────────────────────┘
               │ Context parameter
               │
┌──────────────▼──────────────────────────┐
│  Management Server (Separate Uvicorn)   │
│  - Port 9329 (always HTTP)              │
│  - /health, /status, /metrics           │
│  - /version, /settings, /state          │
│  - Independent of MCP transport         │
└──────────────┬──────────────────────────┘
               │ Both access BackgroundState
               │
┌──────────────▼──────────────────────────┐
│  Background Services Layer              │
│  - BackgroundState lifecycle            │
│  - Indexer (lazy-loaded)                │
│  - FileWatcher                          │
│  - HealthService                        │
│  - Statistics                           │
└──────────────┬──────────────────────────┘
               │ ProviderRegistry
┌──────────────▼──────────────────────────┐
│  Provider Layer                         │
│  - VectorStore (Qdrant)                 │
│  - Embedder (OpenAI/local)              │
│  - Indexer                              │
│  - FailoverManager                      │
└─────────────────────────────────────────┘
```

## Lifespan Management

Uses Starlette `@asynccontextmanager` pattern (NOT FastAPI `@on_event`):

```python
@asynccontextmanager
async def background_lifespan(app: Starlette):
    # Startup
    background_state = BackgroundState()
    await background_state.initialize()
    await background_state.start_background_indexing()
    app.state.background = background_state

    # Server runs
    yield

    # Shutdown
    await background_state.shutdown()
```

## Cross-Platform Support

**HTTP-first approach**: Works on all platforms
**Unix socket optimization**: Optional on Linux/macOS, not available on Windows

Platform detection:
```python
if platform.system() in ("Linux", "Darwin"):
    # Try Unix socket
    ...
else:
    # Use HTTP
    ...
```

## Deployment Models

### Development (Single Process)
```bash
codeweaver server start --transport stdio
# OR
codeweaver server start --transport http
```

### Production (Docker)
```bash
docker-compose up -d
```

### Production (Systemd - Linux)
```bash
sudo systemctl start codeweaver
```

### Production (Windows Service)
```powershell
.\deployment\windows\install-service.ps1
```

## Migration from Separate-Process Design

This implementation uses **same-process separation** with clear boundaries.
It can evolve to **separate-process** architecture if needed:

1. Extract BackgroundState to standalone service process
2. Add IPC layer (HTTP or gRPC) between processes
3. Update MCP server to be thin client to service
4. Maintain identical external API

Design allows both approaches without user-visible changes.
```

### 5.2 User Documentation

**File**: `README.md` (UPDATE)

```markdown
## Quick Start

### Start CodeWeaver

```bash
# Start background services (optional - auto-starts when needed)
codeweaver start

# Start MCP server (HTTP - auto-starts background services if needed)
codeweaver server

# Or with explicit transport
codeweaver server --transport streamable-http

# For stdio transport (launched per-session by MCP clients)
# No manual start needed - clients launch it automatically
```

### Configure MCP Client

**HTTP Transport (Recommended)**:
```json
{
  "mcpServers": {
    "codeweaver": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:9328/mcp"
    }
  }
}
```

**stdio Transport**:
```json
{
  "mcpServers": {
    "codeweaver": {
      "type": "stdio",
      "command": "codeweaver",
      "args": ["server", "--transport", "stdio"]
    }
  }
}
```

## Available Tools

CodeWeaver exposes **one tool** to agents:

### `find_code(query, intent?, token_limit?, focus_languages?)`

Search your codebase using semantic similarity.

**Parameters**:
- `query` (required): Natural language query or code pattern
- `intent` (optional): Search intent for specialized behavior
- `token_limit` (optional): Maximum tokens in response (default: 30000)
- `focus_languages` (optional): Filter by programming languages

**Returns**: Search results with file paths, line numbers, and code snippets

**Example**:
```javascript
// In Claude Desktop
"Find the authentication middleware implementation"

// Behind the scenes:
find_code({
  query: "authentication middleware implementation",
  token_limit: 30000
})
```

## CLI Commands

### Background Services

```bash
# Start background services (indexing, file watching, telemetry)
codeweaver start

# Stop background services
codeweaver stop

# Check if services are running
codeweaver status --services
```

### MCP Server

```bash
# Start MCP server (auto-starts background services if needed)
codeweaver server

# Start with specific transport
codeweaver server --transport streamable-http
codeweaver server --transport stdio

# Start without auto-starting services (advanced)
codeweaver server --no-auto-start
```

### Index Management

```bash
# Manual reindex (rare - usually automatic via background services)
codeweaver index

# Force full reindex
codeweaver index --force

# Clear index
codeweaver index --clear
```

### Status & Monitoring

```bash
# Comprehensive system status
codeweaver status

# Services-only status
codeweaver status --services

# Index-only status
codeweaver status --index

# Continuous monitoring
codeweaver status --watch
```

Note: Reindexing is **not exposed as an MCP tool** to prevent agents from
triggering expensive operations. Use CLI commands for manual index management.

## Configuration

**File**: `~/.config/codeweaver/config.toml`

```toml
[server]
host = "127.0.0.1"
port = 9328

[indexer.background]
auto_index_on_startup = true
file_watching_enabled = true
```

See [Configuration Guide](docs/configuration.md) for full options.

## Platform Support

- ✅ **Linux**: Full support (HTTP + optional Unix sockets)
- ✅ **macOS**: Full support (HTTP + optional Unix sockets)
- ✅ **Windows**: Full support (HTTP transport)
- ✅ **WSL**: Full support (HTTP + optional Unix sockets)
```

---

## Migration Checklist

### Development Tasks

- [ ] Create `server/background/` module structure
- [ ] Implement `BackgroundState` lifecycle manager
- [ ] Implement `ManagementServer` class with observability endpoints (port 9329)
- [ ] Add `/shutdown` endpoint to ManagementServer for graceful shutdown
- [ ] Implement `background_lifespan()` Starlette integration
- [ ] Update `mcp_server.py` with background services
- [ ] Remove custom HTTP endpoints from `mcp_server.py` (move to management server)
- [ ] Fix `find_code()` signature to match actual implementation
- [ ] Remove `reindex` and `get_index_status` tools (Constitutional compliance)
- [ ] Add `@timed_http` decorator to management server endpoints
- [ ] Extend `IndexerSettings` with `BackgroundServicesConfig`
- [ ] Update `ServerSettings` with management_host and management_port fields
- [ ] Implement `transport.py` for platform detection
- [ ] Create `cli/commands/services.py` with `start` and `stop` commands
- [ ] Update `cli/commands/server.py` with auto-start behavior and `--no-auto-start` flag
- [ ] Update `cli/commands/status.py` with `--services` and `--index` flags
- [ ] Register new commands in `cli/main.py`

### Testing Tasks

- [ ] Write background services lifecycle tests
- [ ] Write management server tests (port 9329)
- [ ] Write MCP integration tests
- [ ] Verify ONE TOOL principle (no reindex/status tools)
- [ ] Verify MCP server has no custom HTTP endpoints
- [ ] Test management server runs in stdio mode (independent of MCP transport)
- [ ] Write cross-platform transport tests
- [ ] Test Unix socket fallback on Windows
- [ ] Test immutability patterns (get_settings_map)
- [ ] Benchmark memory usage vs. separate processes
- [ ] Test health endpoints on management server
- [ ] Test statistics collection on management server

### Deployment Tasks

- [ ] Create Docker Compose configuration
- [ ] Create systemd service file (Linux)
- [ ] Create Windows service installation script
- [ ] Test deployment on Linux
- [ ] Test deployment on macOS
- [ ] Test deployment on Windows
- [ ] Test deployment on WSL

### Documentation Tasks

- [ ] Update README with new architecture and CLI commands
- [ ] Document background services architecture
- [ ] Document management server separation (port 9329)
- [ ] Document ONE TOOL principle and rationale
- [ ] Document cross-platform deployment
- [ ] Document immutability patterns
- [ ] Document observability endpoints on management server
- [ ] Document CLI command structure (`start`, `stop`, `server`, `status`)
- [ ] Document auto-start behavior of `server` command
- [ ] Clarify relationship between `index` command and background indexing
- [ ] Create migration guide from alpha.1
- [ ] Update MCP client configuration examples (stdio args changed)

---

## Timeline

**Week 1**: Background Services Foundation
- Days 1-2: BackgroundState and lifecycle management
- Days 3-4: MCP server integration
- Day 5: Initial testing

**Week 2**: Configuration & CLI
- Days 1-2: Update settings (IndexerSettings extension)
- Days 3-4: Update CLI commands (cyclopts)
- Day 5: Cross-platform transport implementation

**Week 3**: Deployment & Testing
- Days 1-2: Deployment configurations (Docker, systemd, Windows)
- Days 3-5: Comprehensive testing (integration, cross-platform)

**Week 4**: Documentation & Polish
- Days 1-2: Architecture and user documentation
- Days 3-4: Migration guide and examples
- Day 5: Final testing and alpha.2 release

---

## Success Metrics

### Functional Requirements

- [ ] **Constitutional Compliance**: ONE TOOL (`find_code`) exposed to agents
- [ ] **Pattern Fidelity**: Uses BasedModel, get_settings_map(), ProviderRegistry
- [ ] **Cross-Platform**: Works on Linux, macOS, Windows, WSL
- [ ] **Lifecycle Management**: Graceful startup/shutdown via Starlette lifespan
- [ ] **Immutability**: All config access via get_settings_map() (read-only)
- [ ] **Type Safety**: NewType + Annotated, _telemetry_keys() on BasedModels

### Quality Requirements

- [ ] All tests pass on all platforms
- [ ] No regressions from alpha.1
- [ ] Statistics integration (@timed_http on all endpoints)
- [ ] Health checks operational
- [ ] Documentation complete and accurate

### Performance Requirements

- [ ] Startup time: < 30s for initial indexing
- [ ] File watching: Real-time updates (< 2s latency)
- [ ] Memory usage: < 500MB for medium projects (50k LOC)
- [ ] Query latency: < 100ms p50, < 500ms p95

---

## Risk Mitigation

### Port Conflicts (CRITICAL)

**Risk**: Port 6334 conflicts with Qdrant (Qdrant uses 6333-6334)

**Mitigation**:
- ✅ Use port **9328** for MCP server (no conflicts)
- Document port configuration clearly
- Implement port conflict detection in startup

### Windows Support

**Risk**: Plan assumes Unix-specific features (Unix sockets, systemd)

**Mitigation**:
- ✅ HTTP-first approach works everywhere
- ✅ Platform detection with fallback
- ✅ Windows service installation script (NSSM)
- Test on Windows in CI/CD

### Constitutional Violation Risk

**Risk**: Accidentally expose reindex/status operations as tools

**Mitigation**:
- ✅ Explicit test verifying only `find_code` tool exists
- Code review checklist item
- Documentation emphasizing ONE TOOL principle

### Type System Mismatch

**Risk**: Using BaseModel instead of BasedModel breaks telemetry

**Mitigation**:
- ✅ All new models inherit from BasedModel
- ✅ Implement _telemetry_keys() (return None if no sensitive fields)
- Type checking in CI/CD

### Immutability Violations

**Risk**: Using get_settings() incorrectly, calling non-existent .get() method

**Mitigation**:
- ✅ Code examples show correct get_settings_map() pattern
- ✅ Documentation emphasizes 95% rule (use settings_map)
- Code review checklist item

---

## Future Evolution Path

This architecture supports evolution to separate-process deployment:

### Phase A (Alpha.2 - Current Plan)
**Same-process separation** with clear boundaries
- BackgroundState manages services in same process as FastMCP
- Clean interfaces between layers
- Users run single `codeweaver start` command

### Phase B (Alpha.3 - Optional Future)
**Separate-process deployment** for advanced users
- Extract BackgroundState to standalone service process
- Add IPC layer (HTTP or Unix socket)
- MCP server becomes thin client
- Users can run: `codeweaver service start` + `codeweaver server start`

### Migration Path (A → B)
1. BackgroundState already has clean interfaces
2. Add HTTP client/server for IPC
3. Move BackgroundState to separate entry point
4. Zero changes to MCP tool interface
5. Users opt-in to separate-process deployment

**Decision**: Start with Phase A (same-process). Evaluate Phase B based on:
- User demand for separate processes
- Resource usage patterns in production
- Kubernetes/container deployment needs

---

## Validation Checklist

Before considering this plan complete, verify:

**Constitutional & Architectural**:
- [ ] ONE TOOL principle maintained (`find_code` only)
- [ ] Uses FastMCP >= 2.13.1 (not FastAPI)
- [ ] Uses Starlette lifespan (not @on_event)
- [ ] Follows AppState → BackgroundState extraction pattern
- [ ] Uses ProviderRegistry singleton

**Type System**:
- [ ] All models inherit from BasedModel
- [ ] All models implement _telemetry_keys()
- [ ] Uses FROZEN_BASEDMODEL_CONFIG
- [ ] Uses NewType + Annotated for type safety

**Configuration**:
- [ ] Extends IndexerSettings (doesn't create new section)
- [ ] Uses get_settings_map() for read-only access (95% of cases)
- [ ] Never calls .get() on Pydantic models
- [ ] All config uses immutable types (tuple, frozenset, etc.)

**CLI**:
- [ ] Uses cyclopts (not click)
- [ ] Extends existing commands (cw server start)
- [ ] Recommends cw start / cw serve convenience commands

**Cross-Platform**:
- [ ] Port 9328 (NOT 6334 - Qdrant conflict)
- [ ] HTTP-first approach
- [ ] Unix socket optional on Unix-like systems
- [ ] Windows deployment strategy (NSSM)
- [ ] Platform detection with graceful fallback

**Statistics & Monitoring**:
- [ ] @timed_http on all HTTP endpoints
- [ ] SessionStatistics integration
- [ ] HealthService integration
- [ ] /health endpoint (HTTP only, not MCP tool)
- [ ] /stats endpoint (HTTP only, not MCP tool)

**Testing**:
- [ ] Tests verify only find_code tool exists
- [ ] Cross-platform transport tests
- [ ] Immutability pattern tests
- [ ] Lifecycle management tests

**Documentation**:
- [ ] ONE TOOL principle explained with rationale
- [ ] Immutability patterns documented with examples
- [ ] Cross-platform deployment documented
- [ ] Migration path from alpha.1 documented

---

## Appendix: Key Architectural Decisions

### Decision: Same-Process vs. Separate-Process

**Chosen**: Same-process with clear boundaries (can evolve to separate-process)

**Rationale**:
- Simpler deployment (single command)
- Lower operational complexity
- Easier debugging
- Clean boundaries enable future separation
- No IPC overhead

**Trade-offs**:
- Can't independently restart components
- Single point of failure
- Resource limits apply to entire process

**Mitigation**: Design supports evolution to separate-process if needed.

### Decision: HTTP-First vs. Unix Socket-First

**Chosen**: HTTP-first with optional Unix socket optimization

**Rationale**:
- HTTP works on all platforms (Linux, macOS, Windows, WSL)
- Unix sockets are Unix-specific optimization
- Plan must support Windows (original plan ignored it)

**Trade-offs**:
- Slight performance overhead vs. Unix socket
- TCP port required

**Mitigation**: Platform detection with automatic Unix socket use when available.

### Decision: Extend IndexerSettings vs. New Service Section

**Chosen**: Extend IndexerSettings with BackgroundServicesConfig

**Rationale**:
- IndexerSettings already exists
- Background services are indexer-related
- Follows DRY principle
- Avoids configuration fragmentation

**Trade-offs**: None significant

### Decision: Constitutional Compliance (ONE TOOL)

**Chosen**: Only `find_code` exposed as MCP tool

**Rationale**: "All of our architectural decisions are built on the core idea that there is only one tool for the user's agent -- find_code"

Reindex/status operations are CLI-only to prevent agents from triggering expensive operations.

**Trade-offs**:
- Agents can't trigger reindex
- Agents can't query status

**Mitigation**: This is intentional design. CLI provides these operations for humans.

---

## Appendix: Code Reference Locations

Key files to reference during implementation:

**Existing Patterns**:
- `src/codeweaver/server/app_bindings.py` - AppState pattern, find_code_tool signature
- `src/codeweaver/core/types/models.py` - BasedModel, _telemetry_keys()
- `src/codeweaver/config/settings.py` - get_settings_map() immutability pattern
- `src/codeweaver/common/registry/provider.py` - ProviderRegistry singleton
- `src/codeweaver/common/statistics.py` - @timed_http decorator
- `claudedocs/fastmcp-deployment-research.md` - FastMCP/Starlette patterns

**Type System**:
- `src/codeweaver/core/types/sentinel.py` - UNSET sentinel pattern
- `src/codeweaver/core/types/models.py` - FROZEN_BASEDMODEL_CONFIG

**CLI**:
- `src/codeweaver/cli/` - Existing cyclopts commands

**Tests**:
- `tests/integration/` - Integration test patterns
- `tests/unit/` - Unit test patterns