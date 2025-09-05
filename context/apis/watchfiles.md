<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Watchfiles - Complete API Research Report

*Expert API Analyst Research - Foundation for CodeWeaver Clean Rebuild*

## Summary

**Feature Name**: File System Monitoring Service  
**Feature Description**: Rust-backed Python library for high-performance local filesystem change detection and automated process reloading  
**Feature Goal**: Enable CodeWeaver's background indexing/watching service to automatically detect and respond to codebase changes for incremental index updates

**Primary External Surface(s)**: `watch()`, `awatch()`, `run_process()`, `arun_process()` functions; `FileChange` dataclass, `Change` enum, Filter system

**Integration Confidence**: High for local filesystem monitoring - Well-documented, performant, already in CodeWeaver dependencies. **Low for cloud/remote abstraction** - Architecture fundamentally limited to local filesystem operations.

## Core Types

| Name | Kind | Definition | Role |
|------|------|------------|------|
| `FileChange` | NamedTuple | `(Change, str)` tuple | Individual file system change event with change type and path |
| `Change` | Enum | `added`, `modified`, `deleted`, `moved` | File system change operation type |
| `BaseFilter` | Abstract Class | `Callable[[Change, str], bool]` | Filter interface for selective change monitoring |
| `DefaultFilter` | Filter Class | Built-in filter with sensible defaults | Standard file filtering (ignores .git, __pycache__, etc.) |
| `PythonFilter` | Filter Class | Python-specific file filter | Monitors only .py, .pyx, .pyi files |
| `RustNotify` | Backend Class | Rust-based filesystem watcher | Low-level filesystem event detection engine |

## Signatures

### Core Watching Functions

