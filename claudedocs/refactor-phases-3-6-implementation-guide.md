# CodeWeaver Server Refactor: Phases 3-6 Implementation Guide

## Status: Phases 1-2 Complete ✅

**Phase 1 Complete**: Lifespan architecture separated into `background_services_lifespan()` and `http_lifespan()`
**Phase 2 Complete**: Main orchestration implemented with `run()`, `_run_http_server()`, `_run_stdio_server()`

**Current State**: The core architecture is complete. Backend services are decoupled from MCP server. Main orchestration properly routes between HTTP and stdio modes.

---

## Phase 3: Wire Up CLI Commands

**Goal**: Update CLI commands to use the new `main.run()` orchestrator

**Risk**: 🟢 LOW
**Complexity**: LOW
**Time**: 20-30 min

### Files to Modify

#### 1. `/home/knitli/codeweaver/src/codeweaver/cli/commands/server.py`

**Current State**: Already calls `main.run()` - likely needs no changes!

**Verification**:
```bash
# Check current implementation
grep -A 5 "from codeweaver.main import run" src/codeweaver/cli/commands/server.py
```

**If changes needed**:
The `_run_server()` function should simply call `main.run()` with all parameters passed through. Current implementation at line 40 already does this.

**No action required** - this file is already correctly wired!

---

#### 2. `/home/knitli/codeweaver/src/codeweaver/cli/commands/start.py`

**Current State**: Has manual `start_cw_services()` implementation that duplicates background service logic

**Required Changes**: Replace manual service startup with new `background_services_lifespan()`

**Implementation**:

```python
# File: src/codeweaver/cli/commands/start.py
# Function: start_cw_services()

async def start_cw_services(
    display: StatusDisplay,
    config_path: Path | None = None,
    project_path: Path | None = None,
    *,
    start_mcp_http_server: bool = False,  # Currently unused, reserved for future
    mcp_host: str | None = None,
    mcp_port: PositiveInt | None = None,
) -> None:
    """Start background services using the new lifespan architecture."""

    from codeweaver.config.settings import get_settings
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.server.lifespan import background_services_lifespan
    from codeweaver.server.management import ManagementServer

    # Load settings
    settings = get_settings()
    if config_path:
        settings.config_file = config_path  # type: ignore
    if project_path:
        settings.project_path = project_path

    statistics = get_session_statistics()

    # Use background_services_lifespan (the new Phase 1 implementation)
    async with background_services_lifespan(
        settings=settings,
        statistics=statistics,
        status_display=display,
        verbose=False,
        debug=False,
    ) as background_state:
        # Start management server
        mgmt_host = getattr(settings, "management_host", "127.0.0.1")
        mgmt_port = getattr(settings, "management_port", 9329)

        management_server = ManagementServer(background_state)
        await management_server.start(host=mgmt_host, port=mgmt_port)

        display.print_success("Background services started successfully")
        display.print_info(
            f"Management server: http://{mgmt_host}:{mgmt_port}", prefix="🌐"
        )

        try:
            # Keep services running until interrupted
            await management_server.server_task
        except (KeyboardInterrupt, asyncio.CancelledError):
            display.print_warning("Shutting down background services...")
        finally:
            await management_server.stop()
```

**What This Does**:
- Replaces manual CodeWeaverState creation with `background_services_lifespan()`
- Uses the lifespan context manager for proper initialization/cleanup
- Starts management server with background state
- Waits on management server task (keeps running)
- Clean shutdown on Ctrl+C

**Lines to Replace**: Approximately lines 71-159 in current start.py

**Testing**:
```bash
# After changes
codeweaver start --verbose

# Should show:
# - Background services starting
# - Health checks
# - Management server ready
# - Clean shutdown on Ctrl+C
```

---

### Phase 3 Validation

**Checklist**:
- [ ] `server.py` verified (likely no changes needed)
- [ ] `start.py` updated to use `background_services_lifespan()`
- [ ] Import test: `python -c "from codeweaver.cli.commands import start, server"`
- [ ] Type check: `ty check src/codeweaver/cli/commands/start.py`
- [ ] Manual test: `codeweaver start` starts successfully
- [ ] Manual test: `codeweaver server` starts successfully

