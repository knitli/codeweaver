# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-complex-if-expressions
"""File watcher implementation using watchfiles.

The `FileWatcher` class wraps `watchfiles.awatch` to monitor file system changes
and trigger indexing via an `Indexer` instance. It supports custom file filters,
logging configuration, and an optional callback handler for file changes.

CodeWeaver's default file filter directly integrates with `rignore` to respect
.gitignore-style rules, ensuring consistent behavior between file watching and indexing.
"""

from __future__ import annotations

import logging
import re
import time

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import rignore
import watchfiles

from fastmcp import Context

from codeweaver.cli.utils import is_tty
from codeweaver.common.utils.checks import is_ci
from codeweaver.engine.indexer.indexer import Indexer
from codeweaver.engine.watcher.logging import WatchfilesLogManager
from codeweaver.engine.watcher.types import FileChange


USE_RICH = not is_ci() and is_tty()

logger = logging.getLogger(__name__)


class FileWatcher:
    """Main file watcher class. Wraps watchfiles.awatch."""

    _indexer: Indexer
    _log_manager: WatchfilesLogManager | None
    _status_display: Any | None  # StatusDisplay instance

    def __init__(
        self,
        *paths: str | Path,
        handler: Awaitable[Callable[[set[FileChange]], Any]]
        | Callable[[set[FileChange]], Any]
        | None = None,
        file_filter: watchfiles.BaseFilter | None = None,
        walker: rignore.Walker | None = None,
        indexer: Indexer | None = None,  # NEW: Accept optional indexer
        status_display: Any | None = None,  # NEW: Accept optional status display
        capture_watchfiles_output: bool = True,
        watchfiles_log_level: int = logging.WARNING,
        watchfiles_use_rich: bool = USE_RICH,
        watchfiles_include_pattern: str | re.Pattern[str] | None = None,
        watchfiles_exclude_pattern: str | re.Pattern[str] | None = None,
        context: Context | None = None,
        route_logs_to_context: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize the FileWatcher with a path and an optional filter.

        Args:
            *paths: Paths to watch for changes
            handler: Optional callback for file changes
            file_filter: Optional filter for file changes
            walker: Optional rignore walker for initial indexing
            indexer: Optional indexer instance to use (if None, creates new one)
            status_display: Optional StatusDisplay instance for user-facing output
            capture_watchfiles_output: Enable watchfiles logging capture
            watchfiles_log_level: Minimum log level (default: WARNING)
            watchfiles_use_rich: Use Rich handler for pretty output
            watchfiles_include_pattern: Only log messages matching this regex
            watchfiles_exclude_pattern: Exclude messages matching this regex
            context: Optional FastMCP context for routing logs
            route_logs_to_context: Route logs through FastMCP context if provided
            **kwargs: Additional watchfiles configuration
        """
        # If an IgnoreFilter is provided, extract its rignore walker for initial indexing.
        self.file_filter = file_filter
        self.paths = paths
        self.handler = handler or self._default_handler
        self.context = context
        self._status_display = status_display
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

        from codeweaver.config.settings import get_settings_map
        from codeweaver.core.discovery import DiscoveredFile
        from codeweaver.core.stores import make_blake_store
        from codeweaver.engine.watcher.types import WatchfilesArgs

        watch_args = (
            WatchfilesArgs(
                paths=self.paths,
                target=Indexer.keep_alive,
                args=kwargs.pop("args", ()) if kwargs else (),
                kwargs=kwargs.pop("kwargs", {}) if kwargs else {},
                target_type="function",
                callback=self.handler,  # ty: ignore[invalid-argument-type]
                watch_filter=self.file_filter,  # ty: ignore[invalid-argument-type]
                grace_period=20.0,
                debounce=200_000,  # milliseconds - we want to avoid rapid re-indexing but not let things go stale, either.
                step=15_000,  # milliseconds -- how long to wait for more changes before yielding on changes
                debug=False,
                recursive=True,
                ignore_permission_denied=True,
            )
            | {k: v for k, v in kwargs.items() if k in WatchfilesArgs.__annotations__}
        )
        watch_args["recursive"] = True  # we always want recursive watching

        # Use provided indexer or create new one
        self._indexer = (
            indexer
            or getattr(self, "_indexer", None)
            or (
                Indexer(
                    walker=walker,
                    store=make_blake_store(value_type=DiscoveredFile),
                    project_path=get_settings_map()["project_path"],
                )
                if walker
                else Indexer.from_settings(get_settings_map())
            )
        )
        self._watch_args = watch_args
        self.watcher = None
        # Note: Call initialize() to perform initial indexing and start watching

    @classmethod
    async def create(
        cls,
        *paths: Path | str,
        handler: Callable[[set[FileChange]], Awaitable[None]]
        | Callable[[set[FileChange]], Any]
        | None = None,
        file_filter: watchfiles.BaseFilter | None = None,
        walker: rignore.Walker | None = None,
        indexer: Indexer | None = None,  # NEW: Accept optional indexer
        status_display: Any | None = None,  # NEW: Accept status_display
        capture_watchfiles_output: bool = True,
        watchfiles_log_level: int = logging.WARNING,
        watchfiles_use_rich: bool = USE_RICH,
        watchfiles_include_pattern: str | re.Pattern[str] | None = None,
        watchfiles_exclude_pattern: str | re.Pattern[str] | None = None,
        context: Context | None = None,
        route_logs_to_context: bool = True,
        **kwargs: Any,
    ) -> FileWatcher:
        """Create and initialize a FileWatcher asynchronously.

        This factory method properly awaits the initial indexing and is the
        recommended way to create a FileWatcher from async contexts.

        Args:
            Same as __init__

        Returns:
            Fully initialized FileWatcher instance
        """
        # Create instance (sync construction)
        instance = cls(
            *paths,
            handler=handler,
            file_filter=file_filter,
            walker=walker,
            indexer=indexer,  # Pass through indexer
            status_display=status_display,  # Pass through status_display
            capture_watchfiles_output=capture_watchfiles_output,
            watchfiles_log_level=watchfiles_log_level,
            watchfiles_use_rich=watchfiles_use_rich,
            watchfiles_include_pattern=watchfiles_include_pattern,
            watchfiles_exclude_pattern=watchfiles_exclude_pattern,
            context=context,
            route_logs_to_context=route_logs_to_context,
            **kwargs,
        )

        # Perform async initialization
        try:
            # Perform a one-time initial indexing pass if we have an indexer
            if initial_count := await instance._indexer.prime_index():
                logger.info("Initial indexing complete: %d files indexed", initial_count)
            instance.watcher = watchfiles.arun_process(
                *(instance._watch_args.pop("paths", ())), **instance._watch_args
            )  # ty: ignore[no-matching-overload]
        except KeyboardInterrupt:
            logger.info("FileWatcher interrupted by user.")
        except Exception:
            logger.exception("Something happened...")
            raise

        return instance

    def update_logging(
        self,
        *,
        level: int | None = None,
        include_pattern: str | re.Pattern[str] | None = None,
        exclude_pattern: str | re.Pattern[str] | None = None,
        context: Context | None = None,
    ) -> None:
        """Update watchfiles logging configuration.

        Args:
            level: New log level
            include_pattern: New include pattern (replaces existing)
            exclude_pattern: New exclude pattern (replaces existing)
            context: New FastMCP context for routing
        """
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

    def _configure_watchfiles_logging(self, log_level: int = logging.WARNING) -> None:
        """Legacy method for backward compatibility. Use WatchfilesLogManager instead."""
        logger.warning(
            "_configure_watchfiles_logging is deprecated, use capture_watchfiles_output parameter instead"
        )
        if not self._log_manager:
            self._log_manager = WatchfilesLogManager(log_level=log_level)

    async def _default_handler(self, changes: set[FileChange]) -> None:
        """Handle file changes with user-facing progress display.

        Shows brief message for small batches (<= 5 files) and progress bar for larger batches.
        """
        num_changes = len(changes)
        if num_changes == 0:
            return

        start_time = time.time()
        chunks_created = 0

        # For large batches, show progress bar
        if num_changes > 5 and self._status_display:
            with self._status_display.progress_bar(
                total=num_changes, description="↻ Reindexing changes"
            ) as update:
                for i, change in enumerate(changes, 1):
                    logger.info("File change detected.", extra={"change": change})
                    # Track chunks before indexing
                    chunks_before = self._indexer.stats.chunks_created
                    await self._indexer.index(change)
                    # Calculate chunks created by this file
                    chunks_created += self._indexer.stats.chunks_created - chunks_before
                    update(i)
        else:
            # For small batches, process without progress bar
            for change in changes:
                logger.info("File change detected.", extra={"change": change})
                chunks_before = self._indexer.stats.chunks_created
                await self._indexer.index(change)
                chunks_created += self._indexer.stats.chunks_created - chunks_before

        duration = time.time() - start_time

        # Show brief summary for all batches
        if self._status_display:
            self._status_display.print_reindex_brief(
                files=num_changes, chunks=chunks_created, duration=duration
            )

    async def run(self) -> int:
        """Run the file watcher until cancelled. Returns the reload count from arun_process."""
        return await self.watcher  # type: ignore[no-any-return]


__all__ = ("FileWatcher",)
