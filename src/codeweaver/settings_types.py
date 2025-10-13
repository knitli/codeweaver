# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# We need to override our generic models with specific types, and type overrides for narrower values is a good thing.

"""Supporting types for CodeWeaver settings and configuration.

This module primarily consists of a series of TypedDict classes that define the structure of various configuration options for CodeWeaver, including logging settings, middleware settings, provider settings, and more.
Most of these settings are optional, with sensible defaults provided where applicable.

Some of these also represent serialized versions of the pydantic settings models, to provide clear typing and validation for configuration files and environment variables in their serialized forms.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
import ssl

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, NotRequired, Required, Self, TypedDict

from fastmcp.contrib.bulk_tool_caller.bulk_tool_caller import BulkToolCaller
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware, RetryMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware, StructuredLoggingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.timing import DetailedTimingMiddleware
from fastmcp.server.server import DuplicateBehavior
from fastmcp.tools import Tool
from mcp.server.auth.settings import AuthSettings
from mcp.server.lowlevel.server import LifespanResultT
from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    FieldSerializationInfo,
    FilePath,
    PositiveFloat,
    PositiveInt,
    PrivateAttr,
    SecretStr,
    field_serializer,
    model_validator,
)
from pydantic_ai.settings import ModelSettings as AgentModelSettings
from starlette.middleware import Middleware as ASGIMiddleware
from uvicorn.config import (
    SSL_PROTOCOL_VERSION,
    HTTPProtocolType,
    InterfaceType,
    LifespanType,
    LoopSetupType,
    WSProtocolType,
)

from codeweaver._common import BasedModel, DictView
from codeweaver._constants import ALL_LANGUAGES, ExtLangPair
from codeweaver._supported_languages import SecondarySupportedLanguage
from codeweaver.exceptions import ConfigurationError
from codeweaver.services.chunker.delimiters.families import LanguageFamily
from codeweaver.services.chunker.delimiters.patterns import DelimiterPattern


if TYPE_CHECKING:
    from codeweaver._common import Unset
    from codeweaver.provider import Provider


AVAILABLE_MIDDLEWARE = (
    BulkToolCaller,
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    StructuredLoggingMiddleware,
    DetailedTimingMiddleware,
    RateLimitingMiddleware,
    RetryMiddleware,
)

# ===========================================================================
# *        TypedDict Representations of Top-Level Settings Models
# ===========================================================================


class FastMcpHttpRunArgs(TypedDict, total=False):
    """Arguments for running FastMCP over HTTP."""

    transport: NotRequired[Literal["http", "streamable-http"]]
    host: NotRequired[str | None]
    port: NotRequired[PositiveInt | None]
    log_level: NotRequired[Literal["debug", "info", "warning", "error"] | None]
    path: NotRequired[str | None]
    uvicorn_config: NotRequired[UvicornServerSettingsDict | None]
    middleware: list[ASGIMiddleware] | None


class FastMcpServerSettingsDict(TypedDict, total=False):
    """TypedDict for FastMCP server settings.

    Not intended to be used directly; used for internal type checking and validation.

    Other notes: FastMCP seems to be moving towards using direct run arguments, particularly for server transport settings (like host/port). It seems like everytime we bump versions a new setting is deprecated.
    """

    name: NotRequired[str]
    instructions: NotRequired[str | None]
    version: NotRequired[str | None]
    lifespan: NotRequired[LifespanResultT | None]  # type: ignore  # it's just for clarity
    include_tags: NotRequired[set[str] | None]
    exclude_tags: NotRequired[set[str] | None]
    transport: NotRequired[Literal["stdio", "http"] | None]
    host: NotRequired[str | None]  # not a valid setting for FastMCP Settings
    port: NotRequired[
        PositiveInt | None
    ]  # host/port need to be popped and used when initiating server
    auth: NotRequired[AuthSettings | None]
    on_duplicate_tools: NotRequired[DuplicateBehavior | None]
    on_duplicate_resources: NotRequired[DuplicateBehavior | None]
    on_duplicate_prompts: NotRequired[DuplicateBehavior | None]
    resource_prefix_format: NotRequired[Literal["protocol", "path"] | None]
    middleware: NotRequired[list[str | Middleware] | None]
    tools: NotRequired[list[str | Tool] | None]


class CustomLanguage(BasedModel):
    """A custom programming language for language specific parsing.

    By default, CodeWeaver only indexes extensions it recognizes. There are a lot (~170 languages and 200+ extensions) but not everything. If you want it to index files with extensions it doesn't recognize, you can define a custom language here. You only need to do this if you **don't** want to define a custom delimiter for your language. CodeWeaver will try to detect the best chunking strategy for your language, and will probably do a decent job, but if you want to define custom delimiters, use the `CustomDelimiter` class instead.
    """

    model_config = BasedModel.model_config | ConfigDict(frozen=True)

    extensions: Annotated[
        list[ExtLangPair],
        Field(
            min_length=1,
            description="""List of file extensions and their associated languages to apply this custom language to. An ExtLangPair is a tuple of `ext: str, language: str`. **If the language and extensions are already defined in `codeweaver._constants`, then this is not required.**""",
        ),
    ]
    language_family: Annotated[
        LanguageFamily | None,
        Field(
            description="The language family this language belongs to. This is used to determine the best chunking strategy for the language. If not provided, CodeWeaver will test it against known language families."
        ),
    ] = None


class CustomDelimiter(BasedModel):
    """A custom delimiter for separating multiple prompts in a single input string. If you only want to define a new language and extensions but not a delimiter, use the `CustomLanguage` class instead.

    Attributes:
        delimiter (str): The delimiter string to use.
        description (str): A description of the delimiter.
    """

    model_config = BasedModel.model_config | ConfigDict(frozen=True)

    delimiters: Annotated[
        list[DelimiterPattern],
        Field(
            default_factory=list,
            min_length=1,
            description="List of delimiters to use. You must provide at least one delimiter.",
        ),
    ]

    extensions: Annotated[
        list[ExtLangPair] | None,
        Field(
            default_factory=list,
            description="""List of file extensions and their associated languages to apply this delimiter to. If you are defining delimiters for a language that does not currently have support see `codeweaver._constants.CODE_FILES_EXTENSIONS`, `codeweaver._constants.DATA_FILES_EXTENSIONS`, and `codeweaver._constants.DOC_FILES_EXTENSIONS`. An ExtLangPair is a tuple of `ext: str, language: str`. If the language and extensions are already defined in `codeweaver._constants` then you don't need to provide these, but you DO need to provide a language.""",
        ),
    ] = None

    language: Annotated[
        SecondarySupportedLanguage | None,
        Field(
            min_length=1,
            max_length=30,
            description="""The programming language this delimiter applies to. Must be one of the languages defined in `codeweaver._constants`. If you want to define delimiters for a new language and/or file extensions, leave this field as `None` and provide the `extensions` field.""",
            default_factory=lambda data: None if data.get("extensions") else str,
        ),
    ] = None

    @model_validator(mode="after")
    def validate_instance(self) -> Self:
        """Validate the instance after initialization."""
        if self.language not in ALL_LANGUAGES and not self.extensions:
            raise ValueError(
                f"If you are defining a delimiter for a language that does not currently have support see `codeweaver._constants.CODE_FILES_EXTENSIONS`, `codeweaver._constants.DATA_FILES_EXTENSIONS`, and `codeweaver._constants.DOC_FILES_EXTENSIONS`. You must provide the `extensions` field if the language '{self.language}' is not supported."
            )
        if not self.delimiters:
            raise ValueError("You must provide at least one delimiter.")
        if (
            self.language
            and self.extensions
            and not all(ext.language for ext in self.extensions if ext.language == self.language)
        ):
            raise ValueError(
                f"The language '{self.language}' must match the language in all provided extensions: {[ext.language for ext in self.extensions]}. You also don't need to provide a language if all extensions have the same language as the one you're defining the delimiter for (which it should)."
            )
        return self


