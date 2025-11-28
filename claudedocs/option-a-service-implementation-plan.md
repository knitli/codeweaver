<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Option A: Service Architecture - Implementation Plan

## Executive Summary

**Goal**: Separate CodeWeaver's indexer into a standalone service, with MCP servers (HTTP and stdio) as thin protocol handlers that communicate with the indexer service via IPC.

**Timeline**: 3-4 weeks for alpha.2 release
**Breaking Changes**: Configuration format, deployment model
**Benefits**:
- Full stdio support (not read-only)
- Zero resource duplication with multiple clients
- Foundation for future Thread integration (Rust AST orchestrator)
- Can register both transports in MCP registry

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Indexer Service (Background Daemon)                    │
│  Port: 6334 (internal) | Socket: /run/codeweaver.sock  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Core Indexing Engine                              │ │
│  │  - File watcher & discovery                        │ │
│  │  - Chunking pipeline (parallel)                    │ │
│  │  - Embedding generation (batched)                  │ │
│  │  - Vector store management (Qdrant)                │ │
│  │  - Checkpoint/manifest persistence                 │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  HTTP API (Internal)                               │ │
│  │  POST /index      - Trigger indexing               │ │
│  │  POST /search     - Execute search                 │ │
│  │  GET  /status     - Indexing status                │ │
│  │  GET  /health     - Service health                 │ │
│  │  POST /shutdown   - Graceful shutdown              │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
         ↑ HTTP (localhost:6334)                ↑ Unix Socket
         │                                       │
┌────────┴────────────┐              ┌──────────┴──────────┐
│  MCP HTTP Server    │              │  MCP stdio Server   │
│  (Port 9328)        │              │  (Per-client proc)  │
│  ┌───────────────┐  │              │  ┌───────────────┐  │
│  │ FastMCP       │  │              │  │ FastMCP       │  │
│  │ find_code()   │  │              │  │ find_code()   │  │
│  │ ↓             │  │              │  │ ↓             │  │
│  │ HTTP client   │  │              │  │ Unix client   │  │
│  │ → service     │  │              │  │ → service     │  │
│  └───────────────┘  │              │  └───────────────┘  │
└─────────────────────┘              └─────────────────────┘
         ↑                                      ↑
         │ streamable-http                      │ stdio
