# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Set up a logger with optional rich formatting."""

import logging

from logging.config import dictConfig
from typing import Any, Literal

from fastmcp import Context
from pydantic_core import to_json
from rich.console import Console
from rich.logging import RichHandler

from codeweaver.settings_types import LoggingConfigDict


def get_rich_handler(rich_kwargs: dict[str, Any]) -> RichHandler:
    """Get a RichHandler instance."""
    console = Console(markup=True, soft_wrap=True, emoji=True)
    return RichHandler(console=console, markup=True, **rich_kwargs)


def _setup_config_logger(
    name: str | None = "codeweaver",
    *,
    level: int = logging.INFO,
    rich: bool = True,
    rich_kwargs: dict[str, Any] | None = None,
    logging_kwargs: LoggingConfigDict | None = None,
) -> logging.Logger:
    """Set up a logger with optional rich formatting."""
    if logging_kwargs:
        dictConfig({**logging_kwargs})
        if rich:
            handler = get_rich_handler(rich_kwargs or {})
            logger = logging.getLogger(name)
            logger.setLevel(level)
            logger.addHandler(handler)
            return logger
        return logging.getLogger(name)
    raise ValueError("No logging configuration provided")


def setup_logger(
    name: str | None = "codeweaver",
    *,
    level: int = logging.INFO,
    rich: bool = True,
    rich_kwargs: dict[str, Any] | None = None,
    logging_kwargs: LoggingConfigDict | None = None,
) -> logging.Logger:
    """Set up a logger with optional rich formatting."""
    if logging_kwargs:
        return _setup_config_logger(
            name=name,
            level=level,
            rich=rich,
            rich_kwargs=rich_kwargs,
            logging_kwargs=logging_kwargs,
        )
    if not rich:
        logging.basicConfig(level=level)
        return logging.getLogger(name)
    handler = get_rich_handler(rich_kwargs or {})
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


def log_to_client_or_fallback(
    logger: logging.Logger,
    message: str,
    level: Literal["debug", "info", "warning", "error"] = "info",
    extra: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> None:
    """Log a message to the client or fallback to standard logging."""
    if ctx and hasattr(ctx, level):
        log_obj = getattr(ctx, level)
        log_obj(f"{message}\n\n{to_json(extra, indent=2) if extra else ''}", logger.name)
    else:
        match level:
            case "debug":
                int_level: int = logging.DEBUG
            case "info":
                int_level: int = logging.INFO
            case "warning":
                int_level: int = logging.WARNING
            case "error":
                int_level: int = logging.ERROR
        logger.log(int_level, message, extra=extra)
