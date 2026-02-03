# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Setup server logging configuration."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from codeweaver.core import DefaultLoggingSettings, LoggingSettingsDict, Unset
from codeweaver.core.constants import DEFAULT_LOG_LEVEL, LOGGERS_TO_SUPPRESS
from codeweaver.core.utils import is_tty


if TYPE_CHECKING:
    from codeweaver.core import DictView
    from codeweaver.core.config.types import CodeWeaverSettingsDict


def _set_log_levels():
    """Suppress third-party library loggers comprehensively.

    Sets log levels AND removes handlers to prevent any output leakage.
    """
    for logger_name in LOGGERS_TO_SUPPRESS:
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
    app_logger_settings: LoggingSettingsDict = (
        DefaultLoggingSettings
        if isinstance(settings.get("logging", {}), Unset)
        else settings.get("logging", {})
    )
    level = app_logger_settings.get("level", DEFAULT_LOG_LEVEL)
    use_rich = app_logger_settings.get("use_rich", is_tty())
    rich_options = app_logger_settings.get("rich_options", {})
    logging_kwargs = app_logger_settings.get("dict_config", None)
    from codeweaver.core import setup_logger as setup_global_logging

    app_logger = setup_global_logging(
        name="codeweaver",
        level=level,
        use_rich=use_rich,
        rich_options=rich_options,
        logging_kwargs=logging_kwargs,
    )

    # Suppress third-party library loggers when level is above INFO
    if level > logging.INFO:
        _set_log_levels()  # Reuse the comprehensive suppression function

    return app_logger


# because of potential namespace issues, we're going to defensively prevent possible bugs:
from logging import getLogger as getLogger
