# Phase 4 Updated Implementation Plan
## Leveraging Existing Infrastructure

**Date**: 2025-01-15
**Status**: Ready for Implementation
**Requires**: Phase 3 complete ✅

## Key Infrastructure Discovered

### 1. HTTP Endpoints (`codeweaver.server.app_bindings`)

**Existing Endpoints**:
```python
# Line 207-339: /health endpoint
async def health(_request: Request) -> PlainTextResponse

# Line 142-160: /stats or /metrics endpoint
async def stats_info(_request: Request) -> PlainTextResponse

# Line 198-204: /state endpoint
async def state_info(_request: Request) -> PlainTextResponse

# Line 163-177: /settings endpoint
async def settings_info(_request: Request) -> PlainTextResponse

# Line 180-195: /version endpoint
async def version_info(_request: Request) -> PlainTextResponse
```

**TODO Comment** (Line 433):
```python
# todo: add status endpoint (more what I'm doing right now/progress than health)
```

**Insight**: This TODO aligns perfectly with Phase 4! We should implement `/status` endpoint.

### 2. Statistics System (`codeweaver.common.statistics`)

**`SessionStatistics` Class**:
- Comprehensive stats: timing, files, tokens, semantic analysis
- Already tracks MCP requests, HTTP requests, index operations
- Has `report()` method returning JSON (line 1270-1281)
- Extensible - we can add failover stats

**Key Fields**:
```python
timing_statistics: TimingStatistics  # Response times
index_statistics: FileStatistics     # File/chunk tracking
token_statistics: TokenCounter       # Token usage
```

**Global Singleton** (line 1329):
```python
_statistics: SessionStatistics = SessionStatistics(...)

def get_session_statistics() -> SessionStatistics:
    return _statistics
```

### 3. Health Service (`codeweaver.server.health_service`)

**`HealthService` Class**:
- Collects health from all components (vector store, embeddings, indexer)
- Returns `HealthResponse` with:
  - Overall status (healthy/degraded/unhealthy)
  - Indexing progress
  - Service health (vector store, embedding, sparse, reranking)
  - Statistics (chunks, files, languages)

**Key Method** (line 77-104):
```python
async def get_health_response(self) -> HealthResponse
```

**Integration Point**: We can extend `HealthService` to include failover status.

### 4. Progress Tracking (`codeweaver.engine.indexer.progress`)

**`IndexingProgressTracker` Class**:
- Rich-based UI for progress display
- Tracks phases: discovery, chunking, embedding, indexing
- Used by CLI `index` command

**`IndexingStats` Class** (line 42-83):
```python
@dataclass
class IndexingStats:
    files_discovered: int
    files_processed: int
    chunks_created: int
    chunks_embedded: int
    chunks_indexed: int
    start_time: float
    files_with_errors: list[Path]
```

**Pattern**: We can create `FailoverStats` following this pattern.

### 5. Client Communication (`codeweaver.common.logging`)

**`log_to_client_or_fallback()` Function** (line 102-139):
```python
async def log_to_client_or_fallback(
    context: Context | None,
    level: Literal["debug", "info", "warning", "error"],
    log_data: dict[str, Any],
    *,
    name: str = "codeweaver",
    logger: logging.Logger | None = None,
) -> None:
    """Log to client via context if available, else standard logging."""
```

**Usage**: Send failover notifications to MCP clients.

### 6. Server-Optional Operation

**Key Insight**: `index` and `search` commands bypass server if not running.

**Implication**: CLI `status` command must handle:
- Server running → Query `/status` endpoint
- Server not running → Read from shared state or report "server offline"

## Updated Phase 4 Tasks

### Task 13: Extend Statistics System ✨

**Objective**: Add failover statistics to `SessionStatistics`

**Implementation** (`src/codeweaver/common/statistics.py`):

1. **Create `FailoverStats` dataclass** (insert after line 83):

