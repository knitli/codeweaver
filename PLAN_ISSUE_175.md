<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Claude (AI Assistant)

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Implementation Plan: Fix Stop Command and Improve CLI Start/Stop Behaviors

**Issue**: #175
**Branch**: feat-background-services
**Created**: 2025-12-01

## Problem Analysis

### Critical Bug in stop.py:47
```python
os.kill(os.getpid(), signal.SIGTERM)
```
This code sends SIGTERM to the **stop command's own process**, not the background services process. The stop command immediately terminates itself without affecting the background services.

### Current Behavior
- `cw start` runs services in **foreground mode** (blocks until Ctrl+C)
- No daemon mode support
- No PID file tracking
- Stop command kills itself instead of background services

### Required Behavior
1. `cw start` should default to **daemon mode** (background, detached)
2. Add `--no-daemon` flag to optionally run in foreground
3. `cw stop` should reliably terminate background services
4. Proper PID file management for process tracking

## Constitutional Requirements

From `.specify/memory/constitution.md`:

1. **Evidence-Based Development (NON-NEGOTIABLE)**: No workarounds, mock implementations, or placeholder code
2. **Proven Patterns**: Use established patterns from pydantic ecosystem
3. **Type System Discipline**: Strict typing with `Protocol`, `TypedDict`, etc.
4. **Testing Philosophy**: Integration tests preferred over unit tests
5. **Simplicity Through Architecture**: Clear, obvious purpose

## Solution Design

### 1. Daemon Utilities Module

**File**: `src/codeweaver/cli/daemon.py`

**Responsibilities**:
- PID file management (create, read, remove, validate)
- Daemon process creation (fork, detach, redirect I/O)
- Signal handling for graceful shutdown
- Process existence checking

**Key Functions**:
```python
class DaemonManager:
    """Manages daemon process lifecycle with PID file tracking."""

    def __init__(self, pid_file_path: Path):
        """Initialize daemon manager with PID file path."""

    def is_running(self) -> bool:
        """Check if daemon is running based on PID file."""

    def get_pid(self) -> int | None:
        """Read PID from file if it exists."""

    def write_pid(self, pid: int) -> None:
        """Write PID to file."""

    def remove_pid_file(self) -> None:
        """Remove PID file (cleanup)."""

    def daemonize(self) -> None:
        """Fork and detach process to run as daemon."""

    def send_signal(self, sig: signal.Signals) -> bool:
        """Send signal to daemon process."""
```

**PID File Location**: `~/.codeweaver/background_services.pid`

**Daemon Process Steps**:
1. Fork first child (parent exits)
2. Create new session (setsid)
3. Fork second child (session leader exits)
4. Change working directory to `/`
5. Set umask to 0
6. Redirect stdin, stdout, stderr to `/dev/null` (or log file)
7. Write PID to file
8. Install signal handlers (SIGTERM, SIGINT)

### 2. Update start.py

**Changes**:
1. Add `--no-daemon` flag (default: daemon mode)
2. Integrate `DaemonManager`
3. Fork process if daemon mode enabled
4. Update display messages based on mode

**New Parameters**:
```python
@app.default
async def start(
    ...,
    *,
    daemon: bool = True,  # Default to daemon mode
    ...
) -> None:
```

**Logic Flow (Daemon Mode)**:
```
1. Check if already running (via DaemonManager.is_running())
2. If running, display message and exit
3. Fork process (DaemonManager.daemonize())
4. Child process:
   - Write PID to file
   - Start background services
   - Install signal handlers
   - Wait indefinitely
5. Parent process:
   - Display success message
   - Exit immediately
```

**Logic Flow (Foreground Mode with --no-daemon)**:
```
1. Check if already running
2. If running, display message and exit
3. Start background services (current behavior)
4. Block until Ctrl+C
5. Clean shutdown
```

### 3. Fix stop.py

**Changes**:
1. Integrate `DaemonManager`
2. Read PID from file
3. Send SIGTERM to **daemon process**, not self
4. Wait for shutdown confirmation
5. Clean up PID file

**New Logic**:
```python
async def stop_background_services(daemon_manager: DaemonManager) -> None:
    """Stop background services gracefully using signal."""
    pid = daemon_manager.get_pid()

    if pid is None:
        raise RuntimeError("Cannot find background services process")

    # Send SIGTERM to daemon process (NOT os.getpid()!)
    success = daemon_manager.send_signal(signal.SIGTERM)

    if not success:
        raise RuntimeError(f"Failed to signal process {pid}")

    # Wait for process to stop (with timeout)
    await wait_for_shutdown(daemon_manager, timeout=10)

    # Clean up PID file
    daemon_manager.remove_pid_file()
```