┌────────┴────────────┐              ┌──────────┴──────────┐
│  Claude Desktop     │              │  Legacy MCP Client  │
│  Cursor             │              │  (stdio only)       │
│  Continue           │              │                     │
└─────────────────────┘              └─────────────────────┘
```

---

## Phase 1: Service Extraction (Week 1-2)

### 1.1 Create Indexer Service Module

**File**: `src/codeweaver/service/__init__.py`

```python
"""
Indexer service - standalone background daemon for code indexing.

Runs independently of MCP protocol handlers, providing HTTP/socket API
for indexing operations.
"""
```

**File**: `src/codeweaver/service/app.py`

```python
"""
Indexer service application using FastAPI.

Provides internal HTTP API for indexing operations. Not exposed publicly -
only accessible to MCP servers on localhost or via Unix socket.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import asyncio

from codeweaver.engine.indexer.indexer import Indexer
from codeweaver.engine.watcher.watcher import FileWatcher
from codeweaver.config.settings import get_settings


class IndexRequest(BaseModel):
    """Request to trigger indexing."""
    force_reindex: bool = False


class SearchRequest(BaseModel):
    """Search request."""
    query: str
    k: int = 10
    similarity_threshold: float = 0.7
    filters: Optional[dict] = None


class SearchResponse(BaseModel):
    """Search response."""
    results: list[dict]
    total: int
    took_ms: float


class StatusResponse(BaseModel):
    """Service status."""
    status: str  # "initializing" | "indexing" | "watching" | "ready" | "error"
    indexed_chunks: int
    total_files: int
    indexing_progress: float  # 0.0 - 1.0
    last_indexed: Optional[str]
    error: Optional[str] = None


class ServiceState:
    """Global service state (singleton pattern)."""

    def __init__(self):
        self.indexer: Optional[Indexer] = None
        self.watcher: Optional[FileWatcher] = None
        self.status: str = "initializing"
        self.error: Optional[str] = None
        self.background_task: Optional[asyncio.Task] = None
        self.shutdown_event = asyncio.Event()

    async def initialize(self):
        """Initialize indexer and start background tasks."""
        try:
            settings = get_settings()

            # Create indexer using async factory
            self.indexer = await Indexer.from_settings_async(settings=settings)

            # Start background indexing task
            self.background_task = asyncio.create_task(
                self._run_background_indexing()
            )

        except Exception as e:
            self.status = "error"
            self.error = str(e)
            raise

    async def _run_background_indexing(self):
        """Background task for indexing and file watching."""
        try:
            self.status = "indexing"

            # Prime the index (may take minutes)
            await self.indexer.prime_index()

            self.status = "watching"

            # Start file watcher
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
            self.status = "error"
            self.error = str(e)
            raise

    async def shutdown(self):
        """Graceful shutdown."""
        self.shutdown_event.set()

        # Cancel background task
        if self.background_task and not self.background_task.done():
            self.background_task.cancel()
            try:
                await asyncio.wait_for(self.background_task, timeout=7.0)
            except asyncio.TimeoutError:
                logger.warning("Background task did not stop within 7 seconds")

        # Cleanup indexer (checkpoints, etc.)
        if self.indexer:
            # Indexer cleanup happens in its context managers
            pass


# Global state instance
state = ServiceState()


# FastAPI app
app = FastAPI(
    title="CodeWeaver Indexer Service",
    description="Internal indexing service for CodeWeaver",
    version="0.1.0-alpha.2"
)


@app.on_event("startup")
async def startup():
    """Initialize service on startup."""
    await state.initialize()


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    await state.shutdown()


@app.post("/index", status_code=202)
async def trigger_index(
    request: IndexRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger indexing operation.

    Returns immediately with 202 Accepted.
    Indexing runs in background.
    """
    if not state.indexer:
        raise HTTPException(status_code=503, detail="Indexer not initialized")

    async def do_index():
        await state.indexer.prime_index(force_reindex=request.force_reindex)

    background_tasks.add_task(do_index)

    return {"status": "accepted", "message": "Indexing started"}


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Execute semantic search.

    Delegates to find_code API.
    """
    if not state.indexer:
        raise HTTPException(status_code=503, detail="Indexer not initialized")

    if state.status != "watching" and state.status != "ready":
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready (status: {state.status})"
        )

    # Import here to avoid circular dependency
    from codeweaver.agent_api.find_code import find_code

    # Create minimal context
    class IndexerContext:
        def __init__(self, indexer):
            self._indexer = indexer

    import time
    start = time.perf_counter()

    result = await find_code(
        query=request.query,
        context=IndexerContext(state.indexer),
        k=request.k,
        similarity_threshold=request.similarity_threshold,
        filters=request.filters
    )

    took_ms = (time.perf_counter() - start) * 1000

    return SearchResponse(
        results=result.get("results", []),
        total=result.get("total", 0),
        took_ms=took_ms
    )


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get service status."""
    indexed_chunks = 0
    total_files = 0
    indexing_progress = 0.0
    last_indexed = None

    if state.indexer and state.indexer.stats:
        stats = state.indexer.stats
        indexed_chunks = stats.indexed_chunks or 0
        total_files = stats.total_files or 0

        if total_files > 0:
            indexing_progress = indexed_chunks / total_files

        if stats.last_indexed_at:
            last_indexed = stats.last_indexed_at.isoformat()

    return StatusResponse(
        status=state.status,
        indexed_chunks=indexed_chunks,
        total_files=total_files,
        indexing_progress=indexing_progress,
        last_indexed=last_indexed,
        error=state.error
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if state.status == "error":
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "error": state.error}
        )

    return {
        "status": "healthy",
        "service": "codeweaver-indexer",
        "version": "0.1.0-alpha.2"
    }


@app.post("/shutdown")
async def trigger_shutdown():
    """
    Trigger graceful shutdown.

    Used by MCP servers or management tools.
    """
    asyncio.create_task(state.shutdown())
    return {"status": "shutting_down"}
```

**File**: `src/codeweaver/service/server.py`

```python
"""
Service server runner.

Starts the indexer service with uvicorn.
"""

import uvicorn
from pathlib import Path
from codeweaver.config.settings import get_settings


