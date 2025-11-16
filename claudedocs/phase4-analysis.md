# Phase 4 Analysis: CLI UI Integration and Command Planning

**Date**: 2025-01-15
**Purpose**: Analyze unified UI system, validate command overlap, and update Phase 4 plan

## Unified UI System (`codeweaver.ui`)

### Architecture Overview

CodeWeaver has a centralized UI system that **all CLI commands must use** for user-facing output:

```python
from codeweaver.ui import CLIErrorHandler, StatusDisplay
```

### Core Components

#### 1. `StatusDisplay` Class

**Purpose**: Rich-based console output for clean, formatted status messages

**Key Methods**:

```python
class StatusDisplay:
    # Headers and structure
    def print_header(host: str, port: int) -> None
    def print_command_header(command: str, description: str | None) -> None
    def print_section(title: str) -> None

    # Status messages
    def print_step(message: str) -> None
    def print_completion(message: str, *, success: bool, details: str | None) -> None
    def print_success(message: str, *, details: str | None) -> None
    def print_error(message: str, *, details: str | None) -> None
    def print_warning(message: str) -> None
    def print_info(message: str, *, prefix: str) -> None

    # Specialized output
    def print_health_check(service_name: str, status: Literal["up", "down", "degraded"], *, model: str | None) -> None
    def print_indexing_stats(files_indexed: int, chunks_created: int, duration_seconds: float, files_per_second: float) -> None
    def print_table(table: Table) -> None
    def print_progress(current: int, total: int, message: str) -> None

    # Interactive elements
    @contextmanager
    def spinner(message: str, *, spinner_style: str) -> Generator[None, None, None]

    @contextmanager
    def live_progress(description: str) -> Generator[Progress, None, None]
```

**Implementation Pattern**:
```python
from codeweaver.ui import StatusDisplay

def my_command():
    display = StatusDisplay()

    display.print_command_header("my-command", "Command description")

    display.print_step("Starting operation...")

    # Do work

    display.print_completion("Operation complete", success=True, details="(42 items)")
```

#### 2. `CLIErrorHandler` Class

**Purpose**: Unified error handling with consistent formatting

**Features**:
- Handles `CodeWeaverError` with suggestions and details
- Handles unexpected exceptions with full tracebacks
- Supports verbose/debug modes
- Automatic exit code management

**Implementation Pattern**:
```python
from codeweaver.ui import CLIErrorHandler, StatusDisplay

def my_command(verbose: bool = False):
    display = StatusDisplay()
    error_handler = CLIErrorHandler(display, verbose=verbose)

    try:
        # Command logic
        pass
    except Exception as e:
        error_handler.handle_error(e, context="My command", exit_code=1)
```

## Existing `doctor` Command

### Purpose
System diagnostics and configuration validation - **NOT runtime status**

### Scope
Validates **prerequisite conditions** for CodeWeaver operation:

1. **Python Version**: Checks ≥3.12 requirement
2. **Dependencies**: Verifies all required packages installed
3. **Project Path**: Confirms valid git repository
4. **Configuration File**: Validates `.codeweaver.toml` exists and loads
5. **Vector Store Config**: Checks Qdrant configuration (local/cloud/remote)
6. **Indexer Config**: Validates cache directory permissions
7. **Provider Availability**: Tests package installation and authentication

### Output Format
```
┌────────────────────────┬──────────┬────────────────────────────┐
│ Check                  │ Status   │ Message                    │
├────────────────────────┼──────────┼────────────────────────────┤
│ Python Version         │ ✅       │ 3.12.1                     │
│ Required Dependencies  │ ✅       │ All packages installed     │
│ Vector Store Config    │ ✅       │ Qdrant local (running)     │
└────────────────────────┴──────────┴────────────────────────────┘

✅ All checks passed
```

### When to Run
- **Installation**: After installing CodeWeaver
- **Configuration Changes**: After modifying settings
- **Troubleshooting**: When commands fail unexpectedly
- **Pre-flight**: Before starting server or indexing

