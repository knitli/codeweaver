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
from types import EllipsisType
from typing import TYPE_CHECKING, Any, Literal, cast, is_typeddict

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware
from pydantic import FilePath
from typing_extensions import TypeIs

from codeweaver.common.utils import lazy_import
from codeweaver.core.types.sentinel import Unset
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
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.server import AppState, ServerSetup

logger = logging.getLogger(__name__)


def is_server_setup(obj: Any) -> TypeIs[ServerSetup]:
    """Type guard to check if an object is a ServerSetup TypedDict."""
    return (
        is_typeddict(obj)
        and all(key in obj for key in ("app", "settings"))
        and isinstance(obj["settings"], CodeWeaverSettings)
    )


async def start_server(server: FastMCP[AppState] | ServerSetup, **kwargs: Any) -> None:
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
    try:
        app = server if isinstance(server, FastMCP) else server["app"]
        resolved_kwargs: dict[str, Any] = kwargs or {}
        server_setup: ServerSetup | EllipsisType = server if is_server_setup(server) else ...

        # Get verbose/debug flags early for use throughout
        verbose = False
        debug = False

        if server_setup and is_server_setup(server_setup):
            settings: CodeWeaverSettings = server_setup["settings"]

            # Get verbose/debug flags
            verbose = server_setup.get("verbose", False)
            debug = server_setup.get("debug", False)

            # Transport priority: 1) CLI param (in server_setup), 2) settings, 3) default
            transport = (
                server_setup.get("transport")
                or (
                    "streamable-http"
                    if isinstance(settings.server, Unset)
                    else settings.server.transport
                )
                or "streamable-http"
            )

            # Configure uvicorn based on verbosity
            uvicorn_config = settings.uvicorn or {}
            if not (verbose or debug):
                # Non-verbose mode: Suppress all uvicorn logging completely
                uvicorn_log_config = {
                    "version": 1,
                    "disable_existing_loggers": False,
                    "formatters": {
                        "default": {
                            "()": "uvicorn.logging.DefaultFormatter",
                            "fmt": "%(levelprefix)s %(message)s",
                            "use_colors": None,
                        }
                    },
                    "handlers": {"null": {"class": "logging.NullHandler"}},
                    "loggers": {
                        "uvicorn": {"handlers": ["null"], "level": "CRITICAL", "propagate": False},
                        "uvicorn.error": {
                            "handlers": ["null"],
                            "level": "CRITICAL",
                            "propagate": False,
                        },
                        "uvicorn.access": {
                            "handlers": ["null"],
                            "level": "CRITICAL",
                            "propagate": False,
                        },
                        # Additional loggers that may leak through
                        "fastapi": {"handlers": ["null"], "level": "CRITICAL", "propagate": False},
                        "fastmcp": {"handlers": ["null"], "level": "CRITICAL", "propagate": False},
                    },
                }

                uvicorn_config = {
                    **uvicorn_config,
                    "access_log": False,  # Disable access logging
                    "log_level": "critical",  # Only critical errors
                    "log_config": uvicorn_log_config,  # Custom logging config
                }
            else:
                # Verbose/debug mode: Enable uvicorn access logs
                uvicorn_config = {
                    **uvicorn_config,
                    "access_log": True,  # Enable access logging in verbose mode
                    "log_level": "debug" if debug else "info",  # Match verbosity level
                }

            new_kwargs = {  # type: ignore
                "transport": transport,
                "host": server_setup.pop("host", "127.0.0.1"),
                "port": server_setup.pop("port", 9328),
                "log_level": server_setup.pop("log_level", "INFO"),
                "middleware": server_setup.pop("middleware", set()),
                "uvicorn_config": uvicorn_config,  # Use configured uvicorn settings
                "show_banner": False,  # We use our own custom banner via StatusDisplay
            }
            resolved_kwargs = new_kwargs | kwargs
        else:
            resolved_kwargs = {  # type: ignore
                "transport": "streamable-http",
                "host": "127.0.0.1",
                "port": 9328,
                "log_level": "INFO",
                "middleware": set(),
                "uvicorn_config": {},
                "show_banner": False,  # We use our own custom banner via StatusDisplay
                **kwargs.copy(),
            }  # type: ignore
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
    finally:
        # Restore original signal handler
        if original_sigint_handler:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGINT, original_sigint_handler)


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
    from codeweaver.server import build_app
    from codeweaver.server.app_bindings import register_app_bindings, register_tool

    server_setup = build_app(verbose=verbose, debug=debug, transport=transport)
    server_setup["verbose"] = verbose
    server_setup["debug"] = debug
    if host:
        server_setup["host"] = host
    if port:
        server_setup["port"] = port
    if config_file or project_path:
        from codeweaver.config.settings import get_settings

        server_setup["settings"] = get_settings(config_file=config_file)
    if project_path:
        from codeweaver.config.settings import update_settings

        logger.debug("Type of server_setup['settings']: %s", type(server_setup["settings"]))
        _ = update_settings(**{  # ty: ignore[invalid-argument-type]
            **server_setup["settings"].model_dump(),
            "project_path": project_path,
        })

    # Explicitly type the middleware to satisfy type checker
    middleware: set[Middleware] = server_setup.get("middleware", set())  # type: ignore[assignment]

    server_setup["app"], server_setup["middleware"] = await register_app_bindings(  # type: ignore
        server_setup["app"],
        cast(set[Middleware], middleware),
        server_setup.get("middleware_settings", {}),  # ty: ignore[invalid-argument-type]
    )
    server_setup["app"] = register_tool(server_setup["app"])
    await start_server(server_setup)


if __name__ == "__main__":
    from codeweaver.common.utils.procs import asyncio_or_uvloop

    asyncio = asyncio_or_uvloop()
    try:
        asyncio.run(run())
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to start CodeWeaver server: ")
        raise InitializationError("Failed to start CodeWeaver server.") from e

__all__ = ("run", "start_server")
