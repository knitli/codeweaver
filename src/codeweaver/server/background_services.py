# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Initialize background services for the CodeWeaver server."""

from __future__ import annotations

import asyncio
import logging

from functools import partial
from typing import TYPE_CHECKING, Any

from codeweaver.core import elapsed_time_to_human_readable
from codeweaver.core.constants import WATCHER_WINDDOWN_TIMEOUT
from codeweaver.core.ui_protocol import ProgressReporter


if TYPE_CHECKING:
    from codeweaver.server.server import CodeWeaverState

_logger = logging.getLogger(__name__)


def _progress_callback(
    progress_reporter: ProgressReporter,
    phase: str,
    current: int,
    total: int,
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    """Report progress using ProgressReporter."""
    progress_reporter.report_progress(phase, current, total, extra=extra)


async def _perform_indexing(
    state: CodeWeaverState, progress_reporter: ProgressReporter, *, verbose: bool, debug: bool
) -> None:
    """Perform the indexing operation with progress tracking."""
    progress_reporter.start_operation("indexing", description="Initializing indexer...")
    progress_reporter.start_operation("indexing", description="Starting indexing process...")

    # Define simple callback wrapper
    callback = partial(_progress_callback, progress_reporter)
    if not state.indexer:
        progress_reporter.report_error(
            "No indexer configured, cannot perform indexing", recoverable=True
        )
        if verbose:
            _logger.warning(
                "No indexer configured, cannot perform indexing. This is probably a bug if you have everything else set up correctly."
            )
        return
    await state.indexer.index_project(force_reindex=False, progress_callback=callback)
    progress_reporter.complete_operation("indexing")


def _display_indexing_summary(progress_reporter: ProgressReporter, stats: Any) -> None:
    """Display the indexing summary statistics."""
    progress_reporter.report_status("Indexing Complete!", level="info")
    progress_reporter.report_status(f"  Files processed: {stats.files_processed}")
    progress_reporter.report_status(f"  Chunks created: {stats.chunks_created}")
    progress_reporter.report_status(f"  Chunks indexed: {stats.chunks_indexed}")
    progress_reporter.report_status(f"  Processing rate: {stats.processing_rate():.2f} files/sec")

    # Format elapsed time in human-readable format
    elapsed = stats.elapsed_time()
    human_time = elapsed_time_to_human_readable(elapsed)
    progress_reporter.report_status(f"  Time elapsed: {human_time}")

    if stats.total_errors() > 0:
        progress_reporter.report_status(
            f"  Files with errors: {stats.total_errors()}", level="warning"
        )


async def start_watcher(
    state: CodeWeaverState, progress_reporter: ProgressReporter
) -> asyncio.Task[None | int]:
    """Start the file watcher as an asynchronous task."""
    from codeweaver.core import get_container
    from codeweaver.engine.services.watching_service import FileWatchingService

    # Use DI container to resolve FileWatchingService with all its dependencies
    watcher = await get_container().resolve(FileWatchingService)

    # Run watcher in a separate task so we can cancel it cleanly
    return asyncio.create_task(watcher.run())


async def _handle_watcher_cancellation(
    watcher_task: asyncio.Task[None | int] | None,
    progress_reporter: ProgressReporter,
    *,
    verbose: bool,
) -> None:
    """Handle graceful cancellation of the watcher task."""
    if not watcher_task or watcher_task.done():
        return

    watcher_task.cancel()
    try:
        await asyncio.wait_for(watcher_task, timeout=WATCHER_WINDDOWN_TIMEOUT)
    except (TimeoutError, asyncio.CancelledError):
        if verbose:
            _logger.warning("Watcher did not stop within timeout")
        progress_reporter.report_status("  Tidying up a few loose threads...")


async def _run_indexing_workflow(
    state: CodeWeaverState, progress_reporter: ProgressReporter, *, verbose: bool, debug: bool
) -> asyncio.Task[None | int] | None:
    """Run the complete indexing workflow and start the watcher."""
    # Perform indexing with progress tracking
    await _perform_indexing(state, progress_reporter, verbose=verbose, debug=debug)

    # Display final summary
    if not state.indexer:
        progress_reporter.report_error(
            "No indexer configured, cannot display indexing summary", recoverable=True
        )
        if verbose:
            _logger.warning(
                "No indexer configured, cannot display indexing summary. This is probably a bug if you have everything else set up correctly."
            )
        return None
    _display_indexing_summary(progress_reporter, state.indexer.stats)

    progress_reporter.report_status("Watching for file changes...")

    # Start file watcher for real-time updates
    if verbose:
        _logger.info("Starting file watcher...")

    return await start_watcher(state, progress_reporter)


async def run_background_indexing(
    state: CodeWeaverState,
    progress_reporter: ProgressReporter,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Background task for indexing and file watching.

    Args:
        state: Application state
        progress_reporter: ProgressReporter instance for user-facing output
        verbose: Whether to show verbose output
        debug: Whether debug mode is enabled
    """
    if verbose:
        _logger.info("Starting background indexing...")

    if not state.indexer:
        # Always show this warning to the user - it's important
        progress_reporter.report_error(
            "No indexer configured, skipping background indexing", recoverable=True
        )
        if verbose:
            _logger.warning(
                "No indexer configured, skipping background indexing. This is probably a bug if you have everything else set up correctly."
            )
        return

    watcher_task = None
    try:
        watcher_task = await _run_indexing_workflow(
            state, progress_reporter, verbose=verbose, debug=debug
        )
    except asyncio.CancelledError:
        # status_display.print_shutdown_start() # Handled in lifespan cleanup usually?
        # But here it catches cancellation of this task.
        progress_reporter.report_status("Saving state...", extra={"end": ""})
        if verbose:
            _logger.info("Background indexing cancelled, shutting down watcher...")
        await _handle_watcher_cancellation(watcher_task, progress_reporter, verbose=verbose)
        raise
    except Exception as e:
        progress_reporter.report_error("Background indexing error", extra={"details": str(e)})
        _logger.warning("Background indexing error", exc_info=True)
    finally:
        # Ensure watcher task is cancelled on any exit
        if watcher_task and not watcher_task.done():
            watcher_task.cancel()
        # status_display.print_shutdown_complete() # Handled in lifespan
        # But wait, original code called print_shutdown_complete here.
        # lifespan calls _cleanup_state which calls print_shutdown_complete.
        # So maybe duplication here?
        # _cleanup_state calls print_shutdown_start/complete.
        # run_background_indexing is a task.


__all__ = ("run_background_indexing",)
