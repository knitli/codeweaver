# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Set up a logger with optional rich formatting."""

from __future__ import annotations

import logging

from importlib import import_module
from logging.config import dictConfig
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from fastmcp import Context
from pydantic_core import to_json

from codeweaver.cli.utils import is_tty
from codeweaver.common.utils.checks import is_ci
from codeweaver.common.utils.lazy_importer import lazy_import
from codeweaver.config._logging import LoggingConfigDict


if TYPE_CHECKING:
    from rich.logging import RichHandler

    from codeweaver.common import LazyImport
else:
    RichHandler: LazyImport[RichHandler] = lazy_import("rich.logging", "RichHandler")


IS_CI = is_ci()
IS_TTY = is_tty()

# Session log file name
SESSION_LOG_FILENAME = "session.log"


def get_session_log_path() -> Path:
    """Get the path to the session log file in the user config directory."""
    from codeweaver.common.utils.utils import get_user_config_dir

    config_dir = get_user_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / SESSION_LOG_FILENAME


def create_session_file_handler(level: int = logging.DEBUG) -> logging.FileHandler:
    """Create a file handler for session logging that overwrites each session.

    Args:
        level: The logging level for the file handler (defaults to DEBUG to capture all logs)

    Returns:
        A configured FileHandler that writes to the session log file
    """
    log_path = get_session_log_path()
    # Use mode='w' to overwrite the file each session
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setLevel(level)

    # Use a detailed format for file logging
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    return handler


def get_rich_handler(**kwargs: Any) -> RichHandler:
    console = import_module("rich.console").Console
    global RichHandler
    return RichHandler(
        console=console(markup=True, soft_wrap=True, emoji=True), markup=True, **kwargs
    )  # type: ignore


def _setup_config_logger(
    name: str = "codeweaver",
    *,
    level: int = logging.WARNING,
    rich: bool = True,
    rich_options: dict[str, Any] | None = None,
    logging_kwargs: LoggingConfigDict | None = None,
    session_log: bool = True,
) -> logging.Logger:
    """Set up a logger with optional rich formatting."""
    if logging_kwargs:
        dictConfig({**logging_kwargs})  # ty: ignore[missing-typed-dict-key]
        if rich and IS_TTY and not IS_CI:
            logger = _setup_logger_with_rich_handler(rich_options, name, level)
        else:
            logger = logging.getLogger(name)

        # Add session file handler if enabled
        if session_log:
            logger.addHandler(create_session_file_handler())

        return logger
    raise ValueError("No logging configuration provided")


def _setup_logger_with_rich_handler(rich_options: dict[str, Any] | None, name: str, level: int):
    """Set up a logger with rich handler."""
    handler = get_rich_handler(**(rich_options or {}))
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Clear existing handlers to prevent duplication
    logger.handlers.clear()
    logger.addHandler(handler)
    return logger


def setup_logger(
    name: str = "codeweaver",
    *,
    level: int = logging.WARNING,
    rich: bool = True,
    rich_options: dict[str, Any] | None = None,
    logging_kwargs: LoggingConfigDict | None = None,
    session_log: bool = True,
) -> logging.Logger:
    """Set up a logger with optional rich formatting.

    Args:
        name: Logger name
        level: Logging level
        rich: Whether to use rich formatting for console output
        rich_options: Options to pass to RichHandler
        logging_kwargs: Dictionary config for logging
        session_log: Whether to write logs to a session file (default True)

    Returns:
        Configured logger instance
    """
    if logging_kwargs:
        return _setup_config_logger(
            name=name,
            level=level,
            rich=rich,
            rich_options=rich_options,
            logging_kwargs=logging_kwargs,
            session_log=session_log,
        )
    if not rich:
        logging.basicConfig(level=level)
        logger = logging.getLogger(name)
        if session_log:
            logger.addHandler(create_session_file_handler())
        return logger
    handler = get_rich_handler(**(rich_options or {}))
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Clear existing handlers to prevent duplication
    logger.handlers.clear()
    logger.addHandler(handler)

    # Add session file handler if enabled
    if session_log:
        logger.addHandler(create_session_file_handler())

    return logger


async def log_to_client_or_fallback(
    context: Context | None,
    level: Literal["debug", "info", "warning", "error"],
    log_data: dict[str, Any],
    *,
    name: str = "codeweaver",
    logger: logging.Logger | None = None,
) -> None:
    """Log structured data to the client or fallback to standard logging.

    Args:
        context: FastMCP context (optional)
        level: Log level
        log_data: Dict with 'msg' (required) and 'extra' (optional) keys
    """
    msg = log_data.get("msg", "")
    extra = log_data.get("extra")

    if context and hasattr(context, level):
        log_obj = getattr(context, level)
        if extra:
            log_obj(f"{msg}\n\n{to_json(extra, indent=2).decode('utf-8')}")
        else:
            log_obj(msg)
    else:
        # Fallback to standard logging
        logger = logger or logging.getLogger(name)
        match level:
            case "debug":
                int_level: int = logging.DEBUG
            case "info":
                int_level: int = logging.INFO
            case "warning":
                int_level: int = logging.WARNING
            case "error":
                int_level: int = logging.ERROR
        logger.log(int_level, msg, extra=extra)


__all__ = (
    "SESSION_LOG_FILENAME",
    "get_session_log_path",
    "log_to_client_or_fallback",
    "setup_logger",
)
