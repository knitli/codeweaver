# UI Output Refactoring Design

**Date**: 2026-01-16
**Problem**: `server` and `engine` importing `StatusDisplay` from `cli` creates circular dependency and blocks monorepo migration
**Goal**: Clean separation with correct dependency direction and centralized output control

**Key Insight**: Rich is already a dependency - leverage Rich's Console + RichHandler instead of reinventing!

## Current Anti-Pattern

```
┌─────────┐
│   CLI   │  (StatusDisplay defined here)
└────▲────┘
     │
     │ WRONG DIRECTION
     │
┌────┴────┐     ┌────────┐
│ Server  │────▶│ Engine │
└─────────┘     └────────┘
```

**Problems**:
1. Inverted dependency (lower layers depend on UI)
2. Monorepo blocker (CLI not always available)
3. Output leakage (scattered suppression logic)

## Target Architecture

```
┌─────────┐
│   CLI   │  (StatusDisplay implements ProgressReporter)
└────┬────┘
     │
     │ CORRECT DIRECTION
     ▼
┌─────────┐     ┌────────┐
│ Server  │────▶│ Engine │
└────┬────┘     └────┬───┘
     │               │
     └───────┬───────┘
             ▼
      ┌──────────┐
      │   Core   │  (ProgressReporter protocol defined here)
      └──────────┘
```

**Benefits**:
1. ✅ Correct dependency direction
2. ✅ Monorepo compatible
3. ✅ Centralized logging control
4. ✅ Type-safe via protocols
5. ✅ Fits existing DI architecture

## Detailed Design

### 1. Core Protocol Definition (`core/ui_protocol.py`)

```python
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0

"""UI protocol for reporting progress and status to presentation layers.

Defines thin protocol layer over Rich primitives for dependency inversion.
Rich provides the output primitives (Console, Progress), this provides the
abstraction layer that enables correct dependency direction.

Key Design:
- Protocol is thin wrapper over Rich concepts
- Implementations use Rich primitives directly
- Business logic depends on protocol (not Rich or CLI)
- CLI/Server provide Rich-based implementations
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from rich.console import Console

@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for reporting progress to UI layer.

    Business logic (engine, server) depends on this protocol.
    Presentation layers (CLI, web UI) implement this protocol.

    This inversion enables correct dependency direction:
    - Core defines protocol (no dependencies)
    - Business logic depends on protocol (depends on core)
    - UI layer implements protocol (depends on core + business logic)
    """

    def report_progress(
        self,
        phase: str,
        current: int,
        total: int,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Report progress update.

        Args:
            phase: Current operation phase (e.g., "discovery", "indexing")
            current: Current progress count
            total: Total items to process
            extra: Additional context for the UI
        """
        ...

    def report_status(
        self,
        message: str,
        *,
        level: str = "info",
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Report status message.

        Args:
            message: Status message to display
            level: Message level ("debug", "info", "warning", "error")
            extra: Additional context
        """
        ...

    def report_error(
        self,
        error: Exception | str,
        *,
        recoverable: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Report error.

        Args:
            error: Error to report
            recoverable: Whether the error is recoverable
            extra: Additional context
        """
        ...

    def start_operation(
        self,
        operation: str,
        *,
        description: str | None = None,
    ) -> None:
        """Signal start of long-running operation.

        Args:
            operation: Operation identifier
            description: Human-readable description
        """
        ...

    def complete_operation(
        self,
        operation: str,
        *,
        success: bool = True,
        message: str | None = None,
    ) -> None:
        """Signal completion of operation.

        Args:
            operation: Operation identifier
            success: Whether operation succeeded
            message: Completion message
        """
        ...


class NoOpProgressReporter:
    """No-op implementation for non-interactive environments.

    Used when:
    - Running in server/daemon mode without CLI
    - Testing without UI
    - Library usage scenarios
    """

    def report_progress(self, phase: str, current: int, total: int, **kwargs) -> None:
        pass

    def report_status(self, message: str, **kwargs) -> None:
        pass

    def report_error(self, error: Exception | str, **kwargs) -> None:
        pass

    def start_operation(self, operation: str, **kwargs) -> None:
        pass

    def complete_operation(self, operation: str, **kwargs) -> None:
        pass


class RichConsoleProgressReporter:
    """Rich Console-based implementation for server/non-CLI environments.

    Uses Rich Console directly without CLI's StatusDisplay.
    Suitable for:
    - Server/daemon mode (structured output to logs)
    - Simple CLI tools without full StatusDisplay
    - Testing with visible output
    """

    def __init__(self, console: Console | None = None):
        """Initialize with Rich Console.

        Args:
            console: Rich Console instance. If None, creates default.
        """
        if console is None:
            from rich.console import Console
            console = Console()
        self.console = console

    def report_progress(
        self,
        phase: str,
        current: int,
        total: int,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Print progress using Rich Console."""
        percent = (current / total * 100) if total > 0 else 0
        self.console.print(
            f"[cyan]{phase}[/cyan]: {current}/{total} ({percent:.1f}%)"
        )

    def report_status(
        self,
        message: str,
        *,
        level: str = "info",
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Print status with Rich formatting."""
        colors = {
            "debug": "dim",
            "info": "cyan",
            "warning": "yellow",
            "error": "red bold",
        }
        color = colors.get(level, "cyan")
        self.console.print(f"[{color}]{message}[/{color}]")

    def report_error(
        self,
        error: Exception | str,
        *,
        recoverable: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Print error with Rich formatting."""
        error_msg = str(error)
        if recoverable:
            self.console.print(f"[yellow]Warning: {error_msg}[/yellow]")
        else:
            self.console.print(f"[red bold]Error: {error_msg}[/red bold]")

    def start_operation(
        self,
        operation: str,
        *,
        description: str | None = None,
    ) -> None:
        """Print operation start."""
        msg = description or operation
        self.console.print(f"[cyan]▶[/cyan] {msg}")

    def complete_operation(
        self,
        operation: str,
        *,
        success: bool = True,
        message: str | None = None,
    ) -> None:
        """Print operation completion."""
        icon = "✓" if success else "✗"
        color = "green" if success else "red"
        msg = message or operation
        self.console.print(f"[{color}]{icon}[/{color}] {msg}")


__all__ = [
    "ProgressReporter",
    "NoOpProgressReporter",
    "RichConsoleProgressReporter",
]
```

