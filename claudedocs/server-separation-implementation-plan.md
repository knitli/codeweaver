<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Server Separation Implementation Plan

## Overview

This document outlines the implementation plan for separating CodeWeaver's HTTP server and background indexing components to support stdio protocol without resource duplication or data corruption.

**Target Architecture**: Hybrid approach combining ASGI composition with coordinator pattern
**Primary Goal**: Enable stdio support while maintaining single-instance indexing semantics
**Secondary Goal**: Prepare foundation for future REST API and multi-project support

---

## Phase 1: Core Separation (1-2 weeks)

### 1.1 Create IndexingCoordinator Service

**File**: `src/codeweaver/services/coordinator.py`

```python
"""
Coordinates indexing operations across multiple clients and projects.

Responsibilities:
- Singleton indexer instance management per project
- Background task lifecycle coordination
- Concurrent access synchronization
- Resource sharing across protocol handlers
"""

import asyncio
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from codeweaver.engine.indexer.indexer import Indexer
from codeweaver.config.settings import CodeWeaverSettings


@dataclass
class ProjectIndexer:
    """Container for project-specific indexing state."""
    indexer: Indexer
    background_task: Optional[asyncio.Task] = None
    access_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_accessed: float = field(default_factory=time.time)


class IndexingCoordinator:
    """
    Singleton service coordinating indexing operations.

    Ensures single indexer instance per project regardless of
    number of connected clients or protocol transport type.
    """

    _instance: Optional['IndexingCoordinator'] = None
    _init_lock = asyncio.Lock()

    def __init__(self):
        self.projects: dict[Path, ProjectIndexer] = {}
        self.project_locks: dict[Path, asyncio.Lock] = {}
        self.background_tasks: set[asyncio.Task] = set()
        self._shutdown_requested = False

    @classmethod
    async def get_instance(cls) -> 'IndexingCoordinator':
        """Get or create singleton coordinator instance."""
        if not cls._instance:
            async with cls._init_lock:
                if not cls._instance:
                    cls._instance = IndexingCoordinator()
                    await cls._instance.initialize()
        return cls._instance

    async def initialize(self):
        """Initialize coordinator resources."""
        logger.info("IndexingCoordinator initialized")

    async def get_or_create_indexer(
        self,
        project_path: Path,
        settings: Optional[CodeWeaverSettings] = None
    ) -> Indexer:
        """
        Get existing indexer or create new one for project.

        Thread-safe singleton pattern ensures only one indexer
        per project path regardless of concurrent requests.
        """
        project_path = project_path.resolve()

        if project_path not in self.projects:
            # Acquire project-specific lock for initialization
            async with self.project_locks.setdefault(
                project_path, asyncio.Lock()
            ):
                # Double-check after acquiring lock
                if project_path not in self.projects:
                    logger.info(f"Creating indexer for {project_path}")

                    # Create indexer using async factory
                    indexer = await Indexer.from_settings_async(
                        settings=settings
                    )

                    # Create project container
                    project = ProjectIndexer(indexer=indexer)
                    self.projects[project_path] = project

                    # Start background indexing task
                    task = asyncio.create_task(
                        self._run_background_indexing(project_path, project)
                    )
                    project.background_task = task
                    self.background_tasks.add(task)

        # Update last access time
        self.projects[project_path].last_accessed = time.time()
        return self.projects[project_path].indexer

    async def _run_background_indexing(
        self,
        project_path: Path,
        project: ProjectIndexer
    ):
        """Run background indexing and file watching for project."""
        try:
            # Prime the index (may take minutes)
            await project.indexer.prime_index()

            # Start file watcher for continuous monitoring
            from codeweaver.engine.watcher.watcher import FileWatcher
            watcher = await FileWatcher.create(
                indexer=project.indexer,
                verbose=False
            )
            await watcher.run()

        except asyncio.CancelledError:
            logger.info(f"Background indexing cancelled for {project_path}")
            raise
        except Exception as e:
            logger.error(f"Background indexing error for {project_path}: {e}")
            raise

    async def search(
        self,
        project_path: Path,
        query: str,
        **kwargs
    ):
        """
        Execute search with automatic indexer retrieval.

        Delegates to find_code API which handles:
        - Intent classification
        - Query embedding generation
        - Vector similarity search
        - Reranking and result formatting
        """
        indexer = await self.get_or_create_indexer(project_path)

        # Import here to avoid circular dependency
        from codeweaver.agent_api.find_code import find_code

        # find_code expects context with indexer reference
        # For now, create minimal context shim
        class IndexerContext:
            def __init__(self, indexer):
                self._indexer = indexer

        ctx = IndexerContext(indexer)
        return await find_code(query=query, context=ctx, **kwargs)

    async def get_indexer_stats(self, project_path: Path):
        """Get indexing statistics for project."""
        if project_path not in self.projects:
            return None
        return self.projects[project_path].indexer.stats

    async def shutdown(self):
        """Graceful shutdown of all indexers."""
        self._shutdown_requested = True

        # Cancel all background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete with timeout
        if self.background_tasks:
            await asyncio.wait(
                self.background_tasks,
                timeout=7.0,
                return_when=asyncio.ALL_COMPLETED
            )

        # Cleanup indexers
        for project_path, project in self.projects.items():
            logger.info(f"Shutting down indexer for {project_path}")
            # Indexer cleanup happens in its own context managers

        logger.info("IndexingCoordinator shutdown complete")
```

