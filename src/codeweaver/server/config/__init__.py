# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Server configuration for CodeWeaver."""

from __future__ import annotations


"""Dynamically import submodules and classes for the config package.

Maps class/function/type names to their respective module paths for lazy loading.
"""

# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.server.config.helpers import get_settings, get_settings_map, update_settings
    from codeweaver.server.config.mcp import (
        CodeWeaverMCPConfig,
        MCPConfig,
        MCPServerConfig,
        StdioCodeWeaverConfig,
        update_mcp_config_file,
    )
    from codeweaver.server.config.middleware import (
        AVAILABLE_MIDDLEWARE,
        DefaultMiddlewareSettings,
        ErrorHandlingMiddlewareSettings,
        LoggingMiddlewareSettings,
        MiddlewareOptions,
        RateLimitingMiddlewareSettings,
        ResponseCachingMiddlewareSettings,
        RetryMiddlewareSettings,
        default_for_transport,
    )
    from codeweaver.server.config.server_defaults import (
        DefaultEndpointSettings,
        DefaultFastMcpHttpRunArgs,
        DefaultFastMcpServerSettings,
        DefaultUvicornSettings,
        DefaultUvicornSettingsForMcp,
    )
    from codeweaver.server.config.settings import (
        DEFAULT_BASE_MIDDLEWARE,
        DEFAULT_HTTP_MIDDLEWARE,
        BaseFastMcpServerSettings,
        CodeWeaverSettings,
        CodeWeaverSettingsDict,
        FastMcpHttpServerSettings,
        FastMcpStdioServerSettings,
    )
    from codeweaver.server.config.types import (
        CodeWeaverMCPConfigDict,
        EndpointSettingsDict,
        FastMcpHttpRunArgs,
        FastMcpServerSettingsDict,
        MCPConfigDict,
        StdioCodeWeaverConfigDict,
        UvicornServerSettings,
        UvicornServerSettingsDict,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AVAILABLE_MIDDLEWARE": (__spec__.parent, "middleware"),
    "DEFAULT_BASE_MIDDLEWARE": (__spec__.parent, "settings"),
    "DEFAULT_HTTP_MIDDLEWARE": (__spec__.parent, "settings"),
    "BaseFastMcpServerSettings": (__spec__.parent, "settings"),
    "CodeWeaverSettings": (__spec__.parent, "settings"),
    "CodeWeaverSettingsDict": (__spec__.parent, "settings"),
    "DefaultEndpointSettings": (__spec__.parent, "server_defaults"),
    "DefaultFastMcpHttpRunArgs": (__spec__.parent, "server_defaults"),
    "DefaultFastMcpServerSettings": (__spec__.parent, "server_defaults"),
    "DefaultMiddlewareSettings": (__spec__.parent, "middleware"),
    "DefaultUvicornSettings": (__spec__.parent, "server_defaults"),
    "DefaultUvicornSettingsForMcp": (__spec__.parent, "server_defaults"),
    "EndpointSettingsDict": (__spec__.parent, "types"),
    "ErrorHandlingMiddlewareSettings": (__spec__.parent, "middleware"),
    "FastMcpHttpRunArgs": (__spec__.parent, "types"),
    "FastMcpHttpServerSettings": (__spec__.parent, "settings"),
    "FastMcpServerSettingsDict": (__spec__.parent, "types"),
    "FastMcpStdioServerSettings": (__spec__.parent, "settings"),
    "LoggingMiddlewareSettings": (__spec__.parent, "middleware"),
    "MiddlewareOptions": (__spec__.parent, "middleware"),
    "RateLimitingMiddlewareSettings": (__spec__.parent, "middleware"),
    "ResponseCachingMiddlewareSettings": (__spec__.parent, "middleware"),
    "RetryMiddlewareSettings": (__spec__.parent, "middleware"),
    "StdioCodeWeaverConfig": (__spec__.parent, "mcp"),
    "StdioCodeWeaverConfigDict": (__spec__.parent, "types"),
    "UvicornServerSettings": (__spec__.parent, "types"),
    "UvicornServerSettingsDict": (__spec__.parent, "types"),
    "CodeWeaverMCPConfig": (__spec__.parent, "mcp"),
    "CodeWeaverMCPConfigDict": (__spec__.parent, "types"),
    "default_for_transport": (__spec__.parent, "middleware"),
    "get_settings": (__spec__.parent, "helpers"),
    "get_settings_map": (__spec__.parent, "helpers"),
    "MCPConfig": (__spec__.parent, "mcp"),
    "MCPConfigDict": (__spec__.parent, "types"),
    "update_mcp_config_file": (__spec__.parent, "mcp"),
    "update_settings": (__spec__.parent, "helpers"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "AVAILABLE_MIDDLEWARE",
    "DEFAULT_BASE_MIDDLEWARE",
    "DEFAULT_HTTP_MIDDLEWARE",
    "BaseFastMcpServerSettings",
    "CodeWeaverMCPConfig",
    "CodeWeaverMCPConfigDict",
    "CodeWeaverSettings",
    "CodeWeaverSettingsDict",
    "DefaultEndpointSettings",
    "DefaultFastMcpHttpRunArgs",
    "DefaultFastMcpServerSettings",
    "DefaultMiddlewareSettings",
    "DefaultUvicornSettings",
    "DefaultUvicornSettingsForMcp",
    "EndpointSettingsDict",
    "ErrorHandlingMiddlewareSettings",
    "FastMcpHttpRunArgs",
    "FastMcpHttpServerSettings",
    "FastMcpServerSettingsDict",
    "FastMcpStdioServerSettings",
    "LoggingMiddlewareSettings",
    "MCPConfig",
    "MCPConfigDict",
    "MCPServerConfig",
    "MiddlewareOptions",
    "RateLimitingMiddlewareSettings",
    "ResponseCachingMiddlewareSettings",
    "RetryMiddlewareSettings",
    "StdioCodeWeaverConfig",
    "StdioCodeWeaverConfigDict",
    "UvicornServerSettings",
    "UvicornServerSettingsDict",
    "default_for_transport",
    "get_settings",
    "get_settings_map",
    "update_mcp_config_file",
    "update_settings",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
