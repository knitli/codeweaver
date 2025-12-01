# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Setup server logging configuration."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from codeweaver.config.logging import DefaultLoggingSettings, LoggingSettings
from codeweaver.core.types.sentinel import Unset


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types import DictView


def _set_log_levels():
    """Suppress third-party library loggers comprehensively.

    Sets log levels AND removes handlers to prevent any output leakage.
    """
    # List of loggers to suppress
    loggers_to_suppress = (
        "anthropic",
        "aws",
        "azure",
        "boto3",
        "botocore",
        "cohere",
        "fastapi",
        "fastmcp",
        "fastmcp.server",
        "google",
        "google.api_core",
        "google.genai",
        "hf",
        "httpcore",
        "httpx",
        "httpx._client",
        "huggingface_hub",
        "mcp",
        "mcp.server",
        "mistral",
        "ollama",
        "openai",
        "qdrant_client",
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "voyage",
    )

    for logger_name in loggers_to_suppress:
        logger_obj = logging.getLogger(logger_name)
        # Set level to CRITICAL to suppress almost everything
        logger_obj.setLevel(logging.CRITICAL)
        # Remove all handlers to prevent output
        logger_obj.handlers.clear()
        # Disable propagation to parent loggers
        logger_obj.propagate = False


def setup_logger(settings: DictView[CodeWeaverSettingsDict]) -> logging.Logger:
    """Set up the logger from settings.

    Returns:
        Configured logger instance
    """
    app_logger_settings: LoggingSettings = (
        DefaultLoggingSettings
        if isinstance(settings.get("logging", {}), Unset)
        else settings.get("logging", {})
    )
    level = app_logger_settings.get("level", 30)
    rich = app_logger_settings.get("use_rich", True)
    rich_options = app_logger_settings.get("rich_options", {})
    logging_kwargs = app_logger_settings.get("dict_config", None)
    from codeweaver.common.logging import setup_logger as setup_global_logging

    app_logger = setup_global_logging(
        name="codeweaver",
        level=level,
        rich=rich,
        rich_options=rich_options,
        logging_kwargs=logging_kwargs,
    )

    # Suppress third-party library loggers when level is above INFO
    if level > logging.INFO:
        _set_log_levels()  # Reuse the comprehensive suppression function

    return app_logger
