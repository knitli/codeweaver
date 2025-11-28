<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Implementation Plan Analysis: Architecture Review

**Date**: 2025-01-28
**Reviewer**: Claude (Sonnet 4.5)
**Plan**: `/home/knitli/codeweaver/claudedocs/option-a-service-implementation-plan-revised.md`

## Executive Summary

The implementation plan proposes a sound **same-process separation** architecture that aligns well with CodeWeaver's existing patterns. However, there are **critical middleware architecture misunderstandings** and **state management opportunities** that need addressing before implementation.

**Key Findings**:
- ✅ **AppState → BackgroundState extraction**: Well-aligned with existing patterns
- ⚠️ **Middleware confusion**: Plan conflates Starlette middleware with FastMCP middleware
- ✅ **Management server separation**: Good architectural decision (port 9329)
- ⚠️ **State management**: Missing opportunity to repurpose AppState for background services
- ✅ **Cross-platform approach**: HTTP-first is correct
- ⚠️ **Telemetry flow**: Needs FastMCP middleware, not Starlette middleware

---

## 1. Server/Background Services Division

### Current Architecture Analysis

**Current State** (`server.py:92-154`):
```python
@dataclass
class AppState(DataclassSerializationMixin):
    """Application state for CodeWeaver server."""

    initialized: bool = False
    settings: CodeWeaverSettings | None
    provider_registry: ProviderRegistry
    services_registry: ServicesRegistry
    model_registry: ModelRegistry
    statistics: SessionStatistics
    middleware_stack: tuple[Middleware, ...]
    indexer: Indexer | None = None
    health_service: HealthService | None = None
    failover_manager: VectorStoreFailoverManager | None = None
    startup_time: float
```

**Current Lifespan** (`server.py:489-592`):
```python
@asynccontextmanager
async def lifespan(app: FastMCP[AppState], ...):
    # Startup
    state = _initialize_app_state(app, settings, statistics)
    indexing_task = asyncio.create_task(_run_background_indexing(...))

    # Health checks
    health_response = await state.health_service.get_health_response()

    yield state

    # Shutdown
    await _cleanup_state(state, indexing_task, ...)
```

### ✅ Recommendation: Repurpose AppState for Background Services

**Your insight is correct**: AppState is 90% background services already. Instead of creating a new `BackgroundState` class, **repurpose the existing `AppState`** for background services.

**Proposed Architecture**:

```python
# src/codeweaver/server/background/state.py
@dataclass
class BackgroundState(DataclassSerializationMixin):
    """
    Background services state (formerly AppState).

    Manages lifecycle of long-running background tasks independent of
    MCP protocol concerns.
    """
    initialized: bool = False
    provider_registry: ProviderRegistry  # Keep existing
    services_registry: ServicesRegistry   # Keep existing
    model_registry: ModelRegistry        # Keep existing
    statistics: SessionStatistics        # Keep existing
    indexer: Indexer | None = None       # Keep existing
    health_service: HealthService | None = None  # Keep existing
    failover_manager: VectorStoreFailoverManager | None = None  # Keep existing
    startup_time: float

    # NEW: Management server reference
    management_server: ManagementServer | None = None

    # NEW: Background task tracking
    background_tasks: set[asyncio.Task] = field(default_factory=set)
    shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)
```

```python
# src/codeweaver/server/mcp/state.py (NEW - lightweight)
@dataclass
class McpServerState:
    """
    Lightweight MCP server state.

    Holds only MCP-specific concerns, references BackgroundState.
    """
    background: BackgroundState  # Reference to background services
    transport: Literal["stdio", "streamable-http"]
    mcp_host: str | None = None
    mcp_port: int | None = None

    @property
    def statistics(self) -> SessionStatistics:
        """Proxy to background statistics."""
        return self.background.statistics

    @property
    def indexer(self) -> Indexer | None:
        """Proxy to background indexer."""
        return self.background.indexer
```

**Benefits**:
1. **Minimal Disruption**: Reuses existing, well-tested AppState structure
2. **Clear Separation**: MCP state is lightweight, background state is heavy
3. **Type Safety**: Existing type hints and validation remain intact
4. **Migration Path**: Rename AppState → BackgroundState, create new lightweight McpServerState

