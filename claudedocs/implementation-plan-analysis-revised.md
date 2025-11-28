<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Implementation Plan Analysis Report (REVISED)

**Analysis Date**: 2025-11-27
**Plan Document**: `/home/knitli/codeweaver/claudedocs/option-a-service-implementation-plan.md`
**Codebase Architecture**: ARCHITECTURE.md v1.1.0
**FastMCP Research**: `/home/knitli/codeweaver/claudedocs/fastmcp-deployment-research.md`

---

## 🎯 EXECUTIVE SUMMARY

The implementation plan proposes separating CodeWeaver's indexer into a background service with MCP servers as protocol handlers. While the **core architectural goal is sound**, the plan has **critical misalignments** with established CodeWeaver patterns, types, architectural principles, and platform requirements.

### 🔴 CRITICAL BLOCKERS (Must Fix Before Implementation)

1. **ARCHITECTURAL VIOLATION**: Proposes exposing `reindex` and `get_index_status` as agent tools — **violates core constitutional principle** of single-tool interface
2. **FRAMEWORK MISMATCH**: Uses FastAPI patterns; CodeWeaver uses **Starlette/Uvicorn via FastMCP**
3. **TYPE SYSTEM**: Uses generic `BaseModel`; must use `BasedModel` with telemetry
4. **TOOL SIGNATURE**: `find_code` signature completely wrong; returns wrong type
5. **CLI FRAMEWORK**: Uses `click`; CodeWeaver uses **cyclopts**
6. **PORT CONFLICT**: Port 6334 conflicts with Qdrant (6333, 6334)
7. **PLATFORM BLIND SPOT**: Ignores Windows entirely (Unix sockets, systemd)

### 🟡 HIGH-PRIORITY ISSUES

8. **CONFIGURATION**: Invents new config sections; should use existing `IndexerSettings`
9. **IMMUTABILITY VIOLATION**: Uses `settings.get()` instead of `get_settings_map()` for read-only access
10. **STATE MANAGEMENT**: Creates new `ServiceState`; should leverage existing `AppState`
11. **ENDPOINT PATTERN**: Missing `@timed_http` decorator and statistics integration
12. **LIFECYCLE**: Uses deprecated `@on_event`; should use Starlette lifespan context manager
13. **PROVIDER INTEGRATION**: Direct instantiation; should use `ProviderRegistry` singleton

---

## 📊 DETAILED DISCREPANCY ANALYSIS

## 🔴 DISCREPANCY #1: CONSTITUTIONAL VIOLATION - TOOL EXPOSURE

**Severity**: 🔴 **BLOCKER** — Violates Core Architectural Principle

### What the Plan Proposes

Lines 653-682 expose THREE tools to agents:
```python
@mcp.tool()
async def find_code(query: str, k: int = 10, ...) -> dict:
    """Search codebase using semantic similarity."""

@mcp.tool()  # ❌ VIOLATION
async def reindex(force: bool = False) -> dict:
    """Trigger re-indexing of the codebase."""

@mcp.tool()  # ❌ VIOLATION
async def get_index_status() -> dict:
    """Get current indexing status."""
```

### Why This is Wrong

From `ARCHITECTURE.md` (Constitutional Principle):

> **Goal 2: Eliminate Cognitive Load on Agents**
> - Single `find_code` tool replaces 5-20+ specialized tools
> - Natural language queries with optional structured filters
> - Agent evaluates needs without polluting primary agent's context

**The entire CodeWeaver architecture is built on ONE TOOL for agents**: `find_code`

### What Actually Exists

1. **`find_code` is the ONLY agent tool** (properly implemented in `server/app_bindings.py:65-80`)
2. **CLI commands handle operations** users need:
   - `cw status` — Get indexing status (exists: `cli/commands/status.py`)
   - `cw index --clear --force` — Force reindex (exists: `cli/commands/index.py`)
3. **Reindexing is intentionally difficult** to discourage expensive operations

### Correct Approach

**For Agents**: ONLY `find_code`
```python
@mcp.tool()
async def find_code(
    query: str,
    intent: IntentType | None = None,
    *,
    token_limit: int = 30000,
    focus_languages: tuple[SemanticSearchLanguage, ...] | None = None,
    context: Context | None = None,
) -> FindCodeResponseSummary:
    """Search codebase. THE ONLY TOOL FOR AGENTS."""
```