```python
@dataclass(config=DATACLASS_CONFIG | ConfigDict(extra="forbid", defer_build=True))
class FailoverStats(DataclassSerializationMixin):
    """Statistics for failover operations."""

    failover_active: bool = False
    failover_count: int = 0  # Total failovers in session
    total_failover_time_seconds: float = 0.0
    last_failover_time: str | None = None
    last_restoration_time: str | None = None

    # Backup sync stats
    backup_syncs_completed: int = 0
    backup_sync_failures: int = 0
    last_backup_sync: str | None = None
    total_backup_sync_time_seconds: float = 0.0

    # Sync-back stats (Phase 3)
    sync_back_operations: int = 0
    chunks_synced_back: int = 0
    sync_back_failures: int = 0
    total_sync_back_time_seconds: float = 0.0

    # Current state
    active_store_type: str | None = None
    primary_circuit_breaker_state: str | None = None
    backup_file_exists: bool = False
    backup_file_size_bytes: int = 0
    chunks_in_failover: int = 0  # Chunks indexed during current failover

    def _telemetry_keys(self) -> None:
        return None
```

2. **Add to `SessionStatistics`** (line 935-963):

```python
@dataclass(kw_only=True, config=DATACLASS_CONFIG | ConfigDict(defer_build=True))
class SessionStatistics(DataclassSerializationMixin):
    # ... existing fields ...

    failover_statistics: Annotated[
        FailoverStats | None,
        Field(
            default_factory=FailoverStats,
            description="""Failover and backup operation statistics.""",
        ),
    ]

    # ... rest of class ...
```

3. **Add update methods**:

```python
def update_failover_stats(
    self,
    *,
    failover_active: bool | None = None,
    sync_completed: bool = False,
    chunks_synced: int = 0,
    # ... other params
) -> None:
    """Update failover statistics."""
    if self.failover_statistics is None:
        self.failover_statistics = FailoverStats()

    if failover_active is not None:
        self.failover_statistics.failover_active = failover_active
        if failover_active:
            self.failover_statistics.failover_count += 1
            self.failover_statistics.last_failover_time = datetime.now(UTC).isoformat()

    if sync_completed:
        self.failover_statistics.backup_syncs_completed += 1
        # ... update other fields
```

### Task 14: Extend Health Service ✨

**Objective**: Include failover status in health checks

**Implementation** (`src/codeweaver/server/health_service.py`):

1. **Add failover manager to HealthService** (line 42-62):

```python
class HealthService:
    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        statistics: SessionStatistics,
        indexer: Indexer | None = None,
        startup_time: float,
        failover_manager: VectorStoreFailoverManager | None = None,  # NEW
    ) -> None:
        # ... existing init ...
        self._failover_manager = failover_manager
```

2. **Add `_get_failover_info()` method** (insert after line 413):

```python
async def _get_failover_info(self) -> dict[str, Any]:
    """Get failover status information."""
    if self._failover_manager is None:
        return {
            "failover_enabled": False,
            "failover_active": False,
        }

    status = self._failover_manager.get_status()

    return {
        "failover_enabled": True,
        "failover_active": status.get("failover_active", False),
        "active_store_type": status.get("active_store_type"),
        "primary_healthy": status.get("primary_healthy", True),
        "circuit_breaker_state": status.get("circuit_breaker_state"),
        "last_health_check": status.get("last_health_check"),
        "failover_time": status.get("failover_time"),
        "backup_file_exists": status.get("backup_file_exists", False),
        "backup_file_size_bytes": status.get("backup_file_size_bytes", 0),
        "last_backup_sync": status.get("last_backup_sync"),
        "chunks_tracked": len(getattr(self._failover_manager, "_failover_chunks", set())),
    }
```

3. **Update `get_health_response()`** to include failover:

```python
async def get_health_response(self) -> HealthResponse:
    # ... existing code ...

    # Add failover info collection
    failover_info_task = asyncio.create_task(self._get_failover_info())

    indexing_info, services_info, statistics_info, failover_info = await asyncio.gather(
        indexing_info_task, services_info_task, statistics_info_task, failover_info_task
    )

    # Include in response metadata or extend HealthResponse model
    # ...
```

### Task 15: Implement `/status` Endpoint ✨

**Objective**: Create dedicated status endpoint (separate from health)

**Implementation** (`src/codeweaver/server/app_bindings.py`):

1. **Add status endpoint handler** (insert after line 339):