---

## 2. Middleware Architecture: Critical Clarification Needed

### ⚠️ **Major Issue**: Plan Conflates Two Distinct Middleware Systems

The plan proposes using **Starlette middleware** for passing state between layers:

**Plan's Proposal** (line 630-644):
```python
class BackgroundStateMiddleware(BaseHTTPMiddleware):
    """Middleware to inject background state into MCP Context."""

    async def dispatch(self, request, call_next):
        request.state.background = request.app.state.background
        request.state.statistics = request.app.state.background.statistics
        response = await call_next(request)
        return response
```

### 🔴 **Problem**: This is the Wrong Middleware Layer

CodeWeaver currently uses **two middleware systems**:

1. **FastMCP Middleware** (`fastmcp.server.middleware.Middleware`)
   - Wraps MCP protocol operations (`on_call_tool`, `on_read_resource`, etc.)
   - Has access to `MiddlewareContext` with `fastmcp_context` and `request_context`
   - **This is where telemetry should live**

2. **Starlette Middleware** (`starlette.middleware.base.BaseHTTPMiddleware`)
   - Wraps HTTP requests/responses
   - Only relevant for HTTP transport mode
   - **Does NOT see MCP protocol operations in stdio mode**

### Current Middleware Usage

**FastMCP Middleware** (`middleware/statistics.py:50-268`):
```python
class StatisticsMiddleware(Middleware):
    """Middleware to track request statistics and performance metrics."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, CallToolResult],
    ) -> CallToolResult:
        """Handle incoming requests and track statistics."""
        start_time = time.perf_counter()
        request_id = context.fastmcp_context.request_id

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.statistics.add_successful_request(request_id=request_id)
            self.timing_statistics.update("on_call_tool_requests", duration_ms, ...)
        except Exception:
            # Track failure
            raise

        return result
```

**This is already correct!** The existing `StatisticsMiddleware` is FastMCP middleware.

### ✅ Solution: Use FastMCP Middleware, Not Starlette Middleware

**For Telemetry** (already implemented correctly):
```python
# Keep existing StatisticsMiddleware (FastMCP middleware)
# It already tracks find_code telemetry via on_call_tool hook

class StatisticsMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        # Already captures:
        # 1. Request timing
        # 2. Success/failure tracking
        # 3. Tool-specific metrics
        ...
```

**For State Access** (use Context injection, not middleware):
```python
# src/codeweaver/server/mcp_server.py

@mcp.tool()
async def find_code(
    query: str,
    *,
    context: Context,  # FastMCP automatically injects this
) -> dict:
    # Access background state via context
    background_state = context.request_context.app.state.background

    # Use background services
    indexer = background_state.indexer
    statistics = background_state.statistics
    ...
```

### Information Flow (Corrected)

**What needs to flow**:

1. **Telemetry**: find_code → telemetry service
   - ✅ **Already handled** by `StatisticsMiddleware` (FastMCP middleware)
   - Captures timing, success/failure, request IDs
   - No changes needed

2. **Queries**: find_code → embedding/vector/reranking services
   - ✅ **Already handled** via `ProviderRegistry` in `BackgroundState`
   - Accessed via `context.request_context.app.state.background`

3. **Search Results**: services → find_code
   - ✅ **Already handled** via return values
   - No middleware needed

4. **Status Information**: services → find_code
   - ✅ **Already handled** via `HealthService` and failover manager
   - Already accessible in `app_bindings.py:127-139`

### 🎯 **Recommendation**: Remove Starlette Middleware from Plan

**What to do**:
1. ❌ **Remove**: `BackgroundStateMiddleware(BaseHTTPMiddleware)` (lines 630-644)
2. ✅ **Keep**: Existing `StatisticsMiddleware` (FastMCP middleware)
3. ✅ **Add**: Expand `StatisticsMiddleware.on_call_tool` if needed for additional metrics
4. ✅ **Document**: How to access `BackgroundState` via `Context` parameter