**Key Design Points**:
1. **Protocol is thin** - Just defines interface, no Rich dependency
2. **RichConsoleProgressReporter** - Uses Rich Console directly (server/daemon)
3. **NoOpProgressReporter** - For testing/library usage
4. **StatusDisplay** (in CLI) - Already uses Rich, will implement protocol

### 2. Leverage Existing Rich Logging (`core/_logging.py` - NO CHANGES NEEDED!)

**Good news**: `core/_logging.py` ALREADY has what we need!

- ✅ `RichHandler` already configured for CLI mode
- ✅ Session file logging already set up
- ✅ `suppress_stdout_logging()` pattern already exists (just needs extraction)

**Only addition needed**:

```python
# Add to core/_logging.py

def get_rich_console() -> Console:
    """Get shared Rich Console instance for non-CLI output.

    Used by RichConsoleProgressReporter in server/daemon mode.
    Returns the same Console instance that RichHandler uses.
    """
    from rich.console import Console
    # Return Console from RichHandler if it exists, else create new
    logger = logging.getLogger("codeweaver")
    for handler in logger.handlers:
        if isinstance(handler, RichHandler) and hasattr(handler, "console"):
            return handler.console
    # No RichHandler found, create new Console
    return Console(markup=True, soft_wrap=True, emoji=True)
```

**That's it!** Rich already handles routing logs through Console via RichHandler.

### 3. DI Integration (`core/dependencies.py` additions)

