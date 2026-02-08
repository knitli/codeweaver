# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Rich-based UI for tracking indexing progress."""

from __future__ import annotations

import contextlib

from typing import Self

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from codeweaver.engine.managers.progress_tracker import IndexingPhase, IndexingStats


class IndexingProgressUI:
    """Progress tracker UI for indexing operations with Rich visualizations."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the UI."""
        self.console = console or Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        )

        # Task IDs for different phases
        self.discovery_task_id: int | None = None
        self.chunking_task_id: int | None = None
        self.embedding_task_id: int | None = None
        self.indexing_task_id: int | None = None

        # Phase tracking
        self.current_phase: IndexingPhase = IndexingPhase.DISCOVERY
        self.live: Live | None = None

    def start(self, total_files: int = 0) -> None:
        """Start the progress tracking interface."""
        # Initialize tasks
        self.discovery_task_id = self.progress.add_task(
            "[cyan]Discovering files...", total=total_files if total_files > 0 else None
        )

        self.chunking_task_id = self.progress.add_task(
            "[blue]Chunking files...", total=total_files if total_files > 0 else None, visible=False
        )

        self.embedding_task_id = self.progress.add_task(
            "[magenta]Generating embeddings...", total=None, visible=False
        )

        self.indexing_task_id = self.progress.add_task(
            "[green]Indexing to vector store...", total=None, visible=False
        )

        # Start live display
        self.live = Live(self.progress, console=self.console, refresh_per_second=10)
        self.live.start()

    def stop(self) -> None:
        """Stop the progress tracking interface."""
        if self.live:
            self.live.stop()
            self.live = None
            if hasattr(self.console.file, "flush"):
                self.console.file.flush()

    def update(self, stats: IndexingStats, phase: str | None = None) -> None:
        """Update progress based on current indexing statistics."""
        if not self.live:
            self.start(total_files=stats.files_discovered)

        if phase:
            with contextlib.suppress(ValueError):
                self.current_phase = IndexingPhase(phase)

        if self.discovery_task_id is not None and stats.files_discovered > 0:
            self.progress.update(
                TaskID(self.discovery_task_id),
                total=stats.files_discovered,
                completed=stats.files_discovered,
                visible=True,
            )

        if self.chunking_task_id is not None and stats.files_processed > 0:
            self.progress.update(
                TaskID(self.chunking_task_id),
                total=stats.files_discovered,
                completed=stats.files_processed,
                visible=True,
            )

        if self.embedding_task_id is not None and stats.chunks_embedded > 0:
            self.progress.update(
                TaskID(self.embedding_task_id),
                total=stats.chunks_created if stats.chunks_created > 0 else None,
                completed=stats.chunks_embedded,
                visible=True,
            )

        if self.indexing_task_id is not None and stats.chunks_indexed > 0:
            self.progress.update(
                TaskID(self.indexing_task_id),
                total=stats.chunks_created if stats.chunks_created > 0 else None,
                completed=stats.chunks_indexed,
                visible=True,
            )

    def display_summary(self, stats: IndexingStats) -> None:
        """Display final summary."""
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right", style="green")

        table.add_row("Files Discovered", str(stats.files_discovered))
        table.add_row("Files Processed", str(stats.files_processed))
        table.add_row("Chunks Created", str(stats.chunks_created))
        table.add_row("Chunks Embedded", str(stats.chunks_embedded))
        table.add_row("Chunks Indexed", str(stats.chunks_indexed))
        table.add_row("Processing Rate", f"{stats.processing_rate():.2f} files/sec")
        table.add_row("Time Elapsed", f"{stats.elapsed_time():.2f} seconds")

        if stats.total_errors() > 0:
            table.add_row("Files with Errors", f"[yellow]{stats.total_errors()}[/yellow]")

        panel = Panel(
            table, title="[bold green]Indexing Summary[/bold green]", border_style="green"
        )

        self.console.print()
        self.console.print(panel)

    def __enter__(self) -> Self:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()


__all__ = ("IndexingProgressUI",)