**Tests**: `tests/services/test_coordinator.py`
```python
import pytest
from pathlib import Path

@pytest.mark.asyncio
async def test_singleton_pattern():
    """Verify coordinator is singleton across calls."""
    coord1 = await IndexingCoordinator.get_instance()
    coord2 = await IndexingCoordinator.get_instance()
    assert coord1 is coord2

@pytest.mark.asyncio
async def test_single_indexer_per_project():
    """Verify only one indexer created per project path."""
    coord = await IndexingCoordinator.get_instance()
    project = Path("/tmp/test-project")

    # Multiple concurrent requests
    indexers = await asyncio.gather(
        coord.get_or_create_indexer(project),
        coord.get_or_create_indexer(project),
        coord.get_or_create_indexer(project),
    )

    # All should be same instance
    assert indexers[0] is indexers[1] is indexers[2]
```

### 1.2 Refactor AppState to Use Coordinator

**File**: `src/codeweaver/server/server.py`

**Current** (lines 142-144):
```python
@dataclass
class AppState:
    indexer: Indexer | None = None
    # ...
```

**New**:
```python
@dataclass
class AppState:
    coordinator: IndexingCoordinator | None = None
    project_path: Path | None = None  # From settings
    # Remove direct indexer reference
    # ...
```

**Update `_initialize_app_state`** (lines 382-420):

**Current**:
```python
async def _initialize_app_state(
    state: AppState, settings: DictView[CodeWeaverSettingsDict], *, verbose: bool = False
) -> None:
    # Line 406: Always creates indexer
    state.indexer = Indexer.from_settings(settings=settings)
```

**New**:
```python
async def _initialize_app_state(
    state: AppState, settings: DictView[CodeWeaverSettingsDict], *, verbose: bool = False
) -> None:
    # Get coordinator singleton
    state.coordinator = await IndexingCoordinator.get_instance()

    # Store project path from settings
    state.project_path = Path(settings["project_path"])

    # Pre-warm indexer for this project (optional, for faster first request)
    # await state.coordinator.get_or_create_indexer(state.project_path, settings)
```

**Update `_run_background_indexing`** (lines 210-380):

**Current**:
```python
async def _run_background_indexing(...):
    # Line 292-296: Blocks on prime_index
    await state.indexer.prime_index(...)
    # Line 342-354: Starts file watcher
    watcher = await FileWatcher.create(indexer=state.indexer, ...)
```

**New**:
```python
async def _run_background_indexing(...):
    """
    Background indexing now handled by coordinator.
    This function becomes a no-op or minimal health check.
    """
    # Coordinator handles background tasks automatically
    # when indexer is first requested via get_or_create_indexer

    # Optional: Pre-warm indexer to maintain current startup behavior
    if not verbose:
        status_display.print_info("Indexer initialization delegated to coordinator")

    # Indexer will be created on first find_code call
    # Background indexing starts automatically
```

**Update Cleanup** (lines 423-487):
```python
async def _cleanup_state(...):
    # No longer need to manage indexing_task directly
    # Coordinator handles all background task lifecycle

    if state.coordinator:
        await state.coordinator.shutdown()

    # Rest of cleanup unchanged
```

### 1.3 Update MCP Tool Bindings

**File**: `src/codeweaver/server/app_bindings.py`

**Current** (`find_code` tool wrapper):
```python
@mcp.tool()
async def find_code(query: str, ctx: Context):
    # Accesses ctx.state.indexer
```