**Example Enhancement** (if more telemetry needed):
```python
# src/codeweaver/middleware/statistics.py (enhance existing)

class StatisticsMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        start_time = time.perf_counter()
        tool_name = context.message.name

        # NEW: Access background state for additional context
        background_state = context.request_context.app.state.background

        # NEW: Capture pre-execution state
        if background_state.failover_manager:
            failover_active = background_state.failover_manager.is_failover_active

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Existing telemetry
            self.statistics.add_successful_request(...)
            self.timing_statistics.update(...)

            # NEW: Enhanced telemetry (if needed)
            if tool_name == "find_code":
                self.statistics.track_find_code_execution(
                    duration_ms=duration_ms,
                    failover_active=failover_active,
                    result_count=len(result.get("results", [])),
                )

            return result
        except Exception:
            # Track failure with context
            self.statistics.add_failed_request(...)
            raise
```

---

## 3. Lifespan Management: Stacking Approach

### Current Plan's Approach

**Plan Proposal** (lines 563-593):
```python
def wrap_mcp_lifespan(mcp_app, background_lifespan_func):
    """Wrap FastMCP lifespan with background services lifespan."""

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

            yield
            # Exit happens automatically via AsyncExitStack

    return combined_lifespan
```

### ✅ **Assessment**: Correct Pattern for Starlette

This follows the correct Starlette `AsyncExitStack` pattern. However, there are implementation details to clarify.

### 🔧 **Refinement Needed**: Integration with FastMCP

FastMCP already has its own lifespan management. The plan needs to clarify:

**Question 1**: Does FastMCP expose `_lifespan_context`?
- Need to verify FastMCP internal API
- Alternative: Use FastMCP's public `lifespan` parameter

**Question 2**: Who owns the `app.state`?
- Background lifespan sets `app.state.background`
- Does FastMCP lifespan expect `app.state` to be something else?

### ✅ **Recommended Approach**

**Option A: Single Lifespan (Simpler)**
```python
# src/codeweaver/server/lifespan.py

@asynccontextmanager
async def combined_lifespan(app: FastMCP):
    """Unified lifespan for background services + MCP server."""

    # 1. Initialize background services
    background_state = BackgroundState()
    await background_state.initialize()
    await background_state.start_background_indexing()

    # 2. Start management server (always HTTP, port 9329)
    await background_state.management_server.start(host="127.0.0.1", port=9329)

    # 3. Attach to app state
    app.state.background = background_state

    try:
        # Server runs here
        yield
    finally:
        # Cleanup
        await background_state.shutdown()
```

**Option B: Stacked Lifespan (More Flexible)**
```python
@asynccontextmanager
async def background_lifespan(app):
    """Background services lifespan (inner layer)."""
    background_state = BackgroundState()
    await background_state.initialize()
    app.state.background = background_state

    try:
        yield background_state
    finally:
        await background_state.shutdown()


@asynccontextmanager
async def mcp_lifespan(app):
    """MCP server lifespan (outer layer)."""
    async with background_lifespan(app):
        # Additional MCP-specific setup if needed
        yield


# Usage
mcp = FastMCP("CodeWeaver", lifespan=mcp_lifespan)
```

**Recommendation**: Use **Option A (Single Lifespan)** unless there's a specific need for separate contexts.

---

## 4. Management Server Separation (Port 9329)

### ✅ **Assessment**: Excellent Architectural Decision

**Benefits**:
1. **Transport Independence**: Available in both stdio and HTTP modes
2. **Clean Separation**: Observability ≠ MCP protocol
3. **Port Allocation**: 9328 (MCP), 9329 (Management) - no conflicts
4. **Monitoring**: Always accessible at http://127.0.0.1:9329

### Current HTTP Endpoints (`app_bindings.py:164-249`)

**Already Implemented**:
- `/metrics` - `stats_info()` - SessionStatistics
- `/settings` - `settings_info()` - Configuration (redacted)
- `/version` - `version_info()` - Version string
- `/state` - `state_info()` - Full AppState dump
- `/health` - `health()` - HealthService response

### 🔧 **Recommendation**: Reuse, Don't Rewrite

The plan proposes creating new endpoint handlers in `ManagementServer` that delegate to `app_bindings.py`:

