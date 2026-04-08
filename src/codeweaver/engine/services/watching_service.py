# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Service for file watching and triggering indexing."""

from __future__ import annotations

import logging
import re
import time

from collections.abc import Awaitable
from pathlib import Path
from typing import Any

import watchfiles

from fastmcp import Context

from codeweaver.core import is_ci, is_tty
from codeweaver.core.constants import (
    DEFAULT_WATCHER_DEBOUNCE_MILLISECONDS,
    DEFAULT_WATCHER_GRACE_PERIOD,
    DEFAULT_WATCHER_STEP_MILLISECONDS,
)
from codeweaver.core.ui_protocol import ProgressReporter
from codeweaver.engine.services.indexing_service import IndexingService
from codeweaver.engine.watcher._logging import WatchfilesLogManager
from codeweaver.engine.watcher.types import FileChange, WatchfilesArgs
from codeweaver.engine.watcher.watch_filters import IgnoreFilter


USE_RICH = not is_ci() and is_tty()

logger = logging.getLogger(__name__)


class FileWatchingService:
    """Service that monitors file system changes and triggers indexing updates."""

    @staticmethod
    def _keep_alive(*args: Any, **kwargs: Any) -> None:
        """Dummy target for watchfiles.arun_process."""

    def __init__(
        self,
        indexer: IndexingService,
        progress_reporter: ProgressReporter,
        file_filter: IgnoreFilter,
        project_path: Path,
        watchfiles_log_level: int = logging.WARNING,
        watchfiles_include_pattern: str | re.Pattern[str] | None = None,
        watchfiles_exclude_pattern: str | re.Pattern[str] | None = None,
        context: Context | None = None,
        *,
        capture_watchfiles_output: bool = True,
        watchfiles_use_rich: bool = USE_RICH,
        route_logs_to_context: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize the FileWatchingService.

        Args:
            indexer: The indexing service to trigger on changes.
            progress_reporter: Reporter for UI progress updates.
            file_filter: Filter to determine which files to watch.
            project_path: Root path of the project to watch.
            capture_watchfiles_output: Enable watchfiles logging capture.
            watchfiles_log_level: Minimum log level (default: WARNING).
            watchfiles_use_rich: Use Rich handler for pretty output.
            watchfiles_include_pattern: Only log messages matching this regex.
            watchfiles_exclude_pattern: Exclude messages matching this regex.
            context: Optional FastMCP context for routing logs.
            route_logs_to_context: Route logs through FastMCP context if provided.
            **kwargs: Additional watchfiles configuration.
        """
        self._indexer = indexer
        self._progress_reporter = progress_reporter
        self.file_filter = file_filter
        self.project_path = project_path
        self.context = context

        # Initialize log manager if capture enabled
        self._log_manager = None
        if capture_watchfiles_output:
            self._log_manager = WatchfilesLogManager(
                log_level=watchfiles_log_level,
                use_rich=watchfiles_use_rich,
                include_pattern=watchfiles_include_pattern,
                exclude_pattern=watchfiles_exclude_pattern,
                context=context,
                route_to_context=route_logs_to_context,
            )

        # Configure watch arguments
        self._watch_args = WatchfilesArgs(
            paths=(self.project_path,),
            target=self._keep_alive,
            args=kwargs.pop("args", ()) if kwargs else (),
            kwargs=kwargs.pop("kwargs", {}) if kwargs else {},
            target_type="function",
            callback=self._handle_changes,  # ty: ignore[invalid-argument-type]
            watch_filter=self.file_filter,  # ty: ignore[invalid-argument-type]
            grace_period=DEFAULT_WATCHER_GRACE_PERIOD,
            debounce=DEFAULT_WATCHER_DEBOUNCE_MILLISECONDS,
            step=DEFAULT_WATCHER_STEP_MILLISECONDS,
            debug=False,
            recursive=True,
            ignore_permission_denied=True,
        ) | {k: v for k, v in kwargs.items() if k in WatchfilesArgs.__annotations__}
        self._watch_args["recursive"] = True
        self.watcher: Awaitable[int] | None = None

    async def _handle_changes(self, changes: set[FileChange]) -> None:
        """Handle file changes with user-facing progress display."""
        num_changes = len(changes)
        if num_changes == 0:
            return

        start_time = time.time()

        if self._progress_reporter:
            self._progress_reporter.start_operation("reindexing", description="Reindexing changes")

        # Process changes via indexer
        # Using process_changes from IndexingService
        processed_count = await self._indexer.process_changes(list(changes))

        if self._progress_reporter and num_changes > 5:
            # Note: process_changes is currently atomic, so we can't report progress *during* it easily
            # unless we pass a callback to it. For now, report completion.
            self._progress_reporter.report_progress("reindexing", num_changes, num_changes)

        duration = time.time() - start_time

        if self._progress_reporter:
            self._progress_reporter.complete_operation(
                "reindexing", message=f"Processed {processed_count} changes ({duration:.1f}s)"
            )

    async def run(self) -> int:
        """Run the file watcher.

        This performs an initial index check (via IndexingService) and then starts
        watching for changes.
        """
        # Perform a one-time initial indexing pass
        # Note: IndexingService.index_project checks manifest and only indexes new stuff
        if initial_count := await self._indexer.index_project():
            logger.info("Initial indexing complete: %d files indexed", initial_count)

        # Start watching
        self.watcher = watchfiles.arun_process(
            *(self._watch_args.pop("paths", ())),  # ty:ignore[not-iterable]
            **self._watch_args,  # ty:ignore[invalid-argument-type]
        )

        try:
            return await self.watcher
        except KeyboardInterrupt:
            logger.info("FileWatchingService interrupted by user.")
            return 0
        except Exception:
            logger.warning("Error in file watcher", exc_info=True)
            raise

    def update_logging(
        self,
        *,
        level: int | None = None,
        include_pattern: str | re.Pattern[str] | None = None,
        exclude_pattern: str | re.Pattern[str] | None = None,
        context: Context | None = None,
    ) -> None:
        """Update watchfiles logging configuration."""
        if not self._log_manager:
            logger.warning("Watchfiles logging not enabled, call has no effect")
            return

        if level is not None:
            self._log_manager.set_level(level)

        if include_pattern or exclude_pattern:
            self._log_manager.add_filter(
                include_pattern=include_pattern, exclude_pattern=exclude_pattern
            )

        if context is not None:
            self._log_manager.update_context(context)
            self.context = context


__all__ = ("USE_RICH", "FileWatchingService")
