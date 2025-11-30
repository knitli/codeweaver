# sourcery skip: avoid-global-variables, snake-case-variable-declarations
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Main FastMCP server entrypoint for CodeWeaver with linear bootstrap."""

from __future__ import annotations

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
    from codeweaver.mcp.server import StdioClientLifespan
    from codeweaver.server.lifespan import CodeWeaverState

logger = logging.getLogger(__name__)


async def start_server(
    server: FastMCP[CodeWeaverState], *, verbose: bool, debug: bool, **kwargs: Any
) -> None:
    """Start CodeWeaver's FastMCP server with force shutdown support.

    We start a minimal server here, and once it's up, we register components and merge in settings.
    Supports force shutdown on second Ctrl+C.
    """
    # Track Ctrl+C count for force shutdown
    shutdown_count = 0
    original_sigint_handler = None

    def force_shutdown_handler(signum: int, frame: Any) -> None:
        """Handle multiple SIGINT signals for force shutdown."""
        nonlocal shutdown_count
        shutdown_count += 1

        if shutdown_count == 1:
            # Silent first interrupt - let lifespan cleanup handle the message
            # Raise KeyboardInterrupt to trigger graceful shutdown
            raise KeyboardInterrupt
        logger.warning("Force shutdown requested, exiting immediately...")
        sys.exit(1)

    # Install force shutdown handler
    with contextlib.suppress(ValueError, OSError):
        original_sigint_handler = signal.signal(signal.SIGINT, force_shutdown_handler)

    registry = lazy_import("codeweaver.common.registry.provider", "get_provider_registry")  # type: ignore
    _ = registry()  # type: ignore

    # Aggressively suppress uvicorn loggers BEFORE starting server
    if not (verbose or debug):
        # Add filter to root logger to block uvicorn access logs
        access_filter = UvicornAccessLogFilter()
        logging.getLogger().addFilter(access_filter)

        for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
            logger_obj = logging.getLogger(logger_name)
            logger_obj.setLevel(logging.CRITICAL)
            logger_obj.handlers.clear()
            logger_obj.propagate = False
            logger_obj.addFilter(access_filter)

    # Wrap in try-except to catch KeyboardInterrupt cleanly without traceback
    with contextlib.suppress(KeyboardInterrupt):
        await app.run_http_async(**resolved_kwargs)  # type: ignore
    # Restore original signal handler
    if original_sigint_handler:
        with contextlib.suppress(ValueError, OSError):
            signal.signal(signal.SIGINT, original_sigint_handler)


async def get_stdio_server(
    *,
    config_file: FilePath | None = None,
    project_path: Path | None = None,
    host: str | None = None,
    port: int | None = None,
) -> FastMCP[StdioClientLifespan]:
    """Get a FastMCP stdio server setup for CodeWeaver.

    Args:
        config_file: Optional path to configuration file.
        project_path: Optional path to project directory.
        host: Optional host for the server (this is the host/port for the *codeweaver http mcp server* that the stdio client will be proxied to -- only needed if not default or not what's in your config).
        port: Optional port for the server (this is the host/port for the *codeweaver http mcp server* that the stdio client will be proxied to -- only needed if not default or not what's in your config).

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
    return await create_stdio_server(
        settings=cast(CodeWeaverSettingsDict | None, settings), host=host, port=port
    )


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
    """Run the CodeWeaver server."""


if __name__ == "__main__":
    from codeweaver.common.utils.procs import asyncio_or_uvloop

    asyncio = asyncio_or_uvloop()
    try:
        asyncio.run(run())
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to start CodeWeaver server: ")
        raise InitializationError("Failed to start CodeWeaver server.") from e

__all__ = ("run", "start_server")