**For Users**: CLI commands
```bash
cw status                    # Indexing status
cw index --clear --force     # Nuclear option (discouraged)
```

**Impact**: 🔴 **BLOCKER**
- Violates Constitutional Principle I (AI-First Context)
- Violates design decision: Single-Tool Interface
- Exposes dangerous operations to agents
- Architectural regression to 5-20+ tool anti-pattern

---

## 🔴 DISCREPANCY #2: TOOL SIGNATURE COMPLETELY WRONG

**Severity**: 🔴 **BLOCKER**

### Plan's Signature (Lines 627-650)

```python
@mcp.tool()
async def find_code(
    query: str,
    k: int = 10,  # ❌ WRONG
    similarity_threshold: float = 0.7  # ❌ WRONG
) -> dict:  # ❌ WRONG RETURN TYPE
```

### Actual Signature (`server/app_bindings.py:65-80`)

```python
async def find_code_tool(
    query: str,
    intent: IntentType | None = None,  # ✅ Intent-driven ranking
    *,
    token_limit: int = 30000,  # ✅ Token-aware assembly
    focus_languages: tuple[SemanticSearchLanguage, ...] | None = None,
    context: Context | None = None,  # ✅ MCP context injection
) -> FindCodeResponseSummary:  # ✅ Structured model return
```

### Key Differences

| Aspect | Plan | Reality | Why It Matters |
|--------|------|---------|----------------|
| **Intent parameter** | Missing | Required | Intent-driven ranking is core feature |
| **Token awareness** | Missing | `token_limit: int = 30000` | Token-aware context assembly |
| **Language filtering** | Missing | `focus_languages` | Semantic search optimization |
| **Context injection** | Missing | `context: Context` | MCP integration + logging |
| **Return type** | `dict` | `FindCodeResponseSummary` (BasedModel) | Structured, validated responses |
| **Internal params** | `k`, `similarity_threshold` | Hidden | Implementation details, not API surface |

### Correct Implementation

```python
from codeweaver.agent_api.find_code import find_code, FindCodeResponseSummary
from codeweaver.agent_api.find_code.intent import IntentType
from codeweaver.core.language import SemanticSearchLanguage
from fastmcp import Context

@mcp.tool()
async def find_code_tool(
    query: str,
    intent: IntentType | None = None,
    *,
    token_limit: int = 30000,
    focus_languages: tuple[SemanticSearchLanguage, ...] | None = None,
    context: Context | None = None,
) -> FindCodeResponseSummary:
    """Search codebase using semantic similarity.

    To use it, provide a natural language query describing what you are looking for.
    You can optionally specify an intent to help narrow down the search results.
    """
    return await find_code(
        query=query,
        intent=intent,
        token_limit=token_limit,
        focus_languages=focus_languages,
        context=context,
    )
```

**Impact**: 🔴 **BLOCKER**
- Wrong API contract with agents
- Missing core features (intent, token awareness, language filtering)
- Returns unstructured dict instead of validated model
- Breaks telemetry and logging integration

---

## 🔴 DISCREPANCY #3: FRAMEWORK PATTERNS MISMATCH

**Severity**: 🔴 **BLOCKER**

### The Reality: Starlette/Uvicorn, Not FastAPI

**CodeWeaver Stack**:
```
FastMCP (≥2.13.1)
    ↓
Starlette (ASGI framework)
    ↓
Uvicorn (ASGI server)
```

**NOT FastAPI** (not in dependencies, pyproject.toml has NO fastapi)

### Plan Issues