# ===========================================================================
# *  TypedDict classes for Python Stdlib Logging Configuration (`dictConfig``)
# ===========================================================================

type FormatterID = str


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


# just so folks are clear on what these `str` keys are

type FilterID = str

type FiltersDict = dict[FilterID, dict[Literal["name"] | str, Any]]

type HandlerID = str

type LoggerName = str


# Basic regex safety heuristics for user-supplied patterns
MAX_REGEX_PATTERN_LENGTH = 8192
# Very simple heuristic to flag obviously dangerous nested quantifiers that are common in ReDoS patterns,
# e.g., (.+)+, (\w+)*, (a|aa)+, etc. This is not exhaustive but catches many foot-guns.
_NESTED_QUANTIFIER_RE = re.compile(
    r"(?:\([^)]*\)|\[[^\]]*\]|\\.|.)(?:\+|\*|\{[^}]*\})\s*(?:\+|\*|\{[^}]*\})"
)


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


# ===========================================================================
# *          TypedDict classes for Middleware Settings
# ===========================================================================


class ErrorHandlingMiddlewareSettings(TypedDict, total=False):
    """Settings for error handling middleware."""

    logger: NotRequired[logging.Logger | None]
    include_traceback: NotRequired[bool]
    error_callback: NotRequired[Callable[[Exception, MiddlewareContext[Any]], None] | None]
    transform_errors: NotRequired[bool]