### What It Does NOT Do
- ❌ Show runtime failover status
- ❌ Display backup mode state
- ❌ Report indexing progress
- ❌ Monitor health checks
- ❌ Show sync-back status

## Proposed `status` Command (Phase 4)

### Purpose
**Runtime status reporting** - show current operational state

### Scope
Displays **dynamic runtime information**:

1. **Failover Status**: Primary/backup mode, failover time
2. **Active Store**: Which vector store is currently active
3. **Health Status**: Circuit breaker states, last health check
4. **Backup State**:
   - Backup file existence and size
   - Last backup sync time
   - Changes tracked during failover
5. **Sync Status**: Sync-back progress if restoration in progress
6. **MCP Server Status**: Server running/stopped, port

### Output Format (Proposed)
```
CodeWeaver Status

Vector Store:
  Mode:              ⚠️ Backup (Failover Active)
  Active Store:      InMemoryVectorStoreProvider
  Primary Status:    ❌ Unhealthy (Circuit Breaker: OPEN)
  Failover Since:    2025-01-15 14:32:10 UTC (5m 23s ago)

Backup:
  File:              .codeweaver/backup/vector_store.json
  Size:              15.2 MB
  Last Sync:         2025-01-15 14:35:00 UTC (2m 33s ago)
  Changes Tracked:   127 chunks indexed during failover

Health:
  Last Check:        2025-01-15 14:37:30 UTC (3s ago)
  Next Check:        2025-01-15 14:38:00 UTC (in 27s)

MCP Server:
  Status:            🟢 Running
  URL:               http://127.0.0.1:9328/codeweaver
```

### Command Signature
```python
@app.command
def status(
    *,
    verbose: bool = False,
    watch: bool = False,  # Optional: auto-refresh mode
) -> None:
    """Show CodeWeaver runtime status.

    Displays current operational state including failover status,
    backup mode, health checks, and vector store information.

    Args:
        verbose: Show detailed diagnostic information
        watch: Continuously refresh status (like `watch` command)
    """
```

## Command Comparison Matrix

| Aspect | `doctor` | `status` |
|--------|----------|----------|
| **Purpose** | Validate prerequisites | Show runtime state |
| **Timing** | Pre-operation / troubleshooting | During operation |
| **Focus** | Configuration correctness | Operational health |
| **Data Type** | Static (config files, packages) | Dynamic (failover, health) |
| **Output** | Validation results + suggestions | Current state + metrics |
| **When to Use** | Setup, config changes, debugging | Monitoring, operations |
| **Frequency** | Occasional (on-demand) | Regular (monitoring) |

### No Overlap Confirmed ✅

The commands serve **completely different purposes**:

- **`doctor`**: "Is my CodeWeaver **configured** correctly?"
- **`status`**: "What is CodeWeaver **doing** right now?"

They are complementary, not duplicative.

## Updated Phase 4 Implementation Plan

### Original Phase 4 Scope (from proposal)
```
### Phase 4: Communication (Week 2-3)
13. Add user-facing status reporting
14. Implement logging and notifications
15. CLI `status` command
16. MCP tool metadata for backup mode
```

### Updated Phase 4 Plan (UI-Integrated)

#### Task 13: User-Facing Status Reporting ✨ NEW

**Implementation**:
1. Add `get_status_report()` method to `VectorStoreFailoverManager`
2. Return structured status dict (not just bool flags)
3. Use existing `get_status()` as foundation

