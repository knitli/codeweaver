# sourcery skip: avoid-global-variables, snake-case-variable-declarations
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Main FastMCP server entrypoint for CodeWeaver with linear bootstrap."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from fastmcp import FastMCP
from pydantic import FilePath

from codeweaver.common.utils import lazy_import
from codeweaver.config.types import CodeWeaverSettingsDict
from codeweaver.exceptions import InitializationError
from codeweaver.providers.provider import Provider as Provider  # needed for pydantic models


class UvicornAccessLogFilter(logging.Filter):
    """Filter that blocks uvicorn access log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False for uvicorn access logs to block them."""
        # Block if it looks like an HTTP access log
        return not (
            record.name in ("uvicorn.access", "uvicorn", "uvicorn.error")
            and (
                "HTTP" in record.getMessage()
                or "GET" in record.getMessage()
                or "POST" in record.getMessage()
            )
        )


if TYPE_CHECKING:
    from codeweaver.mcp.state import CwMcpHttpState

logger = logging.getLogger(__name__)


def _setup_logging_filters(*, verbose: bool, debug: bool) -> None:
    """Suppress uvicorn loggers if not in verbose/debug mode."""
    if not (verbose or debug):
        access_filter = UvicornAccessLogFilter()
        logging.getLogger().addFilter(access_filter)

        for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
            logger_obj = logging.getLogger(logger_name)
            logger_obj.setLevel(logging.CRITICAL)
            logger_obj.handlers.clear()
            logger_obj.propagate = False
            logger_obj.addFilter(access_filter)


def _setup_signal_handler() -> tuple[int, Any]:
    """Setup force shutdown handler and return shutdown counter and original handler."""
    shutdown_count = 0
    original_sigint_handler = None

    def force_shutdown_handler(signum: int, frame: Any) -> None:
        """Handle multiple SIGINT signals for force shutdown."""
        nonlocal shutdown_count
        shutdown_count += 1

        if shutdown_count == 1:
            # Silent first interrupt - let lifespan cleanup handle the message
            raise KeyboardInterrupt
        logger.warning("Force shutdown requested, exiting immediately...")
        sys.exit(1)

    # Install force shutdown handler
    with contextlib.suppress(ValueError, OSError):
        original_sigint_handler = signal.signal(signal.SIGINT, force_shutdown_handler)

    return shutdown_count, original_sigint_handler