class RetryMiddlewareSettings(TypedDict, total=False):
    """Settings for retry middleware."""

    max_retries: NotRequired[int]
    base_delay: NotRequired[float]
    max_delay: NotRequired[float]
    backoff_multiplier: NotRequired[float]
    retry_exceptions: NotRequired[tuple[type[Exception], ...]]
    logger: NotRequired[logging.Logger | None]


class LoggingMiddlewareSettings(TypedDict, total=False):
    """Settings for logging middleware (both structured and unstructured)."""

    logger: Annotated[NotRequired[logging.Logger | None], Field(exclude=True)]
    log_level: NotRequired[int]
    include_payloads: NotRequired[bool]
    max_payload_length: NotRequired[int]
    methods: NotRequired[list[str] | None]

    use_structured_logging: NotRequired[bool]


class RateLimitingMiddlewareSettings(TypedDict, total=False):
    """Settings for rate limiting middleware."""

    max_requests_per_second: NotRequired[PositiveInt]
    burst_capacity: NotRequired[PositiveInt | None]
    get_client_id: NotRequired[Callable[[MiddlewareContext[Any]], str] | None]
    global_limit: NotRequired[bool]


class MiddlewareOptions(TypedDict, total=False):
    """Settings for middleware."""

    error_handling: ErrorHandlingMiddlewareSettings | None
    retry: RetryMiddlewareSettings | None
    logging: LoggingMiddlewareSettings | None
    rate_limiting: RateLimitingMiddlewareSettings | None


# ===========================================================================
# *            Provider Settings classes
# ===========================================================================


class RignoreSettings(TypedDict, total=False):
    """Settings for the rignore library."""

    ignore_hidden: NotRequired[bool]
    read_ignore_files: NotRequired[bool]
    read_parents_ignores: NotRequired[bool]
    read_git_ignore: NotRequired[bool]
    read_global_git_ignore: NotRequired[bool]
    read_git_exclude: NotRequired[bool]
    require_git: NotRequired[bool]
    additional_ignores: NotRequired[list[str | Path]]
    additional_ignore_paths: NotRequired[list[str | Path]]
    max_depth: NotRequired[int]
    max_filesize: NotRequired[int]
    follow_links: NotRequired[bool]
    case_insensitive: NotRequired[bool]
    same_file_system: NotRequired[bool]
    should_exclude_entry: NotRequired[Callable[[Path], bool]]


