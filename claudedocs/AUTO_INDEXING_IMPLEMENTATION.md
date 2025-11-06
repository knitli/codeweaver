<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Auto-Indexing Implementation

## Summary

Successfully integrated automatic indexing into the CodeWeaver server lifecycle and updated the index command to detect and communicate with running servers.

## Implementation Details

### 1. Server Auto-Indexing (server.py)

**Location**: `/home/knitli/codeweaver-mcp/src/codeweaver/server/server.py`

**Changes**:
- Added background indexing task to `lifespan()` context manager
- Created `background_indexing()` async function that:
  1. Runs initial indexing via `indexer.prime_index()` in a thread
  2. Starts `FileWatcher` for real-time file change monitoring
  3. Handles graceful cancellation on shutdown

**Key Features**:
- Initial indexing runs automatically on server startup
- FileWatcher monitors for file changes and re-indexes incrementally
- Graceful shutdown handling with proper task cancellation
- Progress feedback via console output

**Code Structure**:
```python
async def lifespan(...):
    # ... existing setup ...

    # Background indexing task
    async def background_indexing():
        # Prime index (initial)
        await asyncio.to_thread(state.indexer.prime_index, force_reindex=False)

        # Start file watcher
        watcher = FileWatcher(settings.project_path, walker=state.indexer._walker)
        await watcher.run()

    # Start background task
    indexing_task = asyncio.create_task(background_indexing())

    yield state

    # Cleanup on shutdown
    indexing_task.cancel()
```

### 2. Index Command Updates (index.py)

**Location**: `/home/knitli/codeweaver-mcp/src/codeweaver/cli/commands/index.py`

**Changes**:
- Added `_check_server_health()` function to detect running server
- Added `--standalone` flag for explicit standalone indexing
- Updated command behavior:
  - **Default**: Check if server is running, inform user about auto-indexing
  - **Server running**: Display status message with health endpoint info
  - **Server not running**: Fall back to standalone indexing
  - **--standalone**: Force standalone indexing without server check

**User Experience**:

When server is running:
```bash
$ codeweaver index
✓ Server is running

Info: The CodeWeaver server automatically indexes your codebase
  • Initial indexing runs on server startup
  • File watcher monitors for changes in real-time

To check indexing status:
  curl http://localhost:9328/health/ | jq '.indexing'

Tip: Use --standalone to run indexing without the server
```

When server is not running:
```bash
$ codeweaver index
⚠ Server not running
Info: Running standalone indexing
Tip: Start server with 'codeweaver server' for automatic indexing

Loading configuration...
Initializing indexer...
Starting indexing process...
[... indexing progress ...]
```

Force standalone mode:
```bash
$ codeweaver index --standalone
Loading configuration...
[... indexing progress ...]
```

### 3. Health Service Integration

**Location**: `/home/knitli/codeweaver-mcp/src/codeweaver/server/health_service.py`

**Already Implemented**:
- `HealthService` already accepts `indexer` parameter
- `_get_indexing_info()` method provides indexing progress information
- Health endpoint returns indexing state, progress, and statistics

**Indexing Info Response**:
```json
{
  "indexing": {
    "state": "indexing|idle|error",
    "progress": {
      "files_discovered": 1234,
      "files_processed": 456,
      "chunks_created": 5678,
      "errors": 2,
      "current_file": "src/example.py",
      "start_time": "2025-01-06T10:30:00Z",
      "estimated_completion": "2025-01-06T10:35:00Z"
    },
    "last_indexed": "2025-01-06T10:30:00Z"
  }
}
```

## Testing

### Manual Testing

1. **Server Auto-Indexing**:
```bash
# Start server
codeweaver server

# Expected output:
# - "Starting background indexing..."
# - "Initial indexing complete"
# - "Starting file watcher..."

# Check health endpoint
curl http://localhost:9328/health/ | jq '.indexing'
```

2. **Index Command with Server Running**:
```bash
# Start server in background
codeweaver server &

# Run index command
codeweaver index

# Expected: Status message about auto-indexing
```

3. **Index Command without Server**:
```bash
# Ensure server is not running
pkill -f "codeweaver server"

# Run index command
codeweaver index

# Expected: Falls back to standalone indexing
```

4. **Standalone Mode**:
```bash
# With or without server running
codeweaver index --standalone

# Expected: Always runs standalone indexing
```

### Validation Criteria

✅ **Server startup**:
- Indexer initializes automatically
- Background indexing task starts
- Initial indexing completes
- FileWatcher starts monitoring

✅ **File watching**:
- File changes trigger re-indexing
- Real-time updates to vector store
- Health endpoint reflects current state

✅ **Index command**:
- Detects running server
- Provides appropriate feedback
- Falls back to standalone gracefully
- `--standalone` flag works correctly

✅ **Health endpoint**:
- Returns indexing progress
- Shows accurate state (indexing/idle/error)
- Includes statistics and estimates

