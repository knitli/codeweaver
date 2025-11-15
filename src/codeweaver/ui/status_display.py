# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Clean status display for user-facing output."""

from __future__ import annotations

import time

from contextlib import contextmanager
from typing import TYPE_CHECKING, Literal

from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from codeweaver import __version__


if TYPE_CHECKING:
    from collections.abc import Generator


class StatusDisplay:
    """Clean status display using rich for user-facing output.

    This class provides clean, formatted status output that bypasses the logging system
    entirely, ensuring users see clean, contextual information without debug noise.
    """

    def __init__(self, *, console: Console | None = None) -> None:
        """Initialize status display.

        Args:
            console: Optional rich Console instance. If not provided, creates one.
        """
        self.console = console or Console(markup=False, emoji=True)
        self._start_time = time.time()

    def print_header(self, *, host: str = "127.0.0.1", port: int = 9328) -> None:
        """Print the application header with version and server info.

        Args:
            host: Server host address
            port: Server port number
        """
        self.console.print(f"CodeWeaver v{__version__}")
        self.console.print(f"Server: http://{host}:{port}/codeweaver")
        self.console.print()

    def print_step(self, message: str) -> None:
        """Print a status step message.

        Args:
            message: Message to display
        """
        self.console.print(message)

    def print_completion(
        self, message: str, *, success: bool = True, details: str | None = None
    ) -> None:
        """Print a completion status with checkmark or error indicator.

        Args:
            message: Completion message
            success: Whether the operation succeeded
            details: Optional details to display on the same line
        """
        icon = "✓" if success else "✗"
        full_message = f"{icon} {message}"
        if details:
            full_message += f" {details}"
        self.console.print(full_message)

    def print_indexing_stats(
        self,
        files_indexed: int,
        chunks_created: int,
        duration_seconds: float,
        files_per_second: float,
    ) -> None:
        """Print indexing statistics.

        Args:
            files_indexed: Number of files indexed
            chunks_created: Number of chunks created
            duration_seconds: Time taken in seconds
            files_per_second: Processing rate
        """
        self.print_completion(
            f"Indexed {files_indexed} files, {chunks_created} chunks",
            details=f"({duration_seconds:.1f}s, {files_per_second:.1f} files/sec)",
        )

    def print_health_check(
        self,
        service_name: str,
        status: Literal["up", "down", "degraded"],
        *,
        model: str | None = None,
    ) -> None:
        """Print health check status for a service.

        Args:
            service_name: Name of the service
            status: Health status
            model: Optional model name to display
        """
        status_icon = {"up": "✅", "down": "❌", "degraded": "⚠️"}[status]
        model_info = f" ({model})" if model else ""
        self.print_completion(f"{service_name}: {status_icon}{model_info}")

    def print_ready(self) -> None:
        """Print the 'Ready for connections' message."""
        self.console.print()
        self.console.print("Ready for connections.")

    def print_shutdown_start(self) -> None:
        """Print shutdown initiation message."""
        self.console.print()
        self.console.print("Saving state... ", end="")

    def print_shutdown_complete(self) -> None:
        """Print shutdown completion message."""
        self.console.print("✓")
        self.console.print("Goodbye!")

    @contextmanager
    def spinner(self, message: str, *, spinner_style: str = "dots") -> Generator[None, None, None]:
        """Context manager for displaying a spinner during operations.

        Args:
            message: Message to display with spinner
            spinner_style: Spinner style (default: "dots")

        Yields:
            None
        """
        spinner_obj = Spinner(spinner_style, text=Text(message))
        with Live(spinner_obj, console=self.console, refresh_per_second=10):
            yield

    def print_error(self, message: str, *, details: str | None = None) -> None:
        """Print an error message.

        Args:
            message: Error message
            details: Optional additional details
        """
        self.console.print(f"✗ Error: {message}", style="bold red")
        if details:
            self.console.print(f"  {details}", style="red")

    def print_warning(self, message: str) -> None:
        """Print a warning message.

        Args:
            message: Warning message
        """
        self.console.print(f"⚠️  {message}", style="yellow")

    def print_command_header(self, command: str, description: str | None = None) -> None:
        """Print command header with CodeWeaver prefix.

        Args:
            command: Command name (e.g., "index", "search")
            description: Optional command description
        """
        from codeweaver.common import CODEWEAVER_PREFIX

        self.console.print(f"{CODEWEAVER_PREFIX} {command}", style="bold")
        if description:
            self.console.print(f"  {description}")
        self.console.print()

    def print_section(self, title: str) -> None:
        """Print a section header.

        Args:
            title: Section title
        """
        self.console.print(f"\n{title}", style="bold cyan")

    def print_info(self, message: str, *, prefix: str = "ℹ️") -> None:
        """Print an informational message.

        Args:
            message: Information message
            prefix: Optional prefix icon (default: ℹ️)
        """
        self.console.print(f"{prefix}  {message}", style="blue")

    def print_success(self, message: str, *, details: str | None = None) -> None:
        """Print a success message with optional details.

        Args:
            message: Success message
            details: Optional details to display
        """
        full_message = f"✅ {message}"
        if details:
            full_message += f" {details}"
        self.console.print(full_message, style="green")

    def print_table(self, table: Table) -> None:
        """Print a rich table.

        Args:
            table: Rich Table object to display
        """
        self.console.print(table)

    def print_progress(self, current: int, total: int, message: str) -> None:
        """Print progress information.

        Args:
            current: Current progress value
            total: Total value
            message: Progress message
        """
        percentage = (current / total * 100) if total > 0 else 0
        self.console.print(f"  [{current}/{total}] ({percentage:.0f}%) {message}")

    @contextmanager
    def live_progress(self, description: str) -> Generator[Progress, None, None]:
        """Context manager for live progress display.

        Args:
            description: Description to show with progress

        Yields:
            Rich Progress object for tracking tasks
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        )
        with progress:
            yield progress


__all__ = ("StatusDisplay",)