**Plan's Approach** (lines 171-243):
```python
class ManagementServer:
    async def health(self, request):
        from codeweaver.server.app_bindings import health
        request.app.state.background = self.background_state
        return await health(request)

    async def status_info(self, request):
        from codeweaver.server.app_bindings import status_info
        ...
```

**Issue**: This adds indirection without benefit.

**Better Approach**: Direct Starlette route registration
```python
# src/codeweaver/server/background/management.py

from codeweaver.server.app_bindings import (
    health,
    stats_info,
    settings_info,
    version_info,
    state_info,
)

class ManagementServer:
    def create_app(self) -> Starlette:
        """Create Starlette app with management routes."""

        routes = [
            Route("/health", health, methods=["GET"]),
            Route("/metrics", stats_info, methods=["GET"]),
            Route("/version", version_info, methods=["GET"]),
            Route("/settings", settings_info, methods=["GET"]),
            Route("/state", state_info, methods=["GET"]),
        ]

        app = Starlette(routes=routes)

        # Attach background state to app for handlers to access
        app.state.background = self.background_state

        return app
```

**Benefits**:
- No wrapper functions needed
- Reuses existing, tested endpoint logic
- Handlers already use `get_state()` to access AppState
- `@timed_http` decorators already applied

---

## 5. Cross-Platform Support

### ✅ **Assessment**: HTTP-First is Correct

**Plan's Strategy**:
- Primary: HTTP (works everywhere)
- Optional: Unix sockets (Linux/macOS optimization)
- Fallback: Always available

**This is the right approach** for CodeWeaver's cross-platform goals.

### Minor Refinement: Unix Socket Consideration

**Plan includes** (`transport.py:1320-1382`):
```python
def select_optimal_transport(
    unix_socket_path: Path | None,
    fallback_to_http: bool = True
) -> tuple[str, str | Path]:
    ...
```

**Question**: Is Unix socket optimization worth the complexity?

**Recommendation**: **Start HTTP-only, add Unix socket later if needed**

**Rationale**:
1. HTTP latency is negligible for CodeWeaver's use case (semantic search dominates)
2. Unix sockets add testing complexity (platform-specific)
3. Docker deployments don't benefit from Unix sockets
4. Can add later without breaking changes

**Simplified Approach**:
```python
# Phase 1 (alpha.2): HTTP only
server_config = {
    "mcp_host": "127.0.0.1",
    "mcp_port": 9328,
    "management_host": "127.0.0.1",
    "management_port": 9329,
}

# Phase 2 (alpha.3+): Add Unix socket support if latency profiling shows benefit
```

---

## 6. Configuration Structure

### Current Settings Structure

**Plan Proposes**: Extend `IndexerSettings` with `BackgroundServicesSettings`

**Current Structure** (inferred from `server.py`):
```python
class CodeWeaverSettings(BasedModel):
    project_path: Path
    config_file: Path | Unset
    logging: LoggingSettings
    middleware: MiddlewareOptions
    server: ServerSettings  # ← Current server settings
    indexer: IndexerSettings
    # ... other settings
```

### ✅ **Recommendation**: Extend ServerSettings, Not IndexerSettings

**Rationale**:
- Background services are **server lifecycle concerns**, not indexer concerns
- Indexer is just one of many background services (health, stats, failover)
- ServerSettings already exists and manages server lifecycle

**Proposed Structure**:
```python
# src/codeweaver/config/server.py

class ServerSettings(BasedModel):
    """MCP server settings."""

    # MCP server (HTTP mode)
    host: str = "127.0.0.1"
    port: int = 9328
    transport: Literal["stdio", "streamable-http"] = "streamable-http"

    # Management server (always HTTP)
    management_host: str = "127.0.0.1"
    management_port: int = 9329

    # Background services
    auto_index_on_startup: bool = True
    file_watching_enabled: bool = True
    health_check_interval_seconds: int = 30
    statistics_enabled: bool = True
```

**Configuration File**:
```toml
[server]
# MCP server
host = "127.0.0.1"
port = 9328
transport = "streamable-http"

# Management server
management_host = "127.0.0.1"
management_port = 9329

# Background services
auto_index_on_startup = true
file_watching_enabled = true
health_check_interval_seconds = 30
statistics_enabled = true
```

