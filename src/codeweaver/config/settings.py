# sourcery skip: lambdas-should-be-short, name-type-suffix, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# We need to override our generic models with specific types, and type overrides for narrower values is a good thing.
"""Unified configuration system for CodeWeaver.

Provides a centralized settings system using pydantic-settings with
clear precedence hierarchy and validation.
"""

from __future__ import annotations

import inspect
import logging
import os

from collections.abc import Callable
from importlib import util
from pathlib import Path
from typing import Annotated, Any, Literal, Self, Unpack, cast, get_origin, overload

from fastmcp.server.server import DuplicateBehavior
from mcp.server.auth.settings import AuthSettings
from mcp.server.lowlevel.server import LifespanResultT
from pydantic import (
    DirectoryPath,
    Field,
    FilePath,
    PositiveInt,
    PrivateAttr,
    ValidationError,
    computed_field,
)
from pydantic.fields import ComputedFieldInfo, FieldInfo
from pydantic.networks import HttpUrl
from pydantic_core import from_json, to_json
from pydantic_settings import (
    AWSSecretsManagerSettingsSource,
    AzureKeyVaultSettingsSource,
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    GoogleSecretManagerSettingsSource,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)

from codeweaver.common.utils.checks import is_test_environment
from codeweaver.common.utils.lazy_importer import lazy_import
from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.config.chunker import ChunkerSettings, DefaultChunkerSettings
from codeweaver.config.indexer import DefaultIndexerSettings, IndexerSettings
from codeweaver.config.logging import DefaultLoggingSettings, LoggingSettings
from codeweaver.config.mcp import MCPServerConfig, StdioCodeWeaverConfig
from codeweaver.config.middleware import DefaultMiddlewareSettings, MiddlewareOptions
from codeweaver.config.providers import AllDefaultProviderSettings, ProviderSettings
from codeweaver.config.server_defaults import (
    DefaultEndpointSettings,
    DefaultFastMcpHttpRunArgs,
    DefaultUvicornSettings,
)
from codeweaver.config.telemetry import DefaultTelemetrySettings, TelemetrySettings
from codeweaver.config.types import (
    CodeWeaverSettingsDict,
    EndpointSettingsDict,
    FastMcpHttpRunArgs,
    FastMcpServerSettingsDict,
    StdioCodeWeaverConfigDict,
    UvicornServerSettings,
)
from codeweaver.core.types.aliases import FilteredKeyT
from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.models import BasedModel, clean_sentinel_from_schema
from codeweaver.core.types.sentinel import UNSET, Unset
from codeweaver.mcp.middleware import McpMiddleware


logger = logging.getLogger(__name__)


def _determine_setting(
    field_name: str, field_info: FieldInfo, obj: BaseSettings | BasedModel
) -> Any:
    """Determine the correct value for a setting field that was Unset."""
    if (
        isinstance(field_info.default, Unset)
        and hasattr(obj, "_defaults")
        and (defaults := obj._defaults() if callable(obj._defaults) else obj._defaults)  # type: ignore
        and (value := defaults.get(field_name))  # type: ignore
    ):
        return value  # type: ignore
    if (
        (annotation := field_info.annotation)
        and hasattr(annotation, "__args__")
        and (args := annotation.__args__)
        and (other_sources := tuple(arg for arg in args if arg is not Unset and arg is not None))
        and (other := other_sources[0])
    ):
        # Don't return class references or typing constructs - return None instead
        # This prevents TypedDict classes and Annotated types from being returned as values
        if inspect.isclass(other) or get_origin(other) is not None:
            return None
        return other
    return None


def _process_nested_value(value: Any) -> Any:
    """Process a nested value, ensuring all fields are set."""
    if isinstance(value, BaseSettings | BasedModel):
        return ensure_set_fields(value)
    if isinstance(value, list):
        return [
            ensure_set_fields(item) if isinstance(item, BaseSettings | BasedModel) else item
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: ensure_set_fields(item) if isinstance(item, BaseSettings | BasedModel) else item
            for key, item in value.items()
        }  # type: ignore
    return value


def _should_set_field(value: Any, field_type: Any) -> bool:
    """Check if a None value should be set for a field based on its type annotation."""
    if value is not None:
        return True
    if not field_type:
        return True
    args = getattr(field_type, "__args__", None)
    return type(None) in args if args else True


def ensure_set_fields(obj: BaseSettings | BasedModel) -> BaseSettings | BasedModel:
    """Ensure all fields in a pydantic model are set, replacing Unset with None where applicable."""
    for field_name in type(obj).model_fields:
        value = getattr(obj, field_name)

        if not isinstance(value, Unset):
            setattr(obj, field_name, _process_nested_value(value))
            continue

        # Handle Unset values
        field_info = type(obj).model_fields[field_name]
        new_value = _determine_setting(field_name, field_info, obj)

        # Handle class references - instantiate if it's a BaseSettings/BasedModel subclass
        if inspect.isclass(new_value) and issubclass(new_value, BaseSettings | BasedModel):
            new_value = ensure_set_fields(new_value())

        # Check if None is acceptable for this field
        field_type = field_info.annotation
        if not _should_set_field(new_value, field_type):
            continue

        setattr(obj, field_name, new_value)

    return obj


DEFAULT_BASE_MIDDLEWARE = [
    f"codeweaver.mcp.middleware.{mw}"
    for mw in (
        "ResponseCachingMiddleware",
        "ErrorHandlingMiddleware",
        "StatisticsMiddleware",
        "LoggingMiddleware",
    )
]

