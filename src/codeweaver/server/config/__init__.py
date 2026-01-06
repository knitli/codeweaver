# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Server configuration for CodeWeaver."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    # Import everything for IDE and type checker support
    # These imports are never executed at runtime, only during type checking
    from codeweaver.server.config.mcp import CodeWeaverMCPConfig, MCPConfig, StdioCodeWeaverConfig
    from codeweaver.server.config.middleware import (
        AVAILABLE_MIDDLEWARE,
        ErrorHandlingMiddlewareSettings,
        LoggingMiddlewareSettings,
        MiddlewareOptions,
        RateLimitingMiddlewareSettings,
        RetryMiddlewareSettings,
        default_for_transport,
    )
    from codeweaver.server.config.settings import (
        CodeWeaverSettings,
        CodeWeaverSettingsDict,
        FastMcpHttpServerSettings,
        FastMcpStdioServerSettings,
        get_settings,
        get_settings_map,
        update_settings,
    )
    from codeweaver.server.config.types import (
        CodeWeaverMCPConfigDict,
        FastMcpHttpRunArgs,
        FastMcpServerSettingsDict,
        MCPConfigDict,
        StdioCodeWeaverConfigDict,
        UvicornServerSettings,
        UvicornServerSettingsDict,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AVAILABLE_MIDDLEWARE": (__spec__.parent, "middleware"),
    "CodeWeaverMCPConfig": (__spec__.parent, "mcp"),
    "CodeWeaverMCPConfigDict": (__spec__.parent, "types"),
    "CodeWeaverSettings": (__spec__.parent, "settings"),
    "CodeWeaverSettingsDict": (__spec__.parent, "types"),
    "ErrorHandlingMiddlewareSettings": (__spec__.parent, "middleware"),
    "FastMcpHttpRunArgs": (__spec__.parent, "types"),
    "FastMcpHttpServerSettings": (__spec__.parent, "settings"),
    "FastMcpServerSettingsDict": (__spec__.parent, "types"),
    "FastMcpStdioServerSettings": (__spec__.parent, "settings"),
    "FastEmbedGPUProviderSettings": (__spec__.parent, "providers"),
    "LoggingMiddlewareSettings": (__spec__.parent, "middleware"),
    "LoggingSettingsDict": (__spec__.parent, "_logging"),
    "MCPConfig": (__spec__.parent, "mcp"),
    "MCPConfigDict": (__spec__.parent, "types"),
    "MiddlewareOptions": (__spec__.parent, "middleware"),
    "RateLimitingMiddlewareSettings": (__spec__.parent, "middleware"),
    "RetryMiddlewareSettings": (__spec__.parent, "middleware"),
    "SerializableLoggingFilter": (__spec__.parent, "_logging"),
    "StdioCodeWeaverConfig": (__spec__.parent, "mcp"),
    "StdioCodeWeaverConfigDict": (__spec__.parent, "types"),
    "UvicornServerSettings": (__spec__.parent, "types"),
    "UvicornServerSettingsDict": (__spec__.parent, "types"),
    "default_for_transport": (__spec__.parent, "middleware"),
    "get_settings": (__spec__.parent, "settings"),
    "get_settings_map": (__spec__.parent, "settings"),
    "update_settings": (__spec__.parent, "settings"),
})
"""Dynamically import submodules and classes for the config package.

Maps class/function/type names to their respective module paths for lazy loading.
"""

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "AVAILABLE_MIDDLEWARE",
    "CodeWeaverMCPConfig",
    "CodeWeaverMCPConfigDict",
    "CodeWeaverSettings",
    "CodeWeaverSettingsDict",
    "ErrorHandlingMiddlewareSettings",
    "FastEmbedGPUProviderSettings",
    "FastMcpHttpRunArgs",
    "FastMcpHttpServerSettings",
    "FastMcpServerSettingsDict",
    "FastMcpStdioServerSettings",
    "LoggingMiddlewareSettings",
    "MCPConfig",
    "MCPConfigDict",
    "MiddlewareOptions",
    "RateLimitingMiddlewareSettings",
    "RetryMiddlewareSettings",
    "StdioCodeWeaverConfig",
    "StdioCodeWeaverConfigDict",
    "UvicornServerSettings",
    "UvicornServerSettingsDict",
    "default_for_transport",
    "get_settings",
    "get_settings_map",
    "update_settings",
)


def __dir__() -> list[str]:
    """List available attributes for the config package."""
    return list(__all__)