**Benefits**:
- Logical grouping: All server lifecycle settings in one place
- Clear separation: Server settings ≠ Indexer settings
- Easier discovery: Users look in `[server]` for server config

---

## 7. State Access Patterns

### Current Pattern (Correct)

**From `app_bindings.py:100-104`**:
```python
from codeweaver.server.server import get_state

state = get_state()  # Returns AppState
if state.failover_manager and context:
    state.failover_manager.set_context(context)
```

### Proposed Pattern (After Refactor)

**From `find_code` tool**:
```python
@mcp.tool()
async def find_code(
    query: str,
    *,
    context: Context,
) -> dict:
    # Option 1: Via Context (recommended for tools)
    background_state = context.request_context.app.state.background

    # Option 2: Via global getter (for non-tool code)
    from codeweaver.server.background.state import get_background_state
    background_state = get_background_state()

    # Use background services
    indexer = background_state.indexer
    statistics = background_state.statistics
    failover_manager = background_state.failover_manager

    # Execute query
    response = await find_code_impl(query, indexer, ...)

    return response.model_dump()
```

**From HTTP endpoints** (management server):
```python
@timed_http("health")
async def health(request: Request) -> PlainTextResponse:
    # Access via request.app.state
    background_state = request.app.state.background

    health_response = await background_state.health_service.get_health_response()
    return PlainTextResponse(content=health_response.model_dump_json())
```

### ✅ **Recommendation**: Use Context Injection for Tools

**Pattern**:
1. **Tools**: Access via `context.request_context.app.state.background`
2. **HTTP Endpoints**: Access via `request.app.state.background`
3. **Global Getter**: Fallback for code without request context

---

## 8. Implementation Priorities

### Phase 1: Core Refactoring (Week 1)

**Priority 1: Rename and Reorganize State**
- [ ] Rename `AppState` → `BackgroundState`
- [ ] Move to `src/codeweaver/server/background/state.py`
- [ ] Update all imports and references
- [ ] Add `background_tasks` and `shutdown_event` fields

**Priority 2: Create Management Server**
- [ ] Create `ManagementServer` class
- [ ] Reuse existing endpoint handlers from `app_bindings.py`
- [ ] Start on port 9329 (always HTTP)
- [ ] Test endpoints with background state

**Priority 3: Update Lifespan**
- [ ] Consolidate into single `combined_lifespan()`
- [ ] Initialize `BackgroundState`
- [ ] Start background indexing
- [ ] Start management server
- [ ] Attach to `app.state.background`

### Phase 2: Configuration and CLI (Week 2)

**Priority 1: Update ServerSettings**
- [ ] Add `management_host` and `management_port`
- [ ] Add background service flags (auto_index, file_watching, etc.)
- [ ] Update `config.toml` schema

**Priority 2: CLI Commands**
- [ ] Implement `cw start` (background services only)
- [ ] Implement `cw stop` (graceful shutdown)
- [ ] Update `cw server` (auto-start services if not running)
- [ ] Update `cw status` (show services + index)

### Phase 3: Testing and Documentation (Week 3-4)

**Priority 1: Integration Tests**
- [ ] Test background services lifecycle
- [ ] Test management server independence (stdio mode)
- [ ] Test auto-start behavior
- [ ] Test graceful shutdown

**Priority 2: Documentation**
- [ ] Architecture documentation
- [ ] CLI command guide
- [ ] Migration guide from alpha.1

---

## 9. Critical Questions to Resolve

### Q1: Middleware Telemetry Flow

**Question**: Should telemetry be expanded in `StatisticsMiddleware`, or keep it in `find_code()` directly?

**Current** (`app_bindings.py:114-125`):
```python
# Inside find_code_tool()
if context:
    request_id = request_context.request_id
    statistics().add_successful_request(request_id)
```

**Alternative** (expand `StatisticsMiddleware`):
```python
class StatisticsMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        # Capture ALL telemetry here, not in tool
        start_time = time.perf_counter()

        result = await call_next(context)

        # Telemetry happens here automatically
        ...
```