```python
@timed_http("status")
async def status_info(_request: Request) -> PlainTextResponse:
    """Return current operational status (progress, failover, runtime state).

    This differs from /health which focuses on component health.
    Status shows what CodeWeaver is currently doing.
    """
    from codeweaver.server.server import get_state

    try:
        state = get_state()

        # Collect status information
        status_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "uptime_seconds": int(time.time() - state.startup_time),
        }

        # Indexing status
        if state.indexer:
            stats = state.indexer.stats
            status_data["indexing"] = {
                "active": stats.files_processed < stats.files_discovered,
                "files_discovered": stats.files_discovered,
                "files_processed": stats.files_processed,
                "chunks_created": stats.chunks_created,
                "processing_rate": stats.processing_rate(),
                "elapsed_time": stats.elapsed_time(),
            }

        # Failover status
        if hasattr(state, "failover_manager") and state.failover_manager:
            failover_status = state.failover_manager.get_status()
            status_data["failover"] = {
                "enabled": state.failover_manager.backup_enabled,
                "active": failover_status.get("failover_active", False),
                "active_store": failover_status.get("active_store_type"),
                "primary_healthy": failover_status.get("primary_healthy", True),
                "circuit_breaker_state": failover_status.get("circuit_breaker_state"),
                "backup_file_exists": failover_status.get("backup_file_exists", False),
                "last_backup_sync": failover_status.get("last_backup_sync"),
            }

        # Statistics snapshot
        statistics = get_session_statistics()
        status_data["statistics"] = {
            "total_requests": statistics.total_requests,
            "successful_requests": statistics.successful_requests,
            "failed_requests": statistics.failed_requests,
            "total_chunks_indexed": statistics.index_statistics.total_operations if statistics.index_statistics else 0,
        }

        return PlainTextResponse(
            content=to_json(status_data), media_type="application/json"
        )

    except Exception:
        _logger.exception("Failed to get status")
        return PlainTextResponse(
            content=to_json({"error": "Failed to get status"}),
            status_code=500,
            media_type="application/json",
        )
```

2. **Register endpoint** (line 431-433):

```python
if endpoint_settings.get("enable_status", True):
    app.custom_route("/status", methods=["GET"], name="status", include_in_schema=True)(status_info)  # type: ignore[arg-type]
```

### Task 16: Implement CLI `status` Command ✨

**Objective**: User-facing status command using unified UI

**Implementation** (`src/codeweaver/cli/commands/status.py` - NEW FILE):