class FileFilterSettingsDict(TypedDict, total=False):
    """A serialized `FileFilterSettings` object."""

    forced_includes: NotRequired[frozenset[str | Path]]
    excludes: NotRequired[frozenset[str | Path]]
    excluded_extensions: NotRequired[frozenset[str]]
    use_gitignore: NotRequired[bool]
    use_other_ignore_files: NotRequired[bool]
    ignore_hidden: NotRequired[bool]
    include_github_dir: NotRequired[bool]
    other_ignore_kwargs: NotRequired[RignoreSettings | Unset]
    default_rignore_settings: NotRequired[DictView[RignoreSettings]]


class ConnectionRateLimitConfig(TypedDict, total=False):
    """Settings for connection rate limiting."""

    max_requests_per_second: PositiveInt | None
    burst_capacity: PositiveInt | None
    backoff_multiplier: PositiveFloat | None
    max_retries: PositiveInt | None


class ConnectionConfiguration(TypedDict, total=False):
    """Settings for connection configuration. Only required for non-default transports."""

    host: str | None
    port: PositiveInt | None
    headers: NotRequired[dict[str, str] | None]
    rate_limits: NotRequired[ConnectionRateLimitConfig | None]


class BaseProviderSettings(TypedDict, total=False):
    """Base settings for all providers."""

    provider: Required[Provider]
    enabled: Required[bool]
    api_key: NotRequired[str | None]
    connection: NotRequired[ConnectionConfiguration | None]
    client_kwargs: NotRequired[dict[str, Any] | None]
    other: NotRequired[dict[str, Any] | None]


class DataProviderSettings(BaseProviderSettings):
    """Settings for data providers."""


class EmbeddingModelSettings(TypedDict, total=False):
    """Embedding model settings. Use this class for dense (vector) models."""

    model: Required[str]
    dimension: NotRequired[PositiveInt | None]
    data_type: NotRequired[str | None]
    custom_prompt: NotRequired[str | None]
    call_kwargs: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the client model's `embed` method."""
    model_kwargs: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the model's constructor."""


class SparseEmbeddingModelSettings(TypedDict, total=False):
    """Sparse embedding model settings. Use this class for sparse (e.g. bag-of-words) models."""

    model: Required[str]
    call_kwargs: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the client model's `embed` method."""
    model_kwargs: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the model's constructor."""


class RerankingModelSettings(TypedDict, total=False):
    """Rerank model settings."""

    model: Required[str]
    custom_prompt: NotRequired[str | None]
    call_kwargs: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the client model's `rerank` method."""
    client_kwargs: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the client model's constructor."""


class AWSProviderSettings(TypedDict, total=False):
    """Settings for AWS provider.

    You need to provide these settings if you are using Bedrock, and you need to provide them for each Bedrock model you use. It might be repetitive, but a lot of people have different credentials for different models/services.
    """

    region_name: Required[str]
    model_arn: Required[str]
    aws_access_key_id: NotRequired[SecretStr | None]
    """Optional AWS access key ID. If not provided, we'll assume you have you have your AWS credentials configured in another way, such as environment variables, AWS config files, or IAM roles."""
    aws_secret_access_key: NotRequired[SecretStr | None]
    """Optional AWS secret access key. If not provided, we'll assume you have you have your AWS credentials configured in another way, such as environment variables, AWS config files, or IAM roles."""
    aws_session_token: NotRequired[SecretStr | None]
    """Optional AWS session token. If not provided, we'll assume you have you have your AWS credentials configured in another way, such as environment variables, AWS config files, or IAM roles."""