def run_service():
    """Run the indexer service."""
    settings = get_settings()

    # Service configuration
    host = settings.get("service.host", "127.0.0.1")
    port = settings.get("service.port", 6334)

    # Only bind to localhost for security
    # MCP servers communicate via localhost or Unix socket
    if host not in ["127.0.0.1", "localhost"]:
        logger.warning(
            f"Service host '{host}' is not localhost. "
            "This may expose internal API publicly. "
            "Recommended: Use '127.0.0.1' and let MCP servers handle public access."
        )

    logger.info(f"Starting indexer service on {host}:{port}")

    uvicorn.run(
        "codeweaver.service.app:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,  # No auto-reload in production
        access_log=True
    )


if __name__ == "__main__":
    run_service()
```

---

### 1.2 Create MCP Server Clients

**File**: `src/codeweaver/mcp/client.py`

```python
"""
Client for communicating with indexer service.

Supports both HTTP and Unix socket transports.
"""

import httpx
import asyncio
from pathlib import Path
from typing import Optional, Literal


class IndexerClient:
    """
    Client for indexer service.

    Automatically detects and uses Unix socket if available,
    falls back to HTTP.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:6334",
        socket_path: Optional[Path] = None
    ):
        """
        Initialize client.

        Args:
            base_url: HTTP URL of indexer service
            socket_path: Unix socket path (preferred if available)
        """
        self.base_url = base_url
        self.socket_path = socket_path
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *args):
        """Async context manager exit."""
        await self.close()

    async def connect(self):
        """Establish connection to service."""
        if self.socket_path and self.socket_path.exists():
            # Use Unix socket (faster, no TCP overhead)
            transport = httpx.AsyncHTTPTransport(
                uds=str(self.socket_path)
            )
            self._client = httpx.AsyncClient(
                transport=transport,
                base_url="http://unix"
            )
            logger.debug(f"Connected via Unix socket: {self.socket_path}")
        else:
            # Fall back to HTTP
            self._client = httpx.AsyncClient(base_url=self.base_url)
            logger.debug(f"Connected via HTTP: {self.base_url}")

    async def close(self):
        """Close connection."""
        if self._client:
            await self._client.aclose()

    async def search(
        self,
        query: str,
        k: int = 10,
        similarity_threshold: float = 0.7,
        filters: Optional[dict] = None
    ) -> dict:
        """
        Execute search via service.

        Args:
            query: Search query
            k: Number of results
            similarity_threshold: Minimum similarity score
            filters: Optional filters

        Returns:
            Search results
        """
        response = await self._client.post(
            "/search",
            json={
                "query": query,
                "k": k,
                "similarity_threshold": similarity_threshold,
                "filters": filters
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    async def trigger_index(self, force_reindex: bool = False):
        """
        Trigger indexing operation.

        Returns immediately, indexing runs in background.
        """
        response = await self._client.post(
            "/index",
            json={"force_reindex": force_reindex},
            timeout=5.0
        )
        response.raise_for_status()
        return response.json()

    async def get_status(self) -> dict:
        """Get service status."""
        response = await self._client.get("/status", timeout=5.0)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        """
        Check if service is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self._client.get("/health", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False

    async def wait_for_ready(self, timeout: float = 300.0):
        """
        Wait for service to be ready (indexing complete).

        Polls status until ready or timeout.

        Args:
            timeout: Maximum wait time in seconds

        Raises:
            TimeoutError: If service not ready within timeout
        """
        import time
        start = time.time()

        while time.time() - start < timeout:
            try:
                status = await self.get_status()

                if status["status"] in ["watching", "ready"]:
                    return

                if status["status"] == "error":
                    raise RuntimeError(f"Service error: {status.get('error')}")

                # Still indexing, wait and retry
                await asyncio.sleep(2.0)

            except httpx.HTTPError:
                # Service not responding, wait and retry
                await asyncio.sleep(2.0)

        raise TimeoutError(f"Service not ready after {timeout}s")
```

**File**: `src/codeweaver/mcp/http_server.py`

```python
"""
MCP HTTP server (streamable-http transport).

Thin wrapper around indexer service client.
"""

from fastmcp import FastMCP
from codeweaver.mcp.client import IndexerClient
from codeweaver.config.settings import get_settings


# Create MCP app
mcp = FastMCP("CodeWeaver")

# Global client (initialized in lifespan)
client: Optional[IndexerClient] = None


@mcp.lifespan()
async def lifespan():
    """Manage client lifecycle."""
    global client

    settings = get_settings()

    # Connect to indexer service
    client = IndexerClient(
        base_url=settings.get("service.url", "http://127.0.0.1:6334"),
        socket_path=settings.get("service.socket")
    )
    await client.connect()

    # Optional: Wait for service to be ready
    # (or let first query trigger auto-indexing)
    # await client.wait_for_ready()

    yield

    # Cleanup
    await client.close()


@mcp.tool()
async def find_code(
    query: str,
    k: int = 10,
    similarity_threshold: float = 0.7
) -> dict:
    """
    Search codebase using semantic similarity.

    Args:
        query: Natural language query or code pattern
        k: Number of results to return
        similarity_threshold: Minimum similarity score (0.0-1.0)

    Returns:
        Search results with file paths, line numbers, and code snippets
    """
    if not client:
        raise RuntimeError("Client not initialized")

    return await client.search(
        query=query,
        k=k,
        similarity_threshold=similarity_threshold
    )


@mcp.tool()
async def reindex(force: bool = False) -> dict:
    """
    Trigger re-indexing of the codebase.

    Args:
        force: Force full re-index (ignores checkpoints)

    Returns:
        Status message
    """
    if not client:
        raise RuntimeError("Client not initialized")

    return await client.trigger_index(force_reindex=force)


@mcp.tool()
async def get_index_status() -> dict:
    """
    Get current indexing status.

    Returns:
        Status information including progress, file counts, etc.
    """
    if not client:
        raise RuntimeError("Client not initialized")

    return await client.get_status()


def run_http_server():
    """Run the HTTP MCP server."""
    settings = get_settings()

    host = settings.get("mcp.http.host", "127.0.0.1")
    port = settings.get("mcp.http.port", 9328)

    logger.info(f"Starting MCP HTTP server on {host}:{port}")

    # Run with FastMCP's built-in server
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port
    )