**Name**: `watch`  
**Import Path**: `from watchfiles import watch`  
**Concrete Path**: `watchfiles/main.py:watch` (GitHub: https://github.com/samuelcolvin/watchfiles/blob/main/watchfiles/main.py)  
**Signature**: `def watch(*paths: Union[Path, str], watch_filter: Optional[Callable[[Change, str], bool]] = DefaultFilter(), debounce: int = 1600, step: int = 50, stop_event: Optional[AbstractEvent] = None, rust_timeout: int = 5000, yield_on_timeout: bool = False, debug: Optional[bool] = None, raise_interrupt: bool = True, force_polling: Optional[bool] = None, poll_delay_ms: int = 300, recursive: bool = True, ignore_permission_denied: Optional[bool] = None) -> Generator[Set[FileChange], None, None]`

**Params**:
- `*paths: Union[Path, str]` (required) - One or more filesystem paths to monitor (files or directories)
- `watch_filter: Optional[Callable[[Change, str], bool]] = DefaultFilter()` (optional) - Filter function to selectively include/exclude changes
- `debounce: int = 1600` (optional) - Milliseconds to wait for additional changes before yielding
- `step: int = 50` (optional) - Milliseconds between filesystem polls
- `stop_event: Optional[AbstractEvent] = None` (optional) - Event to signal stopping watch
- `rust_timeout: int = 5000` (optional) - Timeout for Rust backend operations
- `yield_on_timeout: bool = False` (optional) - Whether to yield empty set on timeout
- `recursive: bool = True` (optional) - Whether to monitor subdirectories
- `ignore_permission_denied: Optional[bool] = None` (optional) - Ignore permission errors

**Returns**: `Generator[Set[FileChange], None, None]` - Generator yielding sets of file changes  
**Errors**: `OSError` for filesystem access issues, `KeyboardInterrupt` if raise_interrupt=True  
**Notes**: Synchronous blocking operation, recursive by default, includes debouncing to batch rapid changes

**Name**: `awatch`  
**Import Path**: `from watchfiles import awatch`  
**Signature**: `async def awatch(*paths: Union[Path, str], **kwargs) -> AsyncGenerator[Set[FileChange], None]`

**Params**: Identical to `watch()` except `stop_event: Optional[AnyEvent] = None` for async compatibility  
**Returns**: `AsyncGenerator[Set[FileChange], None]` - Async generator yielding file changes  
**Errors**: Same as `watch()` but raised asynchronously  
**Notes**: Non-blocking async version, integrates with asyncio/anyio event loops

### Process Management Functions

**Name**: `run_process`  
**Import Path**: `from watchfiles import run_process`  
**Signature**: `def run_process(*paths: Union[Path, str], target: Union[str, Callable], args: Tuple = (), kwargs: Dict = {}, target_type: str = 'auto', **watch_kwargs) -> int`

**Params**:
- `*paths: Union[Path, str]` (required) - Paths to monitor for changes
- `target: Union[str, Callable]` (required) - Function to call or command string to execute
- `args: Tuple = ()` (optional) - Arguments for target function
- `kwargs: Dict = {}` (optional) - Keyword arguments for target function  
- `target_type: str = 'auto'` (optional) - 'function', 'command', or 'auto' detection

**Returns**: `int` - Exit code of the process  
**Errors**: `ProcessError` for execution failures, filesystem errors from watching  
**Notes**: Automatically restarts target when filesystem changes detected, handles process lifecycle

**Name**: `arun_process`  
**Signature**: `async def arun_process(*paths: Union[Path, str], **kwargs) -> int`  
**Notes**: Async version of run_process, same parameters and behavior

### Filter System

**Name**: `BaseFilter.__call__`  
**Import Path**: `from watchfiles import BaseFilter`  
**Signature**: `def __call__(self, change: Change, path: str) -> bool`

**Params**:
- `change: Change` (required) - Type of filesystem change (added/modified/deleted/moved)
- `path: str` (required) - Absolute path to the changed file

**Returns**: `bool` - True if change should be included, False to ignore  
**Notes**: Abstract interface for implementing custom filtering logic

**Type Information**:
```python
from watchfiles import Change
from enum import Enum

class Change(Enum):
    added = 1      # New file created
    modified = 2   # Existing file modified  
    deleted = 3    # File removed
    moved = 4      # File moved/renamed

# FileChange is a namedtuple
FileChange = namedtuple('FileChange', ['change', 'path'])
# Usage: change_type, path = file_change
```

### Low-Level Backend

**Name**: `RustNotify.__init__`  
**Import Path**: `from watchfiles._rust_notify import RustNotify`  
**Signature**: `def __init__(self, paths: List[str], recursive: bool, force_polling: bool, poll_delay_ms: int, ignore_permission_denied: bool, debug: bool)`

**Params**:
- `paths: List[str]` (required) - List of paths to monitor
- `recursive: bool` (required) - Enable recursive directory monitoring
- `force_polling: bool` (required) - Force polling instead of native filesystem events
- `poll_delay_ms: int` (required) - Polling interval in milliseconds
- `ignore_permission_denied: bool` (required) - Skip permission denied errors
- `debug: bool` (required) - Enable debug output

**Returns**: `RustNotify` instance  
**Notes**: Direct interface to Rust backend, requires manual resource management with close()

## Type Graph

```
watch() -> yields -> Set[FileChange]
awatch() -> yields -> Set[FileChange]

FileChange -> contains -> Change
FileChange -> contains -> str

Change -> enum_values -> added|modified|deleted|moved

BaseFilter -> implements -> Callable[[Change, str], bool] 
DefaultFilter -> extends -> BaseFilter
PythonFilter -> extends -> BaseFilter

RustNotify -> provides -> low_level_filesystem_events
RustNotify -> used_by -> watch|awatch

run_process -> uses -> watch
arun_process -> uses -> awatch
```

## Request/Response Schemas

### File Monitoring Flow

**Monitor Request**:
```python
# Basic directory monitoring
for changes in watch('/path/to/project'):
    # changes: Set[FileChange]
    for change_type, file_path in changes:
        # change_type: Change enum (added/modified/deleted/moved)
        # file_path: str (absolute path to changed file)
        process_change(change_type, file_path)
```

**Change Event Structure**:
```python
FileChange = namedtuple('FileChange', ['change', 'path'])

# Example change events
changes = {
    FileChange(change=Change.added, path='/project/src/new_file.py'),
    FileChange(change=Change.modified, path='/project/src/existing.py'),
    FileChange(change=Change.deleted, path='/project/src/old_file.py')
}
```

### Filter Configuration

**Custom Filter Implementation**:
```python
class CodeWeaverFilter(DefaultFilter):
    """Custom filter for CodeWeaver's specific needs"""
    
    # File extensions to monitor for code intelligence
    monitored_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java', '.cpp', '.h', '.md', '.yml', '.yaml', '.json', '.toml'}
    
    # Directories to always ignore
    ignored_dirs = {'node_modules', '.git', '__pycache__', '.pytest_cache', 'dist', 'build', '.venv'}
    
    def __call__(self, change: Change, path: str) -> bool:
        # Apply base filter first (handles .git, __pycache__, etc.)
        if not super().__call__(change, path):
            return False
            
        # Check if file extension should be monitored
        if not any(path.endswith(ext) for ext in self.monitored_extensions):
            return False
            
        # Check if in ignored directory
        path_parts = Path(path).parts
        if any(ignored_dir in path_parts for ignored_dir in self.ignored_dirs):
            return False
            
        return True
```

### CodeWeaver Integration Patterns

**Async Integration with FastMCP**:
```python
import asyncio
from watchfiles import awatch
from fastmcp import Context

async def background_indexing_service(paths: List[str], context: Context):
    """Background service for CodeWeaver's incremental indexing"""
    
    codeweaver_filter = CodeWeaverFilter()
    
    async for changes in awatch(*paths, watch_filter=codeweaver_filter, debounce=2000):
        if changes:
            # Process changes through CodeWeaver's pydantic-graph pipeline
            await process_file_changes(changes, context)

async def process_file_changes(changes: Set[FileChange], context: Context):
    """Process file changes through CodeWeaver's resolution pipeline"""
    
    for change_type, file_path in changes:
        if change_type == Change.deleted:
            await invalidate_file_embeddings(file_path)
        elif change_type in (Change.added, Change.modified):
            await schedule_file_reindexing(file_path) 
        elif change_type == Change.moved:
            # Handle file moves (may need to update path references)
            await handle_file_move(file_path)
```

## Patterns

### High-Performance Monitoring

```python
# Optimized for CodeWeaver's background indexing
async def efficient_codebase_monitoring(project_root: str):
    """Efficient monitoring pattern for large codebases"""
    
    # Use custom filter to reduce noise
    filter = CodeWeaverFilter()
    
    # Configure for performance
    async for changes in awatch(
        project_root,
        watch_filter=filter,
        debounce=3000,  # Batch changes over 3 seconds
        recursive=True,  # Monitor all subdirectories
        ignore_permission_denied=True  # Skip access errors
    ):
        # Process batched changes
        if len(changes) > 50:
            # Large batch - process asynchronously
            asyncio.create_task(process_large_changeset(changes))
        else:
            # Small batch - process immediately
            await process_incremental_changes(changes)
```

### Integration with pydantic-graph Pipeline

```python
from dataclasses import dataclass
from pydantic_graph import BaseNode, GraphRunContext

@dataclass
class FileChangeEvent(BaseNode[IndexingState, CodeWeaverDeps, None]):
    changes: Set[FileChange]
    
    async def run(self, ctx: GraphRunContext[IndexingState, CodeWeaverDeps]) -> ChunkFiles | InvalidateEmbeddings | End[None]:
        """Process file changes through CodeWeaver's graph pipeline"""
        
        added_files = []
        modified_files = []
        deleted_files = []
        
        for change_type, file_path in self.changes:
            if change_type == Change.deleted:
                deleted_files.append(file_path)
            elif change_type == Change.added:
                added_files.append(file_path) 
            elif change_type == Change.modified:
                modified_files.append(file_path)
        
        if deleted_files:
            return InvalidateEmbeddings(deleted_files)
        elif added_files or modified_files:
            return ChunkFiles(added_files + modified_files)
        else:
            return End(None)
```

### Graceful Resource Management

```python
class FileWatcherService:
    """Managed service for file watching with proper cleanup"""
    
    def __init__(self, paths: List[str], filter: Optional[BaseFilter] = None):
        self.paths = paths
        self.filter = filter or DefaultFilter()
        self._stop_event = asyncio.Event()
        self._watch_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the file watching service"""
        self._watch_task = asyncio.create_task(self._watch_loop())
    
    async def stop(self):
        """Gracefully stop the file watching service"""
        if self._watch_task:
            self._stop_event.set()
            await self._watch_task
    
    async def _watch_loop(self):
        """Main watching loop"""
        try:
            async for changes in awatch(
                *self.paths,
                watch_filter=self.filter,
                stop_event=self._stop_event
            ):
                if self._stop_event.is_set():
                    break
                await self._handle_changes(changes)
        except asyncio.CancelledError:
            pass  # Graceful shutdown
```

## Differences vs Project

### Alignment Strengths

1. **Already Integrated**: watchfiles >=1.1.0 is already included in CodeWeaver's dependencies as a "source-filesystem" provider

2. **Performance Match**: Rust-backed implementation aligns with CodeWeaver's performance requirements for background indexing

3. **Async Compatibility**: `awatch()` integrates seamlessly with FastMCP's async architecture and pydantic-graph's async node execution

4. **Filter Extensibility**: Custom filter system allows CodeWeaver to implement domain-specific filtering (code files, ignore patterns, etc.)

5. **Debouncing Support**: Built-in debouncing helps batch rapid changes during development, reducing indexing overhead

### Critical Limitation: No Abstraction Potential

**Key Finding**: watchfiles **cannot be abstracted** to work with cloud storage or API hooks. The architecture is fundamentally designed for local filesystem operations:

1. **Rust Backend Dependency**: Built on Rust's `notify` crate which is filesystem-specific
2. **Path-Based API**: All operations expect filesystem paths, not cloud storage URIs or API endpoints  
3. **No Plugin Architecture**: No mechanisms for custom backends or protocol adapters
4. **Filesystem Event Model**: Change detection relies on OS-level filesystem events (inotify, FSEvents, ReadDirectoryChangesW)

### Implementation Strategy for CodeWeaver

**Recommended Architecture**:
```python
# Abstract interface for CodeWeaver's needs
from abc import ABC, abstractmethod

class ChangeWatcher(ABC):
    """Abstract interface for file/resource change detection"""
    
    @abstractmethod
    async def watch(self) -> AsyncGenerator[Set[ChangeEvent], None]:
        """Watch for changes and yield change events"""
        pass

class LocalFileWatcher(ChangeWatcher):
    """Local filesystem implementation using watchfiles"""
    
    def __init__(self, paths: List[str], filter: Optional[BaseFilter] = None):
        self.paths = paths
        self.filter = filter or CodeWeaverFilter()
    
    async def watch(self) -> AsyncGenerator[Set[ChangeEvent], None]:
        async for changes in awatch(*self.paths, watch_filter=self.filter):
            # Convert watchfiles.FileChange to CodeWeaver's ChangeEvent
            yield {ChangeEvent.from_file_change(fc) for fc in changes}

class CloudStorageWatcher(ChangeWatcher):
    """Cloud storage implementation using APIs/webhooks (future)"""
    
    async def watch(self) -> AsyncGenerator[Set[ChangeEvent], None]:
        # Custom implementation for S3/GCS/etc change notifications
        # Would use cloud provider APIs, webhooks, or polling
        pass
```

### Integration Considerations

1. **Background Service**: watchfiles should run as a background service within FastMCP, not block the main server thread

2. **Resource Management**: Proper start/stop lifecycle management with graceful shutdown

3. **Error Handling**: Handle filesystem permission errors, network issues (for remote paths), and service interruptions

4. **Configuration**: Expose filtering, debouncing, and monitoring parameters through CodeWeaver's pydantic-settings

5. **Telemetry**: Integrate with CodeWeaver's telemetry system to track watch events, performance metrics, and error rates

## Blocking Questions

1. **Performance Impact**: What is the memory and CPU overhead of monitoring large codebases (10,000+ files) with watchfiles?

2. **Cross-Platform Behavior**: Are there any behavioral differences between Linux/macOS/Windows that could affect CodeWeaver's indexing reliability?

3. **Network Filesystem Support**: How does watchfiles perform with network-mounted filesystems (NFS, SMB) commonly used in development environments?

4. **Concurrent Access**: Can multiple watchfiles instances monitor overlapping paths safely, or would this cause conflicts in CodeWeaver's multi-tenant scenarios?

## Non-blocking Questions

1. **Optimization Strategies**: What are best practices for monitoring paths with many ignored subdirectories (node_modules, .git, etc.)?

2. **Debounce Tuning**: How should debounce timing be configured for different development workflows (rapid editing vs. batch operations)?

3. **Filter Performance**: What is the performance impact of complex custom filters vs. simple extension-based filtering?

4. **Memory Usage**: How does long-running watchfiles monitoring impact memory usage over time?

## Sources

[Context7 Documentation | /samuelcolvin/watchfiles | API, filters, CLI | Reliability: 5]
- Complete API reference for watch, awatch, run_process functions
- Filter system documentation and examples
- Performance characteristics and Rust backend details
- Integration patterns and best practices

[GitHub Repository | https://github.com/samuelcolvin/watchfiles | Source code and examples | Reliability: 5]  
- Implementation details and source code structure
- Issue discussions about performance and limitations
- Example usage patterns and integration guides

[Web Search Results | watchfiles API documentation | Community usage patterns | Reliability: 4]
- Real-world usage examples and performance discussions  
- Integration patterns with async frameworks
- Community feedback on limitations and capabilities

[PyPI Package Information | https://pypi.org/project/watchfiles/ | Version and installation details | Reliability: 5]
- Current stable version (1.1.0) specifications
- Installation requirements and platform support
- Dependency information and release notes

---

*This research provides comprehensive technical foundation for integrating watchfiles into CodeWeaver's background indexing service. **Key finding**: watchfiles is excellent for local filesystem monitoring but cannot be abstracted for cloud storage or remote API integration. CodeWeaver should use watchfiles as designed for local filesystem operations and implement separate solutions for cloud/remote monitoring needs.*