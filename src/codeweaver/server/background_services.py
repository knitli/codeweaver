# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Initialize background services for the CodeWeaver server."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from functools import partial
from typing import TYPE_CHECKING, Any

from codeweaver.cli.ui.status_display import IndexingProgress, StatusDisplay
from codeweaver.common.utils.utils import elapsed_time_to_human_readable
from codeweaver.core.types.sentinel import Unset


if TYPE_CHECKING:
    from codeweaver.server.lifespan import CodeWeaverState

_logger = logging.getLogger(__name__)


# Create callback that maps to IndexingProgress methods (same as index command)
def _progress_callback(
    progress_tracker: IndexingProgress,
    current_batch_files: list[int],
    phase: str,
    current: int,
    total: int,
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    match phase:
        case "batch_complete":
            progress_tracker.complete_batch(current_batch_files[0])
            current_batch_files[0] = 0
        case "batch_start":
            if current == 0:
                # Initial setup - start with total batches
                total_files = extra.get("total_files", 0) if extra else 0
                progress_tracker.start(total_batches=total, total_files=total_files)
            else:
                # Start of a specific batch
                files_in_batch = extra.get("files_in_batch", 0) if extra else 0
                current_batch_files[0] = files_in_batch
                progress_tracker.start_batch(current, files_in_batch)
        case "checking":
            progress_tracker.update_checking(current, total)
        case "chunking":
            chunks_created = extra.get("chunks_created", 0) if extra else 0
            progress_tracker.update_chunking(current, total, chunks_created)
        case "dense_embedding" | "embedding":
            progress_tracker.update_dense_embedding(current, total)
        case "discovery":
            # Legacy discovery callback - maps to checking
            progress_tracker.update_discovery(current, total)
        case "indexing":
            progress_tracker.update_indexing(current, total)
        case "sparse_embedding":
            progress_tracker.update_sparse_embedding(current, total)


async def _perform_indexing(
    state: CodeWeaverState, status_display: StatusDisplay, *, verbose: bool, debug: bool
) -> None:
    """Perform the indexing operation with progress tracking."""
    status_display.print_info("Initializing indexer...")

    # Check if sparse embeddings are configured
    has_sparse = state.indexer._sparse_provider is not None

    # Create progress tracker with batch support (same as index command)
    progress_tracker: IndexingProgress = IndexingProgress(
        console=status_display.console, has_sparse=has_sparse
    )

    # Track files in current batch for complete_batch
    current_batch_files = [0]  # Use list to allow mutation in closure

    status_display.print_success("Starting indexing process...")

    with progress_tracker:
        await state.indexer.prime_index(
            force_reindex=False,
            progress_callback=partial(_progress_callback, progress_tracker, current_batch_files),
            status_display=None if verbose or debug else status_display,
        )
        progress_tracker.complete()


def _display_indexing_summary(status_display: StatusDisplay, stats: Any) -> None:
    """Display the indexing summary statistics."""
    status_display.console.print()
    status_display.print_success("Indexing Complete!")
    status_display.console.print()
    status_display.console.print(f"  Files processed: [cyan]{stats.files_processed}[/cyan]")
    status_display.console.print(f"  Chunks created: [cyan]{stats.chunks_created}[/cyan]")
    status_display.console.print(f"  Chunks indexed: [cyan]{stats.chunks_indexed}[/cyan]")
    status_display.console.print(
        f"  Processing rate: [cyan]{stats.processing_rate():.2f}[/cyan] files/sec"
    )

    # Format elapsed time in human-readable format
    elapsed = stats.elapsed_time()
    human_time = elapsed_time_to_human_readable(elapsed)
    status_display.console.print(f"  Time elapsed: [cyan]{human_time}[/cyan]")

    if stats.total_errors() > 0:
        status_display.console.print(
            f"  [yellow]Files with errors: {stats.total_errors()}[/yellow]"
        )

    status_display.console.print()


async def start_watcher(
    state: CodeWeaverState, status_display: StatusDisplay
) -> asyncio.Task[None]:
    """Start the file watcher as an asynchronous task."""
    import rignore

    from codeweaver.common.utils import get_project_path
    from codeweaver.engine.watcher import FileWatcher, IgnoreFilter

    watcher = await FileWatcher.create(
        get_project_path()
        if isinstance(state.settings.project_path, Unset)
        else state.settings.project_path,
        file_filter=await IgnoreFilter.from_settings_async(),
        walker=rignore.Walker(**state.indexer._walker_settings),  # ty: ignore[invalid-argument-type]
        indexer=state.indexer,
        status_display=status_display,  # Pass status_display to watcher
    )

    # Run watcher in a separate task so we can cancel it cleanly
    return await asyncio.create_task(watcher.run())


async def _handle_watcher_cancellation(
    watcher_task: asyncio.Task[None] | None, status_display: StatusDisplay, *, verbose: bool
) -> None:
    """Handle graceful cancellation of the watcher task."""
    if not watcher_task or watcher_task.done():
        return

    watcher_task.cancel()
    try:
        await asyncio.wait_for(watcher_task, timeout=2.5)
    except (TimeoutError, asyncio.CancelledError):
        if verbose:
            _logger.warning("Watcher did not stop within timeout")
        status_display.console.print("  [dim]Tidying up a few loose threads...[/dim]")


async def _run_indexing_workflow(
    state: CodeWeaverState, status_display: StatusDisplay, *, verbose: bool, debug: bool
) -> asyncio.Task[None]:
    """Run the complete indexing workflow and start the watcher."""
    # Perform indexing with progress tracking
    await _perform_indexing(state, status_display, verbose=verbose, debug=debug)

    # Display final summary
    _display_indexing_summary(status_display, state.indexer.stats)

    status_display.print_step("Watching for file changes...")

    # Start file watcher for real-time updates
    if verbose:
        _logger.info("Starting file watcher...")

    return await start_watcher(state, status_display)


async def run_background_indexing(
    state: CodeWeaverState,
    status_display: StatusDisplay,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Background task for indexing and file watching.

    Args:
        state: Application state
        settings: Configuration settings
        status_display: StatusDisplay instance for user-facing output
        verbose: Whether to show verbose output
        debug: Whether debug mode is enabled
    """
    if verbose:
        _logger.info("Starting background indexing...")

    if not state.indexer:
        # Always show this warning to the user - it's important
        status_display.print_warning("No indexer configured, skipping background indexing")
        if verbose:
            _logger.warning(
                "No indexer configured, skipping background indexing. This is probably a bug if you have everything else set up correctly."
            )
        return

    watcher_task = None
    try:
        watcher_task = await _run_indexing_workflow(
            state, status_display, verbose=verbose, debug=debug
        )
    except asyncio.CancelledError:
        status_display.print_shutdown_start()
        if verbose:
            _logger.info("Background indexing cancelled, shutting down watcher...")
        await _handle_watcher_cancellation(watcher_task, status_display, verbose=verbose)
        raise
    except Exception as e:
        status_display.print_error("Background indexing error", details=str(e))
        _logger.warning("Background indexing error", exc_info=True)
    finally:
        # Ensure watcher task is cancelled on any exit
        if watcher_task and not watcher_task.done():
            watcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher_task
        status_display.print_shutdown_complete()


__all__ = ("run_background_indexing",)