**New**:
```python
@mcp.tool()
async def find_code(
    query: str,
    ctx: Context,
    k: int = 10,
    similarity_threshold: float = 0.7
):
    """
    Search codebase using semantic similarity.

    Now retrieves indexer via coordinator for project isolation.
    """
    state: AppState = ctx.state

    if not state.coordinator or not state.project_path:
        raise RuntimeError("Coordinator not initialized")

    # Get indexer for current project
    indexer = await state.coordinator.get_or_create_indexer(
        state.project_path
    )

    # Call find_code API (existing logic unchanged)
    from codeweaver.agent_api.find_code import find_code as find_code_api

    # Create context shim with indexer reference
    class IndexerContext:
        def __init__(self, indexer):
            self._indexer = indexer

    result = await find_code_api(
        query=query,
        context=IndexerContext(indexer),
        k=k,
        similarity_threshold=similarity_threshold
    )

    return result
```

### 1.4 Add Starlette Router Composition

**File**: `src/codeweaver/server/app.py` (new file)

```python
"""
ASGI application composition combining FastMCP with health endpoints.

Separates MCP protocol handling from observability/monitoring routes.
"""

from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse

from codeweaver.server.server import build_app as build_mcp_app
from codeweaver.services.coordinator import IndexingCoordinator


# Health check endpoints (independent of MCP)
async def get_health(request):
    """Health check endpoint for load balancers."""
    coordinator = await IndexingCoordinator.get_instance()

    # Basic health: coordinator is alive
    return JSONResponse({
        "status": "healthy",
        "active_projects": len(coordinator.projects)
    })


async def get_status(request):
    """Detailed status endpoint for monitoring."""
    coordinator = await IndexingCoordinator.get_instance()

    project_stats = {}
    for project_path, project in coordinator.projects.items():
        stats = project.indexer.stats if project.indexer else None
        project_stats[str(project_path)] = {
            "indexed_chunks": stats.indexed_chunks if stats else 0,
            "last_accessed": project.last_accessed,
            "background_task_running": (
                project.background_task and not project.background_task.done()
            )
        }

    return JSONResponse({
        "status": "running",
        "projects": project_stats
    })


async def lifespan(app: Starlette):
    """Manage application lifecycle."""
    # Initialize coordinator singleton
    coordinator = await IndexingCoordinator.get_instance()
    app.state.coordinator = coordinator

    yield

    # Cleanup on shutdown
    await coordinator.shutdown()


def create_app():
    """Create composed ASGI application."""

    # Build FastMCP app (existing logic)
    mcp_app = build_mcp_app()

    # Compose with Starlette router
    app = Starlette(
        routes=[
            # MCP protocol on /mcp prefix
            Mount('/mcp', app=mcp_app),

            # Health/status endpoints at root level
            Route('/health', get_health),
            Route('/status', get_status),
            Route('/', get_health),  # Default route
        ],
        lifespan=lifespan,
    )

    return app
```

**Update** `src/codeweaver/main.py`:

**Current**:
```python
def run():
    app = build_app()  # FastMCP app
    start_server(app)
```

**New**:
```python
def run():
    from codeweaver.server.app import create_app
    app = create_app()  # Composed ASGI app
    start_server(app)

def start_server(app):
    """Start uvicorn server with composed app."""
    # Change: app is now Starlette, not FastMCP
    # FastMCP is mounted at /mcp

    # Update uvicorn call if needed
    import uvicorn
    uvicorn.run(
        app,
        host=settings.get("server.host", "127.0.0.1"),
        port=settings.get("server.port", 9328),
        # ... other uvicorn config
    )
```

---

## Phase 2: stdio Support (1 week)

### 2.1 Add stdio Read-Only Mode

**File**: `src/codeweaver/server/stdio_adapter.py` (new file)

```python
"""
Lightweight stdio adapter for read-only access.

stdio instances connect to main coordinator but don't perform indexing.
Designed for legacy client compatibility only.
"""

import asyncio
from pathlib import Path

from codeweaver.services.coordinator import IndexingCoordinator


class StdioReadOnlyAdapter:
    """
    stdio MCP server with read-only vector store access.

    Limitations:
    - No background indexing
    - No file watching
    - Search-only capabilities

    Connects to shared coordinator for indexer access.
    """

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.coordinator: Optional[IndexingCoordinator] = None

    async def initialize(self):
        """Connect to shared coordinator."""
        self.coordinator = await IndexingCoordinator.get_instance()

        # Pre-check: indexer must exist (created by HTTP server)
        if self.project_path not in self.coordinator.projects:
            raise RuntimeError(
                "stdio requires HTTP server to be running first. "
                "Start HTTP server, wait for indexing, then use stdio."
            )

    async def search(self, query: str, **kwargs):
        """Execute search via coordinator."""
        return await self.coordinator.search(
            self.project_path,
            query,
            **kwargs
        )

    async def handle_request(self, request):
        """
        Handle MCP request with read-only semantics.

        Rejects any write operations (index, reindex, update).
        """
        if request.method in ['index', 'reindex', 'update', 'watch']:
            return {
                "error": {
                    "code": -32601,
                    "message": (
                        "Method not supported in stdio mode. "
                        "stdio is read-only. Use HTTP transport for full functionality."
                    )
                }
            }

        # Only search operations allowed
        if request.method == 'find_code':
            result = await self.search(
                query=request.params.get('query'),
                **request.params
            )
            return {"result": result}

        return {"error": {"code": -32601, "message": "Method not found"}}
```

