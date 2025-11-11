# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Set up a logger with optional rich formatting."""

from __future__ import annotations

import logging

from importlib import import_module
from logging.config import dictConfig
from typing import TYPE_CHECKING, Any, Literal

from fastmcp import Context
from pydantic_core import to_json

from codeweaver.common.utils.lazy_importer import lazy_import
from codeweaver.config.logging import LoggingConfigDict


if TYPE_CHECKING:
    from rich.logging import RichHandler

    from codeweaver.common import LazyImport
else:
    RichHandler: LazyImport[RichHandler] = lazy_import("rich.logging", "RichHandler")


def get_rich_handler(**kwargs: Any) -> RichHandler:
    console = import_module("rich.console").Console
    global RichHandler
    return RichHandler(
        console=console(markup=True, soft_wrap=True, emoji=True), markup=True, **kwargs
    )  # type: ignore


def _setup_config_logger(
    name: str | None = "codeweaver",
    *,
    level: int = logging.WARNING,
    rich: bool = True,
    rich_options: dict[str, Any] | None = None,
    logging_kwargs: LoggingConfigDict | None = None,
) -> logging.Logger:
    """Set up a logger with optional rich formatting."""
    if logging_kwargs:
        dictConfig({**logging_kwargs})  # ty: ignore[missing-typed-dict-key]
        if rich:
            return _setup_logger_with_rich_handler(rich_options, name, level)
        return logging.getLogger(name)
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
    name: str | None = "codeweaver",
    *,
    level: int = logging.WARNING,
    rich: bool = True,
    rich_options: dict[str, Any] | None = None,
    logging_kwargs: LoggingConfigDict | None = None,
) -> logging.Logger:
    """Set up a logger with optional rich formatting."""
    if logging_kwargs:
        return _setup_config_logger(
            name=name,
            level=level,
            rich=rich,
            rich_options=rich_options,
            logging_kwargs=logging_kwargs,
        )
    if not rich:
        logging.basicConfig(level=level)
        return logging.getLogger(name)
    handler = get_rich_handler(**(rich_options or {}))
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Clear existing handlers to prevent duplication
    logger.handlers.clear()
    logger.addHandler(handler)
    return logger


async def log_to_client_or_fallback(
    context: Context | None,
    level: Literal["debug", "info", "warning", "error"],
    log_data: dict[str, Any],
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
        logger = logging.getLogger("codeweaver")
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


__all__ = ("log_to_client_or_fallback", "setup_logger")