async def _run_http_server(
    *,
    config_file: FilePath | None = None,
    project_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 9328,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Run HTTP MCP server with integrated background services and management server.

    This mode runs three components concurrently:
    1. Background services (indexing, file watching, health monitoring)
    2. MCP HTTP server (port 9328 by default)
    3. Management server (port 9329 by default)

    Args:
        config_file: Optional configuration file path
        project_path: Optional project directory path
        host: Host for MCP server
        port: Port for MCP server
        verbose: Enable verbose logging
        debug: Enable debug logging
    """
    from codeweaver.cli.ui import StatusDisplay
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.common.utils import get_project_path
    from codeweaver.config.settings import get_settings
    from codeweaver.core.types.sentinel import Unset
    from codeweaver.mcp.server import create_http_server
    from codeweaver.server.lifespan import http_lifespan
    from codeweaver.server.management import ManagementServer

    # Load settings
    settings = get_settings()
    if config_file:
        settings.config_file = config_file  # type: ignore
    if project_path:
        settings.project_path = project_path
    elif isinstance(settings.project_path, Unset):
        settings.project_path = get_project_path()

    # Setup logging
    if verbose or debug:
        from codeweaver.config.settings import get_settings_map
        from codeweaver.server.logging import setup_logger

        setup_logger(get_settings_map())

    # Create MCP HTTP server state
    mcp_state: CwMcpHttpState = await create_http_server(
        host=host, port=port, verbose=verbose, debug=debug
    )

    # Create status display
    status_display = StatusDisplay()

    # Get statistics
    statistics = get_session_statistics()

    # Setup management server
    mgmt_host = getattr(settings, "management_host", "127.0.0.1")
    mgmt_port = getattr(settings, "management_port", 9329)

    # Setup signal handler for force shutdowns
    shutdown_count, original_sigint_handler = _setup_signal_handler()

    # Initialize provider registry
    registry = lazy_import("codeweaver.common.registry.provider", "get_provider_registry")  # type: ignore
    _ = registry._resolve()()  # type: ignore

    # Suppress uvicorn loggers if not in verbose/debug mode
    if not (verbose or debug):
        _setup_logging_filters(verbose=verbose, debug=debug)

    # Run with http_lifespan
    try:
        async with http_lifespan(
            mcp_state=mcp_state,
            settings=settings,
            statistics=statistics,
            status_display=status_display,
            verbose=verbose,
            debug=debug,
        ) as background_state:
            # Start management server
            management_server = ManagementServer(background_state)
            await management_server.start(host=mgmt_host, port=mgmt_port)

            try:
                # Run MCP server
                with contextlib.suppress(KeyboardInterrupt):
                    await mcp_state.app.run_http_async(
                        **(mcp_state.run_args | {"show_banner": False, "log_level": "error"})  # ty: ignore[invalid-argument-type]
                    )
            finally:
                # Stop management server
                await management_server.stop()
    except KeyboardInterrupt:
        if shutdown_count == 1:
            logger.info("Shutdown requested, cleaning up...")
        else:
            logger.info("Shutdown requested...")
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.sleep(0.5)
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGINT, original_sigint_handler)
    finally:
        # Restore original signal handler
        if original_sigint_handler:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGINT, original_sigint_handler)


async def _run_stdio_server(
    *,
    config_file: FilePath | None = None,
    project_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 9328,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Run stdio MCP server (proxies to HTTP backend).

    This creates a stdio proxy that forwards MCP requests to an HTTP backend.
    The HTTP backend should already be running via `codeweaver server`.

    Args:
        config_file: Optional configuration file path
        project_path: Optional project directory path
        host: Host of HTTP backend to proxy to
        port: Port of HTTP backend to proxy to
        verbose: Enable verbose logging
        debug: Enable debug logging
    """
    # Create stdio proxy server
    stdio_server = await get_stdio_server(
        config_file=config_file, project_path=project_path, host=host, port=port
    )

    if verbose or debug:
        logger.info("Starting stdio proxy to HTTP server at %s:%d", host, port)

    # Run stdio proxy (blocks until client disconnects)
    try:
        stdio_server.run()
    except KeyboardInterrupt:
        if verbose or debug:
            logger.info("stdio server shutting down...")


async def get_stdio_server(
    *,
    config_file: FilePath | None = None,
    project_path: Path | None = None,
    host: str | None = None,
    port: int | None = None,
) -> FastMCP:  # type: ignore
    """Get a FastMCP stdio server setup for CodeWeaver.

    Args:
        config_file: Optional path to configuration file.
        project_path: Optional path to project directory.
        host: Optional host for the server. This is the host/port for the *codeweaver http mcp server* that the stdio client will be proxied to. **You only need this if you're not connecting to a default setting or not connecting to what is in your config file**.
        port: Optional port for the server. This is the host/port for the *codeweaver http mcp server* that the stdio client will be proxied to. **You only need this if you're not connecting to a default setting or not connecting to what is in your config file**.

    Returns:
        Configured FastMCP stdio server instance.

    """
    from codeweaver.mcp.server import create_stdio_server

    if config_file or project_path:
        # We normally want to use the global settings instance, but here because a proxied stdio client could be used in isolation and outside a typical configuration, we create a unique settings instance.
        from codeweaver.config.settings import CodeWeaverSettings, get_settings

        global_settings = get_settings()
        if config_file and isinstance(config_file, Path) and config_file.exists():
            settings = (
                CodeWeaverSettings(config_file=config_file, project_path=project_path)
                if project_path
                else CodeWeaverSettings(config_file=config_file)
            )
        elif project_path and project_path.exists():
            settings = global_settings.model_copy(update={"project_path": project_path})
        else:
            settings = None
        if settings:
            settings = CodeWeaverSettingsDict(**settings.model_dump())
    else:
        settings = None
    server = await create_stdio_server(
        settings=cast(CodeWeaverSettingsDict | None, settings), host=host, port=port
    )
    await server.run_stdio_async(show_banner=False, log_level="warning")
    return server


async def run(
    *,
    config_file: FilePath | None = None,
    project_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 9328,
    transport: Literal["streamable-http", "stdio"] = "streamable-http",
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Run the CodeWeaver server with appropriate transport.

    This is the main entry point for starting CodeWeaver's MCP server.

    Transport modes:
    - streamable-http: Full server with background services, MCP HTTP server, and management server
    - stdio: stdio proxy that forwards to an existing HTTP backend

    Args:
        config_file: Optional configuration file path
        project_path: Optional project directory path
        host: Host to bind server to
        port: Port to bind server to
        transport: Transport protocol (streamable-http or stdio)
        verbose: Enable verbose logging
        debug: Enable debug logging
    """
    if transport == "stdio":
        await _run_stdio_server(
            config_file=config_file,
            project_path=project_path,
            host=host,
            port=port,
            verbose=verbose,
            debug=debug,
        )
    else:  # streamable-http
        await _run_http_server(
            config_file=config_file,
            project_path=project_path,
            host=host,
            port=port,
            verbose=verbose,
            debug=debug,
        )


if __name__ == "__main__":
    from codeweaver.common.utils.procs import asyncio_or_uvloop

    asyncio = asyncio_or_uvloop()
    try:
        asyncio.run(run())
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to start CodeWeaver server: ")
        raise InitializationError("Failed to start CodeWeaver server.") from e

__all__ = ("get_stdio_server", "run")
