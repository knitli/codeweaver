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
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from codeweaver import __version__


if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from typing import Self


class IndexingProgress:
    """Unified progress tracker for batch-through-pipeline indexing.

    Provides real-time progress updates with batch tracking:
    - Batch X of Y header
    - Per-batch phases: Checking → Chunking → Dense/Sparse Embedding → Indexing
    - Shows all phases from start, updates granularly (every 5-10 items)
    - Dense/sparse embedding split shown only when both providers configured
    """

    def __init__(self, console: Console | None = None, *, has_sparse: bool = False) -> None:
        """Initialize the indexing progress tracker.

        Args:
            console: Optional Rich console instance
            has_sparse: Whether sparse embeddings are configured
        """
        import sys

        is_interactive = sys.stdin.isatty() if hasattr(sys.stdin, "isatty") else False
        self.console = console or Console(markup=True, emoji=True, force_interactive=is_interactive)
        self._has_sparse = has_sparse

        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=self.console,
            expand=False,
        )

        # Task IDs for each phase
        self._batch_task: int | None = None
        self._checking_task: int | None = None
        self._chunking_task: int | None = None
        self._dense_task: int | None = None
        self._sparse_task: int | None = None
        self._indexing_task: int | None = None

        # Batch tracking
        self._current_batch = 0
        self._total_batches = 0
        self._started = False

        # Cumulative totals across batches
        self._total_files_processed = 0
        self._total_chunks_created = 0
        self._total_chunks_embedded = 0
        self._total_chunks_indexed = 0

    def start(
        self, total_batches: int = 1, total_files: int = 0, *, has_sparse: bool | None = None
    ) -> None:
        """Start the progress display with all phases visible.

        Args:
            total_batches: Total number of batches to process
            total_files: Total files across all batches
            has_sparse: Override sparse embedding display (uses init value if None)
        """
        if self._started:
            return

        self._total_batches = total_batches
        if has_sparse is not None:
            self._has_sparse = has_sparse

        # Batch progress (overall)
        self._batch_task = self.progress.add_task(
            f"[bold white]Batch 0/{total_batches}", total=total_batches, visible=True
        )

        # Per-batch phases - all visible from start
        self._checking_task = self.progress.add_task(
            "[cyan]Checking files...", total=0, visible=True
        )
        self._chunking_task = self.progress.add_task(
            "[blue]Chunking...", total=0, visible=True
        )
        self._dense_task = self.progress.add_task(
            "[magenta]Dense embedding...", total=0, visible=True
        )
        if self._has_sparse:
            self._sparse_task = self.progress.add_task(
                "[magenta]Sparse embedding...", total=0, visible=True
            )
        self._indexing_task = self.progress.add_task(
            "[green]Indexing...", total=0, visible=True
        )

        self.progress.start()
        self._started = True

    def stop(self) -> None:
        """Stop the progress display."""
        if self._started:
            self.progress.stop()
            self._started = False

    def start_batch(self, batch_num: int, files_in_batch: int) -> None:
        """Signal start of a new batch.

        Args:
            batch_num: Current batch number (1-indexed)
            files_in_batch: Number of files in this batch
        """
        if not self._started:
            self.start(total_batches=1)

        self._current_batch = batch_num

        # Update batch counter
        if self._batch_task is not None:
            self.progress.update(
                self._batch_task,
                completed=batch_num - 1,
                description=f"[bold white]Batch {batch_num}/{self._total_batches}",
            )

        # Reset per-batch tasks for new batch
        if self._checking_task is not None:
            self.progress.update(
                self._checking_task,
                completed=0,
                total=files_in_batch,
                description="[cyan]Checking files...",
            )
        if self._chunking_task is not None:
            self.progress.update(
                self._chunking_task, completed=0, total=0, description="[blue]Chunking..."
            )
        if self._dense_task is not None:
            self.progress.update(
                self._dense_task, completed=0, total=0, description="[magenta]Dense embedding..."
            )
        if self._sparse_task is not None:
            self.progress.update(
                self._sparse_task, completed=0, total=0, description="[magenta]Sparse embedding..."
            )
        if self._indexing_task is not None:
            self.progress.update(
                self._indexing_task, completed=0, total=0, description="[green]Indexing..."
            )

    def update_checking(self, current: int, total: int) -> None:
        """Update checking/identification phase progress.

        Args:
            current: Files checked so far in this batch
            total: Total files to check in this batch
        """
        if not self._started:
            self.start()

        if self._checking_task is not None:
            self.progress.update(
                self._checking_task,
                completed=current,
                total=total,
                description=f"[cyan]Checking files... ({current}/{total})",
            )

    def update_chunking(self, files_processed: int, total_files: int, chunks_created: int) -> None:
        """Update chunking phase progress.

        Args:
            files_processed: Files chunked so far in this batch
            total_files: Total files to chunk in this batch
            chunks_created: Chunks created so far in this batch
        """
        if not self._started:
            self.start()

        # Mark checking complete
        if self._checking_task is not None:
            self.progress.update(
                self._checking_task,
                completed=total_files,
                total=total_files,
                description=f"[cyan]✓ Checked ({total_files} files)",
            )

        if self._chunking_task is not None:
            self.progress.update(
                self._chunking_task,
                completed=files_processed,
                total=total_files,
                description=f"[blue]Chunking... ({chunks_created} chunks)",
            )

    def update_dense_embedding(self, chunks_embedded: int, total_chunks: int) -> None:
        """Update dense embedding phase progress.

        Args:
            chunks_embedded: Chunks embedded so far
            total_chunks: Total chunks to embed
        """
        if not self._started:
            self.start()

        # Mark chunking complete on first embedding update
        if self._chunking_task is not None:
            task = self.progress.tasks[self._chunking_task]
            if task.total and task.total > 0:
                self.progress.update(
                    self._chunking_task,
                    completed=task.total,
                    description=f"[blue]✓ Chunked ({int(task.total)} files)",
                )

        if self._dense_task is not None:
            self.progress.update(
                self._dense_task,
                completed=chunks_embedded,
                total=total_chunks,
                description=f"[magenta]Dense embedding... ({chunks_embedded}/{total_chunks})",
            )

    def update_sparse_embedding(self, chunks_embedded: int, total_chunks: int) -> None:
        """Update sparse embedding phase progress.

        Args:
            chunks_embedded: Chunks embedded so far
            total_chunks: Total chunks to embed
        """
        if not self._started or self._sparse_task is None:
            return

        self.progress.update(
            self._sparse_task,
            completed=chunks_embedded,
            total=total_chunks,
            description=f"[magenta]Sparse embedding... ({chunks_embedded}/{total_chunks})",
        )

    def update_indexing(self, chunks_indexed: int, total_chunks: int) -> None:
        """Update indexing phase progress.

        Args:
            chunks_indexed: Chunks indexed so far
            total_chunks: Total chunks to index
        """
        if not self._started:
            self.start()

        # Mark embedding complete
        if self._dense_task is not None:
            task = self.progress.tasks[self._dense_task]
            if task.total and task.total > 0:
                self.progress.update(
                    self._dense_task,
                    completed=task.total,
                    description=f"[magenta]✓ Dense ({int(task.total)} chunks)",
                )
        if self._sparse_task is not None:
            task = self.progress.tasks[self._sparse_task]
            if task.total and task.total > 0:
                self.progress.update(
                    self._sparse_task,
                    completed=task.total,
                    description=f"[magenta]✓ Sparse ({int(task.total)} chunks)",
                )

        if self._indexing_task is not None:
            self.progress.update(
                self._indexing_task,
                completed=chunks_indexed,
                total=total_chunks,
                description=f"[green]Indexing... ({chunks_indexed}/{total_chunks})",
            )

    def complete_batch(self) -> None:
        """Mark current batch as complete."""
        # Mark indexing complete
        if self._indexing_task is not None:
            task = self.progress.tasks[self._indexing_task]
            if task.total and task.total > 0:
                self.progress.update(
                    self._indexing_task,
                    completed=task.total,
                    description=f"[green]✓ Indexed ({int(task.total)} chunks)",
                )

        # Update batch counter
        if self._batch_task is not None:
            self.progress.update(self._batch_task, completed=self._current_batch)

    def complete(self) -> None:
        """Mark all batches as complete."""
        self.complete_batch()
        if self._batch_task is not None:
            self.progress.update(
                self._batch_task,
                completed=self._total_batches,
                description=f"[bold green]✓ Complete ({self._total_batches} batches)",
            )

    # Legacy compatibility methods
    def update_discovery(self, current: int, total: int | None = None) -> None:
        """Legacy method for discovery updates - maps to update_checking."""
        if total and total > 0:
            self.update_checking(current, total)
        else:
            # Scanning phase - no total known yet
            if not self._started:
                self.start()
            if self._checking_task is not None:
                self.progress.update(
                    self._checking_task,
                    completed=current,
                    total=current + 1,
                    description=f"[cyan]Scanning files... ({current} found)",
                )

    def update_embedding(self, chunks_embedded: int, total_chunks: int) -> None:
        """Legacy method for embedding updates - maps to update_dense_embedding."""
        self.update_dense_embedding(chunks_embedded, total_chunks)

    def __enter__(self) -> Self:
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Context manager exit."""
        self.stop()


class StatusDisplay:
    """Clean status display using rich for user-facing output.

    This class provides clean, formatted status output that bypasses the logging system
    entirely, ensuring users see clean, contextual information without logging noise. Lets more information through to users if 'verbose' or 'debug' modes are enabled.
    """

    def __init__(self, *, console: Console | None = None) -> None:
        """Initialize status display.

        Args:
            console: Optional rich Console instance. If not provided, creates one.
        """
        # Detect if we're in an interactive terminal to avoid stdin issues in pytest
        import sys

        is_interactive = sys.stdin.isatty() if hasattr(sys.stdin, "isatty") else False
        self.console = console or Console(markup=True, emoji=True, force_interactive=is_interactive)
        self._start_time = time.time()

    def print_header(self, *, host: str = "127.0.0.1", port: int = 9328) -> None:
        """Print the application header with version and server info.

        Args:
            host: Server host address
            port: Server port number
        """
        self.console.print(f"CodeWeaver v{__version__}")
        self.console.print(f"Server: http://{host}:{port}")
        self.console.print("[dim]Built with FastMCP (https://gofastmcp.com)[/dim]")
        self.console.print()
        self.console.print("Built by Knitli: https://knitli.com")
        self.console.print()
        self.console.print(
            "Find a bug? Want to contribute? Visit https://github.com/knitli/codeweaver"
        )

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

    def print_list(
        self, items: list[str], *, title: str | None = None, numbered: bool = False
    ) -> None:
        """Print a list of items.

        Args:
            items: List of strings to display
            title: Optional title for the list
            numbered: Whether to number the list items
        """
        if title:
            self.console.print(f"{title}:", style="bold")
        for i, item in enumerate(items, start=1):
            self.console.print(f" {i if numbered else '-'}{'.' if numbered else ''} {item}")

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

    def print_info(self, message: str, *, prefix: str = "ℹ️") -> None:  # noqa: RUF001
        """Print an informational message.

        Args:
            message: Information message
            prefix: Optional prefix icon (default: ℹ️)
        """  # noqa: RUF002
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

    @contextmanager
    def progress_bar(
        self, total: int, description: str = "Processing"
    ) -> Generator[Callable[[int], None], None, None]:
        """Context manager for displaying a progress bar.

        Args:
            total: Total number of items to process
            description: Description to show with progress bar

        Yields:
            Function to update progress (call with current count)
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
        )

        with progress:
            task = progress.add_task(description, total=total)

            def update(current: int) -> None:
                progress.update(task, completed=current)

            yield update

    def print_index_summary(
        self,
        files_indexed: int,
        chunks_created: int,
        language_breakdown: dict[str, int] | None = None,
        avg_chunks_per_file: float | None = None,
        avg_tokens_per_chunk: float | None = None,
    ) -> None:
        """Print index summary with statistics.

        Args:
            files_indexed: Number of files indexed
            chunks_created: Number of chunks created
            language_breakdown: Optional dict of language -> file count
            avg_chunks_per_file: Average chunks per file
            avg_tokens_per_chunk: Average tokens per chunk
        """
        self.console.print()
        self.console.print("[bold cyan]Index Summary:[/bold cyan]")
        self.console.print(f"  Files indexed: {files_indexed}")
        self.console.print(f"  Code chunks: {chunks_created}")

        if language_breakdown:
            # Format: "Python (8), TypeScript (3), Markdown (1)"
            lang_parts = [
                f"{lang} ({count})"
                for lang, count in sorted(
                    language_breakdown.items(), key=lambda x: x[1], reverse=True
                )
            ]
            lang_str = ", ".join(lang_parts[:5])  # Show top 5
            if len(language_breakdown) > 5:
                lang_str += f", +{len(language_breakdown) - 5} more"
            self.console.print(f"  Languages: {lang_str}")

        if avg_chunks_per_file is not None and avg_tokens_per_chunk is not None:
            self.console.print(
                f"  Average: {avg_chunks_per_file:.1f} chunks/file, "
                f"{avg_tokens_per_chunk:.0f} tokens/chunk"
            )

    def print_reindex_brief(self, files: int, chunks: int, duration: float) -> None:
        """Print brief reindexing message.

        Args:
            files: Number of files reindexed
            chunks: Number of chunks created
            duration: Duration in seconds
        """
        self.console.print(f"↻ Reindexed {files} files, {chunks} chunks ({duration:.1f}s)")


_display: StatusDisplay | None = None


def get_display() -> StatusDisplay:
    """Get the global StatusDisplay instance, creating it if necessary.

    Returns:
        StatusDisplay instance
    """
    global _display
    if _display is None:
        _display = StatusDisplay()
    return _display


__all__ = ("IndexingProgress", "StatusDisplay", "get_display")