```python
# Add to core/dependencies.py

from codeweaver.core.ui_protocol import (
    ProgressReporter,
    NoOpProgressReporter,
    RichConsoleProgressReporter,
)
from codeweaver.core._logging import get_rich_console

@dependency_provider(ProgressReporter, scope="singleton")
def _create_progress_reporter(
    settings: SettingsDep = INJECTED,
) -> ProgressReporter:
    """Factory for progress reporter.

    Returns:
        - NoOpProgressReporter for testing
        - RichConsoleProgressReporter for server/daemon (uses Rich Console)
        - CLI can override with StatusDisplay implementation
    """
    # Check if we're in CLI mode
    if hasattr(settings, "cli_mode") and settings.cli_mode:
        # CLI will override this with StatusDisplay
        # For now, return Rich console reporter as fallback
        console = get_rich_console()
        return RichConsoleProgressReporter(console=console)

    # Server/daemon mode: use Rich Console
    if hasattr(settings, "daemon_mode") and settings.daemon_mode:
        console = get_rich_console()
        return RichConsoleProgressReporter(console=console)

    # Default: no-op (e.g., testing)
    return NoOpProgressReporter()


# Dependency marker
type ProgressReporterDep = Annotated[
    ProgressReporter,
    depends(_create_progress_reporter),
]

__all__ = [
    # ... existing exports ...
    "ProgressReporter",
    "ProgressReporterDep",
    "NoOpProgressReporter",
    "RichConsoleProgressReporter",
]
```

### 4. CLI Implementation (`cli/ui/status_display.py` updates)

**Good news**: StatusDisplay ALREADY uses Rich extensively (Console, Progress, Live, etc.)!

```python
# Update cli/ui/status_display.py

from codeweaver.core.ui_protocol import ProgressReporter

class StatusDisplay(ProgressReporter):
    """CLI-specific implementation of ProgressReporter.

    Already uses Rich primitives (Console, Progress, Live).
    Just needs to implement the protocol interface to enable
    business logic to depend on protocol without depending on CLI package.
    """

    # Existing __init__ and Rich setup - NO CHANGES NEEDED
    # Already has: self.console = Console(...)
    # Already has: self.progress = Progress(...)

    # Add protocol method implementations that delegate to existing logic

    def report_progress(
        self,
        phase: str,
        current: int,
        total: int,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Implement ProgressReporter.report_progress."""
        # Delegate to existing update_progress logic
        self.update_progress(phase, current, total, extra)

    def report_status(
        self,
        message: str,
        *,
        level: str = "info",
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Implement ProgressReporter.report_status."""
        # Route to existing methods based on level
        if level == "error":
            self.show_error(message)
        elif level == "warning":
            self.show_warning(message)
        else:
            self.show_status(message)

    def report_error(
        self,
        error: Exception | str,
        *,
        recoverable: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Implement ProgressReporter.report_error."""
        # Use existing show_error method
        self.show_error(str(error), recoverable=recoverable)

    def start_operation(
        self,
        operation: str,
        *,
        description: str | None = None,
    ) -> None:
        """Implement ProgressReporter.start_operation."""
        # Add task to Rich Progress if not already tracking
        msg = description or operation
        self.show_status(f"Starting: {msg}")

    def complete_operation(
        self,
        operation: str,
        *,
        success: bool = True,
        message: str | None = None,
    ) -> None:
        """Implement ProgressReporter.complete_operation."""
        # Update status and mark task complete in Rich Progress
        msg = message or operation
        if success:
            self.show_status(f"✓ {msg}")
        else:
            self.show_error(f"✗ {msg}")
```

**Key Points**:
- ✅ StatusDisplay ALREADY uses Rich (no refactoring needed)
- ✅ Just add protocol methods that delegate to existing implementation
- ✅ No changes to existing Rich setup (Console, Progress, Live)
- ✅ Minimal changes - just protocol compliance

### 5. CLI Initialization (`cli/__main__.py` updates)

**Simplified**: No custom logging handlers needed! Rich already integrated.

```python
# Update cli/__main__.py

from codeweaver.core import override_dependency
from codeweaver.core.ui_protocol import ProgressReporter
from codeweaver.cli.ui import StatusDisplay

def main():
    """CLI entry point."""
    # Create StatusDisplay (already uses Rich Console/Progress)
    status_display = StatusDisplay()

    # Override DI to use StatusDisplay instead of default RichConsoleProgressReporter
    override_dependency(ProgressReporter, status_display)

    # Rest of CLI initialization...
    # Rich logging already configured in core/_logging.py via RichHandler
```

**Key Simplifications**:
- ✅ No `install_cli_handler()` needed (Rich already configured)
- ✅ No custom logging handlers (RichHandler already does it)
- ✅ Just override DI to use StatusDisplay
- ✅ StatusDisplay's Rich Console/Progress work automatically