```python
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Status command for runtime operational status."""

from __future__ import annotations

import json
import time
from typing import Any

from cyclopts import App
import httpx

from codeweaver.config import load_settings
from codeweaver.ui import CLIErrorHandler, StatusDisplay


app = App("status", help="Show CodeWeaver runtime status.")


@app.default
def status(
    *,
    verbose: bool = False,
    watch: bool = False,
    watch_interval: int = 5,
) -> None:
    """Show CodeWeaver runtime status.

    Displays current operational state including:
    - Server status (running/stopped)
    - Indexing progress (if active)
    - Failover status (primary/backup mode)
    - Vector store health
    - Request statistics

    Args:
        verbose: Show detailed diagnostic information
        watch: Continuously refresh status (auto-refresh mode)
        watch_interval: Seconds between refreshes in watch mode (default: 5)
    """
    display = StatusDisplay()
    error_handler = CLIErrorHandler(display, verbose=verbose)

    try:
        if watch:
            _watch_status(display, verbose, watch_interval)
        else:
            _show_status_once(display, verbose)
    except KeyboardInterrupt:
        display.console.print("\n")
        return
    except Exception as e:
        error_handler.handle_error(e, context="Status command", exit_code=1)


def _show_status_once(display: StatusDisplay, verbose: bool) -> None:  # noqa: FBT001
    """Show current status once.

    Args:
        display: StatusDisplay for output
        verbose: Show detailed information
    """
    display.print_command_header("status", "CodeWeaver Runtime Status")

    # Load settings to get server info
    settings = load_settings()
    server_url = f"http://{settings.server.host}:{settings.server.port}"

    # Try to query server status endpoint
    status_data = _query_server_status(server_url)

    if status_data is None:
        # Server not running
        _display_server_offline(display, server_url)
        return

    # Server running - display full status
    _display_full_status(display, status_data, verbose)


def _query_server_status(server_url: str) -> dict[str, Any] | None:
    """Query server /status endpoint.

    Args:
        server_url: Base server URL (e.g., http://127.0.0.1:9328)

    Returns:
        Status data dict if server running, None if offline
    """
    try:
        response = httpx.get(f"{server_url}/status", timeout=5.0)
        response.raise_for_status()
        return response.json()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        return None


def _display_server_offline(display: StatusDisplay, server_url: str) -> None:
    """Display message when server is offline.

    Args:
        display: StatusDisplay for output
        server_url: Expected server URL
    """
    display.print_section("Server")
    display.console.print(f"  Status:            ❌ Offline")
    display.console.print(f"  Expected URL:      {server_url}")
    display.console.print()

    display.print_info(
        "Server is not running. Status information is limited to server-based operations.",
        prefix="ℹ️"
    )
    display.console.print()
    display.print_info(
        "Commands like 'index' and 'search' work without the server.",
        prefix="💡"
    )


def _display_full_status(
    display: StatusDisplay, status_data: dict[str, Any], verbose: bool  # noqa: FBT001
) -> None:
    """Display full status when server is running.

    Args:
        display: StatusDisplay for output
        status_data: Status data from /status endpoint
        verbose: Show detailed information
    """
    # Server Section
    display.print_section("Server")
    uptime = status_data.get("uptime_seconds", 0)
    display.console.print(f"  Status:            🟢 Running")
    display.console.print(f"  Uptime:            {_format_duration(uptime)}")
    display.console.print(f"  Timestamp:         {status_data.get('timestamp', 'unknown')}")

    # Indexing Section
    if indexing := status_data.get("indexing"):
        display.print_section("Indexing")

        is_active = indexing.get("active", False)
        status_icon = "🔄" if is_active else "✅"
        status_text = "Active" if is_active else "Idle"

        display.console.print(f"  Status:            {status_icon} {status_text}")
        display.console.print(f"  Files Discovered:  {indexing.get('files_discovered', 0)}")
        display.console.print(f"  Files Processed:   {indexing.get('files_processed', 0)}")
        display.console.print(f"  Chunks Created:    {indexing.get('chunks_created', 0)}")

        if is_active:
            rate = indexing.get('processing_rate', 0.0)
            display.console.print(f"  Processing Rate:   {rate:.2f} files/sec")

    # Failover Section
    if failover := status_data.get("failover"):
        display.print_section("Failover")

        if not failover.get("enabled"):
            display.console.print("  Status:            Disabled")
        elif failover.get("active"):
            # In failover mode
            display.console.print("  Mode:              ⚠️  Backup (Failover Active)")
            display.console.print(f"  Active Store:      {failover.get('active_store', 'unknown')}")
            display.console.print(f"  Primary Status:    ❌ Unhealthy")
            display.console.print(f"  Circuit Breaker:   {failover.get('circuit_breaker_state', 'unknown').upper()}")

            if backup_sync := failover.get("last_backup_sync"):
                display.console.print(f"  Last Backup Sync:  {backup_sync}")

            if failover.get("backup_file_exists"):
                size_mb = failover.get("backup_file_size_bytes", 0) / (1024 * 1024)
                display.console.print(f"  Backup File Size:  {size_mb:.2f} MB")
        else:
            # Primary mode
            display.console.print("  Mode:              ✅ Primary")
            display.console.print(f"  Active Store:      {failover.get('active_store', 'unknown')}")
            display.console.print(f"  Primary Status:    ✅ Healthy")

            if backup_sync := failover.get("last_backup_sync"):
                display.console.print(f"  Last Backup Sync:  {backup_sync}")

    # Statistics Section
    if stats := status_data.get("statistics"):
        display.print_section("Statistics")
        display.console.print(f"  Total Requests:    {stats.get('total_requests', 0)}")
        display.console.print(f"  Successful:        {stats.get('successful_requests', 0)}")
        display.console.print(f"  Failed:            {stats.get('failed_requests', 0)}")
        display.console.print(f"  Chunks Indexed:    {stats.get('total_chunks_indexed', 0)}")

    # Verbose details
    if verbose:
        display.print_section("Raw Status Data")
        display.console.print(json.dumps(status_data, indent=2))


def _watch_status(display: StatusDisplay, verbose: bool, interval: int) -> None:  # noqa: FBT001
    """Continuously refresh status display.

    Args:
        display: StatusDisplay for output
        verbose: Show detailed information
        interval: Seconds between refreshes
    """
    display.console.print(f"Watching status (refreshing every {interval}s, Ctrl+C to stop)...\n")

    while True:
        # Clear screen
        display.console.clear()

        # Show status
        _show_status_once(display, verbose)

        # Wait for refresh interval
        time.sleep(interval)


def _format_duration(seconds: int) -> str:
    """Format seconds as human-readable duration.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "5m 23s", "2h 15m", "3d 4h")
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"


def main() -> None:
    """Entry point for status command."""
    app()


if __name__ == "__main__":
    main()
```