DEFAULT_HTTP_MIDDLEWARE = [
    *DEFAULT_BASE_MIDDLEWARE[:-1],
    "codeweaver.mcp.middleware.RateLimitingMiddleware",
    "codeweaver.mcp.middleware.RetryMiddleware",
    "codeweaver.mcp.middleware.StructuredLoggingMiddleware",
]
_sort_order = (
    "ResponseCachingMiddleware",
    "RateLimitingMiddleware",
    "RetryMiddleware",
    "LoggingMiddleware",
    "StructuredLoggingMiddleware",
    "ErrorHandlingMiddleware",
    "StatisticsMiddleware",
)


class BaseFastMcpServerSettings(BasedModel):
    """Base settings for FastMCP server configurations."""

    transport: Annotated[
        Literal["stdio", "streamable-http", "http"] | None,
        Field(
            description="""Transport protocol to use for the FastMCP server. Can be 'stdio', 'streamable-http', or 'http' (which is an alias for streamable-http). These values are always set by CodeWeaver depending on context, so users typically don't need to set this value themselves."""
        ),
    ] = None

    # like Highlander, there can only be one.
    on_duplicate_tools: DuplicateBehavior | None = "replace"
    on_duplicate_resources: DuplicateBehavior | None = "replace"
    on_duplicate_prompts: DuplicateBehavior | None = "replace"
    resource_prefix_format: Literal["protocol", "path"] | None = None
    auth: AuthSettings | None = None

    middleware: list[type[McpMiddleware]] = Field(
        default_factory=lambda: sorted(
            DEFAULT_BASE_MIDDLEWARE, key=lambda mw: _sort_order.index(mw.split(".")[-1])
        ),
        description="""Mcp Middleware classes (classes that subclass and implement `fastmcp.server.middleware.middleware.Middleware`). CodeWeaver includes several middleware by default, and always includes its own required middleware. Setting this field will override default (not required) middleware. Options are set in the `middleware` field of `CodeWeaverSettings`.""",
    )

    @computed_field
    @property
    def name(self) -> str:
        """Get the name of the server based on transport."""
        return (
            "CodeWeaver MCP HTTP Server"
            if self.transport in ("http", "streamable-http")
            else "CodeWeaver MCP Bridge"
        )

    @computed_field
    @property
    def include_tags(self) -> set[str]:
        """Tags for included resources, tools, and prompts."""
        return {"external", "user", "code-context", "agent-api", "public", "human-api"}

    @computed_field
    @property
    def exclude_tags(self) -> set[str]:
        """Tags for excluded resources, tools, and prompts."""
        return {
            "internal",
            "debug",
            "experimental",
            "context-agent-api",
            "system",
            "admin",
            "testing",
        }

    @computed_field
    @property
    def instructions(self) -> str:
        """Get instruction prompt for the server. This is a literal string that can't be set by the user. The `instructions` field provides guidance to MCP clients on how to interact with CodeWeaver."""
        return """CodeWeaver is an advanced code search and analysis tool. It uses cutting edge vector search techniques (sparse and dense embeddings) to find relevant code and documentation snippets based on natural language queries. Code snippets contain rich semantic and relational information about their context in the codebase, with support for over 160 languages. CodeWeaver has only one powerful tool: `find_code`."""

    def _telemetry_handler(self, _serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """Handle telemetry anonymization on dict fields. Set booleans based on non-default values."""
        if self.transport == "stdio":
            if self.middleware == DEFAULT_BASE_MIDDLEWARE:
                return _serialized_self | {"middleware": False}
            return _serialized_self | {"middleware": True}
        # we're dealing with http now
        if not (run_args := getattr(self, "run_args", None)):
            return _serialized_self | {"middleware": self.middleware != DEFAULT_HTTP_MIDDLEWARE}
        if uvicorn_config := run_args.get("uvicorn_config"):
            run_args["uvicorn_config"] = UvicornServerSettings.model_validate(
                uvicorn_config
            ).serialize_for_telemetry()
        return _serialized_self

    def _telemetry_keys(self) -> None:
        return None

    def as_settings(self) -> FastMcpServerSettingsDict:
        """Convert to FastMcpServerSettingsDict for use with FastMCP server."""
        return FastMcpServerSettingsDict(**self.model_dump(exclude_none=True))


class FastMcpStdioServerSettings(BaseFastMcpServerSettings):
    """Settings for FastMCP stdio server configurations."""

    transport: Literal["stdio"] = "stdio"


class FastMcpHttpServerSettings(BaseFastMcpServerSettings):
    """Settings for FastMCP HTTP server configurations."""

    transport: Literal["streamable-http", "http"] = "streamable-http"

    run_args: FastMcpHttpRunArgs = Field(
        default_factory=lambda: DefaultFastMcpHttpRunArgs,
        description="""Run arguments for the FastMCP HTTP server.""",
    )

    lifespan: LifespanResultT | None = None

    middleware: list[type[McpMiddleware]] = Field(
        default_factory=lambda: sorted(
            DEFAULT_HTTP_MIDDLEWARE, key=lambda mw: _sort_order.index(mw.split(".")[-1])
        ),
        description="""Mcp Middleware classes (classes that subclass and implement `fastmcp.server.middleware.middleware.Middleware`). CodeWeaver includes several middlewares by default, and always includes its own required middlewares. Setting this field will override default (not required) middlewares.""",
    )


if not ProviderSettings.__pydantic_complete__:
    _ = ProviderSettings.model_rebuild()


@overload
def _resolve_env_settings_path(*, directory: Literal[False]) -> FilePath | Unset: ...
@overload
def _resolve_env_settings_path(*, directory: Literal[True]) -> DirectoryPath | Unset: ...
def _resolve_env_settings_path(*, directory: bool = False) -> FilePath | DirectoryPath | Unset:
    """Resolve the configuration file path or project directory path from environment variable, if set."""
    if (
        directory
        and (env_var := os.environ.get("CODEWEAVER_PROJECT_PATH"))
        and (env_path := Path(env_var))
        and env_path.exists()
        and env_path.is_dir()
    ):
        return env_path
    if directory:
        return UNSET
    if (
        (env_var := os.environ.get("CODEWEAVER_CONFIG_FILE"))
        and (env_config := Path(env_var))
        and env_config.exists()
        and env_config.is_file()
    ):
        return env_config
    return UNSET


class CodeWeaverSettings(BaseSettings):
    """Main configuration model following pydantic-settings patterns.

    Configuration precedence (highest to lowest):
    1. Environment variables (CODEWEAVER_*)
    2. Local config (codeweaver.local.toml (or .yaml, .yml, .json) in current directory)
    3. Project config (codeweaver.toml (or .yaml, .yml, .json) in project root)
    4. User config (~/codeweaver.toml (or .yaml, .yml, .json))
    5. Global config (/etc/codeweaver.toml (or .yaml, .yml, .json))
    6. Defaults

    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        cli_kebab_case=True,
        extra="allow",  # Allow extra fields in the configuration for plugins/extensions
        field_title_generator=cast(
            Callable[[str, FieldInfo | ComputedFieldInfo], str],
            BasedModel.model_config["field_title_generator"],  # type: ignore
        ),
        json_schema_extra=clean_sentinel_from_schema,
        nested_model_default_partial_update=True,
        from_attributes=True,
        env_ignore_empty=True,
        env_nested_delimiter="__",
        env_nested_max_split=-1,
        env_prefix="CODEWEAVER_",  # environment variables will be prefixed with CODEWEAVER_
        # keep secrets in user config dir
        str_strip_whitespace=True,
        title="CodeWeaver Settings",
        use_attribute_docstrings=True,
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        # spellchecker:off
        # NOTE: Config sources are set in `settings_customise_sources` method below
        # spellchecker:on
    )

    # Core settings
    project_path: Annotated[
        DirectoryPath | Unset,
        Field(
            description="""Root path of the codebase to analyze. CodeWeaver will try to detect the project path automatically if you don't provide one.""",
            validate_default=False,
        ),
    ] = _resolve_env_settings_path(directory=True)

    project_name: Annotated[
        str | Unset,
        Field(
            description="""Project name (auto-detected from directory if None)""",
            validate_default=False,
        ),
    ] = os.environ.get("CODEWEAVER_PROJECT_NAME", UNSET)

    provider: Annotated[
        ProviderSettings | Unset,
        Field(
            description="""Provider and model configurations for agents, data, embedding, reranking, sparse embedding, and vector store providers. Will default to default profile if not provided.""",
            validate_default=False,
        ),
    ] = UNSET

    config_file: Annotated[
        FilePath | Unset,
        Field(description="""Path to the configuration file, if any""", exclude=True),
    ] = _resolve_env_settings_path(directory=False)

    # Performance settings
    token_limit: Annotated[
        PositiveInt | Unset,
        Field(description="""Maximum tokens per response""", validate_default=False),
    ] = UNSET
    max_file_size: Annotated[
        PositiveInt | Unset,
        Field(description="""Maximum file size to process in bytes""", validate_default=False),
    ] = UNSET
    max_results: Annotated[
        PositiveInt | Unset,
        Field(
            description="""Maximum code matches to return. Because CodeWeaver primarily indexes ast-nodes, a page can return multiple matches per file, so this is not the same as the number of files returned. This is the maximum number of code matches returned in a single response. The default is 30.""",
            validate_default=False,
        ),
    ] = UNSET
    mcp_server: Annotated[
        FastMcpHttpServerSettings | Unset,
        Field(
            description="""Optionally customize server settings for the HTTP MCP server.""",
            validate_default=False,
        ),
    ] = UNSET
    stdio_server: Annotated[
        FastMcpStdioServerSettings | Unset,
        Field(description="""Settings for stdio MCP servers.""", validate_default=False),
    ] = UNSET

    logging: Annotated[
        LoggingSettings | Unset,
        Field(description="""Logging configuration""", validate_default=False),
    ] = UNSET

    middleware: Annotated[
        MiddlewareOptions | Unset,
        Field(description="""Middleware settings""", validate_default=False),
    ] = UNSET

    indexer: Annotated[
        IndexerSettings | Unset, Field(description="""Indexer settings""", validate_default=False)
    ] = UNSET

    chunker: Annotated[
        ChunkerSettings | Unset,
        Field(description="""Chunker system configuration""", validate_default=False),
    ] = UNSET

    endpoints: Annotated[
        EndpointSettingsDict | Unset,
        Field(description="""Endpoint settings for optional endpoints.""", validate_default=False),
    ] = UNSET

    uvicorn: Annotated[
        UvicornServerSettings | Unset,
        Field(
            description="""
        Settings for the Uvicorn management server. If you want to configure uvicorn settings for the mcp http server, pass them to `mcp_server.run_args.uvicorn_config`.

        Example:
        ```toml
        # this will set uvicorn settings for the management server:
        [uvicorn]
        log_level = "debug"

        # this will set uvicorn settings for the mcp http server:
        [mcp_server.run_args.uvicorn_config]
        log_level = "debug"
        ```
        """,
            validate_default=False,
        ),
    ] = UNSET

    telemetry: Annotated[
        TelemetrySettings | Unset,
        Field(description="""Telemetry configuration""", validate_default=False),
    ] = UNSET

    # Management Server (Always HTTP, independent of MCP transport)
    management_host: Annotated[
        str | Unset,
        Field(
            description="""Management server host (independent of MCP transport). Default is 127.0.0.1 (localhost)."""
        ),
    ] = UNSET
    management_port: Annotated[
        PositiveInt | Unset,
        Field(
            description="""Management server port (always HTTP, for health/stats/metrics). Default is 9329."""
        ),
    ] = UNSET

    default_mcp_config: Annotated[
        MCPServerConfig | Unset,
        Field(
            description="""Default MCP server configuration for mcp clients. Setting this makes it quick and easy to add codeweaver to any mcp.json file using `cw init`. Defaults to a streamable-http CodeWeaver server at `http://127.0.0.1:9328`.""",
            validate_default=False,
        ),
    ] = UNSET

    profile: Annotated[  # ty: ignore[invalid-assignment]
        Literal["recommended", "quickstart", "testing"] | Unset | None,
        Field(
            description="""Use a premade provider profile.  The recommended profile uses Voyage AI for top-quality embedding and reranking, but requires an API key. The quickstart profile is entirely free and local, and does not require any API key. It sacrifices some search quality and performance compared to the recommended profile. The testing profile is only recommended for testing -- it uses an in-memory vector store and very light weight local models. The testing profile is also CodeWeaver's backup system when a cloud embedding or vector store provider isn't available. Both the quickstart and recommended profiles default to a local qdrant instance for the vector store. If you want to use a cloud or remote instance (which we recommend) you must also provide a URL for it, either with the environment variable CODEWEAVER_VECTOR_STORE_URL or in your codeweaver config in the vector_store settings.""",
            validate_default=False,
        ),
    ] = (
        profile
        if (profile := os.environ.get("CODEWEAVER_PROFILE"))
        and profile in ("recommended", "quickstart", "testing")
        else UNSET
    )  # ty: ignore[invalid-assignment]

    __version__: Annotated[
        str,
        Field(
            description="""Schema version for CodeWeaver settings""",
            pattern=r"\d{1,2}\.\d{1,3}\.\d{1,3}",
            alias="schema_version",
        ),
    ] = "1.1.0"

    schema_: HttpUrl = Field(
        description="URL to the CodeWeaver settings schema",
        default_factory=lambda data: HttpUrl(
            f"https://raw.githubusercontent.com/knitli/codeweaver/main/schema/v{data.get('__version__', data.get('schema_version')) or '1.1.0'}/codeweaver.schema.json"
        ),
    )

    _map: Annotated[DictView[CodeWeaverSettingsDict] | None, PrivateAttr()] = None

    _unset_fields: Annotated[
        set[str], Field(description="Set of fields that were unset", exclude=True)
    ] = set()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize CodeWeaverSettings, loading from config file if provided."""
        if (config := kwargs.get("config_file")) and config is not UNSET:
            content = from_json(config.read_bytes())
            if content and content != kwargs:
                kwargs |= content
        super().__init__(**kwargs)

    def model_post_init(self, __context: Any, /) -> None:
        """Post-initialization validation."""
        self._unset_fields = {
            field for field in type(self).model_fields if getattr(self, field) is Unset
        }
        self.project_path = (
            lazy_import("codeweaver.common.utils", "get_project_path")()
            if isinstance(self.project_path, Unset)
            else self.project_path
        )  # type: ignore
        self.project_name = (
            cast(DirectoryPath, self.project_path).name  # type: ignore
            if isinstance(self.project_name, Unset)
            else self.project_name  # type: ignore
        )
        self.profile = None if isinstance(self.profile, Unset) else self.profile
        if self.profile:
            self._setup_profile()
        else:
            self.provider = (
                ProviderSettings.model_validate(AllDefaultProviderSettings)
                if isinstance(self.provider, Unset) or self.provider is None
                else self.provider
            )
        # Serena uses 17,000 tokens *each turn*, so I feel like 30,000 is a reasonable default limit. We'll strive to keep it well under that.
        self.token_limit = 30_000 if isinstance(self.token_limit, Unset) else self.token_limit
        self.max_file_size = (
            1 * 1024 * 1024 if isinstance(self.max_file_size, Unset) else self.max_file_size
        )
        self.max_results = 30 if isinstance(self.max_results, Unset) else self.max_results
        self.mcp_server = (
            FastMcpHttpServerSettings() if isinstance(self.mcp_server, Unset) else self.mcp_server
        )
        self.stdio_server = (
            FastMcpStdioServerSettings()
            if isinstance(self.stdio_server, Unset)
            else self.stdio_server
        )
        self.middleware = (
            DefaultMiddlewareSettings if isinstance(self.middleware, Unset) else self.middleware
        )
        self.logging = DefaultLoggingSettings if isinstance(self.logging, Unset) else self.logging
        # by default, IndexerSettings has `rignore_options` UNSET, but that needs to be deferred until after CodeWeaverSettings is initialized
        self.indexer = IndexerSettings() if isinstance(self.indexer, Unset) else self.indexer
        self.chunker = ChunkerSettings() if isinstance(self.chunker, Unset) else self.chunker
        self.telemetry = (
            TelemetrySettings._default()  # type: ignore
            if isinstance(self.telemetry, Unset)
            else self.telemetry
        )
        self.management_host = (
            "127.0.0.1" if isinstance(self.management_host, Unset) else self.management_host
        )
        self.management_port = (
            9329 if isinstance(self.management_port, Unset) else self.management_port
        )
        self.uvicorn = (
            UvicornServerSettings.model_validate(DefaultUvicornSettings)
            if isinstance(self.uvicorn, Unset)
            else self.uvicorn
        )
        self.endpoints = (
            DefaultEndpointSettings
            if isinstance(self.endpoints, Unset) or self.endpoints is None
            else DefaultEndpointSettings | self.endpoints
        )
        self.default_mcp_config = (
            StdioCodeWeaverConfig()
            if isinstance(self.default_mcp_config, Unset)
            else self.default_mcp_config
        )
        if not type(self).__pydantic_complete__:
            result = type(self).model_rebuild()
            logger.debug("Rebuilt CodeWeaverSettings during post-init, result: %s", result)
        if type(self).__pydantic_complete__:
            # Ensure all nested Unset values are replaced with defaults
            self = cast(CodeWeaverSettings, ensure_set_fields(self))
            # Exclude computed fields to prevent circular dependency during initialization
            # Computed fields like IndexingSettings.cache_dir may call get_settings()
            self._map = cast(
                DictView[CodeWeaverSettingsDict],
                DictView(self.model_dump(mode="python", exclude_computed_fields=True)),
            )
            globals()["_mapped_settings"] = self._map

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("project_name"): AnonymityConversion.BOOLEAN,
            FilteredKey("config_file"): AnonymityConversion.HASH,
        }

    def _setup_profile(self) -> None:
        """Set up provider settings based on the selected profile."""
        from codeweaver.config.profiles import get_profile

        if self.provider is not UNSET and (
            (vector_url := os.environ.get("CODEWEAVER_VECTOR_STORE_URL"))
            or (
                (
                    vector_settings := self.provider.vector_store
                    if isinstance(self.provider.vector_store, dict)
                    else self.provider.vector_store[0]
                    if isinstance(self.provider.vector_store, tuple)
                    else None
                )
                and (
                    vector_url := vector_settings.get("provider_settings", {}).get("url")
                    or vector_settings.get("connection", {}).get("url")
                )
            )
        ):
            import re

            from urllib.parse import urlparse

            is_cloud = urlparse(vector_url).hostname not in (
                "localhost",
                "127.0.0.1",
                "0.0.0.0",  # noqa: S104
                "::1",
                "0:0:0:0:0:0:0:1",
                "::",  # I guess ruff is ok if we bind to all interfaces in ipv6
                # save the more expensive check for second
                # this checks if the ip range is in private ranges
            ) and not re.match(
                r"^(((192\.168|10\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1]))\.\d{1,3}\.\d{1,3})|(fe80|fc00|fd00):(?:[0-9a-fA-F]{1,4}:){0,7}[0-9a-fA-F]{1,4}(%[0-9a-zA-Z]+))$",
                urlparse(vector_url).hostname or "",
            )  # type: ignore
            self.provider = ProviderSettings.model_validate(
                get_profile(
                    self.profile if self.profile != "testing" else "backup",
                    vector_deployment="cloud" if is_cloud else "local",
                    url=vector_url if is_cloud else None,
                )  # ty: ignore[no-matching-overload]
            )  # type: ignore
        else:
            self.provider = ProviderSettings.model_validate(
                get_profile(
                    self.profile if self.profile != "testing" else "backup",  # ty: ignore[invalid-argument-type]
                    vector_deployment="local",
                )  # ty: ignore[no-matching-overload]
            )

    @classmethod
    def json_schema(cls) -> bytes:
        """Get the JSON validation schema for the settings model."""
        return to_json(cls.model_json_schema(indent=2))

    @classmethod
    def save_schema(cls, path: Path | None = None) -> int:
        """Save the JSON validation schema to a file."""
        if path is None:
            path = Path(__file__).parent.parent.parent.parent / "schema" / "codeweaver.schema.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.write_bytes(cls.json_schema())

    @classmethod
    def _defaults(cls) -> CodeWeaverSettingsDict:
        """Get a default settings dictionary."""
        # Check environment variable first to support Docker deployments without .git
        path = _resolve_env_settings_path(directory=True)
        return CodeWeaverSettingsDict(
            project_path=path,
            project_name=path.name,
            provider=AllDefaultProviderSettings,
            token_limit=30_000,
            max_file_size=1 * 1024 * 1024,
            max_results=30,
            mcp_server=FastMcpHttpServerSettings().as_settings(),
            stdio_server=FastMcpStdioServerSettings().as_settings(),
            logging=DefaultLoggingSettings,
            middleware=DefaultMiddlewareSettings,
            indexer=DefaultIndexerSettings,
            chunker=DefaultChunkerSettings,
            management_host="127.0.0.1",
            management_port=9329,
            default_mcp_config=StdioCodeWeaverConfigDict(StdioCodeWeaverConfig().model_dump()),  # ty: ignore[missing-typed-dict-key]
            telemetry=DefaultTelemetrySettings,
            uvicorn=DefaultUvicornSettings,
            endpoints=DefaultEndpointSettings,
        )

    @classmethod
    def from_config(cls, path: FilePath, **kwargs: Unpack[CodeWeaverSettingsDict]) -> Self:
        """Create a CodeWeaverSettings instance from a configuration file.

        This is a convenience method for creating a settings instance from a specific config file. By default, CodeWeaverSettings will look for configuration files in standard locations (like codeweaver.toml in the project root). This method allows you to specify a particular config file to load settings from, primarily for testing or special use cases.
        """
        extension = path.suffix.lower()
        match extension:
            case ".json":
                cls.model_config["json_file"] = path
            case ".toml":
                cls.model_config["toml_file"] = path
            case ".yaml" | ".yml":
                cls.model_config["yaml_file"] = path
            case _:
                raise ValueError(f"Unsupported configuration file format: {extension}")
        from codeweaver.common.utils import get_project_path

        return cls(project_path=get_project_path(), **{**kwargs, "config_file": path})  # type: ignore

    @computed_field
    def project_root(self) -> Path:
        """Get the project root directory. Alias for `project_path`."""
        if isinstance(self.project_path, Unset):
            from codeweaver.common.utils.git import get_project_path

            self.project_path = get_project_path()
        return self.project_path.resolve()

    @classmethod  # spellchecker:off
    def settings_customise_sources(  # noqa: C901
        # spellchecker:on
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize the sources of settings for a specific settings class.

        Configuration precedence (highest to lowest):
        1. init_settings - Direct initialization arguments
        2. env_settings - Environment variables (CODEWEAVER_*)
            - Nested models are separated by double underscores (__)
            - Only applies to fields in nested BaseModels
            - Currently, this includes all fields in:
                - `CodeWeaverSettings` (`CODEWEAVER__CONFIG_FILE`, etc)
                - `ProviderSettings` (`CODEWEAVER__PROVIDER__VECTOR_STORE`, etc)
                - `FastMcpServerSettings` (`CODEWEAVER__SERVER__HOST`, etc)
                - `IndexerSettings` (`CODEWEAVER__INDEXER__USE_GITIGNORE`, etc)
                - `ChunkerSettings` (`CODEWEAVER__CHUNKER__SEMANTIC_IMPORTANCE_THRESHOLD`, etc)
                - `TelemetrySettings` (`CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY`, etc)
                - UvicornServerSettings (`CODEWEAVER__UVICORN__LOG_LEVEL`, etc)
            - It does NOT apply to `LoggingSettings`, `MiddlewareOptions`, `MCPServerConfig`, or any other fields using TypedDict, including those in the above models.
            - It *does* apply to nested models in those models, currently only `CustomDelimiter`, `PerformanceSettings`, and `ConcurrencySettings`, which are fields in `ChunkerSettings`. You could set: `CODEWEAVER__CHUNKER__PERFORMANCE__MAX_PARALLEL_FILES=4`
        3. dotenv_settings - .env files:
            - .local.env,
            - .env
            - .codeweaver.local.env
            - .codeweaver.env
            - .codeweaver/.local.env
            - .codeweaver/.env
        4. In order of .toml, .yaml/.yml, .json files:
            - codeweaver.local.{toml,yaml,yml,json}
            - codeweaver.{toml,yaml,yml,json}
            - .codeweaver.local.{toml,yaml,yml,json}
            - .codeweaver.{toml,yaml,yml,json}
            - .codeweaver/codeweaver.local.{toml,yaml,yml,json}
            - .codeweaver/codeweaver.{toml,yaml,yml,json}
            - SYSTEM_USER_CONFIG_DIR/codeweaver/codeweaver.{toml,yaml,yml,json}
        5. file_secret_settings - Secret files SYSTEM_USER_CONFIG_DIR/codeweaver/.secrets/
           (see https://docs.pydantic.dev/latest/concepts/pydantic_settings/#secrets for more info)
        6. If available and configured:
            - AWS Secrets Manager
            - Azure Key Vault
            - Google Secret Manager
        """
        config_files: list[PydanticBaseSettingsSource] = []
        user_config_dir = get_user_config_dir()
        secrets_dir = user_config_dir / ".secrets"
        if not user_config_dir.exists():
            user_config_dir.mkdir(parents=True, exist_ok=True)
            user_config_dir.chmod(0o700)
        if not secrets_dir.exists():
            secrets_dir.mkdir(parents=True, exist_ok=True)
            secrets_dir.chmod(0o700)
        # Check if we're in test mode - prioritize test configs
        is_test_mode = is_test_environment()

        locations: list[str] = []
        if is_test_mode:
            # In test mode, look for .test configs first
            locations.extend([
                "codeweaver.test.local",
                "codeweaver.test",
                ".codeweaver.test.local",
                ".codeweaver.test",
                ".codeweaver/codeweaver.test.local",
                ".codeweaver/codeweaver.test",
            ])
        else:
            # Standard config locations
            locations.extend([
                "codeweaver.local",
                "codeweaver",
                ".codeweaver.local",
                ".codeweaver",
                ".codeweaver/codeweaver.local",
                ".codeweaver/codeweaver",
                f"{user_config_dir!s}/codeweaver",
            ])
        for _class in (
            TomlConfigSettingsSource,
            YamlConfigSettingsSource,
            JsonConfigSettingsSource,
        ):
            for loc in locations:
                ext = _class.__name__.split("ConfigSettingsSource")[0].lower()
                config_files.append(_class(settings_cls, Path(f"{loc}.{ext}")))
                if ext == "yaml":
                    config_files.append(_class(settings_cls, Path(f"{loc}.yml")))
        other_sources: list[PydanticBaseSettingsSource] = []
        if any(env for env in os.environ if env.startswith("AWS_SECRETS_MANAGER")):
            other_sources.append(
                AWSSecretsManagerSettingsSource(
                    settings_cls,
                    os.environ.get("AWS_SECRETS_MANAGER_SECRET_ID", ""),
                    os.environ.get("AWS_SECRETS_MANAGER_REGION", ""),
                    os.environ.get("AWS_SECRETS_MANAGER_ENDPOINT_URL", ""),
                )
            )
        if any(env for env in os.environ if env.startswith("AZURE_KEY_VAULT")) and util.find_spec(
            "azure.identity"
        ):
            try:
                from azure.identity import DefaultAzureCredential  # type: ignore

            except ImportError:
                logger.warning("Azure SDK not installed, skipping Azure Key Vault settings.")
            else:
                other_sources.append(
                    AzureKeyVaultSettingsSource(
                        settings_cls,
                        os.environ.get("AZURE_KEY_VAULT_URL", ""),
                        DefaultAzureCredential(),  # type: ignore
                    )
                )
        if any(
            env for env in os.environ if env.startswith("GOOGLE_SECRET_MANAGER")
        ) and util.find_spec("google.auth"):
            try:
                from google.auth import default  # type: ignore

            except ImportError:
                logger.warning(
                    "Google Cloud SDK not installed, skipping Google Secret Manager settings."
                )
            else:
                other_sources.append(
                    GoogleSecretManagerSettingsSource(
                        settings_cls,
                        default()[0],  # type: ignore
                        os.environ.get("GOOGLE_SECRET_MANAGER_PROJECT_ID", ""),
                    )
                )
        return (
            init_settings,
            EnvSettingsSource(
                settings_cls,
                env_prefix="CODEWEAVER_",
                case_sensitive=False,
                env_nested_delimiter="__",
                env_parse_enums=True,
                env_ignore_empty=True,
            ),
            DotEnvSettingsSource(
                settings_cls,
                env_file=(
                    ".local.env",
                    ".env",
                    ".codeweaver.local.env",
                    ".codeweaver.env",
                    ".codeweaver/.local.env",
                    ".codeweaver/.env",
                ),
                env_ignore_empty=True,
            ),
            *config_files,
            SecretsSettingsSource(
                settings_cls=settings_cls,
                secrets_dir=f"{user_config_dir}/secrets",
                env_ignore_empty=True,
            ),
            *other_sources,
        )

    def _update_settings(self, **kwargs: Unpack[CodeWeaverSettingsDict]) -> Self:
        """Update settings, validating a new CodeWeaverSettings instance and updating the global instance."""
        try:
            self.__init__(**kwargs)  # type: ignore # Unpack doesn't extend to nested dicts
        except ValidationError:
            logger.warning(
                "`CodeWeaverSettings` received invalid settings for an update. The settings failed to validate. We did not update the settings."
            )
            return self
        # The global _settings doesn't need updated because its reference didn't change
        # But we do need to update the global _mapped_settings because it's a copy
        # And other modules are using references to that copy
        globals()["_mapped_settings"] = self.view  # this recreates self._map as well
        return self

    @classmethod
    def reload(cls) -> Self:
        """Reloads settings from configuration sources.

        You can use this method to refresh the settings instance, re-reading configuration files and environment variables. This is useful if you expect configuration to change at runtime and want to apply those changes without restarting the application.
        """
        instance = globals().get("_settings")
        if instance is None:
            return cls()
        instance.__init__()
        return instance

    @property
    def view(self) -> DictView[CodeWeaverSettingsDict]:
        """Get a read-only mapping view of the settings."""
        if self._map is None or not self._map:
            try:
                self._map = DictView(self.model_dump(exclude_computed_fields=True))  # type: ignore
            except Exception:
                logger.warning("Failed to create settings map view")
                _ = type(self).model_rebuild()
                self._map = DictView(self.model_dump())  # type: ignore
        if not self._map:
            raise TypeError("Settings map view is not a valid DictView[CodeWeaverSettingsDict]")
        if unset_fields := tuple(
            field for field in type(self).model_fields if getattr(self, field) is Unset
        ):
            logger.warning("Some fields in CodeWeaverSettings are still unset: %s", unset_fields)
            self._unset_fields |= set(unset_fields)
            self = ensure_set_fields(self)
            self._map = DictView(self.model_dump(exclude_computed_fields=True))  # type: ignore
        return self._map  # type: ignore

    @classmethod
    def generate_default_config(cls, path: Path) -> None:
        """Generate a default configuration file at the specified path.

        The file format is determined by the file extension (.toml, .yaml/.yml, .json).
        """
        default_settings = cls()
        data = cls._to_serializable(default_settings, path=path)
        cls._write_config_file(path, data)

    @staticmethod
    def _to_serializable(
        obj: CodeWeaverSettings, path: Path | None = None, **override_kwargs: Any
    ) -> Any:
        """Convert an object to a serializable form."""
        from codeweaver.common.utils.git import get_project_path

        kwargs = {
            "indent": 4,
            "exclude_unset": True,
            "by_alias": True,
            "exclude_defaults": True,
            "round_trip": True,
            "exclude_computed_fields": True,
            "mode": "python",
        } | override_kwargs
        as_obj = obj.model_dump(**kwargs)  # type: ignore
        config_file = (
            path
            or obj.config_file
            or (
                obj.project_path
                if isinstance(obj.project_path, Path)
                else get_project_path() or Path.cwd()
            )
            / Path("codeweaver.toml")
        )
        extension = config_file.suffix.lower()
        match extension:
            case ".json":
                from pydantic_core import to_json

                data = to_json(
                    as_obj,
                    **{
                        k: v
                        for k, v in kwargs.items()
                        if k not in {"exclude_unset", "exclude_defaults", "exclude_computed_fields"}
                    },  # type: ignore
                ).decode("utf-8")
            case ".toml":
                import tomli_w

                data = tomli_w.dumps(as_obj)
            case ".yaml" | ".yml":
                import yaml

                data = yaml.dump(obj.model_dump())
            case _:
                raise ValueError(f"Unsupported configuration file format: {extension}")
        return data

    @staticmethod
    def _write_config_file(path: Path, data: str) -> None:
        """Write configuration data to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(data, encoding="utf-8")

    def save_to_file(self, path: Path | None = None) -> None:
        """Save the current settings to a configuration file.

        The file format is determined by the file extension (.toml, .yaml/.yml, .json).
        """
        path = (  # ty:ignore[invalid-assignment]
            path
            if path and path is not Unset
            else self.config_file
            if self.config_file is not UNSET
            else None
        )
        if path is None and isinstance(self.project_path, Path):
            path = self.project_path / "codeweaver.toml"
        if path is None:
            raise ValueError("No path provided to save configuration file.")
        extension = path.suffix.lower()
        # Use mode='json' to serialize Path objects to strings (needed for TOML/YAML)
        # model_dump kwargs (indent is NOT a valid model_dump parameter)
        dump_kwargs = {
            "exclude_unset": True,
            "by_alias": True,
            "exclude_defaults": True,
            "round_trip": True,
            "exclude_computed_fields": True,
            "mode": "json",  # Changed from "python" to handle Path serialization
            "exclude_none": True,  # Exclude None values for TOML compatibility
            "exclude": {"config_file", "default_mcp_config"},
        }
        # JSON serialization kwargs (includes indent for to_json)
        json_kwargs = {"indent": 4, "round_trip": True}
        as_obj = self.model_dump(**dump_kwargs)  # type: ignore
        data: str
        match extension:
            case ".json":
                from pydantic_core import to_json

                data = to_json(as_obj, **json_kwargs).decode("utf-8")  # type: ignore
            case ".toml":
                import tomli_w

                data = tomli_w.dumps(as_obj)
            case ".yaml" | ".yml":
                import yaml

                data = yaml.dump(self.model_dump())
            case _:
                raise ValueError(f"Unsupported configuration file format: {extension}")
        _ = path.write_text(data, encoding="utf-8")


# Global settings instance
_settings: CodeWeaverSettings | None = None
"""The global settings instance. Use `get_settings()` to access it."""

_mapped_settings: DictView[CodeWeaverSettingsDict] | None = None
"""An immutable mapping view of the global settings instance. Use `get_settings_map()` to access it."""


def get_settings(config_file: FilePath | None = None) -> CodeWeaverSettings:
    """Get the global settings instance.

    This should not be your first choice for getting settings. For most needs, you should. Use get_settings_map() to get a read-only mapping view of the settings. This map is a *live view*, meaning it will update if the settings are updated.

    If you **really** need to get the mutable settings instance, you can use this function. It will create the global instance if it doesn't exist, optionally loading from a configuration file (like, codeweaver.toml) if you provide a path.
    """
    global _settings
    # Ensure chunker models are rebuilt before creating settings
    if not ChunkerSettings.__pydantic_complete__:
        ChunkerSettings._ensure_models_rebuilt()  # type: ignore

    # Rebuild CodeWeaverSettings if needed before instantiation
    if not CodeWeaverSettings.__pydantic_complete__:
        _ = CodeWeaverSettings.model_rebuild()
    if config_file and config_file.exists():
        _settings = CodeWeaverSettings(config_file=config_file)
    if _settings is None or isinstance(_settings, Unset):
        _settings = CodeWeaverSettings()  # type: ignore

    if isinstance(_settings.project_path, Unset):
        from codeweaver.common.utils import get_project_path

        _settings.project_path = get_project_path()
    if isinstance(_settings.project_name, Unset):
        _settings.project_name = _settings.project_path.name
    return _settings


def update_settings(**kwargs: CodeWeaverSettingsDict) -> DictView[CodeWeaverSettingsDict]:
    """Update the global settings instance.

    Returns a read-only mapping view of the updated settings.
    """
    global _settings
    if _settings is None:
        try:
            _settings = get_settings()
        except Exception:
            logger.warning("Failed to get settings: ")
            _ = CodeWeaverSettings.model_rebuild()
            _settings = get_settings()
    _settings = _settings._update_settings(**kwargs)  # type: ignore
    return _settings.view


def get_settings_map() -> DictView[CodeWeaverSettingsDict]:
    """Get a read-only mapping view of the global settings instance.

    Almost nothing in CodeWeaver should need to modify settings at runtime,
    so instead we distribute a live, read-only view of the global settings. It's thread-safe and will update if the settings are changed.
    """
    global _mapped_settings
    global _settings
    try:
        settings = _settings or get_settings()
    except Exception:
        logger.warning("Failed to get settings: ")
        _ = CodeWeaverSettings.model_rebuild()
        settings = get_settings()
    if _mapped_settings is None or _mapped_settings != settings.view:
        _mapped_settings = settings.view or (
            _mapped_settings or DictView(settings.model_dump(round_trip=True))
        )  # type: ignore
    if not _mapped_settings:
        raise TypeError("Mapped settings is not a valid DictView[CodeWeaverSettingsDict]")
    return _mapped_settings


def reset_settings() -> None:
    """Reload settings from configuration sources."""
    global _settings
    global _mapped_settings
    _settings = None
    _mapped_settings = None  # the mapping will be regenerated on next access


__all__ = (
    "CodeWeaverSettings",
    "FastMcpHttpServerSettings",
    "FastMcpStdioServerSettings",
    "get_settings",
    "get_settings_map",
    "reset_settings",
    "update_settings",
)
