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

from fastmcp.server.middleware.middleware import Middleware as McpMiddleware
from fastmcp.server.server import DuplicateBehavior
from mcp.server.auth.settings import AuthSettings
from mcp.server.lowlevel.server import LifespanResultT
from pydantic import Field, PositiveInt, computed_field
from pydantic_settings import SettingsConfigDict

from codeweaver.core import UNSET, BasedModel, Unset
from codeweaver.core.constants import (
    DEFAULT_MANAGEMENT_PORT,
    DEFAULT_MAX_RESULTS,
    DEFAULT_MAX_TOKENS,
    LOCALHOST,
)
from codeweaver.engine.config import CodeWeaverEngineSettings
from codeweaver.providers import ProviderSettings
from codeweaver.server.config import DefaultFastMcpServerSettings
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
    UvicornServerSettingsDict,
)


logger = logging.getLogger(__name__)

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
            DEFAULT_BASE_MIDDLEWARE,
            key=lambda mw: _sort_order.index(mw.split(".")[-1].removeprefix("mcp")),
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
            DEFAULT_HTTP_MIDDLEWARE,
            key=lambda mw: _sort_order.index(mw.split(".")[-1].removeprefix("mcp")),
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
            description="""Maximum code matches to return. Because CodeWeaver primarily indexes ast-nodes, a page can return multiple matches per file, so this is not the same as the number of files returned. This is the maximum number of code matches returned in a single response. """,
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

    def __init__(
        self,
        token_limit: PositiveInt | Unset = UNSET,
        max_results: PositiveInt | Unset = UNSET,
        mcp_server: FastMcpHttpServerSettings | Unset = UNSET,
        stdio_server: FastMcpStdioServerSettings | Unset = UNSET,
        middleware: MiddlewareOptions | Unset = UNSET,
        endpoints: EndpointSettingsDict | Unset = UNSET,
        uvicorn: UvicornServerSettings | Unset = UNSET,
        management_host: str | Unset = UNSET,
        management_port: PositiveInt | Unset = UNSET,
        default_mcp_config: MCPServerConfig | Unset = UNSET,
        **data: Any,
    ) -> None:
        """Initialize server settings."""
        self._set_unset_fields(
            token_limit=token_limit,
            max_results=max_results,
            mcp_server=mcp_server,
            stdio_server=stdio_server,
            middleware=middleware,
            endpoints=endpoints,
            uvicorn=uvicorn,
            management_host=management_host,
            management_port=management_port,
            default_mcp_config=default_mcp_config,
        )
        data["token_limit"] = (
            token_limit
            if token_limit is not UNSET and token_limit is not None
            else DEFAULT_MAX_TOKENS
        )
        data["max_results"] = (
            max_results
            if max_results is not UNSET and max_results is not None
            else DEFAULT_MAX_RESULTS
        )
        data["mcp_server"] = (
            mcp_server
            if mcp_server is not UNSET and mcp_server is not None
            else FastMcpHttpServerSettings.model_construct(**DefaultFastMcpServerSettings)
        )
        data["stdio_server"] = (
            stdio_server
            if stdio_server is not UNSET and stdio_server is not None
            else FastMcpStdioServerSettings.model_construct(**BaseFastMcpServerSettings)
        )
        data["middleware"] = (
            middleware
            if middleware is not UNSET and middleware is not None
            else DefaultMiddlewareSettings
        )
        data["endpoints"] = (
            endpoints
            if endpoints is not UNSET and endpoints is not None
            else DefaultEndpointSettings
        )
        data["uvicorn"] = (
            uvicorn if uvicorn is not UNSET and uvicorn is not None else DefaultUvicornSettings
        )
        data["management_host"] = (
            management_host
            if management_host is not UNSET and management_host is not None
            else LOCALHOST
        )
        data["management_port"] = (
            management_port
            if management_port is not UNSET and management_port is not None
            else DEFAULT_MANAGEMENT_PORT
        )
        data["default_mcp_config"] = (
            default_mcp_config
            if default_mcp_config is not UNSET and default_mcp_config is not None
            else StdioCodeWeaverConfig.model_construct(
                **StdioCodeWeaverConfigDict(**StdioCodeWeaverConfig().model_dump())
            )
        )
        super().__init__(**data)

    async def _initialize(self, **kwargs: Any) -> None:
        """Initialize server settings."""
        mcp_stdio_default = FastMcpStdioServerSettings().as_settings()
        fields = (
            ("token_limit", DEFAULT_MAX_TOKENS, int),
            ("max_results", DEFAULT_MAX_RESULTS, int),
            ("mcp_server", DefaultFastMcpServerSettings, FastMcpHttpServerSettings),
            ("stdio_server", mcp_stdio_default, FastMcpStdioServerSettings),
            ("middleware", DefaultMiddlewareSettings, MiddlewareOptions),
            ("endpoints", DefaultEndpointSettings, EndpointSettingsDict),
            ("uvicorn", DefaultUvicornSettings, UvicornServerSettings),
            ("management_host", LOCALHOST, str),
            ("management_port", DEFAULT_MANAGEMENT_PORT, int),
            ("default_mcp_config", StdioCodeWeaverConfig(), MCPServerConfig),
        )
        for field_name, default, type_cls in fields:
            existing_value = (
                value
                if (value := getattr(self, field_name, None)) and value is not UNSET
                else default
            )
            existing_value = (
                existing_value.model_dump()
                if isinstance(existing_value, BasedModel)
                else existing_value
            )
            if (
                existing_value != default
                and existing_value is not UNSET
                and isinstance(existing_value, dict)
            ):
                existing_value = self._resolve_default_and_provided(existing_value, default)
            field_value = (
                v
                if (v := kwargs.get(field_name, "NON_EXISTENT_VALUE")) is not UNSET
                else "NON_EXISTENT_VALUE"
            )
            if field_value not in ("NON_EXISTENT_VALUE", None, default):
                resolved_value = (
                    field_value if isinstance(field_value, dict) else field_value.model_dump()
                )
                finalized_value = self._resolve_default_and_provided(
                    default.model_dump() if isinstance(default, BasedModel) else default,
                    resolved_value,
                )
            else:
                finalized_value = existing_value
            if isinstance(finalized_value, dict) and hasattr(type_cls, "model_construct"):
                setattr(self, field_name, type_cls.model_construct(**finalized_value))
            else:
                setattr(self, field_name, finalized_value)

        await super()._initialize(**kwargs)

    @classmethod
    def _defaults(cls) -> dict[str, Any]:
        """Get a default settings dictionary."""
        return {
            "token_limit": DEFAULT_MAX_TOKENS,
            "max_results": DEFAULT_MAX_RESULTS,
            "mcp_server": FastMcpHttpServerSettings().as_settings(),
            "stdio_server": FastMcpStdioServerSettings().as_settings(),
            "middleware": DefaultMiddlewareSettings,
            "management_host": LOCALHOST,
            "management_port": DEFAULT_MANAGEMENT_PORT,
            "default_mcp_config": StdioCodeWeaverConfigDict(**StdioCodeWeaverConfig().model_dump()),
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


__all__ = (
    "DEFAULT_BASE_MIDDLEWARE",
    "DEFAULT_HTTP_MIDDLEWARE",
    "BaseFastMcpServerSettings",
    "CodeWeaverSettings",
    "CodeWeaverSettingsDict",
    "FastMcpHttpServerSettings",
    "FastMcpStdioServerSettings",
)