### 2.2 Update Configuration Validation

**File**: `src/codeweaver/config/mcp.py`

```python
def validate_mcp_config(config: MCPConfig) -> None:
    """
    Validate MCP configuration and warn about stdio limitations.
    """
    if config.transport == "stdio":
        logger.warning(
            "⚠️  stdio transport detected. Important limitations:\n"
            "   - Read-only mode (no background indexing)\n"
            "   - Requires HTTP server running first\n"
            "   - Degraded performance compared to HTTP\n"
            "   - Recommended: Use 'streamable-http' instead"
        )

        # Check if HTTP server is reachable
        import httpx
        try:
            response = httpx.get("http://127.0.0.1:9328/health", timeout=2.0)
            if response.status_code != 200:
                raise RuntimeError(
                    "HTTP server not healthy. stdio requires HTTP server."
                )
        except Exception as e:
            logger.error(
                f"Cannot connect to HTTP server: {e}\n"
                f"Start HTTP server first: codeweaver server --transport streamable-http"
            )
            raise
```

### 2.3 Update Documentation

**File**: `README.md`

Add section:

```markdown
## Transport Protocols

CodeWeaver supports two MCP transport protocols:

### HTTP (Recommended) ✅

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

**Benefits**:
- Full functionality (indexing, search, file watching)
- Better performance (connection pooling, HTTP/2)
- Multiple clients share single server instance
- Real-time file change detection

### stdio (Limited Support) ⚠️

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

**Limitations**:
- **Read-only mode** (search only, no indexing)
- **Requires HTTP server running** (creates index first)
- Spawns separate process per client (resource overhead)
- No file watching (stale results if code changes)

**When to use**:
- Legacy MCP clients that only support stdio
- Temporary compatibility during migration

**Recommendation**: Migrate to HTTP transport for production use.
```

---

## Phase 3: Testing & Validation (1 week)

### 3.1 Integration Tests

**File**: `tests/integration/test_server_separation.py`

```python
import pytest
import httpx
from pathlib import Path


@pytest.mark.asyncio
async def test_http_server_creates_indexer():
    """Verify HTTP server initializes coordinator and indexer."""
    async with httpx.AsyncClient() as client:
        # Health check should succeed
        response = await client.get("http://127.0.0.1:9328/health")
        assert response.status_code == 200

        # Status should show active project
        response = await client.get("http://127.0.0.1:9328/status")
        data = response.json()
        assert len(data["projects"]) > 0


@pytest.mark.asyncio
async def test_multiple_http_clients_share_indexer():
    """Verify multiple HTTP clients use same indexer instance."""
    # Simulate 4 concurrent clients
    async with httpx.AsyncClient() as client:
        # All should succeed without creating duplicate indexers
        results = await asyncio.gather(
            client.post("/mcp/find_code", json={"query": "authentication"}),
            client.post("/mcp/find_code", json={"query": "database"}),
            client.post("/mcp/find_code", json={"query": "api"}),
            client.post("/mcp/find_code", json={"query": "security"}),
        )

        # All should return results
        assert all(r.status_code == 200 for r in results)

    # Check only one indexer was created
    response = await client.get("http://127.0.0.1:9328/status")
    data = response.json()
    assert len(data["projects"]) == 1  # Single project


@pytest.mark.asyncio
async def test_stdio_read_only_enforcement():
    """Verify stdio adapter rejects write operations."""
    # Start stdio adapter
    adapter = StdioReadOnlyAdapter(Path("/tmp/test-project"))
    await adapter.initialize()

    # Search should work
    result = await adapter.handle_request({
        "method": "find_code",
        "params": {"query": "test"}
    })
    assert "error" not in result

    # Index should be rejected
    result = await adapter.handle_request({
        "method": "index",
        "params": {}
    })
    assert "error" in result
    assert "read-only" in result["error"]["message"].lower()
```

### 3.2 Performance Benchmarks

**File**: `tests/benchmarks/test_coordinator_overhead.py`

