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
from rich.spinner import Spinner
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


__all__ = ("StatusDisplay",)