**Success Criteria**:
- `codeweaver start` runs background services + management server only
- `codeweaver server` runs full HTTP stack
- Both commands shutdown cleanly on Ctrl+C
- No import errors or type errors

---

## Phase 4: Transport Mode Integration Testing

**Goal**: End-to-end validation that both transport modes work correctly

**Risk**: 🟡 MEDIUM
**Complexity**: MEDIUM
**Time**: 30-45 min

### Test Scenarios

#### Test 1: HTTP Mode Full Stack

```bash
# Start HTTP server
codeweaver server --transport streamable-http --verbose

# Expected output:
# - CodeWeaver header with host:port
# - Health checks running
# - Background indexing starting
# - Management server ready at :9329
# - MCP server ready at :9328

# In another terminal, verify endpoints:
curl http://localhost:9328/mcp  # MCP endpoint
curl http://localhost:9329/health  # Management endpoint

# Verify both respond correctly
```

**Expected Behavior**:
- Server starts without errors
- Both MCP (9328) and Management (9329) servers respond
- Background indexing runs
- Health checks pass (or show degraded state if Qdrant down)
- Clean shutdown on Ctrl+C

#### Test 2: stdio Mode Proxy

**Setup**:
```bash
# Terminal 1: Start HTTP backend first
codeweaver server --transport streamable-http

# Terminal 2: Test stdio proxy
codeweaver server --transport stdio
```

**Expected Behavior**:
- stdio server connects to HTTP backend
- stdio server blocks waiting for MCP protocol input
- Ctrl+C shuts down stdio server cleanly
- HTTP backend continues running

**Note**: Full stdio testing requires an MCP client. For now, verify:
- stdio server starts without errors
- Clean shutdown works
- No error messages about connection to backend

#### Test 3: Daemon Mode

```bash
# Start background services only
codeweaver start --verbose

# Verify management server:
curl http://localhost:9329/health
curl http://localhost:9329/status
curl http://localhost:9329/metrics

# Verify no MCP server:
curl http://localhost:9328/mcp  # Should fail - connection refused
```

**Expected Behavior**:
- Management server responds on 9329
- MCP server NOT running (connection refused on 9328)
- Background indexing runs
- Clean shutdown on Ctrl+C

---

### Phase 4 Validation

**Checklist**:
- [ ] HTTP mode: Both servers (MCP + Management) respond
- [ ] HTTP mode: Background indexing runs successfully
- [ ] HTTP mode: Clean shutdown on Ctrl+C
- [ ] stdio mode: Server starts and connects to backend
- [ ] stdio mode: Clean shutdown on Ctrl+C
- [ ] Daemon mode: Management server only (no MCP)
- [ ] Daemon mode: Background services run
- [ ] All modes: No error messages or tracebacks

**Success Criteria**:
- All three modes start successfully
- All three modes shutdown cleanly
- HTTP endpoints respond correctly
- No regressions in existing functionality

---

## Phase 5: Cleanup Legacy Code

**Goal**: Remove old unused code that's been replaced by new architecture

**Risk**: 🟢 LOW
**Complexity**: LOW
**Time**: 15-20 min

### Code to Remove

#### File: `/home/knitli/codeweaver/src/codeweaver/server/server.py`

**Remove**:

1. **Old `start_server()` function** - No longer used, replaced by `main._run_http_server()`
   - Search for: `async def start_server(`
   - Likely around line 446-499
   - This was the old server startup logic

2. **Old `build_app()` function** - If it exists, no longer used
   - Search for: `def build_app(`
   - This was likely used for building the combined app

**Keep**:
- `CodeWeaverState` dataclass ✅
- `get_state()` global accessor ✅
- `_initialize_cw_state()` helper ✅
- `_cleanup_state()` helper ✅
- `lifespan()` function ✅ (if still exists, used by tests)

**Update `__all__` export**:
```python
__all__ = (
    "CodeWeaverState",
    "get_state",
    # Remove any references to start_server, build_app
)
```