1. **Line 98**: `from fastapi import FastAPI` ❌
2. **Lines 226-235**: `@app.on_event("startup")` ❌ (deprecated even in FastAPI, doesn't exist in Starlette)
3. **Lines 249-274**: `from fastapi import HTTPException` ❌
4. **Line 219**: `app = FastAPI(...)` ❌

### Correct Patterns (from FastMCP research)

#### Lifecycle Management
```python
from contextlib import asynccontextmanager
from fastmcp import FastMCP

@asynccontextmanager
async def lifespan(app):
    """Starlette lifespan pattern."""
    # Startup
    app.state.indexer = await IndexerService.create()
    app.state.background_task = asyncio.create_task(
        app.state.indexer.run_continuous()
    )

    yield  # Server runs

    # Shutdown
    if app.state.background_task:
        app.state.background_task.cancel()
        try:
            await asyncio.wait_for(app.state.background_task, timeout=7.0)
        except (asyncio.CancelledError, TimeoutError):
            pass

mcp = FastMCP("CodeWeaver")
app = mcp.http_app()

# Wrap FastMCP's lifespan with our custom lifespan
original_lifespan = app.router.lifespan_context

@asynccontextmanager
async def combined_lifespan(app):
    async with original_lifespan(app):
        async with lifespan(app):
            yield

app.router.lifespan_context = combined_lifespan
```

#### Endpoint Pattern (Missing from Plan)
```python
from codeweaver.common.statistics import timed_http

@timed_http("health")  # ✅ Statistics tracking
@mcp.custom_route("/health", methods=["GET"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "codeweaver"}
```

**Key Patterns**:
- Uses `@mcp.custom_route()` for HTTP endpoints
- Wraps in `@timed_http()` decorator for statistics
- Returns JSON directly (no Response objects needed)

**Impact**: 🔴 **BLOCKER**
- Code won't run (FastAPI not installed)
- Wrong lifecycle patterns
- Missing statistics integration
- Wrong endpoint registration

---

## 🔴 DISCREPANCY #4: CLI FRAMEWORK WRONG

**Severity**: 🔴 **BLOCKER**

### Plan Uses `click` (Lines 807-884)

```python
import click  # ❌ WRONG

@click.group()
def service():
    """Manage the indexer service."""
    pass

@service.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=6334, type=int)
def start(host: str, port: int):
    """Start the indexer service."""
```

### CodeWeaver Uses `cyclopts`

```python
from cyclopts import App

app = App("codeweaver", ...)

# Commands registered as lazy imports
app.command("codeweaver.cli.commands.server:app", name="server")
app.command("codeweaver.cli.commands.status:app", name="status")
app.command("codeweaver.cli.commands.index:app", name="index")
```

### Existing Functionality

**Already Exists** (don't recreate):

1. **`cw server`** (`cli/commands/server.py`)
   - Starts MCP server (HTTP or stdio transport)
   - Has all suggested functionality from plan

2. **`cw status`** (`cli/commands/status.py`)
   - Shows indexing status
   - More robust than plan's implementation

3. **`cw index`** (`cli/commands/index.py`)
   - Performs indexing
   - Has `--clear` and `--force` flags for nuclear reindex
   - Designed for one-time, UI-first operations

### What SHOULD Be Added

```python
# cli/commands/daemon.py (NEW)
from cyclopts import App

app = App("daemon", help="Manage background services")

@app.default
async def start(
    *,
    detach: bool = False,
    log_file: Path | None = None,
) -> None:
    """Start background indexing service.

    Args:
        detach: Run as background daemon
        log_file: Log output file path
    """
    # Implementation

@app.command
async def stop() -> None:
    """Stop background indexing service."""
    # Implementation

# Register in cli/__main__.py:
app.command("codeweaver.cli.commands.daemon:app", name="start")  # cw start
app.command("codeweaver.cli.commands.daemon:app", name="stop")   # cw stop
```

**Recommended UX**:
- `cw start` — Start background services (more intuitive than "service")
- `cw stop` — Stop background services
- `cw status` — Check status (already exists)
- `cw server` — Start MCP protocol server (already exists)

**Impact**: 🔴 **BLOCKER**
- Wrong framework (click not used)
- Duplicates existing commands
- Breaks existing CLI patterns
- "service" terminology not intuitive

---

## 🔴 DISCREPANCY #5: PORT CONFLICT

**Severity**: 🔴 **BLOCKER**

### Plan Proposes Port 6334 (Lines 376, 835, 1000)

```python
port = settings.get("service.port", 6334)  # ❌ CONFLICT
```

### The Problem: Qdrant Uses 6333 & 6334

**Qdrant Default Ports**:
- `6333` — HTTP API (primary)
- `6334` — gRPC API (optional)

**CodeWeaver's Default**:
- `9328` — All HTTP services (server, MCP)

### Correct Approach

```python
# Use existing port standard
host = settings.server.host  # Default: "127.0.0.1"
port = settings.server.port  # Default: 9328

# OR use socket-first with HTTP fallback
socket_path = settings.server.socket  # Unix socket (if platform supports)
if not socket_path or platform.system() == "Windows":
    # Fall back to HTTP on port 9328
    use_http(host, port)
```

**Impact**: 🔴 **BLOCKER**
- Port collision with Qdrant
- Breaks development environments
- Confusing for users (why two different ports?)

---

## 🔴 DISCREPANCY #6: WINDOWS SUPPORT IGNORED

**Severity**: 🔴 **BLOCKER**

### Plan Assumptions (Linux-Only)

1. **Unix Sockets** (Lines 464-469, 1002)
   ```python
   socket_path: Optional[Path] = None
   transport = httpx.AsyncHTTPTransport(uds=str(self.socket_path))
   ```

2. **systemd Service Files** (Lines 1079-1157)
   ```ini
   [Unit]
   Description=CodeWeaver Indexer Service
   ```

3. **No Windows Alternatives Mentioned**

### The Problem

**Windows Does Not Support**:
- Unix domain sockets (UDS)
- systemd service management
- `/run/` directory paths

**Impact on Users**:
- 40%+ of developers use Windows (GitHub/Stack Overflow surveys)
- WSL2 users need native Windows support
- Cross-platform CLI tools expected to work everywhere

### Correct Approach

#### Socket Pattern (Cross-Platform)
```python
import platform
from pathlib import Path

def get_socket_path() -> Path | None:
    """Get platform-appropriate socket path."""
    if platform.system() == "Windows":
        # Windows: Named pipes or HTTP-only
        return None  # Fall back to HTTP
    else:
        # Unix: Domain sockets
        return Path("/run/codeweaver/indexer.sock")
```

#### Service Management (Cross-Platform)

**Linux**: systemd
**macOS**: launchd
**Windows**: Windows Service or Task Scheduler

```python
# cli/commands/daemon.py
def install_service():
    """Install as system service (platform-specific)."""
    system = platform.system()

    if system == "Linux":
        install_systemd_service()
    elif system == "Darwin":
        install_launchd_service()
    elif system == "Windows":
        install_windows_service()
    else:
        raise UnsupportedPlatformError(f"Platform {system} not supported")
```

**Alternative**: HTTP-only (simpler, works everywhere)
```python
# Default to HTTP on all platforms
# Unix sockets as optional optimization on Unix-like systems
```

**Impact**: 🔴 **BLOCKER**
- Excludes 40%+ of user base
- Violates cross-platform design principle
- Deployment docs incomplete

---

## 🟡 DISCREPANCY #7: TYPE SYSTEM VIOLATIONS

**Severity**: 🟡 **HIGH**

### Plan Uses Generic Pydantic Models

```python
from pydantic import BaseModel  # ❌

class IndexRequest(BaseModel):
    force_reindex: bool = False

class SearchRequest(BaseModel):
    query: str
    k: int = 10
```

### Required Pattern: BasedModel

```python
from codeweaver.core.types import BasedModel, FilteredKeyT
from codeweaver.core.types.models import AnonymityConversion

class IndexRequest(BasedModel):
    """Request to trigger indexing."""
    force_reindex: bool = False

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        # Most models return None (no special anonymization)
        # Only return a dict if fields need anonymization
        return None  # or {"force_reindex": AnonymityConversion.BOOLEAN}
```

**Key Requirements**:
- All models inherit from `BasedModel` (not `BaseModel`)
- Implement `_telemetry_keys()` method (even if returns `None`)
- Use `BASEDMODEL_CONFIG` or `FROZEN_BASEDMODEL_CONFIG`
- Provides `serialize_for_cli()` and `serialize_for_telemetry()`

**Impact**: 🟡 **HIGH**
- Breaks telemetry system
- Missing CLI serialization
- Wrong ConfigDict settings
- Type checker errors

---

## 🟡 DISCREPANCY #8: CONFIGURATION REINVENTION

**Severity**: 🟡 **HIGH**

### Plan Invents New Config Sections (Lines 945-1013)

```python
class ServiceConfig(BaseModel):  # ❌ New section
    host: str = "127.0.0.1"
    port: int = 6334
    socket: Optional[Path] = None

[service]  # ❌ New TOML section
host = "127.0.0.1"
port = 6334
```

### Why Not Use Existing `IndexerSettings`?

**Already Exists** (`config/indexer.py`):
```python
class IndexerSettings(BasedModel):
    """Indexer configuration."""
    # Current fields...
    # ADD:
    # background_mode: bool = False
    # http_endpoint: HttpEndpointConfig | None = None
```

**Existing Config Sections**:
- `server` — Server settings (port 9328)
- `indexer` — Indexer settings
- `mcp` — MCP configuration
- `logging`, `telemetry`, `chunker`, `providers`

### Correct Approach

**Option A**: Extend `IndexerSettings`
```python
# config/indexer.py
class IndexerSettings(BasedModel):
    # ... existing fields ...

    background_mode: bool = Field(
        default=False,
        description="Run indexer as background service"
    )

    auto_index_on_startup: bool = Field(
        default=True,
        description="Automatically index on service startup"
    )
```

**Option B**: Use existing `server` section
```python
# Config access
settings.server.host  # "127.0.0.1"
settings.server.port  # 9328
settings.server.socket  # Path | None (platform-dependent)
```

**Impact**: 🟡 **HIGH**
- Configuration bloat
- User confusion (which section?)
- Breaks existing config patterns
- Documentation burden

---

## 🟡 DISCREPANCY #9: IMMUTABILITY VIOLATION - SETTINGS ACCESS

**Severity**: 🟡 **HIGH** — Violates Core Design Philosophy

### Plan's Settings Access (Lines 153, 376-379)

```python
settings = get_settings()  # ❌ Should use get_settings_map()

# WRONG: Dict-like access on Pydantic model
host = settings.get("service.host", "127.0.0.1")  # ❌ .get() doesn't exist
port = settings.get("service.port", 6334)         # ❌ Wrong pattern
```

### CodeWeaver's Immutability Philosophy

From ARCHITECTURE.md and codebase analysis:

> **CodeWeaver is obsessive about immutability**:
> - `frozen=True` on all models
> - `MappingProxyType` for read-only dicts
> - `frozenset` instead of sets
> - `tuple` instead of lists
> - Sentinel values (`UNSET`) instead of `None`

### The Preferred Pattern: `get_settings_map()`

```python
from codeweaver.config.settings import get_settings_map

# ✅ CORRECT: Immutable typed dict access
settings_map = get_settings_map()  # Returns DictView[CodeWeaverSettingsDict]

# Dict-like access with full type safety
host = settings_map["server"]["host"]  # str
port = settings_map["server"]["port"]  # int
socket = settings_map["server"].get("socket")  # Path | None

# DictView provides:
# - Read-only wrapper (essentially typed MappingProxyType)
# - Full dict protocol (__getitem__, __iter__, keys(), values(), items())
# - Immutable - cannot modify settings
# - Type-safe access to TypedDict structure
```

### When to Use `get_settings()`

**Only use when**:
1. Need to **mutate** settings (rare)
2. Need **property/method access** on Pydantic model

```python
from codeweaver.config.settings import get_settings

# Pydantic model access (when properties/methods needed)
settings = get_settings()  # Returns CodeWeaverSettings (BasedModel)
host = settings.server.host  # Property access
port = settings.server.port

# ❌ NEVER use .get() on Pydantic models
host = settings.get("server.host")  # AttributeError: no .get() method
```

### Why This Matters

**Immutability Benefits**:
- Thread-safe concurrent access
- No accidental mutations
- Clear data flow (read-only by default)
- Type-safe dictionary access

**Performance**:
- `DictView` wraps `MappingProxyType` (C-level immutable dict)
- No copying overhead
- Lazy evaluation where possible

**Architecture**:
- Enforces functional programming patterns
- Reduces bugs from state mutations
- Makes code easier to reason about

### Plan's Violations

1. **Wrong function**: Uses `get_settings()` for read-only access
2. **Wrong method**: Uses `.get()` on Pydantic model (doesn't exist)
3. **Wrong keys**: Uses `"service.host"` (non-existent section)
4. **Wrong pattern**: Treats immutable config as mutable dict

### Correct Examples

```python
# Read-only access (preferred 95% of the time)
settings_map = get_settings_map()

# Access nested config
indexer_config = settings_map["indexer"]
chunk_size = indexer_config["max_chunk_size"]

# Server config
server_host = settings_map["server"]["host"]
server_port = settings_map["server"]["port"]

# Optional values with .get()
socket_path = settings_map["server"].get("socket")  # Path | None

# Check if key exists
if "custom_field" in settings_map["indexer"]:
    value = settings_map["indexer"]["custom_field"]

# Iterate over sections
for section_name in settings_map.keys():
    section = settings_map[section_name]
```

**Impact**: 🟡 **HIGH**
- Violates core immutability philosophy
- Runtime AttributeError (`.get()` doesn't exist on BasedModel)
- Thread-safety concerns if mutating settings
- Wrong mental model of config system

---

## 🟡 DISCREPANCY #10: STATE MANAGEMENT DUPLICATION

**Severity**: 🟡 **HIGH**

### Plan Creates New `ServiceState` (Lines 139-212)

```python
class ServiceState:  # ❌ Duplicates AppState
    def __init__(self):
        self.indexer: Optional[Indexer] = None
        self.watcher: Optional[FileWatcher] = None
        self.status: str = "initializing"
        self.error: Optional[str] = None
```

### Existing `AppState` (`server/app_bindings.py:92-193`)

```python
@dataclass
class AppState:
    """Application state (comprehensive)."""
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
    telemetry: PostHogClient | None = None
```

### User Insight: AppState IS the Solution

> "The existing AppState could be almost exactly plug and play as a background/umbrella lifecycle manager for background services.. you just remove fastmcp from it and create a simpler manager for it."

### Correct Approach

**Background Service Manager** (extends AppState pattern):
```python
# server/background_manager.py
@dataclass
class BackgroundState:
    """Background service state (without FastMCP)."""
    settings: CodeWeaverSettings
    provider_registry: ProviderRegistry
    indexer: Indexer
    watcher: FileWatcher | None = None
    background_tasks: list[asyncio.Task] = field(default_factory=list)
    shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)

    @classmethod
    async def create(cls, settings: CodeWeaverSettings) -> BackgroundState:
        """Initialize background services."""
        registry = get_provider_registry()
        indexer = await Indexer.from_settings_async(settings)

        state = cls(
            settings=settings,
            provider_registry=registry,
            indexer=indexer,
        )

        return state

    async def start_services(self):
        """Start background indexing and file watching."""
        # Start indexer
        task = asyncio.create_task(self._run_indexing())
        self.background_tasks.append(task)

    async def shutdown(self):
        """Graceful shutdown."""
        self.shutdown_event.set()

        for task in self.background_tasks:
            task.cancel()

        await asyncio.gather(*self.background_tasks, return_exceptions=True)
```

**MCP Server** (lightweight protocol handler):
```python
# server/app_bindings.py (simplified)
@asynccontextmanager
async def lifespan(app):
    # Just connect to existing background service
    # (via IPC, or shared in-process reference)
    app.state.indexer = get_shared_indexer()
    yield
```

**Impact**: 🟡 **HIGH**
- Duplicates existing infrastructure
- Missing critical components (registries, telemetry, failover)
- Ignores proven AppState pattern
- More complexity for same functionality

---

## 🟠 DISCREPANCY #11: PROVIDER INTEGRATION PATTERNS

**Severity**: 🟠 **MODERATE**

### Plan Instantiates Providers Directly (Line 156)

```python
self.indexer = await Indexer.from_settings_async(settings=settings)  # ❌ Direct
```

### Actual Pattern: ProviderRegistry

```python
from codeweaver.common.registry import get_provider_registry

registry = get_provider_registry()  # Singleton

if provider_enum := registry.get_provider_enum_for("vector_store"):
    vector_store = registry.get_provider_instance(
        provider_enum,
        "vector_store",
        singleton=True  # ✅ Cached, health-monitored
    )
```

**Why Registry Matters**:
- Singleton caching (prevents duplicate instances)
- Health monitoring
- Failover support (`VectorStoreFailoverManager`)
- Telemetry tracking
- Lazy loading

**Impact**: 🟠 **MODERATE**
- Missing health monitoring
- No failover support
- Duplicate provider instances
- Breaks telemetry

---

## 🎯 ARCHITECTURAL CLARITY: WHAT'S THE GOAL?

### Core Objective (Correct)

**Separate background processes from MCP protocol layer**:
```
Background Services (Independent)
    ↓
HTTP Endpoints (Optional)
    ↓
MCP Server (Pure Protocol)
```

### Two Valid Architectures

#### Option A: Same-Process Separation
```
┌─────────────────────────────────┐
│   CodeWeaver Process            │
│                                 │
│  ┌──────────────────────────┐  │
│  │ Background Service Layer │  │
│  │ • Indexer               │  │
│  │ • File Watcher           │  │
│  │ • AppState/BackgroundState│ │
│  └────────────┬─────────────┘  │
│               │                 │
│  ┌────────────▼─────────────┐  │
│  │   HTTP Endpoints         │  │
│  │   (@timed_http routes)   │  │
│  └────────────┬─────────────┘  │
│               │                 │
│  ┌────────────▼─────────────┐  │
│  │   FastMCP Protocol       │  │
│  │   (find_code tool)       │  │
│  └──────────────────────────┘  │
└─────────────────────────────────┘
```

**Benefits**: Simple, no IPC, direct state access

#### Option B: Separate-Process Service
```
┌───────────────────────────┐
│  Background Daemon        │
│  • Indexer                │
│  • File Watcher           │
│  • HTTP API (internal)    │
└────────────┬──────────────┘
             │ IPC (HTTP or socket)
┌────────────▼──────────────┐
│  MCP Server Process       │
│  • Protocol handler       │
│  • Thin client to daemon  │
└───────────────────────────┘
```

**Benefits**: Process isolation, restart independence, resource limits

### Key Decision Required

**Which architecture?** Plan mixes both, creating confusion.

**Recommendation**: Start with **Option A** (simpler), evolve to **Option B** if needed

---

## ✅ REVISED RECOMMENDATIONS

### Phase 1: Critical Alignment

1. **Remove Tool Violations**
   - ❌ Delete `reindex` and `get_index_status` tools
   - ✅ Keep ONLY `find_code` for agents
   - ✅ Status/reindex via CLI only

2. **Fix Tool Signature**
   - ✅ Use actual `find_code` signature with intent, token_limit, focus_languages
   - ✅ Return `FindCodeResponseSummary` (BasedModel)
   - ✅ Integrate MCP Context

3. **Adopt Starlette/FastMCP Patterns**
   - ✅ Use `@asynccontextmanager` lifespan
   - ✅ Use `@mcp.custom_route()` for endpoints
   - ✅ Add `@timed_http` decorator for statistics

4. **Fix CLI Framework**
   - ✅ Use cyclopts, not click
   - ✅ Add `cw start` / `cw stop` (not "service")
   - ✅ Don't duplicate existing commands

5. **Fix Port**
   - ✅ Use 9328 (existing standard)
   - ❌ Avoid 6334 (Qdrant conflict)

6. **Add Windows Support**
   - ✅ HTTP fallback when sockets unavailable
   - ✅ Cross-platform service management
   - ✅ Platform detection logic

### Phase 2: Type & Configuration Alignment

7. **Use BasedModel**
   - ✅ All models inherit BasedModel
   - ✅ Implement `_telemetry_keys()` (even if returns None)

8. **Use Existing Config**
   - ✅ Extend `IndexerSettings` or use `server` section
   - ❌ Don't create new `service` config section

9. **Use Immutable Settings Access**
   - ✅ Use `get_settings_map()` for read-only config access (95% of cases)
   - ✅ Dict-like access: `settings_map["server"]["host"]`
   - ❌ Don't use `.get()` on Pydantic models (doesn't exist)
   - ⚠️ Only use `get_settings()` when need property/method access or mutation

10. **Leverage AppState**
    - ✅ Extract BackgroundState pattern from AppState
    - ✅ Reuse registries, telemetry, statistics
    - ❌ Don't create minimal ServiceState

11. **Use ProviderRegistry**
    - ✅ Get providers via singleton registry
    - ✅ Leverage health monitoring and failover

### Phase 3: Research & Prototype

12. **Clarify Architecture Goal**
    - Same-process or separate-process?
    - Document decision rationale
    - Prototype chosen approach

13. **Study FastMCP Research**
    - Review `/home/knitli/codeweaver/claudedocs/fastmcp-deployment-research.md`
    - Understand lifespan wrapping pattern
    - Apply middleware bridge for app.state

14. **Windows Testing**
    - Test on Windows (not just WSL)
    - Validate HTTP fallback
    - Document platform limitations

---

## 📋 VALIDATION CHECKLIST

Before implementation:

**Architecture**:
- [ ] ONE tool for agents (`find_code` only)
- [ ] Status/reindex via CLI only
- [ ] Clarified same-process vs separate-process

**Types & Patterns**:
- [ ] All models use `BasedModel`
- [ ] Tool signature matches actual `find_code`
- [ ] Returns `FindCodeResponseSummary`
- [ ] Implements `_telemetry_keys()`

**Framework**:
- [ ] Uses Starlette lifespan context manager
- [ ] Uses `@mcp.custom_route()` for endpoints
- [ ] Uses `@timed_http` decorator
- [ ] No FastAPI imports

**CLI**:
- [ ] Uses cyclopts
- [ ] `cw start` / `cw stop` (not "service")
- [ ] Doesn't duplicate existing commands

**Platform**:
- [ ] Windows support via HTTP fallback
- [ ] Cross-platform service management
- [ ] No Unix-only assumptions

**Configuration**:
- [ ] Uses existing config sections
- [ ] Extends `IndexerSettings` if needed
- [ ] Port 9328 (not 6334)
- [ ] Uses `get_settings_map()` for read-only access (not `get_settings()`)
- [ ] Dict-like access on settings_map, not `.get()` on Pydantic models

**Integration**:
- [ ] Uses `ProviderRegistry` singleton
- [ ] Leverages `AppState` pattern
- [ ] Integrates statistics via `@timed_http`

---

## 🎓 KEY LEARNINGS

### What the Plan Got Right

1. **Architectural Goal**: Separating background services from protocol layer is correct
2. **Lifespan Management**: Using context managers for lifecycle (mostly correct pattern)
3. **Background Task Pattern**: `asyncio.create_task()` for background indexing
4. **Health Checks**: Including health endpoints

### Critical Misunderstandings

1. **Single-Tool Principle**: Didn't understand constitutional commitment to ONE tool
2. **Framework Stack**: Thought FastAPI, actually Starlette/Uvicorn via FastMCP
3. **Immutability Philosophy**: Used `settings.get()` instead of `get_settings_map()` pattern
4. **Existing Infrastructure**: Didn't leverage AppState, ProviderRegistry, statistics
5. **Platform Requirements**: Assumed Linux-only
6. **CLI Framework**: Didn't check existing implementation (cyclopts)

### Recommended Next Steps

1. **Read FastMCP Research** thoroughly
2. **Study Existing Code**:
   - `server/app_bindings.py` (AppState, lifespan, tools)
   - `agent_api/find_code/` (actual find_code implementation)
   - `cli/commands/` (cyclopts patterns)
   - `common/statistics.py` (@timed_http decorator)
3. **Prototype** same-process separation first
4. **Test** on all platforms (Linux, macOS, Windows)
5. **Document** architecture decision

---

**Report Status**: REVISED with user clarifications
**Confidence**: HIGH (based on comprehensive analysis + user corrections)
**Recommendation**: **MAJOR REVISIONS REQUIRED** before implementation

**Estimated Revision Effort**: 3-5 days for complete plan rewrite + cross-platform testing
