<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# FastMCP Deployment Strategies Research Report

## Executive Summary

This report provides comprehensive research on FastMCP deployment patterns, focusing on ASGI composition, multi-protocol support, and architectural approaches for separating indexing services from protocol handlers. The research reveals several viable patterns for building scalable, production-ready MCP servers with shared state management and background service coordination.

**Key Findings:**
- FastMCP supports both STDIO and HTTP transports with fundamentally different lifecycle models
- ASGI composition is possible but requires careful lifespan management
- Multiple architectural patterns exist for separating business logic from protocol handling
- Background services and shared state require specific lifespan coordination patterns
- Multi-protocol support (stdio + HTTP simultaneously) requires separate server instances

---

## 1. ASGI Composition Patterns

### 1.1 Core Architecture

FastMCP servers are built on Starlette, making them fully ASGI-compatible. The framework provides two primary methods for creating ASGI applications:

```python
# Method 1: Direct HTTP server (handles ASGI internally)
mcp.run(transport="http", host="0.0.0.0", port=8000)

# Method 2: ASGI application factory (production recommended)
app = mcp.http_app()
```

**Source:** [HTTP Deployment - FastMCP](https://gofastmcp.com/deployment/http)

### 1.2 Mounting Multiple FastMCP Servers

Multiple FastMCP servers can be composed in a single Starlette/FastAPI application, but **lifespan management is critical**:

#### Pattern A: Combined Lifespan with AsyncExitStack

```python
import contextlib
from starlette.applications import Starlette
from starlette.routing import Mount
from fastmcp import FastMCP

# Create multiple MCP servers
api_mcp = FastMCP("API Server", stateless_http=True, json_response=True)
chat_mcp = FastMCP("Chat Server", stateless_http=True, json_response=True)

@api_mcp.tool()
def api_status() -> str:
    return "API is running"

@chat_mcp.tool()
def send_message(message: str) -> str:
    return f"Message sent: {message}"

# Create combined lifespan to manage both session managers
@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(api_mcp.session_manager.run())
        await stack.enter_async_context(chat_mcp.session_manager.run())
        yield

# Mount servers with combined lifespan
app = Starlette(
    routes=[
        Mount("/api", app=api_mcp.streamable_http_app()),
        Mount("/chat", app=chat_mcp.streamable_http_app()),
    ],
    lifespan=lifespan
)
```

**Key Constraint:** Each FastMCP server has its own lifespan context, but the outer ASGI app can only accept one lifespan parameter. The `AsyncExitStack` pattern solves this by stacking multiple context managers.

**Source:** [GitHub Issue #587 - Combining Multiple HTTP MCP Servers](https://github.com/jlowin/fastmcp/issues/587)

#### Pattern B: Helper Function for Lifespan Combination

```python
import contextlib

def combine_lifespans(*lifespans):
    """Utility to combine multiple ASGI lifespans."""
    @contextlib.asynccontextmanager
    async def combined_lifespan(app):
        async with contextlib.AsyncExitStack() as stack:
            for lifespan in lifespans:
                await stack.enter_async_context(lifespan(app))
            yield
    return combined_lifespan

# Usage
app = Starlette(
    routes=[...],
    lifespan=combine_lifespans(mcp1_app.lifespan, mcp2_app.lifespan)
)
```

**Source:** [GitHub Issue #587](https://github.com/jlowin/fastmcp/issues/587)

### 1.3 Shared State Management Across ASGI Apps

FastMCP provides multiple mechanisms for sharing state between applications:

#### Using Starlette's app.state

```python
from contextlib import asynccontextmanager
import asyncio

def wrap_lifespan_with_background_task(original_lifespan):
    """Wraps FastMCP's existing lifespan to add custom tasks."""
    @asynccontextmanager
    async def combined_lifespan(app):
        async with original_lifespan(app):
            # Startup: Initialize shared resources
            app.state.db_pool = await create_db_pool()
            app.state.indexer = BackgroundIndexer()
            app.state.indexer_task = asyncio.create_task(
                app.state.indexer.run()
            )

            yield  # App runs here

            # Shutdown: Clean up resources
            app.state.indexer.stop()
            app.state.indexer_task.cancel()
            try:
                await asyncio.wait_for(app.state.indexer_task, timeout=5.0)
            except asyncio.CancelledError:
                pass
            await app.state.db_pool.close()

    return combined_lifespan

# Integration
app = mcp.http_app(path="/mcp")
original_lifespan = app.router.lifespan_context
app.router.lifespan_context = wrap_lifespan_with_background_task(original_lifespan)
```

**Source:** [GitHub Discussion #1763 - Working with Lifespan](https://github.com/jlowin/fastmcp/discussions/1763)

#### Using MCP Context for Request-Scoped State

FastMCP's `Context` object provides request-scoped state management via middleware:

```python
from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext

class SharedServiceMiddleware(Middleware):
    """Middleware to inject shared services into request context."""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Access app-level shared state
        app = context.fastmcp_context.request_context.get("app")

        # Inject into request-scoped context
        context.fastmcp_context.set_state("db_pool", app.state.db_pool)
        context.fastmcp_context.set_state("indexer", app.state.indexer)

        return await call_next(context)

mcp = FastMCP("MyServer")
mcp.add_middleware(SharedServiceMiddleware())

@mcp.tool
async def query_data(query: str, ctx: Context) -> str:
    # Access shared service from context
    db_pool = ctx.get_state("db_pool")
    indexer = ctx.get_state("indexer")

    results = await db_pool.execute(query)
    await indexer.index_query(query)

    return str(results)
```

**Important Limitation:** Context state is request-scoped only. As the documentation states: "Each MCP request receives a new context object. Context is scoped to a single request; state or data set in one request will not be available in subsequent requests."

**Source:** [MCP Context - FastMCP](https://gofastmcp.com/servers/context)

### 1.4 Dependency Injection Patterns

FastMCP supports automatic dependency injection via type hints:

```python
from fastmcp import FastMCP, Context

mcp = FastMCP("MyServer")

@mcp.tool
async def process_file(file_uri: str, ctx: Context) -> str:
    """The ctx parameter is automatically injected."""
    await ctx.info(f"Processing {file_uri}")
    return "Processed"

# For code that can't accept Context as parameter
from fastmcp.server.dependencies import get_context

async def helper_function(data: str) -> str:
    ctx = get_context()  # Retrieves active context
    await ctx.info(f"Processing {data}")
    return data.upper()

@mcp.tool
async def use_helper(input: str, ctx: Context) -> str:
    result = await helper_function(input)
    return result
```

**Warning:** `get_context()` only works within a request scope. Outside request handling, it raises `RuntimeError`.

**Source:** [MCP Context - FastMCP](https://gofastmcp.com/servers/context)

---

## 2. Server Deployment Options

### 2.1 Transport Protocol Comparison

| Aspect | STDIO | HTTP (Streamable) | SSE |
|--------|-------|-------------------|-----|
| **Lifecycle** | New process per client | Persistent server | Persistent server |
| **Concurrency** | One client per process | Multiple concurrent clients | Multiple clients |
| **Use Case** | Claude Desktop, CLI tools | Production deployments | Legacy (deprecated) |
| **Communication** | Bidirectional (stdin/stdout) | Full bidirectional | Server-to-client only |
| **Network** | Local only | Network accessible | Network accessible |
| **Session State** | Process-local | Shared via session manager | Limited |

**Source:** [Running Your Server - FastMCP](https://gofastmcp.com/deployment/running-server)

### 2.2 STDIO Deployment Pattern

```python
from fastmcp import FastMCP

mcp = FastMCP("LocalServer")

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()  # Defaults to STDIO transport
```

**Key Characteristics:**
- Each client connection spawns a new process
- No shared state between different client connections
- Ideal for Claude Desktop integration
- Simple, no network configuration needed

**Source:** [Building MCP Servers with FastMCP](https://medium.com/@anil.goyal0057/building-and-exposing-mcp-servers-with-fastmcp-stdio-http-and-sse-ace0f1d996dd)

### 2.3 HTTP Deployment Patterns

#### Development Server (Not Production)

```python
from fastmcp import FastMCP

mcp = FastMCP("HTTPServer")

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
```

Server accessible at `http://localhost:8000/mcp`

#### Production ASGI Deployment

```python
# server.py
from fastmcp import FastMCP

mcp = FastMCP("ProductionServer", stateless_http=True, json_response=True)

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

# ASGI application factory
def create_app():
    return mcp.http_app()

# Create the app instance
app = create_app()

# Run with: uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4
```

**Production Requirements:**
- Use `stateless_http=True` for horizontal scaling
- Enable `json_response=True` for optimal performance
- Deploy with Uvicorn/Gunicorn with multiple workers
- Configure health checks via `@mcp.custom_route()`

**Source:** [HTTP Deployment - FastMCP](https://gofastmcp.com/deployment/http)

### 2.4 Separating Protocol Handling from Business Logic

FastMCP's architecture inherently separates these concerns:

```
┌─────────────────────────────────────────────────┐
│         Protocol Layer (FastMCP Handles)        │
│  • JSON-RPC parsing                             │
│  • Request routing                              │
│  • Error handling                               │
│  • Transport management (STDIO/HTTP/SSE)        │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│         Middleware Layer (Optional)             │
│  • Authentication                               │
│  • Rate limiting                                │
│  • Logging                                      │
│  • Caching                                      │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│         Business Logic Layer (Your Code)        │
│  • Tools (active operations)                    │
│  • Resources (data retrieval)                   │
│  • Prompts (templates)                          │
└─────────────────────────────────────────────────┘
```

**Example: Separating Indexer Logic**

```python
# indexer_service.py - Business logic layer
class IndexerService:
    """Background indexing service - independent of MCP protocol."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.index = {}
        self._task = None

    async def start(self):
        """Start background indexing."""
        self._task = asyncio.create_task(self._index_loop())

    async def stop(self):
        """Stop background indexing."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _index_loop(self):
        """Continuous indexing loop."""
        while True:
            await self._rebuild_index()
            await asyncio.sleep(300)  # Rebuild every 5 minutes

    async def _rebuild_index(self):
        """Rebuild the search index."""
        # Business logic here
        pass

    def search(self, query: str) -> list[dict]:
        """Search the index - synchronous for tool access."""
        return [r for r in self.index.values() if query in r.get("content", "")]


# server.py - Protocol layer
from contextlib import asynccontextmanager
from fastmcp import FastMCP, Context
from indexer_service import IndexerService

@asynccontextmanager
async def lifespan(app):
    """Manage shared services lifecycle."""
    # Startup
    indexer = IndexerService(db_url="postgresql://...")
    await indexer.start()
    app.state.indexer = indexer

    yield

    # Shutdown
    await indexer.stop()

# Create MCP server with custom lifespan
mcp = FastMCP("SearchServer")
app = mcp.http_app()

# Wrap the lifespan
original_lifespan = app.router.lifespan_context

@asynccontextmanager
async def combined_lifespan(app):
    async with original_lifespan(app):
        async with lifespan(app):
            yield

app.router.lifespan_context = combined_lifespan

# MCP tools use the service
@mcp.tool
async def search(query: str, ctx: Context) -> list[dict]:
    """Search the index - protocol layer exposes business logic."""
    # Access shared service from app state
    # (This requires passing app reference through middleware or other means)
    indexer = app.state.indexer
    return indexer.search(query)
```

**Source:** [Building Production-Ready MCP Servers](https://thinhdanggroup.github.io/mcp-production-ready/)

---

## 3. Multi-Protocol Support

### 3.1 Can a Single Server Support Both STDIO and HTTP?

**Short Answer:** No, not in the same process simultaneously. You must choose one transport per server instance.

**Rationale:**
- `mcp.run()` creates an event loop and blocks until shutdown
- STDIO reads from stdin/stdout, which conflicts with HTTP server operation
- Each transport has fundamentally different lifecycle management

**Source:** [Running Your Server - FastMCP](https://gofastmcp.com/deployment/running-server)

### 3.2 Recommended Multi-Protocol Architecture

For services that need to support both STDIO and HTTP, use one of these patterns:

#### Pattern A: Shared Business Logic, Separate Protocol Servers

```
┌─────────────────────────────────────────────────┐
│           Shared Business Logic Layer           │
│  • IndexerService                               │
│  • DatabaseService                              │
│  • SearchService                                │
└────────────────┬────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
┌───────▼─────┐    ┌──────▼──────┐
│ STDIO MCP    │    │  HTTP MCP   │
│ Server       │    │  Server     │
│ (Port: -)    │    │ (Port: 8000)│
└──────────────┘    └─────────────┘
```

```python
# shared_services.py
class IndexerService:
    """Shared business logic - protocol-agnostic."""
    # ... implementation from previous example

# stdio_server.py
from fastmcp import FastMCP
from shared_services import IndexerService

mcp = FastMCP("STDIOServer")
indexer = IndexerService(db_url="postgresql://...")

@mcp.tool
def search(query: str) -> list[dict]:
    return indexer.search(query)

if __name__ == "__main__":
    # Each STDIO connection gets its own process and indexer instance
    asyncio.run(indexer.start())
    try:
        mcp.run()  # STDIO transport
    finally:
        asyncio.run(indexer.stop())

# http_server.py
from fastmcp import FastMCP, Context
from shared_services import IndexerService
from contextlib import asynccontextmanager

@asynccontextmanager
async def app_lifespan(app):
    # Shared indexer for all HTTP clients
    indexer = IndexerService(db_url="postgresql://...")
    await indexer.start()
    app.state.indexer = indexer
    yield
    await indexer.stop()

mcp = FastMCP("HTTPServer")
app = mcp.http_app()

# Setup lifespan wrapper (as shown in previous examples)
# ...

@mcp.tool
async def search(query: str, ctx: Context) -> list[dict]:
    return app.state.indexer.search(query)

# Run with: uvicorn http_server:app --port 8000
```

**Characteristics:**
- Business logic (`IndexerService`) is completely protocol-agnostic
- STDIO server: Each connection gets isolated indexer instance
- HTTP server: Single shared indexer serves all clients
- Choose deployment based on client needs (Claude Desktop = STDIO, API clients = HTTP)

#### Pattern B: HTTP Backend with STDIO Proxy

```
┌──────────────┐         ┌─────────────────┐
│ STDIO Client │──stdin──│  STDIO Wrapper  │
│ (Claude)     │─stdout──│  (Thin Proxy)   │
└──────────────┘         └────────┬────────┘
                                  │ HTTP
                         ┌────────▼────────┐
                         │  HTTP MCP Server│
                         │  with Indexer   │
                         └─────────────────┘
```

```python
# http_backend.py - Main server with business logic
from fastmcp import FastMCP

mcp = FastMCP("BackendServer")
app = mcp.http_app()

# All business logic lives here
# Run with: uvicorn http_backend:app --port 8000

# stdio_proxy.py - Lightweight proxy
import httpx
from fastmcp import FastMCP

BACKEND_URL = "http://localhost:8000/mcp"

proxy_mcp = FastMCP("STDIOProxy")

@proxy_mcp.tool
async def search(query: str) -> list[dict]:
    """Proxy to HTTP backend."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            BACKEND_URL,
            json={"method": "tools/call", "params": {"name": "search", "arguments": {"query": query}}}
        )
        return response.json()["result"]

if __name__ == "__main__":
    proxy_mcp.run()  # STDIO transport
```

**Characteristics:**
- Single source of truth (HTTP backend)
- STDIO wrapper is stateless and lightweight
- All business logic, state, and background services run in HTTP server
- Simplified deployment: Only HTTP server needs complex configuration

**Source:** [FastMCP Multi-Protocol Examples](https://medium.com/@anil.goyal0057/building-and-exposing-mcp-servers-with-fastmcp-stdio-http-and-sse-ace0f1d996dd)

### 3.3 Multiple STDIO Instances and Shared State

**Key Finding:** STDIO instances **cannot** share state across processes.

From the documentation: "With STDIO transport, the client spawns a new server process for each session and manages its lifecycle."

**Implications:**
- Each Claude Desktop connection = separate Python process
- No built-in IPC mechanism between STDIO processes
- Shared state requires external infrastructure (Redis, database, filesystem)

**Workaround for Shared State Across STDIO Instances:**

```python
# stdio_server_with_redis.py
import redis.asyncio as redis
from fastmcp import FastMCP
import json

mcp = FastMCP("SharedSTDIOServer")

# Each process connects to shared Redis
redis_client = redis.from_url("redis://localhost:6379")

@mcp.tool
async def get_shared_data(key: str) -> dict:
    """Read from shared Redis cache."""
    data = await redis_client.get(f"mcp:{key}")
    return json.loads(data) if data else {}

@mcp.tool
async def set_shared_data(key: str, value: dict) -> str:
    """Write to shared Redis cache."""
    await redis_client.set(f"mcp:{key}", json.dumps(value))
    return f"Stored {key}"

if __name__ == "__main__":
    try:
        mcp.run()
    finally:
        asyncio.run(redis_client.close())
```

**Source:** [Building Production-Ready MCP Servers](https://thinhdanggroup.github.io/mcp-production-ready/)

---

## 4. Background Task Coordination with FastMCP

### 4.1 Background Task Management Pattern

```python
from contextlib import asynccontextmanager
import asyncio
from fastmcp import FastMCP, Context

class BackgroundTaskManager:
    """Manages background tasks with proper lifecycle."""

    def __init__(self):
        self.tasks = []
        self._stop_event = asyncio.Event()

    def create_task(self, coro):
        """Create and track a background task."""
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task

    async def stop_all(self, timeout: float = 5.0):
        """Cancel all tasks with timeout."""
        self._stop_event.set()

        for task in self.tasks:
            task.cancel()

        try:
            await asyncio.wait_for(
                asyncio.gather(*self.tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            pass

        self.tasks.clear()

@asynccontextmanager
async def app_lifespan(app):
    """Manage background tasks lifecycle."""
    # Startup
    task_manager = BackgroundTaskManager()
    app.state.task_manager = task_manager

    # Start background tasks
    task_manager.create_task(background_indexer(app))
    task_manager.create_task(background_cleanup(app))

    yield

    # Shutdown
    await task_manager.stop_all()

async def background_indexer(app):
    """Background indexing task."""
    task_manager = app.state.task_manager
    while not task_manager._stop_event.is_set():
        try:
            # Perform indexing work
            await asyncio.sleep(60)  # Index every minute
        except asyncio.CancelledError:
            break

async def background_cleanup(app):
    """Background cleanup task."""
    task_manager = app.state.task_manager
    while not task_manager._stop_event.is_set():
        try:
            # Perform cleanup work
            await asyncio.sleep(300)  # Cleanup every 5 minutes
        except asyncio.CancelledError:
            break

# Integration with FastMCP
mcp = FastMCP("ServerWithBackgroundTasks")
app = mcp.http_app()

# Wrap lifespan
original_lifespan = app.router.lifespan_context

@asynccontextmanager
async def combined_lifespan(app):
    async with original_lifespan(app):
        async with app_lifespan(app):
            yield

app.router.lifespan_context = combined_lifespan

@mcp.tool
async def trigger_index(ctx: Context) -> str:
    """Manually trigger indexing."""
    # Access background service
    # (Would need app reference - see next section)
    return "Indexing triggered"
```

**Source:** [GitHub Discussion #1763 - Working with Lifespan](https://github.com/jlowin/fastmcp/discussions/1763)

### 4.2 Coordinating Tools with Background Services

**Challenge:** Tools need access to `app.state`, but MCP Context doesn't provide direct access.

**Solution: Middleware Bridge Pattern**

```python
from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext

class AppStateMiddleware(Middleware):
    """Bridge app.state into MCP Context."""

    def __init__(self, app):
        super().__init__()
        self.app = app

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Inject app.state into request context
        for key, value in self.app.state._state.items():
            context.fastmcp_context.set_state(key, value)

        return await call_next(context)

# Setup
mcp = FastMCP("CoordinatedServer")
app = mcp.http_app()

# ... lifespan setup with background tasks ...

# Add middleware to bridge app.state
mcp.add_middleware(AppStateMiddleware(app))

@mcp.tool
async def check_index_status(ctx: Context) -> dict:
    """Check background indexer status."""
    task_manager = ctx.get_state("task_manager")
    indexer = ctx.get_state("indexer")

    return {
        "tasks_running": len(task_manager.tasks),
        "index_size": len(indexer.index)
    }
```

**Source:** [MCP Middleware - FastMCP](https://gofastmcp.com/servers/middleware)

---

## 5. Production Deployment Architectures

### 5.1 Redis-Backed Session Management

For horizontal scaling with stateful HTTP connections:

```python
import redis.asyncio as redis
from fastmcp import FastMCP

mcp = FastMCP("ScalableServer", stateless_http=False)

# Configure Redis for session persistence
redis_client = redis.from_url(
    "redis://localhost:6379",
    encoding="utf-8",
    decode_responses=True
)

# Use Redis for OAuth client registration storage
mcp.configure_oauth_storage(
    backend="redis",
    redis_client=redis_client,
    encryption_key="your-fernet-key"  # For production
)

app = mcp.http_app()
```

**Benefits:**
- Session state persists across server restarts
- Multiple server instances can share sessions via Redis
- OAuth client registrations are centrally stored

**Source:** [Building Production-Ready MCP Servers](https://thinhdanggroup.github.io/mcp-production-ready/)

### 5.2 FastAPI Integration Pattern

Combining FastMCP with existing FastAPI applications:

```python
from fastapi import FastAPI
from fastmcp import FastMCP
from contextlib import asynccontextmanager

# Existing FastAPI app
@asynccontextmanager
async def fastapi_lifespan(app: FastAPI):
    # Initialize FastAPI resources
    app.state.db = await init_database()
    yield
    await app.state.db.close()

api_app = FastAPI(lifespan=fastapi_lifespan)

@api_app.get("/health")
async def health():
    return {"status": "healthy"}

# Create MCP server
mcp = FastMCP("IntegratedMCP")

@mcp.tool
def search(query: str) -> list:
    return ["result1", "result2"]

mcp_app = mcp.http_app(path="/mcp")

# Combine lifespans
@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    async with fastapi_lifespan(app):
        async with mcp_app.lifespan(app):
            yield

# Create combined application
combined_app = FastAPI(
    routes=[*mcp_app.routes, *api_app.routes],
    lifespan=combined_lifespan
)
```

**Alternative: Mount as Sub-Application**

```python
from fastapi import FastAPI
from fastmcp import FastMCP

api_app = FastAPI()
mcp = FastMCP("MountedMCP")
mcp_app = mcp.http_app(path="/mcp")

# Mount MCP as sub-application
main_app = FastAPI(lifespan=mcp_app.lifespan)
main_app.mount("/api", api_app)
main_app.mount("/mcp-server", mcp_app)
```

**Critical:** Always pass `mcp_app.lifespan` to the parent app, otherwise the session manager won't initialize.

**Source:** [FastAPI Integration - FastMCP](https://gofastmcp.com/integrations/fastapi)

### 5.3 Production Deployment Checklist

| Component | Configuration | Recommendation |
|-----------|---------------|-----------------|
| **HTTP Mode** | `stateless_http=True` | For horizontal scaling |
| **Response Format** | `json_response=True` | Better performance |
| **Workers** | `uvicorn --workers 4` | CPU count × 2 |
| **Authentication** | OAuth or Bearer tokens | OAuth for production |
| **Health Checks** | `@mcp.custom_route()` | Required for K8s |
| **CORS** | Sub-app level only | Avoid app-wide with OAuth |
| **Session Storage** | Redis with encryption | For stateful deployments |
| **Monitoring** | Middleware-based logging | Structured logs |
| **Error Handling** | Error handling middleware | Centralized exceptions |

**Source:** [HTTP Deployment - FastMCP](https://gofastmcp.com/deployment/http)

---

## 6. Architectural Recommendations

### 6.1 Indexing Service Architecture

**Recommended Pattern: HTTP Backend with Optional STDIO Proxy**

```
┌─────────────────────────────────────────────────────────┐
│                  Background Services Layer               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Indexer    │  │  Embeddings  │  │   Database   │  │
│  │   Service    │  │   Service    │  │   Service    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└───────────────────────────┬─────────────────────────────┘
                            │ Shared via app.state
┌───────────────────────────▼─────────────────────────────┐
│              HTTP MCP Server (Persistent)                │
│  • Runs continuously                                     │
│  • Manages background tasks                              │
│  • Maintains shared state                                │
│  • Serves multiple concurrent clients                    │
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼──────┐   ┌────────▼────────┐   ┌──────▼──────┐
│ HTTP Clients │   │  STDIO Proxy    │   │  Direct API │
│              │   │  (Optional)     │   │             │
└──────────────┘   └─────────────────┘   └─────────────┘
```

**Benefits:**
- Single source of truth for business logic
- Background services run continuously in HTTP server
- STDIO clients can still connect via lightweight proxy
- Horizontal scaling possible with Redis session storage
- Simplified deployment and maintenance

### 6.2 Implementation Template

```python
# indexing_service.py - Business Logic Layer
class IndexingService:
    """Background indexing service with vector embeddings."""

    def __init__(self, db_url: str, embedding_model: str):
        self.db_url = db_url
        self.embedding_model = embedding_model
        self.index = {}
        self._update_queue = asyncio.Queue()
        self._worker_task = None

    async def start(self):
        """Start background indexing worker."""
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        """Gracefully stop background worker."""
        if self._worker_task:
            await self._update_queue.put(None)  # Poison pill
            await self._worker_task

    async def _worker_loop(self):
        """Process indexing queue continuously."""
        while True:
            item = await self._update_queue.get()
            if item is None:  # Shutdown signal
                break

            try:
                await self._index_item(item)
            except Exception as e:
                # Log error, continue processing
                pass
            finally:
                self._update_queue.task_done()

    async def _index_item(self, item: dict):
        """Index a single item with embeddings."""
        # Generate embeddings
        embedding = await self._generate_embedding(item["content"])

        # Store in index
        self.index[item["id"]] = {
            "content": item["content"],
            "embedding": embedding,
            "indexed_at": datetime.now()
        }

    async def queue_for_indexing(self, item: dict):
        """Add item to indexing queue (non-blocking)."""
        await self._update_queue.put(item)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search index (synchronous for tool compatibility)."""
        # Implement vector similarity search
        results = []
        # ... search logic ...
        return results[:limit]


# server.py - Protocol Layer
from contextlib import asynccontextmanager
from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from indexing_service import IndexingService

# Lifespan management
@asynccontextmanager
async def app_lifespan(app):
    # Startup: Initialize services
    app.state.indexer = IndexingService(
        db_url="postgresql://...",
        embedding_model="text-embedding-3-small"
    )
    await app.state.indexer.start()

    yield

    # Shutdown: Clean up
    await app.state.indexer.stop()

# Create MCP server
mcp = FastMCP("IndexingServer", stateless_http=True, json_response=True)
app = mcp.http_app()

# Wrap lifespan
original_lifespan = app.router.lifespan_context

@asynccontextmanager
async def combined_lifespan(app):
    async with original_lifespan(app):
        async with app_lifespan(app):
            yield

app.router.lifespan_context = combined_lifespan

# Middleware to inject services into context
class ServiceMiddleware(Middleware):
    def __init__(self, app):
        super().__init__()
        self.app = app

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        context.fastmcp_context.set_state("indexer", self.app.state.indexer)
        return await call_next(context)

mcp.add_middleware(ServiceMiddleware(app))

# Tools that use the indexing service
@mcp.tool
async def add_document(content: str, metadata: dict, ctx: Context) -> str:
    """Add a document to the index."""
    indexer = ctx.get_state("indexer")

    item = {
        "id": str(uuid.uuid4()),
        "content": content,
        "metadata": metadata
    }

    await indexer.queue_for_indexing(item)
    return f"Document {item['id']} queued for indexing"

@mcp.tool
async def search_documents(query: str, limit: int = 10, ctx: Context) -> list[dict]:
    """Search indexed documents."""
    indexer = ctx.get_state("indexer")
    return indexer.search(query, limit)

@mcp.tool
async def get_index_stats(ctx: Context) -> dict:
    """Get indexing statistics."""
    indexer = ctx.get_state("indexer")
    return {
        "total_documents": len(indexer.index),
        "queue_size": indexer._update_queue.qsize()
    }

# Health check for deployment
@mcp.custom_route("/health", methods=["GET"])
async def health_check():
    return {"status": "healthy", "service": "IndexingServer"}
```

### 6.3 Optional STDIO Proxy

```python
# stdio_proxy.py - Lightweight proxy for Claude Desktop
import httpx
from fastmcp import FastMCP

BACKEND_URL = "http://localhost:8000/mcp"

proxy = FastMCP("STDIOProxy")

async def call_backend(method: str, params: dict) -> any:
    """Generic backend caller."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            BACKEND_URL,
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": 1
            }
        )
        result = response.json()
        return result.get("result")

@proxy.tool
async def add_document(content: str, metadata: dict) -> str:
    return await call_backend("tools/call", {
        "name": "add_document",
        "arguments": {"content": content, "metadata": metadata}
    })

@proxy.tool
async def search_documents(query: str, limit: int = 10) -> list[dict]:
    return await call_backend("tools/call", {
        "name": "search_documents",
        "arguments": {"query": query, "limit": limit}
    })

if __name__ == "__main__":
    proxy.run()  # STDIO transport
```

---

## 7. Key Findings Summary

### 7.1 ASGI Composition

✅ **Possible:** Multiple FastMCP servers can be composed in a single ASGI app

⚠️ **Requires:** Careful lifespan management using `AsyncExitStack` pattern

📌 **Best Practice:** Use helper function `combine_lifespans()` for clarity

### 7.2 Shared State Management

✅ **App-Level State:** Use `app.state` with lifespan wrappers

✅ **Request-Level State:** Use MCP `Context.set_state()` / `get_state()`

⚠️ **Limitation:** Context state is request-scoped only

📌 **Bridge Pattern:** Use middleware to inject `app.state` into `Context`

### 7.3 Multi-Protocol Support

❌ **Single Process:** Cannot run STDIO + HTTP simultaneously

✅ **Separate Servers:** Can deploy parallel STDIO and HTTP servers with shared business logic

📌 **Recommended:** HTTP backend + optional STDIO proxy pattern

### 7.4 Background Services

✅ **Lifespan Integration:** Wrap FastMCP's lifespan to add background tasks

✅ **Task Management:** Use `BackgroundTaskManager` pattern for graceful shutdown

📌 **Access Pattern:** Bridge `app.state` to `Context` via middleware

### 7.5 Production Deployment

✅ **HTTP Recommended:** For persistent services with background tasks

✅ **Stateless Mode:** Enable `stateless_http=True` for horizontal scaling

✅ **Redis Backend:** Use for session persistence across instances

📌 **Architecture:** Separate business logic from protocol handling

---

## 8. Sources

### Official Documentation
- [HTTP Deployment - FastMCP](https://gofastmcp.com/deployment/http)
- [Running Your Server - FastMCP](https://gofastmcp.com/deployment/running-server)
- [MCP Context - FastMCP](https://gofastmcp.com/servers/context)
- [MCP Middleware - FastMCP](https://gofastmcp.com/servers/middleware)
- [FastAPI Integration - FastMCP](https://gofastmcp.com/integrations/fastapi)
- [Server Composition - FastMCP](https://gofastmcp.com/servers/composition)

### GitHub Resources
- [GitHub Issue #587 - Combining Multiple HTTP MCP Servers](https://github.com/jlowin/fastmcp/issues/587)
- [GitHub Discussion #1763 - Working with Lifespan](https://github.com/jlowin/fastmcp/discussions/1763)
- [FastMCP GitHub Repository](https://github.com/jlowin/fastmcp)

### Tutorials and Guides
- [Building MCP Servers with FastMCP (STDIO, HTTP and SSE)](https://medium.com/@anil.goyal0057/building-and-exposing-mcp-servers-with-fastmcp-stdio-http-and-sse-ace0f1d996dd)
- [Building Production-Ready MCP Servers](https://thinhdanggroup.github.io/mcp-production-ready/)
- [Building an MCP Server and Client with FastMCP 2.0 - DataCamp](https://www.datacamp.com/tutorial/building-mcp-server-client-fastmcp)
- [Build MCP Servers in Python with FastMCP - MCPcat](https://mcpcat.io/guides/building-mcp-server-python-fastmcp/)
- [How MCP Servers Work - WorkOS](https://workos.com/blog/how-mcp-servers-work)

### Additional Resources
- [Understanding FastAPI: Building Production-Grade Applications](https://rileylearning.medium.com/understanding-fastapi-building-production-grade-asynchronous-applications-with-mcp-96d392535467)
- [FastAPI Lifespan Events - Sarim Ahmed](https://www.sarimahmed.net/blog/fastapi-lifespan/)

---

## Conclusion

FastMCP provides a flexible, production-ready framework for building MCP servers with comprehensive support for ASGI composition, background services, and state management. The key to successful deployment lies in:

1. **Choosing the right transport** - HTTP for persistent services, STDIO for Claude Desktop
2. **Proper lifespan management** - Using `AsyncExitStack` for multiple services
3. **Clear separation of concerns** - Business logic independent of protocol handling
4. **Middleware bridges** - Connecting app-level state to request-level context
5. **Background task coordination** - Proper startup/shutdown lifecycle management

The recommended architecture for indexing services is an **HTTP backend with optional STDIO proxy**, which provides the best balance of functionality, scalability, and maintainability.

---

**Report Generated:** 2025-11-27
**Research Scope:** FastMCP deployment strategies, ASGI composition, multi-protocol support, state management, and production architectures
**Confidence Level:** High (based on official documentation, community discussions, and production examples)
