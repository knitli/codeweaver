<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Implementation Plan Revision Summary

## Overview

The original implementation plan has been revised to align with CodeWeaver's established patterns, idioms, and architectural principles. This document summarizes the key changes.

## Critical Changes (Blockers)

### 1. Constitutional Compliance - ONE TOOL Principle

**Original**: Exposed 3 MCP tools: `find_code`, `reindex`, `get_index_status`

**Revised**: Only `find_code` exposed as MCP tool

**Rationale**: "All of our architectural decisions are built on the core idea that there is only one tool for the user's agent -- find_code"

Reindexing is intentionally CLI-only to prevent agents from triggering expensive operations.

### 2. Tool Signature Correction

**Original**:
```python
async def find_code(
    query: str,
    k: int = 10,
    similarity_threshold: float = 0.7
) -> dict:
```

**Revised**:
```python
async def find_code(
    query: str,
    intent: str | None = None,
    *,
    token_limit: int = 30000,
    focus_languages: tuple[str, ...] | None = None,
    context: Context | None = None,
) -> dict:  # Returns FindCodeResponseSummary.model_dump()
```

### 3. Framework Stack Correction

**Original**: Used FastAPI patterns (`@app.on_event`, `HTTPException`)

**Revised**: Uses FastMCP/Starlette patterns:
- `@asynccontextmanager` for lifespan (not `@on_event`)
- `@mcp.custom_route()` for HTTP endpoints
- `@timed_http` decorator for statistics
- Starlette-native patterns throughout

### 4. CLI Framework

**Original**: Used click framework