**Register Command** (`src/codeweaver/cli/__main__.py`):
```python
from codeweaver.cli.commands import status

app.command(status.app)
```

### Task 17: Add Failover Notifications ✨

**Objective**: Send notifications to MCP clients on failover events

**Implementation** (`src/codeweaver/engine/failover.py`):

1. **Add context tracking**:

```python
from fastmcp import Context

class VectorStoreFailoverManager:
    def __init__(self, ...):
        # ... existing init ...
        self._last_context: Context | None = None  # Track last MCP context
```

2. **Update `_activate_failover()` to notify**:

```python
async def _activate_failover(self) -> None:
    # ... existing activation code ...

    # Notify client if context available
    if self._last_context:
        await log_to_client_or_fallback(
            self._last_context,
            "warning",
            {
                "msg": "⚠️ Failover activated - switched to backup vector store",
                "extra": {
                    "reason": "Primary vector store unhealthy",
                    "active_store": "backup",
                    "backup_file_exists": backup_file.exists(),
                }
            }
        )
```

3. **Update `_restore_to_primary()` to notify**:

```python
async def _restore_to_primary(self) -> None:
    # ... existing restoration code ...

    # Notify client
    if self._last_context:
        await log_to_client_or_fallback(
            self._last_context,
            "info",
            {
                "msg": "✅ Primary vector store restored - normal operation resumed",
                "extra": {
                    "active_store": "primary",
                    "chunks_synced_back": len(new_chunks),
                }
            }
        )
```

4. **Track context in operations** (update tool bindings):

```python
async def find_code_tool(..., context: Context | None = None):
    # Store context for failover notifications
    if context and hasattr(state, "failover_manager"):
        state.failover_manager._last_context = context

    # ... rest of tool implementation
```

### Task 18: Extend MCP Tool Metadata ✨

**Objective**: Include failover status in tool response metadata

**Implementation** (`src/codeweaver/agent_api/find_code/response.py`):

1. **Extend `FindCodeResponseSummary` model**:

```python
class FindCodeResponseSummary(BasedModel):
    # ... existing fields ...

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the search operation"
    )
```

2. **Add metadata in tool response** (`src/codeweaver/server/app_bindings.py`):

```python
async def find_code_tool(...) -> FindCodeResponseSummary:
    # ... existing implementation ...

    response = await find_code(...)

    # Add failover metadata if available
    from codeweaver.server.server import get_state
    state = get_state()

    if hasattr(state, "failover_manager") and state.failover_manager:
        failover_status = state.failover_manager.get_status()
        response.metadata["failover"] = {
            "backup_mode": failover_status.get("failover_active", False),
            "active_store_type": failover_status.get("active_store_type"),
            "primary_healthy": failover_status.get("primary_healthy", True),
        }

    return response
```

## Implementation Order

1. **Task 13**: Extend statistics (foundation)
2. **Task 14**: Extend health service (integrate with existing)
3. **Task 15**: Implement `/status` endpoint (new HTTP endpoint)
4. **Task 16**: CLI `status` command (user interface)
5. **Task 17**: Failover notifications (client communication)
6. **Task 18**: MCP tool metadata (tool integration)

## Testing Plan

### Unit Tests