### 6. Server/Engine Usage

```python
# engine/services/indexing_service.py

from codeweaver.core import INJECTED, ProgressReporterDep

class IndexingService:
    """Indexing service with progress reporting."""

    def __init__(
        self,
        # ... other dependencies ...
        progress_reporter: ProgressReporterDep = INJECTED,
    ):
        self.progress_reporter = progress_reporter

    async def index_project(self, project_path: Path) -> IndexingStats:
        """Index project with progress reporting."""
        # Report operation start
        self.progress_reporter.start_operation(
            "indexing",
            description=f"Indexing {project_path}",
        )

        try:
            # Discover files
            files = await self._discover_files(project_path)
            self.progress_reporter.report_progress(
                "discovery",
                len(files),
                len(files),
            )

            # Process files
            for i, batch in enumerate(self._batch_files(files)):
                # ... processing ...

                self.progress_reporter.report_progress(
                    "indexing",
                    i * batch_size,
                    len(files),
                    extra={"batch": i},
                )

            # Report success
            self.progress_reporter.complete_operation("indexing", success=True)

        except Exception as e:
            self.progress_reporter.report_error(e, recoverable=False)
            self.progress_reporter.complete_operation("indexing", success=False)
            raise
```

### 7. Server Initialization (daemon mode)

**Simplified**: Rich Console handles output automatically!

```python
# server/daemon.py

def start_daemon():
    """Start server in daemon mode."""
    # DI will inject RichConsoleProgressReporter automatically
    # Uses shared Rich Console from get_rich_console()
    # Output goes to stdout with Rich formatting (captured by systemd/Docker)
    # File logging already configured via RichHandler in core/_logging.py

    # No StatusDisplay in this environment
    # No need to suppress stdout - Rich Console output is structured and appropriate

    # Start server...
```

**Key Simplifications**:
- ✅ No `suppress_stdout_logging()` needed
- ✅ RichConsoleProgressReporter uses Rich Console (same as RichHandler)
- ✅ Structured output to stdout is good (systemd/Docker capture it)
- ✅ File logging already configured
- ✅ Everything "just works" with Rich

## Migration Strategy

**Much Simpler with Rich!** Estimated 3-4 days (was 5-7 days).

### Phase 1: Create Core Infrastructure (0.5 day)

1. **Create `core/ui_protocol.py`**:
   - Define `ProgressReporter` protocol
   - Implement `NoOpProgressReporter`
   - Implement `RichConsoleProgressReporter` (uses Rich Console)

2. **Update `core/_logging.py`**:
   - Add `get_rich_console()` helper function (10 lines)
   - **That's it!** RichHandler already configured

3. **Update `core/dependencies.py`**:
   - Add `ProgressReporter` factory
   - Export `ProgressReporterDep`
   - Use `get_rich_console()` for RichConsoleProgressReporter

### Phase 2: Update CLI (0.5 day)

1. **Update `cli/ui/status_display.py`**:
   - Add `ProgressReporter` protocol inheritance
   - Add 5 protocol methods that delegate to existing methods
   - **NO changes to Rich setup** (already perfect!)

2. **Update `cli/__main__.py`**:
   - Override DI with StatusDisplay (1 line)
   - **NO custom logging handlers** (Rich already configured)

### Phase 3: Update Engine (1 day)

1. **Update all engine services**:
   - Inject `ProgressReporterDep`
   - Replace direct StatusDisplay usage with protocol calls
   - Use protocol methods instead of StatusDisplay methods

2. **Remove StatusDisplay imports**:
   - Delete all `from codeweaver.cli import StatusDisplay`
   - Verify no circular dependencies

### Phase 4: Update Server (0.5 day)

1. **Update server components**:
   - Inject `ProgressReporterDep`
   - Remove StatusDisplay imports
   - **NO suppression logic needed** (Rich handles it)

2. **Server initialization**:
   - **NO changes needed** - DI injects RichConsoleProgressReporter automatically

### Phase 5: Testing & Validation (0.5 day)

1. **Test CLI mode**:
   - Verify StatusDisplay receives progress
   - Check Rich integration still works
   - Test all progress scenarios

