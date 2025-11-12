"""File watcher implementation using watchfiles.

The `FileWatcher` class wraps `watchfiles.awatch` to monitor file system changes
and trigger indexing via an `Indexer` instance. It supports custom file filters,
logging configuration, and an optional callback handler for file changes.

CodeWeaver's default file filter directly integrates with `rignore` to respect
.gitignore-style rules, ensuring consistent behavior between file watching and indexing.
"""

from __future__ import annotations

import asyncio
import logging
import re

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import rignore
import watchfiles

from fastmcp import Context

from codeweaver.engine.indexer.indexer import Indexer
from codeweaver.engine.watcher.logging import WatchfilesLogManager
from codeweaver.engine.watcher.types import FileChange


logger = logging.getLogger(__name__)


class FileWatcher:
    """Main file watcher class. Wraps watchfiles.awatch."""

    _indexer: Indexer
    _log_manager: WatchfilesLogManager | None

    def __init__(
        self,
        *paths: str | Path,
        handler: Awaitable[Callable[[set[FileChange]], Any]]
        | Callable[[set[FileChange]], Any]
        | None = None,
        file_filter: watchfiles.BaseFilter | None = None,
        walker: rignore.Walker | None = None,
        capture_watchfiles_output: bool = False,
        watchfiles_log_level: int = logging.WARNING,
        watchfiles_use_rich: bool = True,
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

        from codeweaver.common.utils.checks import is_debug
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
                debug=is_debug(),
                recursive=True,
                ignore_permission_denied=True,
            )
            | {k: v for k, v in kwargs.items() if k in WatchfilesArgs.__annotations__}
        )
        watch_args["recursive"] = True  # we always want recursive watching
        try:
            # Perform a one-time initial indexing pass if we have a walker
            if initial_count := asyncio.run(self._indexer.prime_index()):
                logger.info("Initial indexing complete: %d files indexed", initial_count)
            self.watcher = watchfiles.arun_process(*(watch_args.pop("paths", ())), **watch_args)  # ty: ignore[no-matching-overload]
        except KeyboardInterrupt:
            logger.info("FileWatcher interrupted by user.")
        except Exception:
            logger.exception("Something happened...")
            raise

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
        """Default may be misleading -- 'placeholder' handler."""
        for change in changes:
            logger.info("File change detected.", extra={"change": change})
            await self._indexer.index(change)

    async def run(self) -> int:
        """Run the file watcher until cancelled. Returns the reload count from arun_process."""
        return await self.watcher  # type: ignore[no-any-return]


__all__ = ("FileWatcher",)