**Recommendation**: **Move telemetry to `StatisticsMiddleware`**
- Cleaner separation: Tool logic ≠ telemetry
- Consistent: All MCP operations tracked the same way
- Already partially implemented (timing is already there)

### Q2: Management Server Shutdown Endpoint

**Question**: Plan mentions `/shutdown` endpoint (line 792-804), but is this safe?

**Security Concern**: Unauthenticated shutdown endpoint is risky.

**Recommendation**: **Use signal-based shutdown instead**
```python
# Instead of HTTP endpoint
async def stop_background_services():
    """Stop via management server health check + signal."""

    # Send SIGTERM to process
    import signal
    os.kill(os.getpid(), signal.SIGTERM)
```

**Alternative**: Add authentication if HTTP shutdown is needed
```python
@require_auth_token
async def shutdown(request: Request):
    """Shutdown endpoint (requires auth token)."""
    ...
```

### Q3: Indexer Auto-Start Timing

**Question**: When should auto-indexing start?

**Options**:
1. **On server startup** (current behavior)
2. **On first `find_code` call** (lazy)
3. **On explicit `cw index` command** (manual)

**Current Plan**: Option 1 (auto on startup)

**Recommendation**: **Keep Option 1, add flag to disable**
```toml
[server]
auto_index_on_startup = true  # Default: true for convenience
```

---

## 10. Specific Plan Corrections

### Correction 1: Remove Starlette Middleware

**Lines to Remove**: 630-648

**Reason**: Not needed. Use Context injection instead.

### Correction 2: Simplify Management Server

**Lines to Simplify**: 171-243

**Change**:
```python
# BEFORE (plan's proposal)
async def health(self, request):
    from codeweaver.server.app_bindings import health
    request.app.state.background = self.background_state
    return await health(request)

# AFTER (direct route registration)
def create_app(self) -> Starlette:
    from codeweaver.server.app_bindings import health

    routes = [Route("/health", health, methods=["GET"])]
    app = Starlette(routes=routes)
    app.state.background = self.background_state
    return app
```

### Correction 3: Move Background Settings to ServerSettings

**Lines to Change**: 1159-1200

**Change**:
```python
# BEFORE (plan's proposal)
class IndexerSettings(BasedModel):
    background: BackgroundServicesSettings

# AFTER (recommended)
class ServerSettings(BasedModel):
    # Background services settings directly in ServerSettings
    auto_index_on_startup: bool = True
    file_watching_enabled: bool = True
    ...
```

### Correction 4: Clarify FastMCP Lifespan Integration

**Lines to Clarify**: 563-593

**Add documentation**:
```python
# NOTE: FastMCP's lifespan parameter expects a function with signature:
#   async def lifespan(app: FastMCP) -> AsyncIterator[None]
#
# Our combined_lifespan matches this signature.
```

---

## 11. Architecture Diagram (Corrected)

```
┌─────────────────────────────────────────────────────────┐
│  CodeWeaver Process                                     │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  MCP Server Layer (FastMCP)                        │ │
│  │  - Port 9328 (HTTP mode) or stdio                  │ │
│  │  - ONE TOOL: find_code()                           │ │
│  │  - FastMCP Middleware:                             │ │
│  │    * StatisticsMiddleware (telemetry)              │ │
│  │    * ErrorHandlingMiddleware                       │ │
│  │    * RateLimitingMiddleware                        │ │
│  └────────────────────────────────────────────────────┘ │
│         ↓ Context.request_context.app.state.background   │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Management Server (Separate Uvicorn - Port 9329) │ │
│  │  - Always HTTP (independent of MCP transport)      │ │
│  │  - /health, /metrics, /version, /settings, /state  │ │
│  │  - Accesses BackgroundState via app.state         │ │
│  └────────────────────────────────────────────────────┘ │
│         ↓ Both layers access same BackgroundState        │
│  ┌────────────────────────────────────────────────────┐ │
│  │  BackgroundState (formerly AppState)               │ │
│  │  - ProviderRegistry (singleton)                    │ │
│  │  - Indexer (lazy-loaded)                           │ │
│  │  - FileWatcher                                     │ │
│  │  - HealthService                                   │ │
│  │  - SessionStatistics                               │ │
│  │  - VectorStoreFailoverManager                      │ │
│  │  - ManagementServer (reference)                    │ │
│  │  - background_tasks: set[asyncio.Task]             │ │
│  │  - shutdown_event: asyncio.Event                   │ │
│  └────────────────────────────────────────────────────┘ │
│         ↓ Uses providers                                 │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Provider Layer (ProviderRegistry)                 │ │
│  │  - VectorStore (Qdrant)                            │ │
│  │  - Embedder (Voyage AI)                            │ │
│  │  - Sparse Embedder (local SPLADE)                  │ │
│  │  - Reranker                                        │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
         ↑ MCP Protocol (stdio or HTTP:9328)
         ↑ Management HTTP (always :9329)
┌────────┴────────────┐
│  MCP Clients        │  Monitoring: http://127.0.0.1:9329
│  - Claude Desktop   │  (health, metrics, status)
│  - Cursor           │
└─────────────────────┘
```

