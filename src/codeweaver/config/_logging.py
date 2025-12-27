# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Logging configuration settings and utilities for CodeWeaver."""

from __future__ import annotations

import logging
import os
import re

from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    NewType,
    NotRequired,
    Required,
    TypedDict,
    cast,
)

from pydantic import BeforeValidator, Field, FieldSerializationInfo, PrivateAttr, field_serializer

from codeweaver.core import AnonymityConversion, BasedModel, is_tty, validate_regex_pattern


if TYPE_CHECKING:
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT


# ===========================================================================
# *  TypedDict classes for Python Stdlib Logging Configuration (`dictConfig``)
# ===========================================================================


type FiltersDict = dict[FilterID, dict[Literal["name"] | str, Any]]

FormatterID = NewType("FormatterID", str)

# just so folks are clear on what these `str` keys are

FilterID = NewType("FilterID", str)

HandlerID = NewType("HandlerID", str)

LoggerName = NewType("LoggerName", str)


class FormattersDict(TypedDict, total=False):
    """A dictionary of formatters for logging configuration.

    This is used to define custom formatters for logging in a dictionary format.
    Each formatter can have a `format`, `date_format`, `style`, and other optional fields.

    [See the Python documentation for more details](https://docs.python.org/3/library/logging.html#logging.Formatter).
    """

    format: NotRequired[str]
    date_format: NotRequired[str]
    style: NotRequired[str]
    validate: NotRequired[bool]
    defaults: NotRequired[
        Annotated[
            dict[str, Any],
            Field(
                default_factory=dict,
                description="""Default values for the formatter. [See the Python documentation for more details](https://docs.python.org/3/library/logging.html#logging.Formatter).""",
            ),
        ]
    ]
    class_name: NotRequired[
        Annotated[
            str,
            Field(
                description="""The class name of the formatter in the form of an import path, like `logging.Formatter` or `rich.logging.RichFormatter`.""",
                serialization_alias="class",
            ),
        ]
    ]


class SerializableLoggingFilter(BasedModel, logging.Filter):
    """A logging.Filter object that implements a custom pydantic serializer.
    The filter can be serialized and deserialized using Pydantic.

    Uses regex patterns to apply filtering logic to log message text. Provide include and/or exclude patterns to filter messages. Include patterns are applied *after* exclude patterns (defaults to logging if there's a conflict)).

    If you provide a `simple_filter`, any patterns will only be applied to records that pass the simple filter.
    """

    simple_filter: LoggerName | None = Field(
        default_factory=logging.Filter,
        description="""A simple name filter that matches the `name` attribute of a `logging.Logger`. This is equivalent to using `logging.Filter(name)`.""",
    )

    include_pattern: Annotated[
        re.Pattern[str] | None,
        BeforeValidator(validate_regex_pattern),
        Field(
            description="""Regex pattern to filter the body text of log messages. Records matching this pattern will be *included* in log output."""
        ),
    ] = None

    exclude_pattern: Annotated[
        re.Pattern[str] | None,
        BeforeValidator(validate_regex_pattern),
        Field(
            description="""Regex pattern to filter the body text of log messages. Records matching this pattern will be *excluded* from log output."""
        ),
    ] = None

    _filter: Annotated[
        logging.Filter | Callable[[logging.LogRecord], bool | logging.LogRecord] | None,
        PrivateAttr(),
    ] = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {FilteredKey("simple_filter"): AnonymityConversion.BOOLEAN}

    @field_serializer("include_pattern", "exclude_pattern", when_used="json-unless-none")
    def serialize_patterns(self, value: re.Pattern[str], info: FieldSerializationInfo) -> str:
        """Serialize a regex pattern for JSON output."""
        return value.pattern


class HandlersDict(TypedDict, total=False):
    """A dictionary of handlers for logging configuration.

    This is used to define custom handlers for logging in a dictionary format.
    Each handler can have a `class_name`, `level`, and other optional fields.

    [See the Python documentation for more details](https://docs.python.org/3/library/logging.html#logging.Handler).
    """

    class_name: Required[
        Annotated[
            str,
            Field(
                description="""The class name of the handler in the form of an import path, like `logging.StreamHandler` or `rich.logging.RichHandler`.""",
                serialization_alias="class",
            ),
        ]
    ]
    level: NotRequired[Literal[0, 10, 20, 30, 40, 50]]  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    formatter: NotRequired[FormatterID]  # The ID of the formatter to use for this handler
    filters: NotRequired[list[FilterID]]