✅ **Graceful shutdown**:
- Background task cancels cleanly
- No hanging processes
- Checkpoint saved on shutdown

## Architecture

### Component Relationships

```
┌─────────────────────────────────────────────────────────┐
│                    FastMCP Server                        │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │           lifespan() Context Manager                │ │
│  │                                                      │ │
│  │  ┌────────────────────────────────────────────────┐ │ │
│  │  │      background_indexing() Task                 │ │ │
│  │  │                                                  │ │ │
│  │  │  1. Prime Index (initial)                       │ │ │
│  │  │  2. Start FileWatcher                           │ │ │
│  │  │                                                  │ │ │
│  │  │     ┌──────────────┐      ┌──────────────┐     │ │ │
│  │  │     │   Indexer    │ <──> │ FileWatcher  │     │ │ │
│  │  │     └──────────────┘      └──────────────┘     │ │ │
│  │  │            │                      │             │ │ │
│  │  │            v                      v             │ │ │
│  │  │     ┌──────────────┐      ┌──────────────┐     │ │ │
│  │  │     │ VectorStore  │      │  Watchfiles  │     │ │ │
│  │  │     └──────────────┘      └──────────────┘     │ │ │
│  │  └────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │            Health Service                           │ │
│  │                                                      │ │
│  │  - Indexing progress                                │ │
│  │  - Service health                                   │ │
│  │  - Statistics                                       │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│               CLI Index Command                          │
│                                                          │
│  1. Check server health                                 │
│  2. If running: Show status message                     │
│  3. If not running: Run standalone indexing             │
│  4. --standalone: Force standalone mode                 │
└─────────────────────────────────────────────────────────┘
```

### Execution Flow

**Server Startup**:
1. `build_app()` creates FastMCP application
2. `lifespan()` context manager initializes AppState
3. `Indexer.from_settings()` creates indexer instance
4. Background indexing task starts:
   - Initial indexing via `prime_index()`
   - File watcher via `FileWatcher.run()`
5. Server is ready for requests

**File Change Detection**:
1. FileWatcher detects file change
2. Calls `indexer.index(change)` with FileChange event
3. Indexer processes change:
   - Added/Modified: Re-index file
   - Deleted: Remove from store and vector DB
4. Health endpoint reflects updated progress

**Index Command**:
1. Parse command arguments
2. If not `--standalone`:
   - Check server health via HTTP
   - If running: Display status and exit
   - If not running: Continue to standalone
3. Run standalone indexing:
   - Load settings
   - Create indexer
   - Execute `prime_index()`
   - Display results

## Future Enhancements

### Phase 2 (Future)

1. **Admin Endpoint** (T009):
   - POST `/admin/reindex` to trigger re-index
   - Support for force and incremental options
   - Authentication/authorization

2. **Server Communication**:
   - Update `_trigger_server_reindex()` to use admin endpoint
   - Enable `codeweaver index --force` to trigger server re-index

3. **Progress Streaming**:
   - WebSocket or SSE for real-time progress updates
   - CLI progress bar when triggering server re-index

4. **Configuration**:
   - Disable auto-indexing via config
   - Configure file watcher debounce/grace periods
   - Control indexing batch sizes

## Known Limitations

1. **No Manual Trigger**: In v0.1, cannot manually trigger re-index on running server
   - Workaround: Restart server or use `--standalone`

2. **No Progress Visibility**: When server is indexing, CLI only shows health endpoint URL
   - Workaround: Poll health endpoint manually

3. **Single Project**: File watcher monitors single project path
   - Workaround: Run multiple server instances on different ports

## Dependencies

**Required Packages**:
- `httpx`: HTTP client for server health checks
- `asyncio`: Async task management
- `watchfiles`: File system monitoring (already in `indexer.py`)

**Internal Dependencies**:
- `codeweaver.engine.indexer.Indexer`: Indexing engine
- `codeweaver.engine.indexer.FileWatcher`: File monitoring
- `codeweaver.server.health_service.HealthService`: Health reporting
- `codeweaver.config.settings.get_settings`: Configuration

## References

**Source Files**:
- `/home/knitli/codeweaver-mcp/src/codeweaver/server/server.py` (lines 318-427)
- `/home/knitli/codeweaver-mcp/src/codeweaver/cli/commands/index.py` (full file)
- `/home/knitli/codeweaver-mcp/src/codeweaver/engine/indexer.py` (lines 1457-1513)
- `/home/knitli/codeweaver-mcp/src/codeweaver/server/health_service.py` (lines 105-157)

**Related Tasks**:
- T003: Indexer implementation
- T007-T008: Checkpoint/persistence support
- T009: Admin endpoints (future)

**Planning Documents**:
- `/home/knitli/codeweaver-mcp/claudedocs/CLI_CORRECTIONS_PLAN.md` (lines 381-406)