```python
import time
import pytest


@pytest.mark.benchmark
async def test_coordinator_latency():
    """Measure coordinator overhead vs direct indexer access."""

    # Baseline: Direct indexer
    indexer = await Indexer.from_settings_async()
    start = time.perf_counter()
    for _ in range(100):
        await indexer.search("test query")
    direct_time = time.perf_counter() - start

    # Coordinator-mediated access
    coordinator = await IndexingCoordinator.get_instance()
    start = time.perf_counter()
    for _ in range(100):
        await coordinator.search(Path("/tmp/project"), "test query")
    coordinator_time = time.perf_counter() - start

    # Overhead should be minimal (< 5%)
    overhead = (coordinator_time - direct_time) / direct_time
    assert overhead < 0.05, f"Coordinator overhead too high: {overhead:.1%}"
```

---

## Migration Checklist

### Pre-Migration

- [ ] Review all `state.indexer` references in codebase
- [ ] Identify CLI commands that use indexer directly
- [ ] Document current startup flow for comparison
- [ ] Create test project for validation

### Development

- [ ] Create `IndexingCoordinator` class with tests
- [ ] Refactor `AppState` to use coordinator
- [ ] Update `_initialize_app_state` function
- [ ] Modify `_run_background_indexing` logic
- [ ] Create Starlette router composition
- [ ] Update `main.py` startup
- [ ] Add stdio adapter (optional Phase 2)
- [ ] Update configuration validation

### Testing

- [ ] Unit tests for coordinator singleton
- [ ] Integration tests for multi-client scenarios
- [ ] Performance benchmarks (coordinator overhead)
- [ ] stdio adapter read-only enforcement tests
- [ ] Resource consumption validation (memory, CPU)

### Documentation

- [ ] Update README with transport comparison
- [ ] Add architecture diagrams (ASCII)
- [ ] Document coordinator API
- [ ] Create migration guide for users
- [ ] Update server.json with correct protocol info

### Deployment

- [ ] Update Docker Compose configuration
- [ ] Test deployment in WSL environment
- [ ] Validate systemd service configuration (if used)
- [ ] Update CI/CD pipeline tests
- [ ] Create rollback plan

### Post-Migration Validation

- [ ] Monitor resource usage (memory should be 75% lower with 4 clients)
- [ ] Verify no duplicate indexing operations
- [ ] Check vector store for duplicate entries
- [ ] Validate checkpoint/manifest consistency
- [ ] Test graceful shutdown behavior

---

## Risk Mitigation

### High-Risk Areas

1. **Coordinator Singleton Thread Safety**
   - Risk: Race conditions in `get_instance()`
   - Mitigation: Use `asyncio.Lock()` around initialization
   - Validation: Stress test with 100 concurrent calls

2. **Background Task Lifecycle**
   - Risk: Tasks not cleaned up properly on shutdown
   - Mitigation: Track all tasks in `background_tasks` set
   - Validation: Monitor for leaked tasks in long-running tests

3. **Backward Compatibility**
   - Risk: Breaking existing HTTP deployments
   - Mitigation: Make coordinator transparent (same interface)
   - Validation: Run full test suite against new implementation

### Rollback Plan

If critical issues discovered:

1. **Immediate**: Revert `main.py` to directly use `build_app()`
2. **Short-term**: Keep coordinator code but disable via feature flag
3. **Long-term**: Gradual migration via opt-in configuration

---

## Success Metrics

### Performance Targets

| Metric | Current (4 HTTP clients) | Target (with coordinator) |
|--------|--------------------------|---------------------------|
| Memory usage | 960MB (4× indexers) | 240MB (1× indexer) |
| Startup time | 30s per instance | 30s total (shared) |
| API calls (initial index) | 10K × 4 = 40K | 10K (no duplication) |
| Duplicate vector entries | High (race conditions) | Zero (coordinated writes) |

### Functional Requirements

- [ ] Single indexer per project path
- [ ] Multiple HTTP clients share indexer
- [ ] Background indexing runs once
- [ ] File watcher coordinates changes
- [ ] Graceful shutdown preserves checkpoints
- [ ] stdio adapter enforces read-only
- [ ] Health endpoints report accurate status

---

## Timeline Summary

**Total Estimated Time**: 3-4 weeks

- **Week 1-2**: Core coordinator implementation and testing
- **Week 3**: stdio adapter and documentation
- **Week 4**: Integration testing and deployment preparation

**First Deliverable** (End of Week 2):
- Working coordinator with HTTP transport
- Single indexer guarantee verified
- Resource consumption validated

**Final Deliverable** (End of Week 4):
- Full stdio support (read-only)
- Comprehensive documentation
- Production-ready deployment
