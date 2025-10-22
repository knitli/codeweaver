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
import os
import platform
import ssl

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, NotRequired, Required, TypedDict

from fastmcp.server.middleware import Middleware
from fastmcp.server.server import DuplicateBehavior
from fastmcp.tools import Tool
from mcp.server.auth.settings import AuthSettings
from mcp.server.lowlevel.server import LifespanResultT
from pydantic import ConfigDict, Field, PositiveFloat, PositiveInt, SecretStr
from starlette.middleware import Middleware as ASGIMiddleware
from uvicorn.config import (
    SSL_PROTOCOL_VERSION,
    HTTPProtocolType,
    InterfaceType,
    LifespanType,
    LoopSetupType,
    WSProtocolType,
)

from codeweaver.config.logging import LoggingConfigDict
from codeweaver.core import BASEDMODEL_CONFIG, BasedModel


if TYPE_CHECKING:
    from codeweaver.core import DictView, Unset
    from codeweaver.providers.provider import Provider

# ===========================================================================
# *          Rignore and File Filter Settings
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
    include_tooling_dir: NotRequired[bool]
    other_ignore_kwargs: NotRequired[RignoreSettings | Unset]
    default_rignore_settings: NotRequired[DictView[RignoreSettings]]


# ===========================================================================
# *            Provider Connection and Rate Limit Settings
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
    other: NotRequired[dict[str, Any] | None]


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
        | BASEDMODEL_CONFIG
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


__all__ = (
    "ConnectionConfiguration",
    "ConnectionRateLimitConfig",
    "FastMcpHttpRunArgs",
    "FileFilterSettingsDict",
    "RignoreSettings",
    "UvicornServerSettings",
    "UvicornServerSettings",
    "UvicornServerSettingsDict",
    "default_config_file_locations",
)
