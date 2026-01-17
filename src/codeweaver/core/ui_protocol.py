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
        self, phase: str, current: int, total: int, *, extra: dict[str, Any] | None = None
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
        self, message: str, *, level: str = "info", extra: dict[str, Any] | None = None
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

    def start_operation(self, operation: str, *, description: str | None = None) -> None:
        """Signal start of long-running operation.

        Args:
            operation: Operation identifier
            description: Human-readable description
        """
        ...

    def complete_operation(
        self, operation: str, *, success: bool = True, message: str | None = None
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
        """No-op progress report."""

    def report_status(self, message: str, **kwargs) -> None:
        """No-op status report."""

    def report_error(self, error: Exception | str, **kwargs) -> None:
        """No-op error report."""

    def start_operation(self, operation: str, **kwargs) -> None:
        """No-op start operation."""

    def complete_operation(self, operation: str, **kwargs) -> None:
        """No-op complete operation."""


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
        self, phase: str, current: int, total: int, *, extra: dict[str, Any] | None = None
    ) -> None:
        """Print progress using Rich Console."""
        percent = (current / total * 100) if total > 0 else 0
        self.console.print(f"[cyan]{phase}[/cyan]: {current}/{total} ({percent:.1f}%)")

    def report_status(
        self, message: str, *, level: str = "info", extra: dict[str, Any] | None = None
    ) -> None:
        """Print status with Rich formatting."""
        colors = {"debug": "dim", "info": "cyan", "warning": "yellow", "error": "red bold"}
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

    def start_operation(self, operation: str, *, description: str | None = None) -> None:
        """Print operation start."""
        msg = description or operation
        self.console.print(f"[cyan]▶[/cyan] {msg}")

    def complete_operation(
        self, operation: str, *, success: bool = True, message: str | None = None
    ) -> None:
        """Print operation completion."""
        icon = "✓" if success else "✗"
        color = "green" if success else "red"
        msg = message or operation
        self.console.print(f"[{color}]{icon}[/{color}] {msg}")


__all__ = ["NoOpProgressReporter", "ProgressReporter", "RichConsoleProgressReporter"]