2. **Test server/daemon mode**:
   - Verify Rich Console output works
   - Check file logging works
   - Test without CLI package

3. **Test library usage**:
   - Verify NoOpProgressReporter works
   - Check no UI dependencies

## Benefits

### Immediate

1. **Correct Dependencies**: `cli` → `server`/`engine` → `core` ✅
2. **Monorepo Ready**: Packages independently deployable ✅
3. **Leverages Rich**: Uses existing Rich infrastructure (50% less code) ✅
4. **Type Safety**: Protocol enforces contract ✅
5. **No Custom Logging**: RichHandler already does everything we need ✅
6. **Simpler Migration**: 3-4 days instead of 5-7 days ✅

### Long-term

1. **Flexibility**: Easy to add web UI, API, etc. (just implement protocol)
2. **Testing**: Mock progress reporter in tests (NoOpProgressReporter)
3. **Observability**: Rich Console + file logging + RichHandler = complete observability
4. **Maintainability**: One protocol, Rich handles implementation
5. **Consistency**: All output uses Rich formatting (CLI and server)

## Alternative Considered: Event Bus

We considered using an event bus pattern but rejected it because:
- ❌ More complex (adds new abstraction)
- ❌ Harder to debug (async event flow)
- ❌ Overkill for current needs
- ✅ Protocol + DI is simpler and fits existing architecture

## Open Questions

1. **Should we keep StatusDisplay name or rename to CLIProgressReporter?**
   - Recommendation: Keep StatusDisplay (it's more than just progress)
   - Add type alias: `CLIProgressReporter = StatusDisplay`

2. **How to handle context managers (with statement)?**
   - Add `__enter__` / `__exit__` to protocol?
   - Or separate `OperationContext` protocol?
   - Recommendation: Add to protocol as optional

3. **Should LoggingProgressReporter be the default?**
   - Recommendation: Yes for non-CLI
   - NoOp only for explicit testing scenarios

## Success Criteria

- ✅ No imports from `cli` in `server` or `engine`
- ✅ CLI works with StatusDisplay
- ✅ Server works without CLI package
- ✅ All tests pass
- ✅ No stdout spam in daemon mode
- ✅ Logging routes correctly in all modes

## Timeline

**Total**: 3-4 days (40% faster due to Rich!)

- Phase 1 (Core): 0.5 day (Rich Console helper + protocol)
- Phase 2 (CLI): 0.5 day (StatusDisplay already has Rich)
- Phase 3 (Engine): 1 day (inject protocol)
- Phase 4 (Server): 0.5 day (automatic via DI)
- Phase 5 (Testing): 0.5-1 day (verify all modes)

Can be done in parallel with engine DI refactoring (different files).

## Comparison: Custom Logging vs Rich-Based

### Original Approach (Custom Logging)
- ❌ Custom `CLIStatusHandler` class (~100 lines)
- ❌ Custom logging setup and configuration
- ❌ Manual stdout suppression logic
- ❌ Bridging between logging and UI
- ⏱️ 5-7 days implementation
- 📝 ~400 lines of new code

### Rich-Based Approach (What We're Doing)
- ✅ Use existing `RichHandler` (already configured!)
- ✅ Use existing Rich Console (StatusDisplay already has it!)
- ✅ `get_rich_console()` helper (10 lines)
- ✅ Protocol + 2 implementations (~200 lines)
- ⏱️ 3-4 days implementation
- 📝 ~210 lines of new code (50% reduction!)

**Key Insight**: Rich ALREADY does everything we were about to build ourselves!

---

**Document Version**: 2.0 (Rich-Based Approach)
**Last Updated**: 2026-01-16
**Authors**: Claude Sonnet 4.5 + User
**Status**: Ready for Review

**Changelog**:
- v2.0 (2026-01-16): Complete rewrite to leverage existing Rich infrastructure
  - Changed from custom logging approach to Rich Console-based
  - Reduced implementation from 5-7 days to 3-4 days
  - Reduced new code from ~400 lines to ~210 lines (50% reduction)
  - Simplified all sections to use existing RichHandler and Rich Console
- v1.0 (2026-01-16): Initial design with custom logging handlers (deprecated)