class LoggersDict(TypedDict, total=False):
    """A dictionary of loggers for logging configuration.

    This is used to define custom loggers for logging in a dictionary format.
    Each logger can have a `level`, `handlers`, and other optional fields.

    [See the Python documentation for more details](https://docs.python.org/3/library/logging.html#logging.Logger).
    """

    level: NotRequired[Literal[0, 10, 20, 30, 40, 50]]  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    propagate: NotRequired[bool]  # Whether to propagate messages to the parent logger
    handlers: NotRequired[list[HandlerID]]  # The IDs of the handlers to use for this logger
    filters: NotRequired[
        list[FilterID]
    ]  # The IDs of the filters to use for this logger, or filter instances


class LoggingConfigDict(TypedDict, total=False):
    """Logging configuration settings. You may optionally use this to customize logging in a very granular way.

    `LoggingConfigDict` is structured to match the format expected by Python's `logging.config.dictConfig` function. You can use this to define loggers, handlers, and formatters in a dictionary format -- either programmatically or in your CodeWeaver settings file.
    [See the Python documentation for more details](https://docs.python.org/3/library/logging.config.html).
    """

    version: Required[Literal[1]]
    formatters: NotRequired[dict[FormatterID, FormattersDict]]
    filters: NotRequired[FiltersDict]
    handlers: NotRequired[dict[HandlerID, HandlersDict]]
    loggers: NotRequired[dict[str, LoggersDict]]
    root: NotRequired[
        Annotated[LoggersDict, Field(description="""The root logger configuration.""")]
    ]
    incremental: NotRequired[
        Annotated[
            bool,
            Field(
                description="""Whether to apply this configuration incrementally or replace the existing configuration. [See the Python documentation for more details](https://docs.python.org/3/library/logging.config.html#logging-config-dict-incremental)."""
            ),
        ]
    ]
    disable_existing_loggers: NotRequired[
        Annotated[
            bool,
            Field(
                description="""Whether to disable all existing loggers when configuring logging. If not present, defaults to `True`."""
            ),
        ]
    ]


def _from_env_log_level() -> Literal[0, 10, 20, 30, 40, 50]:
    """Get log level from environment variable."""
    if level_str := os.environ.get("CODEWEAVER_LOG_LEVEL"):
        if level_str.isdigit():
            return (
                int(level_str)
                if level_str in {"0", "10", "20", "30", "40", "50"}
                else logging.WARNING  # ty: ignore[invalid-return-type]
            )
        level_str = level_str.upper()
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return level_map.get(level_str, logging.WARNING)  # ty: ignore[invalid-return-type]
    return logging.WARNING


class LoggingSettings(TypedDict, total=False):
    """Global logging settings."""

    name: NotRequired[str]
    level: NotRequired[Literal[0, 10, 20, 30, 40, 50]]  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    use_rich: NotRequired[bool]
    dict_config: NotRequired[
        Annotated[
            LoggingConfigDict,
            Field(
                description="""Logging configuration in dictionary format that matches the format expected by [`logging.config.dictConfig`](https://docs.python.org/3/library/logging.config.html)."""
            ),
        ]
    ]
    rich_options: NotRequired[
        Annotated[
            dict[str, Any],
            Field(
                description="""Additional keyword arguments for the `rich` logging handler, [`rich.logging.RichHandler`], if enabled."""
            ),
        ]
    ]


DefaultLoggingSettings: LoggingSettings = {
    "name": "codeweaver",
    "level": cast(Literal[0, 10, 20, 30, 40, 50], _from_env_log_level()),
    "use_rich": is_tty(),
    "rich_options": {
        "show_time": True,
        "show_level": True,
        "show_path": True,
        "rich_tracebacks": False,
    }
    if is_tty()
    else {},
}


__all__ = (
    "FilterID",
    "FiltersDict",
    "FormatterID",
    "FormattersDict",
    "HandlerID",
    "HandlersDict",
    "LoggerName",
    "LoggersDict",
    "LoggingConfigDict",
    "LoggingSettings",
    "SerializableLoggingFilter",
)