**Revised**: Uses cyclopts (CodeWeaver's actual CLI framework)
- Extends existing `cw server start` command
- Recommends adding `cw start` (stdio) and `cw serve` (HTTP) convenience commands

### 5. Port Configuration

**Original**: Service on port 6334

**Revised**: Server on port 9328

**Rationale**: Port 6334 conflicts with Qdrant (which uses 6333-6334 by default)

### 6. Windows Support

**Original**: Assumed Unix-only features (Unix sockets, systemd, assumed Linux/macOS)

**Revised**: Cross-platform approach:
- HTTP-first (works everywhere)
- Unix socket optional optimization on Unix-like systems
- Platform detection with graceful fallback
- Windows service installation script (NSSM)
- Tested deployment strategies for Windows

## High-Priority Changes

### 7. Type System Alignment

**Original**: Used `BaseModel` (Pydantic)

**Revised**: Uses CodeWeaver's `BasedModel`:
```python
from codeweaver.core.types.models import BasedModel, FROZEN_BASEDMODEL_CONFIG

class BackgroundServicesConfig(BasedModel):
    model_config = FROZEN_BASEDMODEL_CONFIG

    def _telemetry_keys(self) -> dict | None:
        """No sensitive fields."""
        return None
```

### 8. Configuration Reinvention → Extension

**Original**: Created new `[service]` configuration section

**Revised**: Extends existing `IndexerSettings`:
```toml
[indexer.background]
auto_index_on_startup = true
file_watching_enabled = true
health_check_interval_seconds = 30
```

**Rationale**: `IndexerSettings` already exists - extend it instead of creating new section

### 9. Immutability Pattern Compliance

**Original**: Used `settings = get_settings()` for all access, called non-existent `.get()` method

**Revised**: Follows CodeWeaver's immutability pattern:
```python
# ✅ CORRECT (95% of cases): Immutable read-only access
settings_map = get_settings_map()  # Returns DictView[CodeWeaverSettingsDict]
auto_index = settings_map["indexer"]["background"]["auto_index_on_startup"]

# ⚠️ Only when need property/method access or mutation:
settings = get_settings()
auto_index = settings.indexer.background.auto_index_on_startup

# ❌ NEVER:
settings.get("key")  # AttributeError - doesn't exist on Pydantic models
```

### 10. State Management Pattern Reuse

**Original**: Created minimal `ServiceState` from scratch

**Revised**: Extracted `BackgroundState` from existing `AppState` pattern:
- Reuses ProviderRegistry singleton
- Reuses HealthService
- Reuses SessionStatistics
- Reuses VectorStoreFailoverManager
- Follows established lifecycle patterns

### 11. Provider Integration

**Original**: Created new provider initialization logic

**Revised**: Uses existing `ProviderRegistry` singleton:
```python
registry = ProviderRegistry.get_instance()
failover_manager = VectorStoreFailoverManager(registry=registry, settings_map=settings_map)
```

## Architectural Changes

### Management Server Separation (CRITICAL ADDITION)

**Issue**: Original plan used `@mcp.custom_route()` for health/stats endpoints, which only work when FastMCP runs in HTTP mode. stdio clients wouldn't have access to these endpoints.

**Solution**: Separate management server (port 9329) running independently of MCP transport choice.

**Architecture**:
```
Single Process with Two HTTP Servers:

1. MCP Server (port 9328, HTTP mode only OR stdio)
   - find_code() tool
   - MCP protocol handling

2. Management Server (port 9329, always HTTP)
   - /health, /status, /metrics
   - /version, /settings, /state
   - Available for both stdio AND HTTP modes
```

**Benefits**:
- Health checks work regardless of MCP transport (stdio or HTTP)
- Docker health checks always work: `curl http://localhost:9329/health`
- Monitoring tools can access metrics even in stdio mode
- Clean separation: protocol vs. observability

**Implementation**:
- `ManagementServer` class wraps existing endpoint handlers from `app_bindings.py`
- Runs via separate `uvicorn.Server` instance in background task
- Managed by `BackgroundState` lifecycle
- Reuses all existing endpoint logic (no duplication)

### Same-Process vs. Separate-Process

**Original**: Assumed separate-process architecture (indexer service + MCP servers as separate processes)

**Revised**: Same-process separation with clear boundaries
- BackgroundState manages services in same process as FastMCP
- Clean interfaces between protocol layer and background services
- Designed to evolve to separate-process if needed
- Simpler deployment, lower operational complexity

**Rationale**:
- Start simple, evolve if needed
- User insight: "The existing AppState could be almost exactly plug and play as a background/umbrella lifecycle manager"
- Maintains option for future separate-process deployment

### Architecture Diagram

**Before** (Original):
```
┌─────────────────┐        ┌─────────────────┐
│ Indexer Service │ ←HTTP→ │ MCP HTTP Server │
│ (Separate Proc) │        │ (Separate Proc) │
└─────────────────┘        └─────────────────┘
```

**After** (Revised):
```
┌──────────────────────────────────────┐
│  Single Process                      │
│  ┌────────────────────────────────┐  │
│  │ Protocol Layer (FastMCP)       │  │
│  │ - find_code() tool ONLY        │  │
│  └────────────┬───────────────────┘  │
│               │ Context              │
│  ┌────────────▼───────────────────┐  │
│  │ Background Services Layer      │  │
│  │ - BackgroundState              │  │
│  │ - Indexer, FileWatcher         │  │
│  └────────────┬───────────────────┘  │
│               │ ProviderRegistry     │
│  ┌────────────▼───────────────────┐  │
│  │ Provider Layer                 │  │
│  │ - VectorStore, Embedder        │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

## Statistics & Monitoring

**Added**: `@timed_http` decorator integration on all HTTP endpoints:
```python
@mcp.custom_route("/health", methods=["GET"])
@timed_http("health_check")
async def health_check(request):
    ...
```

Feeds request/response timings to SessionStatistics service.

## Testing Changes

### Added Tests

1. **Constitutional Compliance Test**:
```python
async def test_no_reindex_tool_exposed():
    """Verify reindex is NOT exposed as MCP tool."""
    tools = [tool.name for tool in mcp.list_tools()]
    assert "find_code" in tools
    assert "reindex" not in tools
    assert "get_index_status" not in tools
```

2. **Cross-Platform Tests**:
   - Unix socket detection
   - HTTP fallback on Windows
   - Platform-specific deployment

3. **Immutability Tests**:
   - Verify get_settings_map() returns DictView
   - Verify dict-like access works
   - Verify .get() raises AttributeError

## Documentation Changes

### Added Sections

1. **ONE TOOL Principle** - Explains constitutional compliance and rationale
2. **Immutability Philosophy** - Documents 95% rule and patterns
3. **Cross-Platform Deployment** - Windows, Linux, macOS strategies
4. **Pattern Reuse** - How BackgroundState extracts from AppState
5. **Evolution Path** - How to evolve to separate-process if needed

### Updated Examples

All code examples now show:
- Correct FastMCP/Starlette patterns
- BasedModel with _telemetry_keys()
- get_settings_map() for immutable access
- cyclopts CLI patterns
- @timed_http statistics integration

## Migration Impact

### Breaking Changes

**Original Plan**: Significant breaking changes (configuration format, deployment model, separate processes)

**Revised Plan**: Minimal breaking changes
- Same user-facing commands
- Same MCP tool interface (`find_code` only)
- Configuration changes are additive (extend IndexerSettings)
- Deployment remains single process

### User Migration

**Original**: Users need to:
1. Update config to new `[service]` section
2. Run two processes (`codeweaver service start` + `codeweaver server start`)
3. Update MCP client configurations

**Revised**: Users need to:
1. Update to alpha.2 (no config changes required for defaults)
2. Continue using same commands (`cw start` or `cw serve`)
3. No MCP client configuration changes

## Validation Checklist Additions

The revised plan includes comprehensive validation checklist:

**Constitutional & Architectural**:
- [ ] ONE TOOL principle maintained
- [ ] Uses FastMCP >= 2.13.1 (not FastAPI)
- [ ] Uses Starlette lifespan (not @on_event)
- [ ] Follows AppState → BackgroundState pattern
- [ ] Uses ProviderRegistry singleton

**Type System**:
- [ ] All models inherit from BasedModel
- [ ] All models implement _telemetry_keys()
- [ ] Uses FROZEN_BASEDMODEL_CONFIG

**Configuration**:
- [ ] Extends IndexerSettings (doesn't create new section)
- [ ] Uses get_settings_map() for read-only access
- [ ] Never calls .get() on Pydantic models

**CLI**:
- [ ] Uses cyclopts (not click)
- [ ] Extends existing commands

**Cross-Platform**:
- [ ] Port 9328 (NOT 6334)
- [ ] HTTP-first approach
- [ ] Windows deployment strategy

**Statistics**:
- [ ] @timed_http on all endpoints
- [ ] SessionStatistics integration

## Files Changed

### New Files Created
- `src/codeweaver/server/background/__init__.py`
- `src/codeweaver/server/background/state.py`
- `src/codeweaver/server/background/lifecycle.py`
- `src/codeweaver/server/transport.py`
- `deployment/windows/install-service.ps1`
- `tests/integration/test_background_services.py`
- `tests/integration/test_cross_platform.py`
- `docs/architecture/background-services.md`

### Files Updated
- `src/codeweaver/server/mcp_server.py` - Updated for background services
- `src/codeweaver/config/indexer.py` - Added BackgroundServicesConfig
- `src/codeweaver/config/server.py` - Updated ServerSettings
- `src/codeweaver/cli/commands/server.py` - Cyclopts patterns
- `config.toml` - Extended [indexer.background] section
- `docker-compose.yml` - Simplified to single service
- `README.md` - Updated quick start and tool documentation

### Files Removed/Not Created
- ❌ `src/codeweaver/service/` - Not created (same-process approach)
- ❌ `src/codeweaver/mcp/client.py` - Not needed (no IPC)
- ❌ `src/codeweaver/config/service.py` - Use IndexerSettings instead

## Summary

The revised plan maintains the core goal of separating background processes from MCP protocol layer, but does so in a way that:

1. **Aligns with CodeWeaver's patterns**: BasedModel, get_settings_map(), ProviderRegistry, AppState
2. **Respects constitutional principles**: ONE TOOL (find_code only)
3. **Supports all platforms**: Windows, Linux, macOS, WSL
4. **Reuses existing infrastructure**: Extends IndexerSettings, extracts from AppState
5. **Maintains simplicity**: Same-process, single command deployment
6. **Enables future evolution**: Can evolve to separate-process if needed

**Key insight from user**: "The existing AppState could be almost exactly plug and play as a background/umbrella lifecycle manager"

The revised plan follows this insight, extracting BackgroundState from AppState and reusing all existing provider/service infrastructure.