class AzureCohereProviderSettings(TypedDict, total=False):
    """Provider settings for Azure Cohere.

    You need to provide these settings if you are using Azure Cohere, and you need to provide them for each Azure Cohere model you use.
    They're **all required**. They're marked `NotRequired` in the TypedDict because you can also provide them by environment variables, but you must provide them one way or another.
    """

    model_deployment: NotRequired[str]
    """The deployment name of the model you want to use. Important: While the OpenAI API uses the model name to identify the model, you must separately provide a codeweaver-compatible name for the model, as well as your Azure resource name here. We're open to PRs if you want to add a parser for model names that can extract the deployment name from them."""
    api_key: NotRequired[SecretStr | None]
    """Your Azure API key. If not provided, we'll assume you have your Azure credentials configured in another way, such as environment variables."""
    azure_resource_name: NotRequired[str]
    """The name of your Azure resource. This is used to identify your resource in Azure."""
    azure_endpoint: NotRequired[str]
    """The endpoint for your Azure resource. This is used to send requests to your resource. Only provide the endpoint, not the full URL. For example, if your endpoint is `https://your-cool-resource.<region_name>.inference.ai.azure.com/v1`, you would only provide "your-cool-resource" here."""
    region_name: NotRequired[str]
    """The Azure region where your resource is located. This is used to route requests to the correct regional endpoint."""


class AzureOpenAIProviderSettings(TypedDict, total=False):
    """Provider settings for Azure OpenAI.

    You need to provide these settings if you are using Azure OpenAI, and you need to provide them for each Azure OpenAI model you use.

    **For embedding models:**
    **We only support the "**next-generation** Azure OpenAI API." Currently, you need to opt into this API in your Azure settings. We didn't want to start supporting the old API knowing it's going away.

    For agent models:
    We support both APIs for agentic models because our support comes from `pydantic_ai`, which supports both.
    """

    azure_resource_name: NotRequired[str]
    """The name of your Azure resource. This is used to identify your resource in Azure."""
    model_deployment: NotRequired[str]
    """The deployment name of the model you want to use. Important: While the OpenAI API uses the model name to identify the model, you must separately provide a codeweaver-compatible name for the model, as well as your Azure resource name here. We're open to PRs if you want to add a parser for model names that can extract the deployment name from them."""
    endpoint: NotRequired[str | None]
    """The endpoint for your Azure resource. This is used to send requests to your resource. Only provide the endpoint, not the full URL. For example, if your endpoint is `https://your-cool-resource.<region_name>.inference.ai.azure.com/v1`, you would only provide "your-cool-resource" here."""
    region_name: NotRequired[str]
    """The Azure region where your resource is located. This is used to route requests to the correct regional endpoint."""
    api_key: NotRequired[SecretStr | None]
    """Your Azure API key. If not provided, we'll assume you have your Azure credentials configured in another way, such as environment variables."""


class FastembedGPUProviderSettings(TypedDict, total=False):
    """Special settings for Fastembed-GPU provider.

    These settings only apply if you are using a Fastembed provider, installed the `codeweaver-mcp[provider-fastembed-gpu]` extra, have a CUDA-capable GPU, and have properly installed and configured the ONNX GPU runtime.
    You can provide these settings with your CodeWeaver embedding provider settings, or rerank provider settings. If you're using fastembed-gpu for both, we'll assume you are using the same settings for both if we find one of them.
    """

    cuda: NotRequired[bool | None]
    """Whether to use CUDA (if available). If `None`, will auto-detect. We'll generally assume you want to use CUDA if it's available unless you provide a `False` value here."""
    provider_settings: NotRequired[list[int] | None]
    """List of GPU device IDs to use. If `None`, we will try to detect available GPUs using `nvidia-smi` if we can find it. We recommend specifying them because our checks aren't perfect."""


type ProviderSpecificSettings = (
    FastembedGPUProviderSettings
    | AWSProviderSettings
    | AzureOpenAIProviderSettings
    | AzureCohereProviderSettings
)