**Validation**:
```bash
# Check what's exported
python -c "from codeweaver.server.server import *; print(dir())"

# Verify no import errors
python -c "from codeweaver.server.server import CodeWeaverState, get_state"

# Type check
ty check src/codeweaver/server/server.py
```

---

#### File: `/home/knitli/codeweaver/src/codeweaver/main.py`

**Already Clean**: Phase 2 implementation replaced all old code. No cleanup needed.

---

### Phase 5 Validation

**Checklist**:
- [ ] Old `start_server()` removed from server.py (if it exists)
- [ ] Old `build_app()` removed from server.py (if it exists)
- [ ] `__all__` updated to remove old exports
- [ ] No unused imports in server.py
- [ ] Type check passes: `ty check src/codeweaver/server/server.py`
- [ ] All tests still pass: `pytest tests/unit/server/`
- [ ] No import errors in dependent code

**Success Criteria**:
- No old/unused functions remain
- Cleaner, more maintainable codebase
- All tests pass
- No regressions

---

## Phase 6: Integration Testing

**Goal**: Comprehensive end-to-end validation of all modes and error scenarios

**Risk**: 🔴 HIGH (this validates everything)
**Complexity**: HIGH
**Time**: 60-90 min

### Test Matrix

| Test Case | Command | Expected Result | Validation Method |
|-----------|---------|-----------------|-------------------|
| **HTTP Server** | `codeweaver server` | MCP:9328, Mgmt:9329 | `curl` both endpoints |
| **HTTP Verbose** | `codeweaver server -v` | Logs visible | Check stdout |
| **stdio Server** | `codeweaver server -t stdio` | Proxy works | Starts without error |
| **Daemon Mode** | `codeweaver start` | Mgmt:9329 only | MCP port refuses connection |
| **Custom Config** | `codeweaver server -c config.toml` | Uses config | Check settings endpoint |
| **Graceful Shutdown** | Ctrl+C during index | Clean exit | No errors, exit code 0 |
| **Force Shutdown** | Double Ctrl+C | Immediate exit | Exit code 1 |
| **Port Conflict** | Start two servers | Error message | Clear error about port in use |

---

### Error Scenario Testing

#### Test: Missing Dependencies (Qdrant)

```bash
# Stop Qdrant if running
docker stop qdrant 2>/dev/null || true

# Start server
codeweaver server --verbose

# Expected:
# - Server starts successfully
# - Vector store shows "degraded" or "down" in health
# - Helpful message: "To enable semantic search: docker run -p 6333:6333 qdrant/qdrant"
# - Server continues with sparse-only search
# - No crashes or errors
```

**Validation**:
```bash
curl http://localhost:9329/health | jq '.services.vector_store.status'
# Should show: "down" or "degraded"
```

---

#### Test: Port Conflicts

```bash
# Start first server
codeweaver server &
sleep 5

# Try to start second server (should fail)
codeweaver server

# Expected:
# - Clear error message about port 9328 already in use
# - Suggests checking if server already running
# - Exit code non-zero
```

---

#### Test: Invalid Configuration

```bash
# Test with nonexistent config file
codeweaver server -c /nonexistent/config.toml

# Expected:
# - Clear error message about config file not found
# - Exit code non-zero
# - No traceback (clean error handling)
```

---

### Performance Validation

**Metrics to Check**:

1. **Startup Time**: Server should start in < 5 seconds
   ```bash
   time codeweaver server
   # Measure time to "ready" message
   ```

2. **Memory Usage**: Idle server should use < 500MB
   ```bash
   # Start server
   codeweaver server &

   # After startup, check memory
   ps aux | grep codeweaver | awk '{print $6/1024 " MB"}'
   ```

3. **Indexing Performance**: Should complete without memory leaks
   ```bash
   # Start server, let it index, wait 10 minutes
   # Check memory hasn't grown excessively
   ```

4. **Health Check Latency**: Health endpoint should respond in < 100ms
   ```bash
   time curl http://localhost:9329/health
   ```

---