**Required Changes** (`src/codeweaver/engine/failover.py`):
```python
def get_status_report(self) -> dict[str, Any]:
    """Get comprehensive status report for user display.

    Returns structured data suitable for StatusDisplay formatting.
    """
    from datetime import datetime, UTC

    status = self.get_status()  # Existing status dict

    # Add human-readable fields
    if status.get("failover_time"):
        failover_dt = datetime.fromisoformat(status["failover_time"])
        now = datetime.now(UTC)
        elapsed = now - failover_dt
        status["failover_duration_seconds"] = elapsed.total_seconds()
        status["failover_duration_human"] = self._format_duration(elapsed)

    # Add backup file info
    backup_file = self._backup_store._backup_file if self._backup_store else None
    if backup_file and backup_file.exists():
        status["backup_file_path"] = str(backup_file)
        status["backup_file_size_mb"] = backup_file.stat().st_size / (1024 * 1024)

    # Add sync status if in progress
    if hasattr(self, "_sync_in_progress") and self._sync_in_progress:
        status["sync_status"] = {
            "active": True,
            "synced_count": getattr(self, "_synced_count", 0),
            "total_count": getattr(self, "_total_to_sync", 0),
        }

    return status

@staticmethod
def _format_duration(delta: timedelta) -> str:
    """Format timedelta as human-readable string."""
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"
```

#### Task 14: Logging and Notifications ✅ COMPLETE

**Status**: Already implemented in Phases 1-3
- Comprehensive logging throughout failover lifecycle
- Health check logging
- Sync-back progress logging
- Error and warning notifications

**No changes needed** - existing logging is sufficient.

#### Task 15: CLI `status` Command ✨ NEW

**File**: `src/codeweaver/cli/commands/status.py` (new file)

**Implementation**:
```python
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Status command for runtime operational status."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cyclopts import App
from rich.table import Table

from codeweaver.ui import CLIErrorHandler, StatusDisplay


if TYPE_CHECKING:
    pass


app = App("status", help="Show CodeWeaver runtime status.")


@app.default
def status(
    *,
    verbose: bool = False,
    watch: bool = False,
) -> None:
    """Show CodeWeaver runtime status.

    Displays current operational state including:
    - Failover status (primary/backup mode)
    - Active vector store
    - Health check results
    - Backup state and sync information
    - MCP server status

    Args:
        verbose: Show detailed diagnostic information
        watch: Continuously refresh status (auto-refresh mode)
    """
    display = StatusDisplay()
    error_handler = CLIErrorHandler(display, verbose=verbose)

    try:
        if watch:
            _watch_status(display, verbose)
        else:
            asyncio.run(_show_status(display, verbose))
    except KeyboardInterrupt:
        display.console.print("\n")
        return
    except Exception as e:
        error_handler.handle_error(e, context="Status command", exit_code=1)


async def _show_status(display: StatusDisplay, verbose: bool) -> None:  # noqa: FBT001
    """Show current status once.

    Args:
        display: StatusDisplay for output
        verbose: Show detailed information
    """
    from codeweaver.config import load_settings
    from codeweaver.engine.failover import VectorStoreFailoverManager

    # Load settings
    settings = load_settings()

    # Get failover manager status (would need to access running instance or reconstruct)
    # For now, this is a placeholder - actual implementation would need to:
    # 1. Connect to running MCP server to get status, OR
    # 2. Read from shared state file, OR
    # 3. Query vector store directly

    display.print_command_header("status", "CodeWeaver Runtime Status")

    # Vector Store Section
    display.print_section("Vector Store")

    # This would come from failover manager
    failover_active = False  # Placeholder

    if failover_active:
        display.console.print("  Mode:              ⚠️  Backup (Failover Active)")
        display.console.print("  Active Store:      InMemoryVectorStoreProvider")
        display.console.print("  Primary Status:    ❌ Unhealthy (Circuit Breaker: OPEN)")
        display.console.print("  Failover Since:    2025-01-15 14:32:10 UTC (5m 23s ago)")
    else:
        display.console.print("  Mode:              ✅ Primary")
        display.console.print("  Active Store:      QdrantVectorStoreProvider")
        display.console.print("  Primary Status:    ✅ Healthy")

    # Backup Section (if enabled)
    if settings.backup_enabled:
        display.print_section("Backup")
        display.console.print("  File:              .codeweaver/backup/vector_store.json")
        display.console.print("  Size:              15.2 MB")
        display.console.print("  Last Sync:         2025-01-15 14:35:00 UTC (2m 33s ago)")
        if failover_active:
            display.console.print("  Changes Tracked:   127 chunks indexed during failover")

    # Health Section
    display.print_section("Health")
    display.console.print("  Last Check:        2025-01-15 14:37:30 UTC (3s ago)")
    display.console.print("  Next Check:        2025-01-15 14:38:00 UTC (in 27s)")

    # Server Section
    display.print_section("MCP Server")
    display.console.print("  Status:            🟢 Running")
    display.console.print(f"  URL:               http://{settings.server.host}:{settings.server.port}/codeweaver")

    # Verbose details
    if verbose:
        display.print_section("Detailed Diagnostics")
        # Add verbose information
        pass


def _watch_status(display: StatusDisplay, verbose: bool) -> None:  # noqa: FBT001
    """Continuously refresh status display.

    Args:
        display: StatusDisplay for output
        verbose: Show detailed information
    """
    import time

    display.console.print("Watching status (Ctrl+C to stop)...\n")

    while True:
        # Clear screen
        display.console.clear()

        # Show status
        asyncio.run(_show_status(display, verbose))

        # Wait for refresh interval
        time.sleep(5)


def main() -> None:
    """Entry point for status command."""
    app()


if __name__ == "__main__":
    main()
```