class EmbeddingProviderSettings(BaseProviderSettings):
    """Settings for embedding models, including sparse embedding models. It validates that the model and provider settings are compatible and complete, reconciling environment variables and config file settings as needed.

    You must provide either `model_settings` or `sparse_model_settings`, but not both. To configure both, use two EmbeddingProviderSettings entries in your config.
    """

    model_settings: NotRequired[EmbeddingModelSettings | None]
    """Settings for the embedding model(s)."""
    sparse_model_settings: NotRequired[SparseEmbeddingModelSettings | None]
    """Settings for sparse embedding model(s)."""
    provider_settings: NotRequired[ProviderSpecificSettings | None]
    """Settings for specific providers, if any. Some providers have special settings that are required for them to work properly, but you may provide them by environment variables as well as in your config, or both."""


class RerankingProviderSettings(BaseProviderSettings):
    """Settings for re-ranking models."""

    model_settings: Required[RerankingModelSettings]
    """Settings for the re-ranking model(s)."""
    provider_settings: NotRequired[ProviderSpecificSettings | None]
    top_n: NotRequired[PositiveInt | None]


# Agent model settings are imported/defined from `pydantic_ai`

type ModelString = Annotated[
    str,
    Field(
        description="""The model string, as it appears in `pydantic_ai.models.KnownModelName`."""
    ),
]


class AgentProviderSettings(BaseProviderSettings):
    """Settings for agent models."""

    model: Required[ModelString | None]
    model_settings: Required[AgentModelSettings | None]
    """Settings for the agent model(s)."""


# ===========================================================================
# *                        UVICORN Server Settings
# ===========================================================================


class UvicornServerSettings(BasedModel):
    """
    Uvicorn server settings. Besides the port, these are all defaults for uvicorn.

    We expose them so you can configure them for advanced deployments inside your codeweaver.toml (or yaml or json).
    """

    # For the following, we just want to track if it's the default value or not (True/False), not the actual value.
    model_config = (
        ConfigDict(
            json_schema_extra={
                "TelemetryBoolProps": [
                    "host",
                    "name",
                    "ssl_keyfile",
                    "ssl_certfile",
                    "ssl_keyfile_password",
                    "ssl_version",
                    "ssl_cert_reqs",
                    "ssl_ca_certs",
                    "ssl_ciphers",
                    "root_path",
                    "headers",
                    "server_header",
                    "data_header",
                    "forwarded_allow_ips",
                    "env_file",
                    "log_config",
                ]
            }
        )
        | BasedModel.model_config
    )

    name: Annotated[str, Field(exclude=True)] = "CodeWeaver_http"
    host: str = "127.0.0.1"
    port: PositiveInt = 9328
    uds: str | None = None
    fd: int | None = None
    loop: LoopSetupType | str = "auto"
    http: type[asyncio.Protocol] | HTTPProtocolType | str = "auto"
    ws: type[asyncio.Protocol] | WSProtocolType | str = "auto"
    ws_max_size: PositiveInt = 16777216  # 16 MiB
    ws_max_queue: PositiveInt = 32
    ws_ping_interval: PositiveFloat = 20.0
    ws_ping_timeout: PositiveFloat = 20.0
    ws_per_message_deflate: bool = True
    lifespan: LifespanType = "auto"
    env_file: str | os.PathLike[str] | None = None
    log_config: LoggingConfigDict | None = None
    log_level: str | int | None = "info"
    access_log: bool = True
    use_colors: bool | None = None
    interface: InterfaceType = "auto"
    reload: bool = False  # TODO: We should add it, but we need to manage handling it mid-request.
    reload_dirs: list[str] | str | None = None
    reload_delay: PositiveFloat = 0.25
    reload_includes: list[str] | str | None = None
    reload_excludes: list[str] | str | None = None
    workers: int | None = None
    proxy_headers: bool = True
    server_header: bool = True
    data_header: bool = True
    forwarded_allow_ips: str | list[str] | None = None
    root_path: str = ""
    limit_concurrency: PositiveInt | None = None
    limit_max_requests: PositiveInt | None = None
    backlog: PositiveInt = 2048
    timeout_keep_alive: PositiveInt = 5
    timeout_notify: PositiveInt = 30
    timeout_graceful_shutdown: PositiveInt | None = None
    callback_notify: Callable[..., Awaitable[None]] | None = None
    ssl_keyfile: str | os.PathLike[str] | None = None
    ssl_certfile: str | os.PathLike[str] | None = None
    ssl_keyfile_password: SecretStr | None = None
    ssl_version: int | None = SSL_PROTOCOL_VERSION
    ssl_cert_reqs: int = ssl.CERT_NONE
    ssl_ca_certs: SecretStr | None = None
    ssl_ciphers: str = "TLSv1"
    headers: list[tuple[str, str]] | None = None
    factory: bool = False
    h11_max_incomplete_event_size: int | None = None


