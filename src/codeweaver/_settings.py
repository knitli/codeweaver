# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# We need to override our generic models with specific types, and type overrides for narrower values is a good thing.
# pyright: reportIncompatibleMethodOverride=false,reportIncompatibleVariableOverride=false
"""Core settings and provider definitions."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
import re
import ssl

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, Any, Literal, NotRequired, Required, TypedDict, cast, is_typeddict

from fastmcp.contrib.bulk_tool_caller.bulk_tool_caller import BulkToolCaller
from fastmcp.server.auth.auth import OAuthProvider
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware, RetryMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware, StructuredLoggingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.timing import DetailedTimingMiddleware
from fastmcp.server.server import DuplicateBehavior
from fastmcp.tools.tool import Tool
from mcp.server.lowlevel.server import LifespanResultT
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    FieldSerializationInfo,
    PositiveFloat,
    PositiveInt,
    PrivateAttr,
    SecretStr,
    field_serializer,
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

from codeweaver._common import BaseEnum
from codeweaver.exceptions import ConfigurationError


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
                description="Default values for the formatter. [See the Python documentation for more details](https://docs.python.org/3/library/logging.html#logging.Formatter).",
            ),
        ]
    ]
    class_name: NotRequired[
        Annotated[
            str,
            Field(
                description="""The class name of the formatter in the form of an import path, like `logging.Formatter` or `rich.logging.RichFormatter`.""",
                alias="class",
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


class SerializableLoggingFilter(BaseModel, logging.Filter):
    """A logging.Filter object that implements a custom pydantic serializer.
    The filter can be serialized and deserialized using Pydantic.

    Uses regex patterns to apply filtering logic to log message text. Provide include and/or exclude patterns to filter messages. Include patterns are applied *after* exclude patterns (defaults to logging if there's a conflict)).

    If you provide a `simple_filter`, any patterns will only be applied to records that pass the simple filter.
    """

    simple_filter: Annotated[
        LoggerName | None,
        Field(
            default_factory=logging.Filter,
            description="A simple name filter that matches the `name` attribute of a `logging.Logger`. This is equivalent to using `logging.Filter(name)`.",
        ),
    ]

    include_pattern: Annotated[
        re.Pattern[str] | None,
        # NOTE: `include_pattern` and `exclude_pattern` are prime candidates for Python 3.14's `template strings`.
        # TODO: Once they become more available, we should use `raw template strings` here
        # See 👁️ https://docs.python.org/3.14/library/string.templatelib.html#template-strings
        BeforeValidator(validate_regex_pattern),
        Field(
            description="Regex pattern to filter the body text of log messages. Records matching this pattern will be *included* in log output."
        ),
    ] = None

    exclude_pattern: Annotated[
        re.Pattern[str] | None,
        BeforeValidator(validate_regex_pattern),
        Field(
            description="Regex pattern to filter the body text of log messages. Records matching this pattern will be *excluded* from log output."
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
                alias="class",
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
                description="Whether to apply this configuration incrementally or replace the existing configuration. [See the Python documentation for more details](https://docs.python.org/3/library/logging.config.html#logging-config-dict-incremental)."
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
                description="Logging configuration in dictionary format that matches the format expected by [`logging.config.dictConfig`](https://docs.python.org/3/library/logging.config.html)."
            ),
        ]
    ]
    rich_kwargs: NotRequired[
        Annotated[
            dict[str, Any],
            Field(
                description="Additional keyword arguments for the `rich` logging handler, [`rich.logging.RichHandler`], if enabled."
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
    model_kwargs: NotRequired[dict[str, Any] | None]
    other: NotRequired[dict[str, Any] | None]


class DataProviderSettings(BaseProviderSettings):
    """Settings for data providers."""


class EmbeddingModelSettings(TypedDict, total=False):
    """Embedding model settings."""

    model: Required[str]
    dimension: NotRequired[PositiveInt | None]
    data_type: NotRequired[str | None]
    custom_prompt: NotRequired[str | None]
    client_kwargs: NotRequired[dict[str, Any] | None]


class RerankingModelSettings(TypedDict, total=False):
    """Rerank model settings."""

    model: Required[str]
    custom_prompt: NotRequired[str | None]
    client_kwargs: NotRequired[dict[str, Any] | None]


class AWSProviderSettings(TypedDict, total=False):
    """Settings for AWS provider.

    You need to provide these settings if you are using Bedrock, and you need to provide them for each Bedrock model you use. It might be repetitive, but a lot of people have different credentials for different models/services.
    """

    region_name: Required[str]
    model_arn: Required[str]
    aws_access_key_id: NotRequired[str | None]
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
    api_key: NotRequired[str | None]
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
    api_key: NotRequired[str | None]
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
    """Settings for embedding models. It validates that the model and provider settings are compatible and complete, reconciling environment variables and config file settings as needed."""

    model_settings: Required[tuple[EmbeddingModelSettings, ...] | EmbeddingModelSettings]
    """Settings for the embedding model(s)."""
    provider_settings: NotRequired[
        tuple[ProviderSpecificSettings, ...] | ProviderSpecificSettings | None
    ]
    """Settings for specific providers, if any. Some providers have special settings that are required for them to work properly, but you may provide them by environment variables as well as in your config, or both."""


class RerankingProviderSettings(BaseProviderSettings):
    """Settings for re-ranking models."""

    model_settings: Required[RerankingModelSettings | tuple[RerankingModelSettings, ...] | None]
    """Settings for the re-ranking model(s)."""
    provider_settings: NotRequired[ProviderSpecificSettings | None]
    top_n: NotRequired[PositiveInt | None]


# Agent model settings are imported/defined from `pydantic_ai`


class AgentProviderSettings(BaseProviderSettings):
    """Settings for agent models."""

    models: Required[tuple[str, ...] | str | None]
    model_settings: Required[AgentModelSettings | tuple[AgentModelSettings, ...] | None]
    """Settings for the agent model(s)."""


class FastMcpHttpRunArgs(TypedDict, total=False):
    transport: Literal["http"]
    host: str | None
    port: PositiveInt | None
    log_level: Literal["debug", "info", "warning", "error"] | None
    path: str | None
    uvicorn_config: UvicornServerSettingsType | None
    middleware: list[ASGIMiddleware] | None


class FastMcpServerSettingsType(TypedDict, total=False):
    """TypedDict for FastMCP server settings.

    Not intended to be used directly; used for internal type checking and validation.
    """

    name: str
    instructions: str | None
    version: str | None
    lifespan: LifespanResultT | None  # type: ignore  # it's just for clarity
    include_tags: set[str] | None
    exclude_tags: set[str] | None
    transport: Literal["stdio", "http"] | None
    host: str | None
    port: PositiveInt | None
    path: str | None
    auth: OAuthProvider | None
    cache_expiration_seconds: float | None
    on_duplicate_tools: DuplicateBehavior | None
    on_duplicate_resources: DuplicateBehavior | None
    on_duplicate_prompts: DuplicateBehavior | None
    resource_prefix_format: Literal["protocol", "path"] | None
    middleware: list[Middleware | Callable[..., Any]] | None
    tools: list[Tool | Callable[..., Any]] | None
    dependencies: list[str] | None


# ===========================================================================
# *                        UVICORN Server Settings
# ===========================================================================


class UvicornServerSettings(BaseModel):
    """
    Uvicorn server settings. Besides the port, these are all defaults for uvicorn.

    We expose them so you can configure them for advanced deployments inside your codeweaver.toml (or yaml or json).
    """

    # For the following, we just want to track if it's the default value or not (True/False), not the actual value.
    model_config = ConfigDict(
        str_strip_whitespace=True,
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
        },
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


class UvicornServerSettingsType(TypedDict, total=False):
    """TypedDict for Uvicorn server settings.

    Not intended to be used directly; used for internal type checking and validation.
    """

    name: str
    host: str
    port: PositiveInt
    uds: str | None
    fd: int | None
    loop: LoopSetupType | str
    http: type[asyncio.Protocol] | HTTPProtocolType | str
    ws: type[asyncio.Protocol] | WSProtocolType | str
    ws_max_size: PositiveInt
    ws_max_queue: PositiveInt
    ws_ping_interval: PositiveFloat
    ws_ping_timeout: PositiveFloat
    ws_per_message_deflate: bool
    lifespan: LifespanType
    env_file: str | os.PathLike[str] | None
    log_config: LoggingConfigDict | None
    log_level: str | int | None
    access_log: bool
    use_colors: bool | None
    interface: InterfaceType
    reload: bool
    reload_dirs: list[str] | str | None
    reload_delay: PositiveFloat
    reload_includes: list[str] | str | None
    reload_excludes: list[str] | str | None
    workers: int | None
    proxy_headers: bool
    server_header: bool
    data_header: bool
    forwarded_allow_ips: str | list[str] | None
    root_path: str
    limit_concurrency: PositiveInt | None
    limit_max_requests: PositiveInt | None
    backlog: PositiveInt
    timeout_keep_alive: PositiveInt
    timeout_notify: PositiveInt
    timeout_graceful_shutdown: PositiveInt | None
    callback_notify: Callable[..., Awaitable[None]] | None
    ssl_keyfile: str | os.PathLike[str] | None
    ssl_certfile: str | os.PathLike[str] | None
    ssl_keyfile_password: SecretStr | None
    ssl_version: int | None
    ssl_cert_reqs: int
    ssl_ca_certs: SecretStr | None
    ssl_ciphers: str
    headers: list[tuple[str, str]] | None
    factory: bool
    h11_max_incomplete_event_size: int | None


# ===========================================================================
# *     PROVIDER ENUM - main provider enum for all Codeweaver providers
# ===========================================================================

type ProviderEnvVarInfo = tuple[str, str]


class ProviderEnvVars(TypedDict, total=False):
    """Provides information about environment variables used by a provider's client that are not part of CodeWeaver's settings.

    You can optionally use these to configure the provider's client, or you can use the equivalent CodeWeaver environment variables or settings.

    Each setting is a tuple of the form `(env_var_name, description)`, where `env_var_name` is the name of the environment variable and `description` is a brief description of what it does or the expected format.
    """

    note: NotRequired[str]
    api_key: NotRequired[ProviderEnvVarInfo]
    host: NotRequired[ProviderEnvVarInfo]
    """URL or hostname of the provider's API endpoint."""
    endpoint: NotRequired[ProviderEnvVarInfo]
    """A customer-specific endpoint hostname for the provider's API."""
    log_level: NotRequired[ProviderEnvVarInfo]
    tls_cert_path: NotRequired[ProviderEnvVarInfo]
    tls_key_path: NotRequired[ProviderEnvVarInfo]
    tls_on_off: NotRequired[ProviderEnvVarInfo]
    tls_version: NotRequired[ProviderEnvVarInfo]
    config_path: NotRequired[ProviderEnvVarInfo]
    region: NotRequired[ProviderEnvVarInfo]

    port: NotRequired[ProviderEnvVarInfo]
    path: NotRequired[ProviderEnvVarInfo]
    oauth: NotRequired[ProviderEnvVarInfo]

    other: NotRequired[dict[str, ProviderEnvVarInfo]]


class Provider(BaseEnum):
    """Enumeration of available providers."""

    VOYAGE = "voyage"
    FASTEMBED = "fastembed"

    QDRANT = "qdrant"

    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    COHERE = "cohere"
    GOOGLE = "google"
    X_AI = "x-ai"
    HUGGINGFACE_INFERENCE = "hf-inference"
    SENTENCE_TRANSFORMERS = "sentence-transformers"
    MISTRAL = "mistral"
    OPENAI = "openai"

    # OpenAI Compatible with OpenAIModel
    AZURE = "azure"  # supports rerank, but not w/ OpenAI API
    DEEPSEEK = "deepseek"
    FIREWORKS = "fireworks"
    GITHUB = "github"
    GROQ = "groq"  # yes, it's different from Grok...
    HEROKU = "heroku"
    MOONSHOT = "moonshot"
    OLLAMA = "ollama"  # supports rerank, but not w/ OpenAI API
    OPENROUTER = "openrouter"
    PERPLEXITY = "perplexity"
    TOGETHER = "together"
    VERCEL = "vercel"

    DUCKDUCKGO = "duckduckgo"
    TAVILY = "tavily"

    UNSET = "unset"

    @classmethod
    def validate(cls, value: str) -> BaseEnum:
        """Validate provider-specific settings."""
        with contextlib.suppress(AttributeError, KeyError, ValueError):
            if value_in_self := cls.from_string(value.strip()):
                return value_in_self
        # TODO: We need to allow for dynamic providers in the future, we would check if there's a provider class registered for the value, then register the provider here with `cls.add_member("NEW_PROVIDER", "new_provider")`.
        raise ConfigurationError(f"Invalid provider: {value}")

    @property
    def other_env_vars(  # noqa: C901
        self,
    ) -> (
        ProviderEnvVars
        | tuple[ProviderEnvVars, ProviderEnvVars]
        | tuple[ProviderEnvVars, ProviderEnvVars, ProviderEnvVars]
        | None
    ):
        """Get the environment variables used by the provider's client that are not part of CodeWeaver's settings."""
        httpx_env_vars = {
            "other": {
                "http_proxy": ("HTTPS_PROXY", "HTTP proxy for requests"),
                "ssl_cert_file": ("SSL_CERT_FILE", "Path to the SSL certificate file for requests"),
            }
        }
        match self:
            case Provider.QDRANT:
                return ProviderEnvVars(
                    note="Qdrant supports setting **all** configuration options using environment variables. Like with CodeWeaver, nested variables are separated by double underscores (`__`). For all options, see [the Qdrant documentation](https://qdrant.tech/documentation/guides/configuration/)",
                    log_level=("QDRANT__LOG_LEVEL", "DEBUG, INFO, WARNING, or ERROR"),
                    api_key=("QDRANT__SERVICE__API_KEY", "API key for Qdrant service"),
                    tls_on_off=(
                        "QDRANT__SERVICE__ENABLE_TLS",
                        "Enable TLS for Qdrant service, expects truthy or false value (e.g. 1 for on, 0 for off).",
                    ),
                    tls_cert_path=(
                        "QDRANT__TLS__CERT",
                        "Path to the TLS certificate file for Qdrant service. Only needed if using a self-signed certificate. If you're using qdrant-cloud, you don't need this.",
                    ),
                    host=("QDRANT__SERVICE__HOST", "Hostname or URL of the Qdrant service"),
                    port=("QDRANT__SERVICE__HTTP_PORT", "Port number for the Qdrant service"),
                )
            case Provider.VOYAGE:
                return ProviderEnvVars(
                    api_key=("VOYAGE_API_KEY", "API key for Voyage service"),
                    **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                )
            case Provider.AZURE:
                # Azure has env vars by model provider, so we return a tuple of them.
                return (
                    ProviderEnvVars(
                        note="These variables are for the Azure OpenAI service.",
                        api_key=("AZURE_OPENAI_API_KEY", "API key for Azure OpenAI service"),
                        endpoint=("AZURE_OPENAI_ENDPOINT", "Endpoint for Azure OpenAI service"),
                        region=("AZURE_OPENAI_REGION", "Region for Azure OpenAI service"),
                        **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                    ),
                    ProviderEnvVars(
                        note="These variables are for the Azure Cohere service.",
                        api_key=("AZURE_COHERE_API_KEY", "API key for Azure Cohere service"),
                        endpoint=("AZURE_COHERE_ENDPOINT", "Endpoint for Azure Cohere service"),
                        region=("AZURE_COHERE_REGION", "Region for Azure Cohere service"),
                        **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                    ),
                    cast(ProviderEnvVars, self.OPENAI.other_env_vars),
                )
            case Provider.VERCEL:
                return (
                    ProviderEnvVars(
                        note="You may also use the OpenAI-compatible environment variables with Vercel, since it uses the OpenAI client.",
                        api_key=("AI_GATEWAY_API_KEY", "API key for Vercel service"),
                        **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                    ),
                    ProviderEnvVars(api_key=("VERCEL_OIDC_TOKEN", "OIDC token for Vercel service")),
                    cast(ProviderEnvVars, self.OPENAI.other_env_vars),
                )
            case Provider.TOGETHER:
                return (
                    ProviderEnvVars(
                        note="These variables are for the Together service.",
                        api_key=("TOGETHER_API_KEY", "API key for Together service"),
                        **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                    ),
                    cast(ProviderEnvVars, self.OPENAI.other_env_vars),
                )
            case Provider.HEROKU:
                return (
                    ProviderEnvVars(
                        note="These variables are for the Heroku service.",
                        api_key=("INFERENCE_KEY", "API key for Heroku service"),
                        host=("INFERENCE_URL", "Host URL for Heroku service"),
                        other={"model_id": ("INFERENCE_MODEL_ID", "Model ID for Heroku service")},
                        **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                    ),
                    cast(ProviderEnvVars, self.OPENAI.other_env_vars),
                )
            case Provider.DEEPSEEK:
                return (
                    ProviderEnvVars(
                        note="These variables are for the DeepSeek service.",
                        api_key=("DEEPSEEK_API_KEY", "API key for DeepSeek service"),
                        **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                    ),
                    cast(ProviderEnvVars, self.OPENAI.other_env_vars),
                )
            case (
                Provider.OPENAI
                | Provider.FIREWORKS
                | Provider.GITHUB
                | Provider.X_AI
                | Provider.GROQ
                | Provider.MOONSHOT
                | Provider.OLLAMA
                | Provider.OPENROUTER
                | Provider.PERPLEXITY
            ):
                return ProviderEnvVars(
                    note="These variables are for any OpenAI-compatible service, including OpenAI itself, Azure OpenAI, and others -- any provider that we use the OpenAI client to connect to.",
                    api_key=(
                        "OPENAI_API_KEY",
                        "API key for OpenAI-compatible services (not necessarily an API key *for* OpenAI). The OpenAI client also requires an API key, even if you don't actually need one for your provider -- in that case, use a mock value like 'MADEUPAPIKEY'",
                    ),
                    log_level=("OPENAI_LOG", "One of: 'debug', 'info', 'warning', 'error'"),
                    **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                )
            case Provider.HUGGINGFACE_INFERENCE:
                return ProviderEnvVars(
                    note="Hugging Face allows for setting many configuration options by environment variable. See [the Hugging Face documentation](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables) for more details.",
                    api_key=("HF_TOKEN", "API key/token for Hugging Face service"),
                    log_level=(
                        "HF_HUB_VERBOSITY",
                        "One of: 'debug', 'info', 'warning', 'error', or 'critical'",
                    ),
                    **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                )
            case Provider.BEDROCK:
                return ProviderEnvVars(
                    note="AWS allows for setting many configuration options by environment variable. See [the AWS documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-environment-variables) for more details. Because AWS has multiple authentication methods, and ways to configure settings, we don't provide them here. We'd just confuse people. Unlike other providers, we also don't check for AWS's environment variables, we just assume you're authorized to do what you need to do."
                )
            case Provider.COHERE:
                return ProviderEnvVars(
                    api_key=("COHERE_API_KEY", "Your Cohere API Key"),
                    host=("CO_API_URL", "Host URL for Cohere service"),
                    **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                )
            case Provider.TAVILY:
                return ProviderEnvVars(
                    api_key=("TAVILY_API_KEY", "Your Tavily API Key"),
                    **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                )
            case Provider.GOOGLE:
                return ProviderEnvVars(
                    api_key=("GEMINI_API_KEY", "Your Google Gemini API Key"),
                    **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                )
            case Provider.MISTRAL:
                return ProviderEnvVars(
                    api_key=("MISTRAL_API_KEY", "Your Mistral API Key"),
                    **httpx_env_vars,  # pyright: ignore[reportArgumentType]
                )
            case _:
                return None

    @property
    def is_huggingface_model_provider(self) -> bool:
        """Check if the provider is a Hugging Face model provider."""
        return self in {
            Provider.HUGGINGFACE_INFERENCE,
            Provider.FASTEMBED,
            Provider.GROQ,
            Provider.SENTENCE_TRANSFORMERS,
            Provider.FIREWORKS,
            Provider.OLLAMA,
            Provider.TOGETHER,
        }

    @property
    def uses_openai_api(self) -> bool:
        """Check if the provider uses the OpenAI API."""
        return self in {
            Provider.OPENAI,
            Provider.AZURE,
            Provider.DEEPSEEK,
            Provider.FIREWORKS,
            Provider.GITHUB,
            Provider.X_AI,
            Provider.GROQ,
            Provider.HEROKU,
            Provider.MOONSHOT,
            Provider.OLLAMA,
            Provider.OPENROUTER,
            Provider.PERPLEXITY,
            Provider.TOGETHER,
            Provider.VERCEL,
        }

    @staticmethod
    def _flatten_envvars(env_vars: ProviderEnvVars) -> list[ProviderEnvVarInfo]:
        """Flatten a ProviderEnvVars TypedDict into a list of ProviderEnvVarInfo tuples."""
        found_vars: list[ProviderEnvVarInfo] = []
        for key, value in env_vars.items():
            if key not in ("note", "other") and isinstance(value, tuple):
                found_vars.append((key, value))  # pyright: ignore[reportArgumentType]
            elif key == "other" and isinstance(value, dict) and value:
                found_vars.extend(
                    (key, nested_value)
                    for nested_value in value.values()  # type: ignore
                )
        return found_vars

    @classmethod
    def all_envs(cls) -> tuple[tuple[Provider, ProviderEnvVarInfo], ...]:
        """Get all environment variables used by all providers."""
        found_vars: list[tuple[Provider, ProviderEnvVarInfo]] = []
        for p in cls:
            if (v := p.other_env_vars) is not None and is_typeddict(v):
                # singleton
                found_vars.extend(cls._flatten_envvars(v))  # pyright: ignore[reportArgumentType]
            if isinstance(v, tuple):
                found_vars.extend(cls._flatten_envvars(v) for v in v if is_typeddict(v))  # pyright: ignore[reportArgumentType]
        return tuple(found_vars)

    def is_embedding_provider(self) -> bool:
        """Check if the provider is an embedding provider."""
        from codeweaver._capabilities import get_provider_kinds

        return ProviderKind.EMBEDDING in get_provider_kinds(self)

    def is_sparse_provider(self) -> bool:
        """Check if the provider is a sparse embedding provider."""
        from codeweaver._capabilities import get_provider_kinds

        return ProviderKind.SPARSE_EMBEDDING in get_provider_kinds(self)

    def is_reranking_provider(self) -> bool:
        """Check if the provider is a reranking provider."""
        from codeweaver._capabilities import get_provider_kinds

        return ProviderKind.RERANKING in get_provider_kinds(self)


class ProviderKind(BaseEnum):
    """Enumeration of available provider kinds."""

    DATA = "data"
    """Provider for data retrieval and processing (e.g. Tavily)"""
    EMBEDDING = "embedding"
    """Provider for text embedding (e.g. Voyage)"""
    SPARSE_EMBEDDING = "sparse_embedding"
    """Provider for sparse text embedding (traditional indexed search, more-or-less).

    Sparse embeddings tend to be very fast and lightweight. We only support local providers (currently Fastembed and Sentence Transformers), because you probably won't know they're running.
    While vector embeddings are more powerful and flexible, sparse embeddings can be a force multiplier that improves overall results when used in combination with vector embeddings.
    Our default vectorstore, Qdrant, supports storing multiple vectors on a "point", which allows you to combine sparse and dense embeddings in a single search.
    """
    RERANKING = "reranking"
    """Provider for re-ranking (e.g. Voyage)"""
    VECTOR_STORE = "vector-store"
    """Provider for vector storage (e.g. Qdrant)"""
    AGENT = "agent"
    """Provider for agents (e.g. OpenAI or Anthropic)"""

    UNSET = "unset"
    """A sentinel setting to identify when a `ProviderKind` is not set or is configured."""

    @property
    def settings_object(self) -> object:
        """Get the settings object for this provider kind."""
        if self == ProviderKind.DATA:
            return DataProviderSettings
        if self == ProviderKind.EMBEDDING:
            return EmbeddingProviderSettings
        if self == ProviderKind.RERANKING:
            return RerankingProviderSettings
        if self == ProviderKind.AGENT:
            return AgentProviderSettings
        raise ConfigurationError(f"ProviderKind {self} does not have a settings object.")


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
