# sourcery skip: no-complex-if-expressions, snake-case-variable-declarations
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
import datetime
import os
import ssl

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Annotated, Any, Literal, NotRequired, Required, TypedDict

from fastmcp.server.server import DuplicateBehavior
from fastmcp.tools import Tool
from mcp.server.auth.settings import AuthSettings
from mcp.server.lowlevel.server import LifespanResultT
from pydantic import DirectoryPath, Field, FilePath, PositiveFloat, PositiveInt, SecretStr
from starlette.middleware import Middleware as ASGIMiddleware
from uvicorn.config import (
    SSL_PROTOCOL_VERSION,
    HTTPProtocolType,
    InterfaceType,
    LifespanType,
    WSProtocolType,
)

from codeweaver.config.chunker import ChunkerSettingsDict
from codeweaver.config.indexer import IndexerSettingsDict
from codeweaver.config.logging import LoggingConfigDict
from codeweaver.config.telemetry import TelemetrySettingsDict
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.models import BASEDMODEL_CONFIG, BasedModel
from codeweaver.core.types.sentinel import Unset
from codeweaver.mcp.middleware import McpMiddleware


if TYPE_CHECKING:
    from codeweaver.config.logging import LoggingSettings
    from codeweaver.config.middleware import MiddlewareOptions
    from codeweaver.config.providers import ProviderSettingsDict
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT


# ===========================================================================
# *        TypedDict Representations of Top-Level Settings Models
# ===========================================================================


class FastMcpHttpRunArgs(TypedDict, total=False):
    """Arguments for running FastMCP over HTTP."""

    transport: NotRequired[Literal["http", "streamable-http"]]
    host: NotRequired[str | None]
    port: NotRequired[PositiveInt | None]
    """Default port for the mcp server. Defaults to `9328`."""
    log_level: NotRequired[Literal["debug", "info", "warning", "error"] | None]
    path: NotRequired[str | None]
    """The base path for MCP HTTP requests. Defaults to `/mcp/`."""
    uvicorn_config: NotRequired[UvicornServerSettingsDict | None]
    middleware: list[ASGIMiddleware] | None
    """Note that this is *ASGI* middleware for Uvicorn/Starlette, not MCP middleware. You can also pass ASGI middleware directly in your `uvicorn_config` if you prefer. We have no default ASGI middleware."""
    json_response: NotRequired[bool | None]
    stateless_http: NotRequired[bool | None]


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
    # note: run_args must be popped out before passing to FastMCP constructor.
    # We construct the FastMCP instance and then pass run_args to the run_http_async method.
    run_args: NotRequired[FastMcpHttpRunArgs | None]
    auth: NotRequired[AuthSettings | None]
    on_duplicate_tools: NotRequired[DuplicateBehavior | None]
    on_duplicate_resources: NotRequired[DuplicateBehavior | None]
    on_duplicate_prompts: NotRequired[DuplicateBehavior | None]
    resource_prefix_format: NotRequired[Literal["protocol", "path"] | None]
    middleware: NotRequired[list[str | McpMiddleware] | None]
    tools: NotRequired[list[str | Tool] | None]


class EndpointSettingsDict(TypedDict, total=False):
    """Defines enable/disable settings for various CodeWeaver HTTP endpoints.

    Health and metrics are always enabled because they are used internally for monitoring and diagnostics (CodeWeaver is actually multiple servers which sometimes need to check in with each other).
    """

    enable_state: NotRequired[bool | Unset]
    enable_settings: NotRequired[bool | Unset]
    enable_version: NotRequired[bool | Unset]


class CodeWeaverSettingsDict(TypedDict, total=False):
    """TypedDict for CodeWeaver settings.

    Not intended to be used directly; used for internal type checking and validation.
    """

    project_path: NotRequired[DirectoryPath | Unset]
    project_name: NotRequired[str | Unset]
    provider: NotRequired[ProviderSettingsDict | Unset]
    config_file: NotRequired[FilePath | Unset]
    token_limit: NotRequired[PositiveInt | Unset]
    max_file_size: NotRequired[PositiveInt | Unset]
    max_results: NotRequired[PositiveInt | Unset]
    # Mcp HTTP Server Settings
    mcp_server: NotRequired[FastMcpServerSettingsDict | Unset]
    stdio_server: NotRequired[FastMcpServerSettingsDict | Unset]
    logging: NotRequired[LoggingSettings | Unset]
    middleware: NotRequired[MiddlewareOptions | Unset]
    chunker: NotRequired[ChunkerSettingsDict | Unset]
    uvicorn: NotRequired[UvicornServerSettingsDict | Unset]
    # Management Server (Always HTTP, independent of MCP transport)
    management_host: NotRequired[str | Unset]
    management_port: NotRequired[PositiveInt | Unset]
    indexer: NotRequired[IndexerSettingsDict | Unset]
    telemetry: NotRequired[TelemetrySettingsDict | Unset]
    endpoints: NotRequired[EndpointSettingsDict | Unset]
    default_mcp_config: NotRequired[dict[str, dict] | Unset]


# ===========================================================================
# *                        UVICORN Server Settings
# ===========================================================================


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