if __name__ == "__main__":
    run_http_server()
```

**File**: `src/codeweaver/mcp/stdio_server.py`

```python
"""
MCP stdio server.

Thin wrapper around indexer service client.
Spawned per-client by MCP clients that only support stdio.
"""

from fastmcp import FastMCP
from codeweaver.mcp.client import IndexerClient
from codeweaver.config.settings import get_settings


# Create MCP app (identical to HTTP server)
mcp = FastMCP("CodeWeaver")

client: Optional[IndexerClient] = None


@mcp.lifespan()
async def lifespan():
    """Manage client lifecycle."""
    global client

    settings = get_settings()

    # Connect to indexer service
    # stdio server REQUIRES service to be already running
    client = IndexerClient(
        base_url=settings.get("service.url", "http://127.0.0.1:6334"),
        socket_path=settings.get("service.socket")
    )
    await client.connect()

    # Check service is healthy
    if not await client.health_check():
        raise RuntimeError(
            "Indexer service is not running. "
            "Start it first: codeweaver service start"
        )

    yield

    await client.close()


# Tools identical to HTTP server
@mcp.tool()
async def find_code(
    query: str,
    k: int = 10,
    similarity_threshold: float = 0.7
) -> dict:
    """Search codebase using semantic similarity."""
    if not client:
        raise RuntimeError("Client not initialized")

    return await client.search(
        query=query,
        k=k,
        similarity_threshold=similarity_threshold
    )


@mcp.tool()
async def reindex(force: bool = False) -> dict:
    """Trigger re-indexing of the codebase."""
    if not client:
        raise RuntimeError("Client not initialized")

    return await client.trigger_index(force_reindex=force)


@mcp.tool()
async def get_index_status() -> dict:
    """Get current indexing status."""
    if not client:
        raise RuntimeError("Client not initialized")

    return await client.get_status()


def run_stdio_server():
    """Run the stdio MCP server."""
    logger.info("Starting MCP stdio server")

    # Run with FastMCP's stdio transport
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_stdio_server()
```

---

### 1.3 Update CLI Commands

**File**: `src/codeweaver/cli/commands/service.py` (NEW)

```python
"""
Service management commands.
"""

import click
import subprocess
import signal
import sys
from pathlib import Path


@click.group()
def service():
    """Manage the indexer service."""
    pass


