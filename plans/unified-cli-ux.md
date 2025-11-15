# Unified CLI UX Plan

## Problem Statement

Currently, CodeWeaver CLI commands have inconsistent user experiences:

1. **Server command** - Uses `StatusDisplay` for clean output during startup, but error handling breaks the UI in certain scenarios
2. **Index command** - Has cleaner UX with status messages and progress tracking using `IndexingProgressTracker`
3. **Search command** - Mixes rich console output with plain prints
4. **Doctor command** - Uses `DoctorCheck` class for structured validation results

## Current State

### Server Command (`cli/commands/server.py`)
- Uses `StatusDisplay` in `lifespan()` for server startup
- Error handling tries to show helpful messages but was broken when suppressing logs
- Issue: Balance between clean output and error visibility not maintained

### Index Command (`cli/commands/index.py`)
- Uses `Console` from rich for all output
- Has structured status messages with `CODEWEAVER_PREFIX`
- Uses `IndexingProgressTracker` for live progress updates
- Cleanest UX of all commands

### Search Command (`cli/commands/search.py`)
- Uses `Console` for structured output
- Mixes different output styles
- Needs improvement for consistency

### Doctor Command (`cli/commands/doctor.py`)
- Uses `DoctorCheck` class for validation results
- Table-based output with rich
- Good for structured diagnostics

## Proposed Solution

### 1. Unified Status Display System

Extend `StatusDisplay` class in `src/codeweaver/ui/status_display.py` to support all CLI command patterns:

```python
class StatusDisplay:
    """Unified status display for all CLI commands."""
    
    # Current methods (keep these):
    # - print_header()
    # - print_step()
    # - print_completion()
    # - print_indexing_stats()
    # - print_health_check()
    # - print_ready()
    # - print_shutdown_start()
    # - print_shutdown_complete()
    # - spinner()
    # - print_error()
    # - print_warning()
    
    # New methods to add:
    def print_command_header(self, command: str, description: str) -> None:
        """Print command header with CodeWeaver prefix."""
        
    def print_section(self, title: str) -> None:
        """Print a section header."""
        
    def print_info(self, message: str) -> None:
        """Print an informational message."""
        
    def print_success(self, message: str, details: str | None = None) -> None:
        """Print a success message with optional details."""
        
    def print_table(self, table: Table) -> None:
        """Print a rich table."""
        
    def print_progress(self, current: int, total: int, message: str) -> None:
        """Print progress information."""
        
    @contextmanager
    def live_progress(self, description: str) -> Generator[Progress, None, None]:
        """Context manager for live progress display."""
```

### 2. Structured Error Handling

Create a unified error handler that:
- Shows minimal output during normal operation
- Shows full details when errors occur
- Respects verbose/debug flags
- Maintains clean UX consistency

```python
class CLIErrorHandler:
    """Unified error handling for CLI commands."""
    
    def __init__(self, display: StatusDisplay, verbose: bool = False, debug: bool = False):
        self.display = display
        self.verbose = verbose
        self.debug = debug
    
    def handle_error(self, error: Exception, context: str) -> None:
        """Handle and display errors appropriately."""
        if isinstance(error, CodeWeaverError):
            self._handle_codeweaver_error(error, context)
        else:
            self._handle_unexpected_error(error, context)
    
    def _handle_codeweaver_error(self, error: CodeWeaverError, context: str) -> None:
        """Display CodeWeaver-specific errors."""
        self.display.print_error(f"{context}: {error}")
        if hasattr(error, "details") and error.details:
            # Show details
        if error.suggestions:
            # Show suggestions
        if self.verbose or self.debug:
            # Show traceback
    
    def _handle_unexpected_error(self, error: Exception, context: str) -> None:
        """Display unexpected errors."""
        # Always show full details for unexpected errors
```

### 3. Migration Strategy

#### Phase 1: Extend StatusDisplay (This PR)
- Add new methods to `StatusDisplay` class
- Keep existing methods for backward compatibility
- Add `CLIErrorHandler` class

#### Phase 2: Update Server Command (This PR)
- Fix server error handling to use new error handler
- Ensure clean output during normal operation
- Ensure errors are visible when they occur

#### Phase 3: Migrate Other Commands (Future PR)
- Update index command to use unified display
- Update search command to use unified display
- Update doctor command to use unified display
- Remove duplicate display logic

## Implementation Details

### Server Command Error Handling Fix

The server command issue stems from trying to suppress logging output for clean UX while still showing errors. The solution:

1. **Use StatusDisplay exclusively** for user-facing output in server lifespan
2. **Keep logging** for internal diagnostics (controlled by verbose/debug)
3. **Error handling** should:
   - Catch errors in server startup
   - Display them through StatusDisplay
   - Show full traceback only in verbose/debug mode
   - Exit cleanly with appropriate error code

### Key Principles

1. **User-facing output** → StatusDisplay (always clean)
2. **Internal logging** → Python logging (controlled by flags)
3. **Errors** → Always visible, details controlled by verbosity
4. **Consistency** → Same patterns across all commands
5. **Progressive disclosure** → Show more with verbose/debug flags

## Success Criteria

- [ ] Server starts with clean, informative output
- [ ] Server startup errors are clearly visible with helpful messages
- [ ] All commands use consistent output format
- [ ] Error messages are helpful and actionable
- [ ] Verbose/debug flags work consistently across commands
- [ ] No redundant or duplicate UX code across commands

## Related Files

- `src/codeweaver/ui/status_display.py` - Core display class
- `src/codeweaver/cli/commands/server.py` - Server command
- `src/codeweaver/cli/commands/index.py` - Index command (best UX currently)
- `src/codeweaver/server/server.py` - Server lifespan function
- `src/codeweaver/exceptions.py` - Error definitions

## Testing

1. Test server startup success case
2. Test server startup failure case
3. Test with verbose flag
4. Test with debug flag
5. Test keyboard interrupt handling
6. Test all commands for consistent UX
