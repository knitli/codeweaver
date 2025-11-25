# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Module for tracking indexing progress and statistics in the CodeWeaver Indexer engine."""

from __future__ import annotations

import contextlib
import time

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, ClassVar, Self

from pydantic import Field
from pydantic.dataclasses import dataclass
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.models import DataclassSerializationMixin


if TYPE_CHECKING:
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion


@dataclass
class IndexingStats(DataclassSerializationMixin):
    """Statistics tracking for indexing progress."""

    files_discovered: int = 0
    files_processed: int = 0
    chunks_created: int = 0
    chunks_embedded: int = 0
    chunks_indexed: int = 0
    start_time: float = Field(default_factory=time.time)
    files_with_errors: ClassVar[
        Annotated[
            list[Path],
            Field(description="""List of file paths that encountered errors during indexing."""),
        ]
    ] = []

    def elapsed_time(self) -> float:
        """Calculate elapsed time since indexing started."""
        return time.time() - self.start_time

    def processing_rate(self) -> float:
        """Files processed per second."""
        if self.elapsed_time() == 0:
            return 0.0
        return self.files_processed / self.elapsed_time()

    @property
    def total_errors(self) -> int:
        """Total number of files with errors."""
        return len(self.files_with_errors)

    @property
    def total_files_discovered(self) -> int:
        """Total files discovered (alias for files_discovered)."""
        return self.files_discovered

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {FilteredKey("files_with_errors"): AnonymityConversion.COUNT}


class IndexingPhase(str, BaseEnum):
    """Enum representing different phases of the indexing process."""

    DISCOVERY = "discovery"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETE = "complete"

    __slots__ = ()

    @property
    def is_complete(self) -> bool:
        """Check if the phase is complete."""
        return self == IndexingPhase.COMPLETE


class IndexingProgressTracker:
    """Progress tracker for indexing operations with Rich visualizations.

    Provides real-time progress indicators for:
    - File discovery
    - Chunking progress
    - Embedding generation
    - Vector store indexing
    """

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the progress tracker.

        Args:
            console: Optional Rich console instance (creates default if not provided)
        """
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
        """Start the progress tracking interface.

        Args:
            total_files: Total number of files to process (0 if unknown)
        """
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
            # Explicitly flush to ensure clean terminal state
            if hasattr(self.console.file, 'flush'):
                self.console.file.flush()

    def update(self, stats: IndexingStats, phase: str | None = None) -> None:
        """Update progress based on current indexing statistics.

        Args:
            stats: Current indexing statistics
            phase: Optional phase name to transition to
        """
        if not self.live:
            # Auto-start if not already started
            self.start(total_files=stats.files_discovered)

        # Update phase if provided
        if phase:
            with contextlib.suppress(ValueError):
                self.current_phase = IndexingPhase(phase)

        # Update discovery task
        if self.discovery_task_id is not None and stats.files_discovered > 0:
            self.progress.update(
                self.discovery_task_id,
                total=stats.files_discovered,
                completed=stats.files_discovered,
                visible=True,
            )

        # Update chunking task
        if self.chunking_task_id is not None and stats.files_processed > 0:
            self.progress.update(
                self.chunking_task_id,
                total=stats.files_discovered,
                completed=stats.files_processed,
                visible=True,
            )

        # Update embedding task
        if self.embedding_task_id is not None and stats.chunks_embedded > 0:
            self.progress.update(
                self.embedding_task_id,
                total=stats.chunks_created if stats.chunks_created > 0 else None,
                completed=stats.chunks_embedded,
                visible=True,
            )

        # Update indexing task
        if self.indexing_task_id is not None and stats.chunks_indexed > 0:
            self.progress.update(
                self.indexing_task_id,
                total=stats.chunks_created if stats.chunks_created > 0 else None,
                completed=stats.chunks_indexed,
                visible=True,
            )

    def display_summary(self, stats: IndexingStats) -> None:
        """Display final summary of indexing operation.

        Args:
            stats: Final indexing statistics
        """
        # Create summary table
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

        if stats.total_errors > 0:
            table.add_row("Files with Errors", f"[yellow]{stats.total_errors}[/yellow]")

        # Display in panel
        panel = Panel(
            table, title="[bold green]Indexing Summary[/bold green]", border_style="green"
        )

        self.console.print()
        self.console.print(panel)

    def __enter__(self) -> Self:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Context manager exit - ensures clean terminal state."""
        self.stop()
        # Additional flush to ensure terminal is fully reset
        if hasattr(self.console.file, 'flush'):
            self.console.file.flush()


__all__ = ("IndexingPhase", "IndexingProgressTracker", "IndexingStats")