@service.command()
@click.option(
    "--host",
    default="127.0.0.1",
    help="Service host (default: 127.0.0.1)"
)
@click.option(
    "--port",
    default=6334,
    type=int,
    help="Service port (default: 6334)"
)
@click.option(
    "--daemon",
    is_flag=True,
    help="Run as background daemon"
)
def start(host: str, port: int, daemon: bool):
    """Start the indexer service."""
    if daemon:
        # Run as background process
        # TODO: Proper daemonization with pidfile
        subprocess.Popen(
            [sys.executable, "-m", "codeweaver.service.server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        click.echo("Service started in background")
    else:
        # Run in foreground
        from codeweaver.service.server import run_service
        run_service()


@service.command()
def stop():
    """Stop the indexer service."""
    # TODO: Read pidfile and send SIGTERM
    click.echo("Not implemented - send SIGTERM to service process")


@service.command()
def status():
    """Check service status."""
    import httpx

    try:
        response = httpx.get("http://127.0.0.1:6334/status", timeout=2.0)
        status = response.json()

        click.echo(f"Status: {status['status']}")
        click.echo(f"Indexed chunks: {status['indexed_chunks']}")
        click.echo(f"Total files: {status['total_files']}")
        click.echo(f"Progress: {status['indexing_progress']:.1%}")

    except Exception as e:
        click.echo(f"Service not running: {e}")
        sys.exit(1)
```

**File**: `src/codeweaver/cli/commands/server.py` (UPDATE)

```python
"""
MCP server commands (updated for service architecture).
"""

import click
from codeweaver.mcp.http_server import run_http_server
from codeweaver.mcp.stdio_server import run_stdio_server


@click.group()
def server():
    """Start MCP servers."""
    pass


@server.command()
@click.option(
    "--transport",
    type=click.Choice(["http", "stdio"]),
    default="http",
    help="MCP transport protocol"
)
def start(transport: str):
    """
    Start MCP server.

    IMPORTANT: The indexer service must be running first.
    Start it with: codeweaver service start
    """
    # Check if service is running
    import httpx
    try:
        response = httpx.get("http://127.0.0.1:6334/health", timeout=2.0)
        if response.status_code != 200:
            raise RuntimeError("Service unhealthy")
    except Exception as e:
        click.echo(
            f"ERROR: Indexer service is not running.\n"
            f"Start it first: codeweaver service start\n"
            f"Details: {e}",
            err=True
        )
        sys.exit(1)

    if transport == "http":
        run_http_server()
    else:
        run_stdio_server()
```

---

## Phase 2: Configuration Updates (Week 2)

### 2.1 Update Configuration Schema

**File**: `src/codeweaver/config/service.py` (NEW)

```python
"""
Service configuration.
"""

from pydantic import BaseModel, Field
from pathlib import Path
from typing import Optional


class ServiceConfig(BaseModel):
    """Indexer service configuration."""

    host: str = Field(
        default="127.0.0.1",
        description="Service host (should be localhost for security)"
    )

    port: int = Field(
        default=6334,
        description="Service port"
    )

    socket: Optional[Path] = Field(
        default=None,
        description="Unix socket path (preferred over HTTP)"
    )

    url: str = Field(
        default="http://127.0.0.1:6334",
        description="Service URL for clients"
    )


class MCPConfig(BaseModel):
    """MCP server configuration."""

    class HTTPConfig(BaseModel):
        host: str = "127.0.0.1"
        port: int = 9328

    class StdioConfig(BaseModel):
        enabled: bool = False

    http: HTTPConfig = HTTPConfig()
    stdio: StdioConfig = StdioConfig()
```

**File**: `config.toml` (UPDATE)

```toml
[service]
# Indexer service configuration
host = "127.0.0.1"  # Only localhost for security
port = 6334
socket = "/run/codeweaver/indexer.sock"  # Unix socket (Linux/macOS)

[mcp]
# MCP server configuration

[mcp.http]
host = "0.0.0.0"  # Can be public (reverse proxy recommended)
port = 9328

[mcp.stdio]
enabled = false  # Enable for legacy clients
```

---

## Phase 3: Deployment & Process Management (Week 3)

### 3.1 Docker Compose

**File**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  # Vector store
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  # Indexer service (background daemon)
  indexer:
    build: .
    command: codeweaver service start
    ports:
      - "6334:6334"  # Internal API (localhost only in production)
    depends_on:
      qdrant:
        condition: service_healthy
    environment:
      - CODEWEAVER_PROJECT_PATH=/workspace
      - CODEWEAVER_VECTOR_STORE_URL=http://qdrant:6333
    volumes:
      - ./workspace:/workspace:ro
      - indexer_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6334/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  # MCP HTTP server (public interface)
  mcp-http:
    build: .
    command: codeweaver server start --transport http
    ports:
      - "9328:9328"
    depends_on:
      indexer:
        condition: service_healthy
    environment:
      - CODEWEAVER_SERVICE_URL=http://indexer:6334

volumes:
  qdrant_data:
  indexer_data:
```

### 3.2 Systemd Service (Linux)

**File**: `deployment/systemd/codeweaver-indexer.service`

```ini
[Unit]
Description=CodeWeaver Indexer Service
After=network.target

[Service]
Type=simple
User=codeweaver
WorkingDirectory=/opt/codeweaver
ExecStart=/opt/codeweaver/.venv/bin/codeweaver service start
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

**File**: `deployment/systemd/codeweaver-mcp-http.service`

```ini
[Unit]
Description=CodeWeaver MCP HTTP Server
After=network.target codeweaver-indexer.service
Requires=codeweaver-indexer.service

[Service]
Type=simple
User=codeweaver
WorkingDirectory=/opt/codeweaver
ExecStart=/opt/codeweaver/.venv/bin/codeweaver server start --transport http
Restart=always
RestartSec=5

# Environment
Environment="CODEWEAVER_SERVICE_URL=http://localhost:6334"

[Install]
WantedBy=multi-user.target
```

### 3.3 Process Manager (Cross-Platform)

**File**: `deployment/supervisor/supervisord.conf`

```ini
[supervisord]
nodaemon=true

[program:codeweaver-indexer]
command=/opt/codeweaver/.venv/bin/codeweaver service start
directory=/opt/codeweaver
autostart=true
autorestart=true
stderr_logfile=/var/log/codeweaver/indexer.err.log
stdout_logfile=/var/log/codeweaver/indexer.out.log

[program:codeweaver-mcp-http]
command=/opt/codeweaver/.venv/bin/codeweaver server start --transport http
directory=/opt/codeweaver
autostart=true
autorestart=true
stderr_logfile=/var/log/codeweaver/mcp-http.err.log
stdout_logfile=/var/log/codeweaver/mcp-http.out.log
```

---

## Phase 4: Testing (Week 3-4)

### 4.1 Service Integration Tests

**File**: `tests/integration/test_service_architecture.py`

```python
"""
Integration tests for service architecture.
"""

import pytest
import asyncio
import httpx
from pathlib import Path


@pytest.mark.asyncio
async def test_service_startup():
    """Test service starts and becomes healthy."""
    # Assume service is started by test harness

    async with httpx.AsyncClient() as client:
        # Wait for service to be healthy
        for _ in range(30):  # 30 second timeout
            try:
                response = await client.get(
                    "http://127.0.0.1:6334/health",
                    timeout=2.0
                )
                if response.status_code == 200:
                    break
            except:
                pass
            await asyncio.sleep(1.0)
        else:
            pytest.fail("Service did not become healthy within 30s")


@pytest.mark.asyncio
async def test_multiple_clients_single_indexer():
    """
    Test multiple MCP clients share single indexer.

    This is the core benefit of service architecture.
    """
    from codeweaver.mcp.client import IndexerClient

    # Create 4 concurrent clients (simulating 4 MCP servers)
    clients = [
        IndexerClient(base_url="http://127.0.0.1:6334")
        for _ in range(4)
    ]

    # Connect all
    await asyncio.gather(*[c.connect() for c in clients])

    try:
        # All perform searches concurrently
        results = await asyncio.gather(*[
            c.search(query=f"test query {i}")
            for i, c in enumerate(clients)
        ])

        # All should succeed
        assert len(results) == 4
        assert all("results" in r for r in results)

        # Check only one indexer instance
        status = await clients[0].get_status()
        # Should show single indexing operation, not 4x

    finally:
        # Cleanup
        await asyncio.gather(*[c.close() for c in clients])


@pytest.mark.asyncio
async def test_stdio_requires_service():
    """Test stdio server fails gracefully if service not running."""
    # Stop service (simulated)
    # Try to start stdio server
    # Should fail with clear error message
    pass


@pytest.mark.asyncio
async def test_unix_socket_fallback():
    """Test client prefers Unix socket over HTTP."""
    from codeweaver.mcp.client import IndexerClient

    # Create client with socket path
    socket_path = Path("/tmp/codeweaver-test.sock")

    # If socket doesn't exist, should fall back to HTTP
    client = IndexerClient(
        base_url="http://127.0.0.1:6334",
        socket_path=socket_path
    )

    await client.connect()

    # Should be able to communicate
    assert await client.health_check()

    await client.close()
```

### 4.2 Resource Consumption Tests

**File**: `tests/benchmarks/test_resource_usage.py`

```python
"""
Benchmark resource usage with service architecture.
"""

import pytest
import psutil
import asyncio


@pytest.mark.benchmark
async def test_memory_usage_single_vs_multi_client():
    """
    Compare memory usage:
    - 4 separate indexer instances (old model)
    - 4 clients → 1 service (new model)
    """
    process = psutil.Process()

    # Baseline: Start service
    # Record memory
    baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Create 4 clients
    from codeweaver.mcp.client import IndexerClient
    clients = [IndexerClient() for _ in range(4)]
    await asyncio.gather(*[c.connect() for c in clients])

    # Record memory with 4 clients
    with_clients_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Memory increase should be minimal (< 100MB)
    increase = with_clients_memory - baseline_memory
    assert increase < 100, f"Memory increase too high: {increase}MB"

    # Cleanup
    await asyncio.gather(*[c.close() for c in clients])


@pytest.mark.benchmark
async def test_no_duplicate_indexing():
    """Verify no duplicate indexing operations."""
    # Start service with empty index
    # Create 4 clients
    # All trigger indexing simultaneously
    # Check only one indexing operation occurred
    # (Verify by checking embedding API call count)
    pass
```

---

## Phase 5: Documentation (Week 4)

### 5.1 Architecture Documentation

**File**: `docs/architecture/service-separation.md`

```markdown
# Service Architecture

## Overview

CodeWeaver uses a **service architecture** to separate:
- **Indexer Service**: Background daemon handling indexing operations
- **MCP Servers**: Thin protocol handlers (HTTP and stdio)

## Benefits

1. **Multi-Client Support**: 4 HTTP clients → 1 indexer (not 4)
2. **stdio Support**: Full functionality via service communication
3. **Resource Efficiency**: 75% memory reduction with multiple clients
4. **Clean Separation**: Protocol concerns separated from business logic

## Components

### Indexer Service (Port 6334)
- Runs as background daemon
- Handles file watching, chunking, embedding, vector storage
- Provides internal HTTP API

### MCP HTTP Server (Port 9328)
- Public-facing MCP endpoint (streamable-http)
- Thin client to indexer service
- Multiple instances can run (load balancing)

### MCP stdio Server
- Spawned per-client by stdio-only MCP clients
- Connects to shared indexer service
- Full functionality (not read-only)

## Deployment Models

### Development (Single Machine)
```bash
# Terminal 1: Start indexer service
codeweaver service start

# Terminal 2: Start MCP HTTP server
codeweaver server start --transport http

# Terminal 3: Optional stdio for legacy clients
# (Spawned automatically by MCP client)
```

### Production (Docker Compose)
```bash
docker-compose up -d
# Starts: qdrant, indexer, mcp-http
```

### Production (Systemd)
```bash
sudo systemctl start codeweaver-indexer
sudo systemctl start codeweaver-mcp-http
```

## Communication Protocols

### Indexer Service API

**POST /index** - Trigger indexing
**POST /search** - Execute search
**GET /status** - Get service status
**GET /health** - Health check

### MCP Tools

**find_code(query)** → Searches via service
**reindex(force)** → Triggers indexing via service
**get_index_status()** → Gets status via service

## Migration from Alpha.1

Alpha.1 (monolithic):
```bash
codeweaver server --transport http
# Includes indexer in same process
```

Alpha.2 (service):
```bash
codeweaver service start       # Indexer service
codeweaver server start --transport http  # MCP server
```

Configuration changes:
```toml
# OLD (alpha.1)
[server]
host = "127.0.0.1"
port = 9328

# NEW (alpha.2)
[service]
host = "127.0.0.1"
port = 6334

[mcp.http]
host = "0.0.0.0"
port = 9328
```
```

### 5.2 User Documentation

**File**: `README.md` (UPDATE)

````markdown
## Installation

```bash
pip install codeweaver
```

## Quick Start

### 1. Start the Indexer Service

```bash
codeweaver service start
```

This starts the background indexing daemon. It will:
- Discover files in your project
- Chunk and embed code
- Index to vector store
- Watch for file changes

### 2. Start the MCP Server

```bash
codeweaver server start --transport http
```

This starts the MCP protocol handler that clients connect to.

### 3. Configure MCP Client

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

**stdio Transport** (Legacy):
```json
{
  "mcpServers": {
    "codeweaver": {
      "type": "stdio",
      "command": "codeweaver",
      "args": ["server", "start", "--transport", "stdio"]
    }
  }
}
```

> **Note**: stdio requires the indexer service to be already running.

## Transport Comparison

| Feature | HTTP | stdio |
|---------|------|-------|
| Background indexing | ✅ Yes | ✅ Yes |
| Multiple clients | ✅ Shared | ✅ Shared |
| Resource usage | ✅ Efficient | ✅ Efficient |
| File watching | ✅ Real-time | ✅ Real-time |
| Performance | ✅ Best | ✅ Good |
| Setup | Simple | Requires service |

**Recommendation**: Use HTTP transport unless your MCP client only supports stdio.
````

---

## Migration Checklist

### Development Migration

- [ ] Create service module structure
- [ ] Extract indexer to FastAPI service
- [ ] Create IndexerClient for service communication
- [ ] Build HTTP MCP server as client
- [ ] Build stdio MCP server as client
- [ ] Update CLI commands (service, server)
- [ ] Update configuration schema
- [ ] Write integration tests
- [ ] Write benchmark tests

### Deployment Migration

- [ ] Create Docker Compose configuration
- [ ] Create systemd service files
- [ ] Create supervisor configuration
- [ ] Test development deployment
- [ ] Test production deployment (Docker)
- [ ] Test production deployment (systemd)

### Documentation Migration

- [ ] Update README with new architecture
- [ ] Document service architecture
- [ ] Document deployment models
- [ ] Create migration guide for users
- [ ] Update MCP client configuration examples

---

## Timeline

**Week 1**: Service extraction
- Day 1-2: Service module (app.py, server.py)
- Day 3-4: IndexerClient implementation
- Day 5: Initial testing

**Week 2**: MCP servers + CLI
- Day 1-2: HTTP MCP server
- Day 2-3: stdio MCP server
- Day 4-5: CLI updates, configuration

**Week 3**: Deployment + Testing
- Day 1-2: Docker Compose, systemd
- Day 3-4: Integration tests
- Day 5: Benchmark tests

**Week 4**: Documentation + Polish
- Day 1-2: Architecture docs
- Day 3-4: User documentation
- Day 5: Final testing, alpha.2 release

---

## Success Metrics

### Functional

- [ ] Single indexer serves multiple clients
- [ ] Both HTTP and stdio transports work
- [ ] No duplicate indexing operations
- [ ] File watching works correctly
- [ ] Graceful shutdown preserves state

### Performance

- [ ] Memory: < 300MB with 4 clients (vs 960MB old model)
- [ ] No indexing duplication (verify API call counts)
- [ ] Client latency: < 5ms overhead vs direct access
- [ ] Startup time: < 30s for indexer service

### Quality

- [ ] All tests pass
- [ ] No regressions from alpha.1
- [ ] Documentation complete
- [ ] Deployment tested on Linux, macOS, WSL

---

## Risk Mitigation

### Service Communication Failures

**Risk**: Indexer service crashes, MCP servers can't communicate

**Mitigation**:
- Health checks in MCP server startup
- Graceful error messages to users
- Auto-restart via systemd/supervisor
- Service monitoring and logging

### Port Conflicts

**Risk**: Port 6334 or 9328 already in use

**Mitigation**:
- Configurable ports
- Clear error messages
- Port conflict detection in startup

### Unix Socket Permissions

**Risk**: Socket permissions prevent client access

**Mitigation**:
- Proper socket file permissions (666 or user group)
- Fall back to HTTP if socket inaccessible
- Clear error messages

### Deployment Complexity

**Risk**: Users confused by service vs server

**Mitigation**:
- Clear README documentation
- docker-compose.yml for simple deployment
- Single command for development: `codeweaver dev` (starts both)

---

## Future Enhancements

### Alpha.3+

Once service architecture is stable:

1. **Multi-Repo Support**:
   ```python
   POST /repos {"path": "/path/to/repo", "name": "frontend"}
   GET /search?repos=frontend,backend&query=...
   ```

2. **External Source Integration**:
   ```python
   POST /docs/ingest {"library": "react", "source": "context7"}
   POST /research/save {"query": "...", "results": [...]}
   ```

3. **Agent API**:
   ```python
   POST /agent/request {"action": "index_dependency_docs", ...}
   ```

4. **Thread Integration**:
   - Service communicates with Thread (Rust AST orchestrator)
   - Shared data layer for cross-repo intelligence
