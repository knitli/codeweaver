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

import logging

from typing import Annotated, Any, Literal, TypedDict

from fastmcp.server.server import DuplicateBehavior
from mcp.server.auth.settings import AuthSettings
from mcp.server.lowlevel.server import LifespanResultT
from pydantic import Field, PositiveInt, computed_field
from pydantic_settings import SettingsConfigDict

from codeweaver.core import UNSET, BasedModel, Unset
from codeweaver.engine.config import CodeWeaverEngineSettings
from codeweaver.providers import ProviderSettings
from codeweaver.server.config.mcp import MCPServerConfig, StdioCodeWeaverConfig
from codeweaver.server.config.middleware import DefaultMiddlewareSettings, MiddlewareOptions
from codeweaver.server.config.server_defaults import (
    DefaultEndpointSettings,
    DefaultFastMcpHttpRunArgs,
    DefaultUvicornSettings,
)
from codeweaver.server.config.types import (
    EndpointSettingsDict,
    FastMcpHttpRunArgs,
    FastMcpServerSettingsDict,
    StdioCodeWeaverConfigDict,
    UvicornServerSettings,
)
from codeweaver.server.mcp import McpMiddleware


logger = logging.getLogger(__name__)

ONE_MEGABYTE = 1 * 1024 * 1024


DEFAULT_BASE_MIDDLEWARE = [
    f"codeweaver.server.mcp{mw}"
    for mw in (
        "ResponseCachingMiddleware",
        "ErrorHandlingMiddleware",
        "StatisticsMiddleware",
        "LoggingMiddleware",
    )
]

DEFAULT_HTTP_MIDDLEWARE = [
    *DEFAULT_BASE_MIDDLEWARE[:-1],
    "codeweaver.server.mcpRateLimitingMiddleware",
    "codeweaver.server.mcpRetryMiddleware",
    "codeweaver.server.mcpStructuredLoggingMiddleware",
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
        return FastMcpServerSettingsDict(
            **self.model_dump(
                exclude_none=True,
                exclude={f for f in type(self).model_fields if getattr(self, f, None) is UNSET},
            )
        )


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


class CodeWeaverSettings(CodeWeaverEngineSettings):
    """Main configuration model following pydantic-settings patterns."""

    model_config = CodeWeaverEngineSettings.model_config | SettingsConfigDict(
        title="CodeWeaver Settings"
    )

    # Performance settings
    token_limit: Annotated[
        PositiveInt | Unset,
        Field(description="""Maximum tokens per response""", validate_default=False),
    ] = UNSET

    max_results: Annotated[
        PositiveInt | Unset,
        Field(
            description="""Maximum code matches to return. Because CodeWeaver primarily indexes ast-nodes, a page can return multiple matches per file, so this is not the same as the number of files returned. This is the maximum number of code matches returned in a single response. The default is 15.""",
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

    middleware: Annotated[
        MiddlewareOptions | Unset,
        Field(description="""MCP middleware settings""", validate_default=False),
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
            description="""Default MCP server configuration for mcp clients. Setting this makes it quick and easy to add codeweaver to any mcp.json file using `cw init`. Defaults to a stdio transport.""",
            validate_default=False,
        ),
    ] = UNSET

    def _initialize(self, **kwargs: Any) -> dict[str, Any]:
        """Initialize server settings."""
        constructors = (
            FastMcpHttpServerSettings,
            FastMcpStdioServerSettings,
            StdioCodeWeaverConfig,
            UvicornServerSettings,
        )
        fields = type(self).model_fields
        for k, v in type(self)._defaults().items():
            if (value := kwargs.get(k)) is Unset or not value:
                kwargs[k] = (
                    constructor.model_construct(**v)
                    if (field_info := fields.get(k))
                    and (constructor := field_info.annotation) in constructors
                    else v
                )
            elif k in ("token_limit", "max_results", "management_host", "management_port"):
                kwargs[k] = value
            elif (field_info := fields.get(k)) and (
                constructor := field_info.annotation
            ) in constructors:
                kwargs[k] = constructor.model_validatee(
                    **self._resolve_default_and_provided(v, value)
                )
            else:
                kwargs[k] = value
        kwargs |= super()._initialize(**kwargs)
        return kwargs

    @classmethod
    def _defaults(cls) -> dict[str, Any]:
        """Get a default settings dictionary."""
        return {
            "token_limit": 15_000,
            "max_results": 15,
            "mcp_server": FastMcpHttpServerSettings().as_settings(),
            "stdio_server": FastMcpStdioServerSettings().as_settings(),
            "middleware": DefaultMiddlewareSettings,
            "management_host": "127.0.0.1",
            "management_port": 9329,
            "default_mcp_config": StdioCodeWeaverConfigDict(StdioCodeWeaverConfig().model_dump()),  # ty: ignore[missing-typed-dict-key, invalid-argument-type]
            "uvicorn": DefaultUvicornSettings,
            "endpoints": DefaultEndpointSettings,
        }


class CodeWeaverSettingsDict(TypedDict, total=False):
    """TypedDict for CodeWeaverSettings serialization."""

    token_limit: PositiveInt | None
    max_results: PositiveInt | None
    mcp_server: FastMcpServerSettingsDict | None
    stdio_server: FastMcpServerSettingsDict | None
    middleware: MiddlewareOptions | None
    endpoints: EndpointSettingsDict | None
    uvicorn: UvicornServerSettingsDict | None
    management_host: str | None
    management_port: PositiveInt | None
    default_mcp_config: StdioCodeWeaverConfigDict | None


__all__ = ("CodeWeaverSettings", "FastMcpHttpServerSettings", "FastMcpStdioServerSettings")
