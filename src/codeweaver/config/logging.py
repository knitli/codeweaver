"""Logging configuration settings and utilities for CodeWeaver."""

import logging
import re

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any, Literal, NewType, NotRequired, Required, TypedDict

from pydantic import BeforeValidator, Field, FieldSerializationInfo, PrivateAttr, field_serializer

from codeweaver.core import BasedModel
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.exceptions import ConfigurationError


if TYPE_CHECKING:
    from codeweaver.core import AnonymityConversion, FilteredKey


# ===========================================================================
# *  TypedDict classes for Python Stdlib Logging Configuration (`dictConfig``)
# ===========================================================================


# Basic regex safety heuristics for user-supplied patterns
MAX_REGEX_PATTERN_LENGTH = 8192
# Very simple heuristic to flag obviously dangerous nested quantifiers that are common in ReDoS patterns,
# e.g., (.+)+, (\w+)*, (a|aa)+, etc. This is not exhaustive but catches many foot-guns.
_NESTED_QUANTIFIER_RE = re.compile(
    r"(?:\([^)]*\)|\[[^\]]*\]|\\.|.)(?:\+|\*|\{[^}]*\})\s*(?:\+|\*|\{[^}]*\})"
)

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


def walk_pattern(s: str) -> str:
    r"""Normalize a user-supplied regex pattern string.

    - Preserves whitespace exactly (no strip).
    - Doubles unknown escapes so they are treated literally (e.g. "\y" -> "\\y")
      instead of raising "bad escape" at compile time.
    - Protects against a lone trailing backslash by doubling it.
    This aims to accept inputs written as if they were r-strings while remaining robust to
    config/env string parsing that may have processed standard escapes like "\n".
    """
    if not isinstance(s, str):  # pyright: ignore[reportUnnecessaryIsInstance]  # just being defensive
        raise TypeError("Pattern must be a string.")

    out: list[str] = []
    i = 0
    n = len(s)

    # First character after a backslash that we consider valid in Python's `re` syntax or as an escaped metachar.
    legal_next = set("AbBdDsSwWZzGAfnrtvxuUN0123456789") | set(".*+?^$|()[]{}\\")

    while i < n:
        ch = s[i]
        if ch == "\\":
            # If pattern ends with a single backslash, double it so compile won't fail.
            if i == n - 1:
                out.append("\\\\")
                i += 1
                continue
            nxt = s[i + 1]
            if nxt in legal_next:
                # Keep known/valid escapes and escaped metacharacters as-is.
                out.append("\\")
            else:
                # Unknown escape — make it literal by doubling the backslash.
                out.append("\\\\")
            out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1

    return "".join(out)


def validate_regex_pattern(value: re.Pattern[str] | str | None) -> re.Pattern[str] | None:
    """Validate and compile a regex pattern from config/env.

    - Accepts compiled patterns as-is.
    - For strings, applies normalization via `walk_pattern`, basic length and nested-quantifier checks,
      then compiles. Raises `ConfigurationError` on invalid/unsafe patterns.
    """
    if value is None:
        return None
    if isinstance(value, re.Pattern):
        return value

    if len(value) > MAX_REGEX_PATTERN_LENGTH:
        raise ConfigurationError(
            f"Regex pattern is too long (max {MAX_REGEX_PATTERN_LENGTH} characters)."
        )

    normalized = walk_pattern(value)

    # Heuristic check for patterns likely to cause catastrophic backtracking
    if _NESTED_QUANTIFIER_RE.search(normalized):
        raise ConfigurationError(
            "Pattern contains nested quantifiers (e.g., (.+)+), which can cause excessive backtracking. Please simplify the pattern."
        )

    # Optional sanity check on number of groups (very large numbers are often accidental or risky)
    try:
        open_groups = sum(
            c == "(" and (i == 0 or normalized[i - 1] != "\\") for i, c in enumerate(normalized)
        )
    except Exception:
        logging.getLogger(__name__).debug(
            "Failed to count groups in regex safety check", exc_info=True
        )
    else:
        if open_groups > 100:
            raise ConfigurationError("Pattern uses too many capturing/non-capturing groups (>100).")

    try:
        return re.compile(normalized)
    except re.error as e:
        raise ConfigurationError(f"Invalid regex pattern: {e.args[0]}") from e


class SerializableLoggingFilter(BasedModel, logging.Filter):
    """A logging.Filter object that implements a custom pydantic serializer.
    The filter can be serialized and deserialized using Pydantic.

    Uses regex patterns to apply filtering logic to log message text. Provide include and/or exclude patterns to filter messages. Include patterns are applied *after* exclude patterns (defaults to logging if there's a conflict)).

    If you provide a `simple_filter`, any patterns will only be applied to records that pass the simple filter.
    """

    simple_filter: Annotated[
        LoggerName | None,
        Field(
            default_factory=logging.Filter,
            description="""A simple name filter that matches the `name` attribute of a `logging.Logger`. This is equivalent to using `logging.Filter(name)`.""",
        ),
    ]

    include_pattern: Annotated[
        re.Pattern[str] | None,
        # NOTE: `include_pattern` and `exclude_pattern` are prime candidates for Python 3.14's `template strings`.
        # TODO: Once they become more available, we should use `raw template strings` here
        # See 👁️ https://docs.python.org/3.14/library/string.templatelib.html#template-strings
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

    def _telemetry_keys(self) -> dict[FilteredKey, AnonymityConversion]:
        from codeweaver.core import AnonymityConversion, FilteredKey

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


class LoggingSettings(TypedDict, total=False):
    """Global logging settings."""

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
    rich_kwargs: NotRequired[
        Annotated[
            dict[str, Any],
            Field(
                description="""Additional keyword arguments for the `rich` logging handler, [`rich.logging.RichHandler`], if enabled."""
            ),
        ]
    ]


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