class UvicornServerSettings(BasedModel):
    """
    Uvicorn server settings. Besides the port, these are all defaults for uvicorn.

    We expose them so you can configure them for advanced deployments inside your codeweaver.toml (or yaml or json).
    """

    # For the following, we just want to track if it's the default value or not (True/False), not the actual value.
    model_config = BASEDMODEL_CONFIG

    name: Annotated[str, Field(exclude=True)] = "CodeWeaver_Management_Server"
    host: str = os.environ.get("CODEWEAVER_HOST", "127.0.0.1")
    port: PositiveInt = (
        int(port)
        if (port := os.environ.get("CODEWEAVER_PORT"), os.environ.get("CODEWEAVER__UVICORN__PORT"))
        else 9329
    )
    uds: str | None = None
    fd: int | None = None
    http: type[asyncio.Protocol] | HTTPProtocolType | str = "auto"
    ws: type[asyncio.Protocol] | WSProtocolType | str = "auto"
    ws_max_size: PositiveInt = 16_777_216  # 16 MiB
    ws_max_queue: PositiveInt = 32
    ws_ping_interval: PositiveFloat = 20.0
    ws_ping_timeout: PositiveFloat = 20.0
    ws_per_message_deflate: bool = True
    lifespan: LifespanType = "auto"
    env_file: str | os.PathLike[str] | None = None
    log_config: LoggingConfigDict | None = None
    log_level: str | int | None = "warning"
    access_log: bool = True
    use_colors: bool | None = None
    interface: InterfaceType = "auto"
    reload: bool = False
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

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("host"): AnonymityConversion.BOOLEAN,
            FilteredKey("name"): AnonymityConversion.BOOLEAN,
            FilteredKey("ssl_keyfile"): AnonymityConversion.BOOLEAN,
            FilteredKey("ssl_certfile"): AnonymityConversion.BOOLEAN,
            FilteredKey("ssl_keyfile_password"): AnonymityConversion.BOOLEAN,
            FilteredKey("ssl_version"): AnonymityConversion.BOOLEAN,
            FilteredKey("ssl_cert_reqs"): AnonymityConversion.BOOLEAN,
            FilteredKey("ssl_ca_certs"): AnonymityConversion.BOOLEAN,
            FilteredKey("ssl_ciphers"): AnonymityConversion.BOOLEAN,
            FilteredKey("root_path"): AnonymityConversion.BOOLEAN,
            FilteredKey("headers"): AnonymityConversion.BOOLEAN,
            FilteredKey("server_header"): AnonymityConversion.BOOLEAN,
            FilteredKey("data_header"): AnonymityConversion.BOOLEAN,
            FilteredKey("forwarded_allow_ips"): AnonymityConversion.BOOLEAN,
            FilteredKey("env_file"): AnonymityConversion.BOOLEAN,
            FilteredKey("log_config"): AnonymityConversion.BOOLEAN,
        }

    @classmethod
    def codeweaver_management_defaults(cls) -> UvicornServerSettingsDict:
        """Get default Uvicorn settings for CodeWeaver Management Server."""
        return UvicornServerSettingsDict(
            **cls().model_dump(exclude_none=True, exclude_computed_fields=True).model_dump()
        )

    @classmethod
    def codeweaver_mcp_defaults(cls) -> UvicornServerSettingsDict:
        """Get default Uvicorn settings for CodeWeaver MCP Server."""
        return UvicornServerSettingsDict(
            cls.codeweaver_management_defaults()
            | {
                "name": "CodeWeaver MCP Server",
                "port": int(env)
                if (env := os.environ.get("CODEWEAVER_MCP_PORT")) and env.isnumeric()
                else 9328,
            }
        )


# ===========================================================================
# *                            Mcp Configuration Typed Dicts
# ===========================================================================


class CodeWeaverMCPConfigDict(TypedDict, total=False):
    """TypedDict for CodeWeaverMCPConfig serialization."""

    url: Required[str]
    transport: NotRequired[Literal["http", "streamable-http"] | None]
    timeout: NotRequired[int | None]
    auth: NotRequired[str | Literal["oauth"] | Any | None]  # httpx.Auth at runtime
    authentication: NotRequired[dict[str, Any] | None]
    headers: NotRequired[dict[str, str] | None]
    description: NotRequired[str | None]
    icon: NotRequired[str | None]
    sse_read_timeout: NotRequired[int | datetime.timedelta | float | None]  # deprecated


class StdioCodeWeaverConfigDict(TypedDict, total=False):
    """TypedDict for StdioCodeWeaverConfig serialization."""

    command: Required[str]
    args: NotRequired[list[str] | None]
    env: NotRequired[dict[str, Any] | None]
    transport: NotRequired[Literal["stdio"]]
    cwd: NotRequired[str | None]
    timeout: NotRequired[int | None]
    authentication: NotRequired[dict[str, Any] | None]
    type: NotRequired[Literal["stdio"] | None]
    description: NotRequired[str | None]
    icon: NotRequired[str | None]


class MCPConfigDict(TypedDict):
    """TypedDict for MCPConfig serialization."""

    mcpServers: list[CodeWeaverMCPConfigDict | StdioCodeWeaverConfigDict]


__all__ = (
    "CodeWeaverMCPConfigDict",
    "CodeWeaverSettingsDict",
    "FastMcpHttpRunArgs",
    "FastMcpServerSettingsDict",
    "MCPConfigDict",
    "StdioCodeWeaverConfigDict",
    "UvicornServerSettings",
    "UvicornServerSettingsDict",
)