class UvicornServerSettingsDict(TypedDict, total=False):
    """TypedDict for Uvicorn server settings.

    Not intended to be used directly; used for internal type checking and validation.
    We're all adults here, so it's here if you want it.
    """

    name: NotRequired[str]
    host: NotRequired[str]
    port: NotRequired[PositiveInt]
    uds: NotRequired[str | None]
    fd: NotRequired[int | None]
    loop: NotRequired[LoopSetupType | str]
    http: NotRequired[type[asyncio.Protocol] | HTTPProtocolType | str]
    ws: NotRequired[type[asyncio.Protocol] | WSProtocolType | str]
    ws_max_size: NotRequired[PositiveInt]
    ws_max_queue: NotRequired[PositiveInt]
    ws_ping_interval: NotRequired[PositiveFloat]
    ws_ping_timeout: NotRequired[PositiveFloat]
    ws_per_message_deflate: NotRequired[bool]
    lifespan: NotRequired[LifespanType]
    env_file: NotRequired[str | os.PathLike[str] | None]
    log_config: NotRequired[LoggingConfigDict | None]
    log_level: NotRequired[str | int | None]
    access_log: NotRequired[bool]
    use_colors: NotRequired[bool | None]
    interface: NotRequired[InterfaceType]
    reload: NotRequired[bool]
    reload_dirs: NotRequired[list[str] | str | None]
    reload_delay: NotRequired[PositiveFloat]
    reload_includes: NotRequired[list[str] | str | None]
    reload_excludes: NotRequired[list[str] | str | None]
    workers: NotRequired[int | None]
    proxy_headers: NotRequired[bool]
    server_header: NotRequired[bool]
    data_header: NotRequired[bool]
    forwarded_allow_ips: NotRequired[str | list[str] | None]
    root_path: NotRequired[str]
    limit_concurrency: NotRequired[PositiveInt | None]
    limit_max_requests: NotRequired[PositiveInt | None]
    backlog: NotRequired[PositiveInt]
    timeout_keep_alive: NotRequired[PositiveInt]
    timeout_notify: NotRequired[PositiveInt]
    timeout_graceful_shutdown: NotRequired[PositiveInt | None]
    callback_notify: NotRequired[Callable[..., Awaitable[None]] | None]
    ssl_keyfile: NotRequired[str | os.PathLike[str] | None]
    ssl_certfile: NotRequired[str | os.PathLike[str] | None]
    ssl_keyfile_password: NotRequired[SecretStr | None]
    ssl_version: NotRequired[int | None]
    ssl_cert_reqs: NotRequired[int]
    ssl_ca_certs: NotRequired[SecretStr | None]
    ssl_ciphers: NotRequired[str]
    headers: NotRequired[list[tuple[str, str]] | None]
    factory: NotRequired[bool]
    h11_max_incomplete_event_size: NotRequired[int | None]