### 4. Signal Handling

**Graceful Shutdown Sequence**:
1. Receive SIGTERM or SIGINT
2. Set shutdown flag
3. Stop accepting new requests
4. Flush statistics
5. Close connections
6. Stop background tasks
7. Remove PID file
8. Exit cleanly

**Implementation** (in start.py):
```python
def setup_signal_handlers(daemon_manager: DaemonManager) -> None:
    """Install signal handlers for graceful shutdown."""

    def handle_shutdown(signum, frame):
        # Set flag for async shutdown
        asyncio.create_task(graceful_shutdown(daemon_manager))

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
```

### 5. Update status.py

**Enhancement**: Show daemon status

**New Information**:
- Daemon mode vs foreground mode
- PID of running process
- Location of PID file

### 6. Testing Strategy

**Integration Tests** (preferred per constitution):

1. **Test daemon mode start**:
   ```python
   async def test_start_daemon_mode():
       # Start in daemon mode
       # Verify PID file created
       # Verify process is running
       # Verify management server responds
       # Stop daemon
       # Verify cleanup
   ```

2. **Test foreground mode start**:
   ```python
   async def test_start_foreground_mode():
       # Start with --no-daemon
       # Verify no PID file created
       # Verify process blocks
       # Send SIGTERM
       # Verify graceful shutdown
   ```

3. **Test stop command**:
   ```python
   async def test_stop_daemon():
       # Start daemon
       # Run stop command
       # Verify SIGTERM sent to daemon
       # Verify daemon stops
       # Verify PID file removed
   ```

4. **Test stop when not running**:
   ```python
   async def test_stop_not_running():
       # Ensure no daemon running
       # Run stop command
       # Verify graceful error message
   ```

5. **Test multiple start attempts**:
   ```python
   async def test_start_already_running():
       # Start daemon
       # Try starting again
       # Verify second start detects first
       # Verify no duplicate processes
   ```

## Implementation Steps

1. ✅ Create planning document
2. Create `src/codeweaver/cli/daemon.py` with `DaemonManager` class
3. Update `src/codeweaver/cli/commands/start.py`:
   - Add daemon mode support
   - Add `--no-daemon` flag
   - Integrate `DaemonManager`
   - Add signal handlers
4. Fix `src/codeweaver/cli/commands/stop.py`:
   - Replace buggy `os.kill(os.getpid(), ...)`
   - Use `DaemonManager` to signal correct process
   - Add shutdown confirmation
5. Update `src/codeweaver/cli/commands/status.py`:
   - Show daemon vs foreground status
   - Display PID information
6. Add integration tests in `tests/integration/cli/test_daemon_lifecycle.py`
7. Run pre-commit checks (`hk check`, `hk fix`)
8. Test manually:
   - `cw start` (daemon mode)
   - `cw status` (verify daemon running)
   - `cw stop` (verify stops)
   - `cw start --no-daemon` (foreground mode)
9. Commit and create PR

## Edge Cases to Handle

1. **Stale PID file**: PID file exists but process is dead
   - Solution: Validate process exists before reporting "running"

2. **Permission errors**: Cannot write PID file
   - Solution: Check permissions, provide clear error message

3. **Process killed externally**: Daemon killed without cleanup
   - Solution: Status command should detect and offer to clean up

4. **Multiple concurrent starts**: Race condition
   - Solution: Use file locking for PID file writes

## Success Criteria

1. ✅ `cw start` defaults to daemon mode (background)
2. ✅ `cw start --no-daemon` runs in foreground
3. ✅ `cw stop` reliably terminates daemon
4. ✅ PID file correctly tracks daemon process
5. ✅ Graceful shutdown on SIGTERM/SIGINT
6. ✅ Clear error messages for edge cases
7. ✅ Integration tests pass
8. ✅ Pre-commit checks pass (hk check, hk fix)
9. ✅ Constitutional compliance verified

## References

- Issue: #175
- Failed PR: #174
- Constitution: `.specify/memory/constitution.md`
- Architecture: `ARCHITECTURE.md`
- Python daemon patterns: PEP 3143 (daemon module)
- Signal handling: Python `signal` module docs