**Key Differences from Plan**:
1. **No Starlette middleware** for state passing
2. **FastMCP middleware** handles telemetry
3. **Context injection** for state access
4. **BackgroundState** is renamed AppState, not new class

---

## 12. Summary of Recommendations

### ✅ Keep From Plan
1. Management server on port 9329 (excellent separation)
2. HTTP-first cross-platform approach
3. Same-process architecture with clear boundaries
4. Background indexing and file watching
5. CLI commands (`cw start`, `cw stop`, `cw server`)

### ⚠️ Modify From Plan
1. **State Management**: Rename `AppState` → `BackgroundState`, don't create new class
2. **Middleware**: Remove Starlette middleware, enhance FastMCP `StatisticsMiddleware`
3. **Configuration**: Put background settings in `ServerSettings`, not `IndexerSettings`
4. **Management Server**: Direct route registration, not wrapper methods
5. **Unix Sockets**: Defer to later phase, start HTTP-only

### ❌ Remove From Plan
1. `BackgroundStateMiddleware(BaseHTTPMiddleware)` - not needed
2. `/shutdown` HTTP endpoint - use signal-based shutdown
3. Complex lifespan wrapping - use single unified lifespan

---

## 13. Implementation Checklist (Revised)

### Week 1: Core Architecture
- [ ] Rename `AppState` → `BackgroundState` in `server/background/state.py`
- [ ] Add `background_tasks`, `shutdown_event`, `management_server` fields
- [ ] Create `ManagementServer` class (direct route registration)
- [ ] Create unified `combined_lifespan()` function
- [ ] Update `find_code` to access state via `context.request_context.app.state.background`
- [ ] Test: Background services lifecycle
- [ ] Test: Management server independence (stdio mode)

### Week 2: Configuration and CLI
- [ ] Update `ServerSettings` with management ports and background flags
- [ ] Create `cw start` command (background services)
- [ ] Create `cw stop` command (signal-based shutdown)
- [ ] Update `cw server` (auto-start services)
- [ ] Update `cw status` (services + index)
- [ ] Test: CLI commands end-to-end

### Week 3: Testing and Polish
- [ ] Integration tests for all lifecycle scenarios
- [ ] Cross-platform tests (Linux, macOS, Windows, WSL)
- [ ] Performance benchmarks (startup time, memory usage)
- [ ] Documentation updates

### Week 4: Alpha.2 Release
- [ ] Migration guide from alpha.1
- [ ] Release notes
- [ ] User documentation
- [ ] Alpha.2 tag and release

---

## Conclusion

The plan is **fundamentally sound** but needs **middleware architecture corrections** and **state management simplification**. The biggest wins:

1. **Management server separation** (port 9329) - excellent decision
2. **Reuse existing AppState** as BackgroundState - minimal disruption
3. **FastMCP middleware** for telemetry - already implemented correctly
4. **Context injection** for state access - clean and Pythonic

**Critical Path**:
1. Fix middleware understanding (use FastMCP, not Starlette)
2. Rename AppState → BackgroundState (don't create new class)
3. Move background settings to ServerSettings
4. Implement management server with direct routes
5. Test, document, release

**Risk Assessment**: Low risk if middleware corrections are applied. High risk if Starlette middleware approach is used (won't work in stdio mode).