**Integration** (`src/codeweaver/cli/__main__.py`):
```python
# Add to command imports
from codeweaver.cli.commands import status

# Register command
app.command(status.app)
```

#### Task 16: MCP Tool Metadata for Backup Mode ✨ NEW

**Purpose**: Let MCP clients know when backup mode is active

**Implementation** (`src/codeweaver/server/server.py`):

```python
# In server initialization or tool registration
def get_tool_metadata() -> dict[str, Any]:
    """Get metadata for MCP tools including operational state."""
    from codeweaver.engine.failover import get_failover_manager

    manager = get_failover_manager()  # Singleton or from app context
    status = manager.get_status()

    return {
        "backup_mode": status.get("failover_active", False),
        "active_store": status.get("active_store_type", "unknown"),
        "last_health_check": status.get("last_health_check"),
    }

# In find_code tool or other MCP responses
async def find_code(...) -> FindCodeResponse:
    # ... existing logic ...

    # Add metadata to response
    metadata = get_tool_metadata()
    response.metadata = metadata

    return response
```

## Implementation Checklist

### Phase 4 Tasks

- [ ] **Task 13**: Add `get_status_report()` to `VectorStoreFailoverManager`
  - [ ] Implement human-readable duration formatting
  - [ ] Add backup file size calculation
  - [ ] Add sync progress tracking
  - [ ] Unit tests for status report generation

- [ ] **Task 14**: ✅ **Logging** (already complete)

- [ ] **Task 15**: Create `status` command
  - [ ] Create `src/codeweaver/cli/commands/status.py`
  - [ ] Implement `_show_status()` display logic
  - [ ] Implement `_watch_status()` auto-refresh mode
  - [ ] Integrate with CLI app in `__main__.py`
  - [ ] Add command tests
  - [ ] Handle case when server not running (graceful degradation)
  - [ ] **Challenge**: Access running server's failover state
    - Option A: HTTP endpoint on MCP server for status queries
    - Option B: Shared state file (JSON) written by server
    - Option C: Query vector store directly for circuit breaker state

- [ ] **Task 16**: MCP tool metadata
  - [ ] Add metadata to `FindCodeResponse` type
  - [ ] Implement `get_tool_metadata()` in server
  - [ ] Include in all MCP tool responses
  - [ ] Update MCP tool schemas to include metadata field
  - [ ] Document metadata format for clients

### Additional Considerations

#### Challenge: Accessing Running Server State

**Problem**: CLI `status` command needs to access live failover manager state, but runs in separate process from MCP server.

**Solution Options**:

1. **HTTP Status Endpoint** (Recommended):
   ```python
   # In server.py - add FastAPI endpoint
   @app.get("/api/status")
   async def get_status_endpoint():
       manager = get_failover_manager()
       return manager.get_status_report()
   ```

   **Pros**: Clean separation, works remotely, RESTful
   **Cons**: Requires server running, needs HTTP client in CLI

2. **Shared State File**:
   ```python
   # Server writes state periodically
   state_file = Path.home() / ".codeweaver" / "state.json"
   state_file.write_text(json.dumps(manager.get_status_report()))
   ```

   **Pros**: Works without server, simple
   **Cons**: Stale data, file sync issues, write overhead

3. **Direct Vector Store Query**:
   ```python
   # CLI queries vector store directly
   from codeweaver.providers.vector_stores import get_vector_store
   store = get_vector_store(settings)
   # Check circuit breaker state
   ```

   **Pros**: Always accurate, no server dependency
   **Cons**: Complex, requires provider initialization, slow

**Recommendation**: **Option 1 (HTTP endpoint)** with graceful fallback to Option 3 if server not running.

#### UI Integration Examples

All output MUST use `StatusDisplay`:

```python
# ✅ CORRECT - Uses StatusDisplay
from codeweaver.ui import StatusDisplay

display = StatusDisplay()
display.print_info("Failover mode active")
display.print_warning("Primary vector store unhealthy")
display.print_success("Backup activated successfully")

# ❌ WRONG - Direct print()
print("Failover mode active")  # NO!
console.print("Status...")      # NO!
logger.info("Status...")         # NO! (logging is for diagnostics, not user output)
```

## Success Criteria

Phase 4 will be complete when:

1. ✅ **Status Command Works**: `codeweaver status` displays current operational state
2. ✅ **Failover Visible**: Users can see when backup mode is active
3. ✅ **Sync Progress Shown**: Sync-back progress is visible during restoration
4. ✅ **MCP Metadata**: Tools include backup mode indicator in responses
5. ✅ **UI Consistency**: All output uses `StatusDisplay` consistently
6. ✅ **No Overlap**: `doctor` and `status` serve distinct purposes
7. ✅ **Watch Mode Works**: `codeweaver status --watch` auto-refreshes

## Testing Plan

### Unit Tests

```python
# tests/unit/cli/commands/test_status.py

class TestStatusCommand:
    async def test_status_shows_primary_mode(self):
        """Test status display when primary is active."""

    async def test_status_shows_failover_mode(self):
        """Test status display when in failover mode."""

    async def test_status_shows_backup_info(self):
        """Test backup section shows file size and sync time."""

    async def test_watch_mode_refreshes(self):
        """Test watch mode updates display periodically."""

class TestStatusReporting:
    async def test_get_status_report_includes_human_duration(self):
        """Test human-readable duration formatting."""

    async def test_status_report_includes_backup_file_size(self):
        """Test backup file size calculation."""
```

### Integration Tests

```python
# tests/integration/test_status_command.py

class TestStatusCommandIntegration:
    async def test_status_reads_from_running_server(self):
        """Test status command reads from live MCP server."""

    async def test_status_graceful_when_server_stopped(self):
        """Test status command handles server not running."""
```

## Conclusion

Phase 4 implementation is clear and distinct from existing functionality:

### Key Points

1. **No Overlap**: `doctor` (config validation) and `status` (runtime monitoring) serve different purposes
2. **UI Integration**: All output uses `StatusDisplay` - implementation pattern is established
3. **Implementation Path**: Clear tasks with specific code locations
4. **Main Challenge**: Accessing live server state - solvable with HTTP endpoint
5. **Testing Strategy**: Comprehensive unit and integration tests

### Next Steps

1. Implement `get_status_report()` in failover manager
2. Create HTTP status endpoint in MCP server
3. Implement `status` command using `StatusDisplay`
4. Add MCP tool metadata to responses
5. Write comprehensive tests
6. Document usage in user guide

Phase 4 is ready for implementation! 🚀