### Regression Testing

**Critical Functionality to Verify**:

1. **Background Indexing**:
   - [ ] Indexing starts automatically on server start
   - [ ] File watcher detects changes
   - [ ] Progress is displayed correctly
   - [ ] Summary statistics shown at completion

2. **Health Monitoring**:
   - [ ] All services show correct status
   - [ ] Degraded states handled gracefully
   - [ ] Health endpoint responds correctly

3. **Statistics**:
   - [ ] Request counting works
   - [ ] Metrics endpoint returns valid data
   - [ ] Statistics persist across requests

4. **Telemetry** (if enabled):
   - [ ] Session starts correctly
   - [ ] Events logged properly
   - [ ] Clean shutdown sends final telemetry

---

### Phase 6 Validation

**Comprehensive Checklist**:

**Functionality**:
- [ ] All test matrix cases pass
- [ ] Error scenarios handled gracefully
- [ ] Performance metrics acceptable
- [ ] No regressions in existing features

**Code Quality**:
- [ ] All type checks pass
- [ ] All linters pass
- [ ] No TODO comments for critical functionality
- [ ] Documentation updated

**Deployment Readiness**:
- [ ] Both transport modes work
- [ ] Daemon mode works independently
- [ ] Clean error messages for common failures
- [ ] Logs are clean and helpful

---

## Final Acceptance Criteria

**The refactor is complete when**:

✅ **Architectural**:
- Background services completely independent of MCP server
- stdio and HTTP transports both functional
- Clean separation of concerns maintained

✅ **Functional**:
- `codeweaver server` starts HTTP MCP + background + management
- `codeweaver server -t stdio` starts stdio proxy
- `codeweaver start` starts background services only
- All modes shutdown cleanly

✅ **Quality**:
- All type checks pass
- All linters pass
- No regressions in tests
- Code is cleaner than before

✅ **Tested**:
- HTTP mode: Both servers respond, indexing works
- stdio mode: Proxy connects and works
- Daemon mode: Management only, no MCP
- Error cases handled gracefully
- Performance acceptable

---

## Quick Reference Commands

### Testing Commands

```bash
# Phase 3 validation
codeweaver start --verbose
codeweaver server --verbose

# Phase 4 validation
codeweaver server --transport streamable-http
codeweaver server --transport stdio
curl http://localhost:9328/mcp
curl http://localhost:9329/health

# Phase 5 validation
ty check src/codeweaver/server/server.py
pytest tests/unit/server/

# Phase 6 validation
# Run all test matrix commands
# Run all error scenario tests
# Check performance metrics
```

### Debugging Commands

```bash
# Check what's running
ps aux | grep codeweaver
lsof -i :9328
lsof -i :9329

# Check logs
tail -f ~/.local/state/codeweaver/logs/codeweaver.log

# Test endpoints
curl -v http://localhost:9328/mcp
curl -v http://localhost:9329/health | jq '.'
curl -v http://localhost:9329/status | jq '.'
```

---

## Rollback Strategy

If something breaks:

```bash
# Phase 3 issues
git reset --hard <commit-before-phase-3>

# Phase 4 issues
# No code changes, just testing

# Phase 5 issues
git reset --hard <commit-before-phase-5>

# Phase 6 issues
# No code changes, just testing
```

---

## Notes for Future Implementer

**What's Done**:
- Phase 1: Lifespan architecture separated and working
- Phase 2: Main orchestration complete and working
- All type checks pass
- Architecture is sound

**What's Left**:
- Phase 3: Mostly updating start.py (~30 lines)
- Phase 4: Just testing, no code changes
- Phase 5: Removing old code (~50 lines)
- Phase 6: Comprehensive testing, no code changes

**Estimated Time**: 2-3 hours total for phases 3-6

**Key Files**:
- `src/codeweaver/cli/commands/start.py` - Main work in Phase 3
- `src/codeweaver/server/server.py` - Cleanup in Phase 5
- Everything else is testing and validation

**The Hard Part is Done**: The core architecture (phases 1-2) is complete and working. What remains is wiring and testing.
