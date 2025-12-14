# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Logging utilities for the CodeWeaver engine.
"""

from __future__ import annotations

import asyncio
import logging
import re

from typing import Any

from fastmcp import Context

from codeweaver.common._logging import log_to_client_or_fallback, setup_logger
from codeweaver.common.utils.normalize import validate_regex_pattern
from codeweaver.config._logging import SerializableLoggingFilter


def normalize_and_validate_patterns(
    include_pattern: str | re.Pattern[str] | None, exclude_pattern: str | re.Pattern[str] | None
) -> tuple[re.Pattern[str] | None, re.Pattern[str] | None]:
    """Normalize and validate include/exclude regex patterns.

    Args:
        include_pattern: Include regex pattern as string or compiled regex
        exclude_pattern: Exclude regex pattern as string or compiled regex
    Returns:
        Tuple of compiled include and exclude regex patterns (or None)
    """
    include_pattern = validate_regex_pattern(include_pattern) if include_pattern else None
    exclude_pattern = validate_regex_pattern(exclude_pattern) if exclude_pattern else None
    return include_pattern, exclude_pattern


class WatchfilesLogManager:
    """Manage watchfiles logging with filtering, routing, and Rich handler support.

    Integrates watchfiles logging output with CodeWeaver's logging infrastructure:
    - SerializableLoggingFilter for pattern-based filtering
    - Rich handler support via setup_logger
    - FastMCP context routing via log_to_client_or_fallback
    - Configurable log levels and output destinations
    """

    def __init__(
        self,
        *,
        log_level: int = logging.WARNING,
        use_rich: bool = True,
        include_pattern: str | re.Pattern[str] | None = None,
        exclude_pattern: str | re.Pattern[str] | None = None,
        context: Context | None = None,
        route_to_context: bool = True,
    ) -> None:
        """Initialize the watchfiles log manager.

        Args:
            log_level: Minimum log level to capture (default: WARNING)
            use_rich: Use Rich handler for pretty console output
            include_pattern: Regex pattern - only log messages matching this
            exclude_pattern: Regex pattern - exclude messages matching this
            context: Optional FastMCP context for routing logs to client
            route_to_context: If True and context provided, route logs through FastMCP
        """
        self.log_level = log_level
        self.use_rich = use_rich
        self.context = context
        self.route_to_context = route_to_context
        self.watchfiles_logger = logging.getLogger("watchfiles")
        # Create and configure filter
        self.log_filter: SerializableLoggingFilter | None = None
        processed_include, processed_exclude = normalize_and_validate_patterns(
            include_pattern, exclude_pattern
        )
        if processed_include or processed_exclude:
            self.include_pattern = processed_include
            self.exclude_pattern = processed_exclude
            self.log_filter = SerializableLoggingFilter(
                include_pattern=processed_include, exclude_pattern=processed_exclude
            )

        # Configure the logger
        self._configure_logger()

    def _configure_logger(self) -> None:
        """Configure the watchfiles logger with our settings."""
        # Clear existing handlers to avoid duplicates
        self.watchfiles_logger.handlers.clear()

        if self.route_to_context and self.context:
            # Use a custom handler that routes to FastMCP context
            handler = self._create_context_handler()
        elif self.use_rich:
            # Use Rich handler via setup_logger
            logger = setup_logger(
                name="watchfiles",
                level=self.log_level,
                rich=True,
                rich_options={
                    "show_time": True,
                    "show_level": True,
                    "show_path": False,
                    "rich_tracebacks": False,
                },
            )
            # Logger is already configured, just return
            self.watchfiles_logger = logger
            if self.log_filter:
                self.watchfiles_logger.addFilter(self.log_filter)
            return
        else:
            # Use standard StreamHandler
            handler = logging.StreamHandler()
            handler.setLevel(self.log_level)
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)

        # Add filter if configured
        if self.log_filter:
            handler.addFilter(self.log_filter)

        self.watchfiles_logger.addHandler(handler)
        self.watchfiles_logger.setLevel(self.log_level)
        self.watchfiles_logger.propagate = False

    def _create_context_handler(self) -> logging.Handler:
        """Create a custom handler that routes logs to FastMCP context."""

        class ContextHandler(logging.Handler):
            """Handler that routes logs through FastMCP context."""

            def __init__(self, context: Context | None, manager: WatchfilesLogManager):
                super().__init__()
                self.context = context
                self.manager = manager
                self._background_tasks: set[asyncio.Task[Any]] = set()

            def emit(self, record: logging.LogRecord) -> None:
                """Emit a log record to FastMCP context."""
                try:
                    # Map logging level to FastMCP context level
                    if record.levelno >= logging.ERROR:
                        level = "error"
                    elif record.levelno >= logging.WARNING:
                        level = "warning"
                    elif record.levelno >= logging.INFO:
                        level = "info"
                    else:
                        level = "debug"

                    # Format the message
                    msg = self.format(record)

                    # Build log data
                    log_data = {
                        "msg": msg,
                        "extra": {
                            "logger": record.name,
                            "level": record.levelname,
                            "module": record.module,
                            "function": record.funcName,
                            "line": record.lineno,
                        },
                    }

                    # Route to context asynchronously
                    # We need to schedule this in the event loop
                    try:
                        loop = asyncio.get_running_loop()
                        task = loop.create_task(
                            log_to_client_or_fallback(self.context, level, log_data)
                        )
                        self._background_tasks.add(task)
                        task.add_done_callback(self._background_tasks.discard)
                    except RuntimeError:
                        # No event loop, fallback to sync logging
                        logger = logging.getLogger("codeweaver.watchfiles")
                        logger.log(record.levelno, msg, extra=log_data.get("extra"))  # ty: ignore[invalid-argument-type]

                except Exception:
                    self.handleError(record)

        handler = ContextHandler(self.context, self)
        handler.setLevel(self.log_level)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        return handler

    def update_context(self, context: Context | None) -> None:
        """Update the FastMCP context for log routing.

        Args:
            context: New FastMCP context or None to disable context routing
        """
        self.context = context
        if self.route_to_context and context:
            self._configure_logger()

    def set_level(self, level: int) -> None:
        """Change the log level.

        Args:
            level: New logging level (e.g., logging.DEBUG, logging.INFO)
        """
        self.log_level = level
        self.watchfiles_logger.setLevel(level)
        for handler in self.watchfiles_logger.handlers:
            handler.setLevel(level)

    def add_filter(
        self,
        *,
        include_pattern: str | re.Pattern[str] | None = None,
        exclude_pattern: str | re.Pattern[str] | None = None,
    ) -> None:
        """Add or update filtering patterns.

        Args:
            include_pattern: Only log messages matching this pattern
            exclude_pattern: Exclude messages matching this pattern
        """
        # Remove existing filter if present
        if self.log_filter:
            self.watchfiles_logger.removeFilter(self.log_filter)

        # Create new filter
        processed_include, processed_exclude = normalize_and_validate_patterns(
            include_pattern, exclude_pattern
        )
        self.log_filter = SerializableLoggingFilter(
            include_pattern=processed_include, exclude_pattern=processed_exclude
        )

        # Add to logger and all handlers
        self.watchfiles_logger.addFilter(self.log_filter)
        for handler in self.watchfiles_logger.handlers:
            handler.addFilter(self.log_filter)

    def clear_filters(self) -> None:
        """Remove all filters from the logger."""
        if self.log_filter:
            self.watchfiles_logger.removeFilter(self.log_filter)
            for handler in self.watchfiles_logger.handlers:
                handler.removeFilter(self.log_filter)
            self.log_filter = None


__all__ = ("WatchfilesLogManager",)
