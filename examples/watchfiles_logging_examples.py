#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Examples of capturing and controlling watchfiles logging output.

This module demonstrates various ways to capture, filter, and route
logging output from watchfiles using CodeWeaver's integrated logging
infrastructure.
"""

import asyncio
import logging
import re

from fastmcp import Context

from codeweaver.engine.indexer import FileWatcher, WatchfilesLogManager


# ==============================================================================
# Example 1: Basic Logging Capture with Default Settings
# ==============================================================================


def example_basic_capture() -> FileWatcher:
    """Enable watchfiles logging with default WARNING level."""
    return FileWatcher("/path/to/watch", capture_watchfiles_output=True)
    # watchfiles will now log warnings and errors to console with Rich formatting


# ==============================================================================
# Example 2: Verbose Debug Logging
# ==============================================================================


def example_debug_logging() -> FileWatcher:
    """Capture all watchfiles debug output for troubleshooting."""
    return FileWatcher(
        "/path/to/watch",
        capture_watchfiles_output=True,
        watchfiles_log_level=logging.DEBUG,  # Show everything
    )
    # Now you'll see detailed internal watchfiles operations


# ==============================================================================
# Example 3: Suppress Most Output (Errors Only)
# ==============================================================================


def example_quiet_mode() -> FileWatcher:
    """Only show critical errors, suppress all other watchfiles output."""
    return FileWatcher(
        "/path/to/watch",
        capture_watchfiles_output=True,
        watchfiles_log_level=logging.ERROR,  # Only errors
    )


# ==============================================================================
# Example 4: Filter Logging with Regex Patterns
# ==============================================================================


def example_pattern_filtering() -> FileWatcher:
    """Only show logs matching specific patterns."""
    return FileWatcher(
        "/path/to/watch",
        capture_watchfiles_output=True,
        watchfiles_log_level=logging.INFO,
        # Only show logs containing "file" or "change"
        watchfiles_include_pattern=r"file|change",
        # Exclude logs containing "debug" or "trace"
        watchfiles_exclude_pattern=r"debug|trace",
    )


# ==============================================================================
# Example 5: Route Logs to FastMCP Context
# ==============================================================================


async def example_fastmcp_routing(context: Context) -> None:
    """Route watchfiles logs to FastMCP client for structured logging."""
    watcher = FileWatcher(
        "/path/to/watch",
        capture_watchfiles_output=True,
        watchfiles_log_level=logging.INFO,
        context=context,  # Provide FastMCP context
        route_logs_to_context=True,  # Enable routing
    )

    # Logs will now appear in the FastMCP client with structured data
    await watcher.run()


# ==============================================================================
# Example 6: Dynamic Log Level Changes
# ==============================================================================


async def example_dynamic_updates() -> None:
    """Change logging configuration at runtime."""
    watcher = FileWatcher(
        "/path/to/watch", capture_watchfiles_output=True, watchfiles_log_level=logging.WARNING
    )

    # Start watching...
    # Later, increase verbosity for debugging
    watcher.update_logging(level=logging.DEBUG)

    # Filter to only show file additions
    watcher.update_logging(include_pattern=r"added|new file")

    # Update FastMCP context
    # watcher.update_logging(context=new_context)

    await watcher.run()


# ==============================================================================
# Example 7: Standalone WatchfilesLogManager
# ==============================================================================


def example_standalone_log_manager() -> WatchfilesLogManager:
    """Use WatchfilesLogManager independently for any watchfiles usage."""
    # Create log manager
    log_manager = WatchfilesLogManager(
        log_level=logging.INFO,
        use_rich=True,
        include_pattern=r"file",
        exclude_pattern=r"permission",
    )

    # Now any watchfiles operations will use this logging config
    # The manager configures the 'watchfiles' logger globally

    # Later, update configuration
    log_manager.set_level(logging.DEBUG)
    log_manager.add_filter(include_pattern=r"change|modify", exclude_pattern=r"error")

    return log_manager


# ==============================================================================
# Example 8: Complex Filtering with Compiled Patterns
# ==============================================================================


def example_complex_filtering() -> FileWatcher:
    """Use compiled regex patterns for advanced filtering."""
    # Pre-compile complex patterns
    include_pattern = re.compile(r"(?:file|directory).*(?:added|modified|deleted)", re.IGNORECASE)

    exclude_pattern = re.compile(r"\.git/|node_modules/|__pycache__/", re.IGNORECASE)

    return FileWatcher(
        "/path/to/watch",
        capture_watchfiles_output=True,
        watchfiles_log_level=logging.INFO,
        watchfiles_include_pattern=include_pattern,
        watchfiles_exclude_pattern=exclude_pattern,
    )


# ==============================================================================
# Example 9: Rich vs Plain Text Output
# ==============================================================================


def example_output_formats() -> tuple[FileWatcher, FileWatcher]:
    """Control output formatting."""
    # Rich formatted output (default)
    watcher_rich = FileWatcher(
        "/path/to/watch",
        capture_watchfiles_output=True,
        watchfiles_use_rich=True,  # Pretty colors and formatting
    )

    # Plain text output (for logging to files or scripts)
    watcher_plain = FileWatcher(
        "/path/to/watch",
        capture_watchfiles_output=True,
        watchfiles_use_rich=False,  # Standard text format
    )

    return watcher_rich, watcher_plain


# ==============================================================================
# Example 10: Integration with FastMCP Tool
# ==============================================================================


async def example_mcp_tool_integration() -> None:
    """Complete example of using watchfiles logging in an MCP tool."""
    from fastmcp import FastMCP

    mcp = FastMCP("file-watcher-tool")

    @mcp.tool()
    async def watch_directory(path: str, log_level: str = "INFO") -> str:
        """Watch a directory for changes with configurable logging.

        Args:
            path: Directory to watch
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)

        Returns:
            Status message
        """
        # Get FastMCP context for routing logs
        context = mcp.get_context()

        # Convert string level to int
        level = getattr(logging, log_level.upper())

        # Create watcher with integrated logging
        watcher = FileWatcher(
            path,
            capture_watchfiles_output=True,
            watchfiles_log_level=level,
            context=context,
            route_logs_to_context=True,
            # Filter out noisy logs
            watchfiles_exclude_pattern=r"\.git/|__pycache__/",
        )

        # Start watching (this would run until interrupted)
        try:
            reload_count = await watcher.run()
        except KeyboardInterrupt:
            return "Watching interrupted by user"
        else:
            return f"Watcher completed with {reload_count} reloads"

    # Run the MCP server
    await mcp.run()


# ==============================================================================
# Example 11: Conditional Logging Based on Environment
# ==============================================================================


def example_environment_based() -> FileWatcher:
    """Configure logging based on environment variables or conditions."""
    import os

    # Determine logging level from environment
    debug_mode = os.getenv("DEBUG", "").lower() == "true"
    log_level = logging.DEBUG if debug_mode else logging.WARNING

    # Use Rich only in TTY environments
    import sys

    use_rich = sys.stdout.isatty()

    return FileWatcher(
        "/path/to/watch",
        capture_watchfiles_output=True,
        watchfiles_log_level=log_level,
        watchfiles_use_rich=use_rich,
    )



# ==============================================================================
# Example 12: Multiple Watchers with Different Logging
# ==============================================================================


async def example_multiple_watchers() -> None:
    """Run multiple watchers with different logging configurations."""
    # Source code watcher - verbose logging
    watcher_src = FileWatcher(
        "/path/to/src",
        capture_watchfiles_output=True,
        watchfiles_log_level=logging.DEBUG,
        watchfiles_include_pattern=r"\.(py|js|ts)$",
    )

    # Documentation watcher - minimal logging
    watcher_docs = FileWatcher(
        "/path/to/docs",
        capture_watchfiles_output=True,
        watchfiles_log_level=logging.WARNING,
        watchfiles_include_pattern=r"\.(md|rst)$",
    )

    # Config watcher - moderate logging
    watcher_config = FileWatcher(
        "/path/to/config",
        capture_watchfiles_output=True,
        watchfiles_log_level=logging.INFO,
        watchfiles_include_pattern=r"\.(toml|yaml|json)$",
    )

    # Run all watchers concurrently
    await asyncio.gather(watcher_src.run(), watcher_docs.run(), watcher_config.run())


# ==============================================================================
# Example 13: Custom Handler for Special Processing
# ==============================================================================


def example_custom_processing() -> tuple[FileWatcher, logging.Handler]:
    """Process watchfiles logs with custom logic."""
    import queue

    class CustomHandler(logging.Handler):
        """Custom handler that processes logs."""

        def __init__(self):
            super().__init__()
            self.log_queue = queue.Queue()

        def emit(self, record: logging.LogRecord):
            """Process each log record."""
            # Store in queue for async processing
            self.log_queue.put(record)

            # Could also:
            # - Send to external monitoring system
            # - Write to database
            # - Trigger alerts
            # - Update UI/dashboard

    # Create watcher with basic capture
    watcher = FileWatcher(
        "/path/to/watch", capture_watchfiles_output=True, watchfiles_log_level=logging.INFO
    )

    # Add custom handler to watchfiles logger
    custom_handler = CustomHandler()
    watchfiles_logger = logging.getLogger("watchfiles")
    watchfiles_logger.addHandler(custom_handler)

    return watcher, custom_handler


# ==============================================================================
# Example 14: Temporary Verbose Logging
# ==============================================================================


async def example_temporary_verbose() -> None:
    """Temporarily increase logging verbosity for debugging."""
    watcher = FileWatcher(
        "/path/to/watch",
        capture_watchfiles_output=True,
        watchfiles_log_level=logging.WARNING,  # Start quiet
    )

    # Start watching
    watch_task = asyncio.create_task(watcher.run())

    # After some time, enable verbose logging
    await asyncio.sleep(60)
    watcher.update_logging(level=logging.DEBUG)
    print("Verbose logging enabled")

    # Debug for a bit
    await asyncio.sleep(60)

    # Return to quiet mode
    watcher.update_logging(level=logging.WARNING)
    print("Verbose logging disabled")

    await watch_task


# ==============================================================================
# Main Example Runner
# ==============================================================================


async def main() -> None:
    """Run example demonstrations."""
    print("CodeWeaver Watchfiles Logging Examples\n" + "=" * 50)

    # Example 1: Basic capture
    print("\n1. Basic Logging Capture")
    print("-" * 50)
    watcher = example_basic_capture()
    print(f"Created watcher with default logging: {watcher}")

    # Example 2: Debug logging
    print("\n2. Verbose Debug Logging")
    print("-" * 50)
    watcher_debug = example_debug_logging()
    print(f"Created watcher with debug logging: {watcher_debug}")

    # Example 3: Quiet mode
    print("\n3. Quiet Mode (Errors Only)")
    print("-" * 50)
    watcher_quiet = example_quiet_mode()
    print(f"Created quiet watcher: {watcher_quiet}")

    # Example 4: Pattern filtering
    print("\n4. Pattern-Based Filtering")
    print("-" * 50)
    watcher_filtered = example_pattern_filtering()
    print(f"Created filtered watcher: {watcher_filtered}")

    # Example 7: Standalone manager
    print("\n7. Standalone Log Manager")
    print("-" * 50)
    log_manager = example_standalone_log_manager()
    print(f"Created log manager: {log_manager}")

    # Example 8: Complex filtering
    print("\n8. Complex Regex Filtering")
    print("-" * 50)
    watcher_complex = example_complex_filtering()
    print(f"Created watcher with complex filters: {watcher_complex}")

    # Example 9: Output formats
    print("\n9. Rich vs Plain Text")
    print("-" * 50)
    watcher_rich, watcher_plain = example_output_formats()
    print(f"Rich: {watcher_rich}")
    print(f"Plain: {watcher_plain}")

    # Example 11: Environment-based
    print("\n11. Environment-Based Configuration")
    print("-" * 50)
    watcher_env = example_environment_based()
    print(f"Created environment-based watcher: {watcher_env}")

    print("\n" + "=" * 50)
    print("Examples completed. See source code for more details.")


if __name__ == "__main__":
    asyncio.run(main())