def default_config_file_locations(
    *, as_yaml: bool = False, as_json: bool = False
) -> tuple[str, ...]:
    """Get default file locations for configuration files."""
    # Determine base extensions
    extensions = (
        ["yaml", "yml"] if not as_yaml and not as_json else ["yaml", "yml"] if as_yaml else ["json"]
    )
    # Get user config directory
    user_config_dir = (
        os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        if platform.system() == "Windows"
        else os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    )

    # Build file paths maintaining precedence order
    base_paths = [
        (Path.cwd(), ".codeweaver.local"),
        (Path.cwd(), ".codeweaver"),
        (Path(user_config_dir) / "codeweaver", "settings"),
    ]

    # Generate all file paths using list comprehension
    file_paths = [
        str(base_dir / f"{filename}.{ext}")
        for base_dir, filename in base_paths
        for ext in extensions
    ]

    return tuple(file_paths)


# ===========================================================================
# *                    More TypedDict versions of Models
# ===========================================================================


class ProviderSettingsDict(TypedDict, total=False):
    """A dictionary representation of provider settings."""

    data: NotRequired[tuple[DataProviderSettings, ...] | None]
    embedding: NotRequired[tuple[EmbeddingProviderSettings, ...] | None]
    reranking: NotRequired[tuple[RerankingProviderSettings, ...] | None]
    # vector: NotRequired[tuple[VectorProviderSettings, ...] | None]
    agent: NotRequired[tuple[AgentProviderSettings, ...] | None]


type ProviderSettingsView = DictView[ProviderSettingsDict]


class CodeWeaverSettingsDict(TypedDict, total=False):
    """A serialized `CodeWeaverSettings` object."""

    project_path: NotRequired[Path | None]
    project_name: NotRequired[str | None]
    provider: NotRequired[ProviderSettingsDict | None]
    config_file: NotRequired[FilePath | None]
    token_limit: NotRequired[PositiveInt]
    max_file_size: NotRequired[PositiveInt]
    max_results: NotRequired[PositiveInt]
    server: NotRequired[FastMcpServerSettingsDict]
    logging: NotRequired[LoggingSettings]
    middleware_settings: NotRequired[MiddlewareOptions]
    project_root: NotRequired[Path | None]
    uvicorn_settings: NotRequired[UvicornServerSettingsDict]
    filter_settings: NotRequired[FileFilterSettingsDict]
    enable_background_indexing: NotRequired[bool]
    enable_telemetry: NotRequired[bool]
    enable_health_endpoint: NotRequired[bool]
    enable_statistics_endpoint: NotRequired[bool]
    enable_settings_endpoint: NotRequired[bool]
    enable_version_endpoint: NotRequired[bool]
    allow_identifying_telemetry: NotRequired[bool]
    enable_ai_intent_analysis: NotRequired[bool]
    enable_precontext: NotRequired[bool]


__all__ = (
    "AWSProviderSettings",
    "AgentProviderSettings",
    "AzureCohereProviderSettings",
    "AzureOpenAIProviderSettings",
    "BaseProviderSettings",
    "CodeWeaverSettingsDict",
    "ConnectionConfiguration",
    "ConnectionRateLimitConfig",
    "DataProviderSettings",
    "EmbeddingProviderSettings",
    "ErrorHandlingMiddlewareSettings",
    "FastMcpHttpRunArgs",
    "FastembedGPUProviderSettings",
    "FileFilterSettingsDict",
    "FiltersDict",
    "FormattersDict",
    "HandlersDict",
    "LoggersDict",
    "LoggingConfigDict",
    "LoggingMiddlewareSettings",
    "LoggingSettings",
    "MiddlewareOptions",
    "ModelString",
    "ProviderSettingsDict",
    "ProviderSettingsView",
    "ProviderSpecificSettings",
    "RateLimitingMiddlewareSettings",
    "RerankingProviderSettings",
    "RetryMiddlewareSettings",
    "RignoreSettings",
    "SerializableLoggingFilter",
    "SparseEmbeddingModelSettings",
    "UvicornServerSettings",
    "UvicornServerSettings",
    "UvicornServerSettingsDict",
    "default_config_file_locations",
)