**Test `FailoverStats`** (`tests/unit/common/test_statistics.py`):
```python
def test_failover_stats_tracks_operations():
    stats = FailoverStats()
    assert stats.failover_count == 0
    # ... test all operations
```

**Test `/status` endpoint** (`tests/unit/server/test_app_bindings.py`):
```python
async def test_status_endpoint_returns_comprehensive_info():
    response = await status_info(Mock())
    assert response.status_code == 200
    data = json.loads(response.body)
    assert "indexing" in data
    assert "failover" in data
```

**Test CLI `status` command** (`tests/unit/cli/commands/test_status.py`):
```python
def test_status_command_handles_server_offline():
    # Mock httpx to raise ConnectError
    ...

def test_status_command_displays_failover_mode():
    # Mock server response with failover active
    ...
```

### Integration Tests

**End-to-End Status Flow** (`tests/integration/test_status_display.py`):
```python
async def test_full_status_flow_with_failover():
    """Test complete status flow: server → endpoint → CLI display"""
    # 1. Start server
    # 2. Trigger failover
    # 3. Query /status endpoint
    # 4. Verify CLI display
```

## Success Criteria

- ✅ `/status` endpoint returns comprehensive operational status
- ✅ CLI `status` command displays status using `StatusDisplay`
- ✅ Handles server offline gracefully
- ✅ Shows failover mode clearly (⚠️ Backup mode vs ✅ Primary mode)
- ✅ Statistics include failover metrics
- ✅ Health endpoint includes failover information
- ✅ MCP clients receive failover notifications
- ✅ Tool metadata includes backup mode indicator
- ✅ Watch mode works (`status --watch`)

## Files to Create

1. `src/codeweaver/cli/commands/status.py` - CLI command (new)
2. `tests/unit/cli/commands/test_status.py` - CLI tests (new)
3. `tests/integration/test_status_display.py` - Integration tests (new)

## Files to Modify

1. `src/codeweaver/common/statistics.py` - Add `FailoverStats`
2. `src/codeweaver/server/health_service.py` - Add failover info
3. `src/codeweaver/server/app_bindings.py` - Add `/status` endpoint
4. `src/codeweaver/engine/failover.py` - Add notifications
5. `src/codeweaver/agent_api/find_code/response.py` - Add metadata field
6. `src/codeweaver/cli/__main__.py` - Register `status` command

## Key Design Decisions

### 1. Separate `/status` from `/health`

**Rationale**:
- `/health` = component health (vector store up/down, circuit breakers)
- `/status` = operational state (what's happening now, progress, failover mode)
- Aligns with TODO comment in `app_bindings.py:433`

### 2. CLI Queries HTTP Endpoint

**Rationale**:
- Consistent with existing architecture
- Server already has all state information
- Clean separation of concerns
- Handles server-optional operation gracefully

### 3. Extend Existing Statistics

**Rationale**:
- `SessionStatistics` is already comprehensive
- Avoids duplicate tracking
- Integrates with existing `/stats` endpoint
- Consistent with project patterns

### 4. Use Existing Client Communication

**Rationale**:
- `log_to_client_or_fallback()` already handles MCP context
- Consistent with existing notification patterns
- Graceful fallback to logging

## Dependencies

- Phase 3 complete (sync-back implementation) ✅
- `httpx` (already in dependencies for HTTP client)
- `StatusDisplay` (existing UI system)
- `SessionStatistics` (existing stats system)
- `HealthService` (existing health system)

## Conclusion

Phase 4 is now properly integrated with existing infrastructure:

**Leverages**:
- ✅ HTTP endpoint system (`app_bindings.py`)
- ✅ Statistics system (`SessionStatistics`)
- ✅ Health service (`HealthService`)
- ✅ Progress tracking patterns (`IndexingStats`)
- ✅ Client communication (`log_to_client_or_fallback`)
- ✅ Unified UI (`StatusDisplay`)

**Adds**:
- ✨ `/status` endpoint (implements TODO from app_bindings.py)
- ✨ `FailoverStats` (extends statistics system)
- ✨ CLI `status` command (user interface)
- ✨ Failover notifications (MCP client communication)
- ✨ Tool metadata (backup mode indicator)

Ready for implementation! 🚀
