# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Configuration module for CodeWeaver."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.common.utils.lazy_importer import create_lazy_getattr


if TYPE_CHECKING:
    # Import everything for IDE and type checker support
    # These imports are never executed at runtime, only during type checking
    from codeweaver.config.chunker import (
        ChunkerSettings,
        ChunkerSettingsDict,
        CustomDelimiter,
        CustomLanguage,
    )
    from codeweaver.config.indexer import IndexerSettings, IndexerSettingsDict, RignoreSettings
    from codeweaver.config.logging import (
        FilterID,
        FiltersDict,
        FormatterID,
        FormattersDict,
        HandlerID,
        HandlersDict,
        LoggerName,
        LoggersDict,
        LoggingConfigDict,
        LoggingSettings,
        SerializableLoggingFilter,
    )
    from codeweaver.config.mcp import CodeWeaverMCPConfig, MCPConfig, StdioCodeWeaverConfig
    from codeweaver.config.middleware import (
        AVAILABLE_MIDDLEWARE,
        ErrorHandlingMiddlewareSettings,
        LoggingMiddlewareSettings,
        MiddlewareOptions,
        RateLimitingMiddlewareSettings,
        RetryMiddlewareSettings,
    )
    from codeweaver.config.providers import (
        AgentModelSettings,
        AgentProviderSettings,
        AWSProviderSettings,
        AzureCohereProviderSettings,
        AzureOpenAIProviderSettings,
        ConnectionConfiguration,
        ConnectionRateLimitConfig,
        DataProviderSettings,
        EmbeddingModelSettings,
        EmbeddingProviderSettings,
        FastembedGPUProviderSettings,
        ModelString,
        ProviderSettingsDict,
        ProviderSettingsView,
        ProviderSpecificSettings,
        RerankingModelSettings,
        RerankingProviderSettings,
        SparseEmbeddingModelSettings,
        VectorStoreProviderSettings,
    )
    from codeweaver.config.settings import (
        CodeWeaverSettings,
        CodeWeaverSettingsDict,
        FastMcpHttpServerSettings,
        FastMcpStdioServerSettings,
        get_settings,
        get_settings_map,
        update_settings,
    )
    from codeweaver.config.telemetry import TelemetrySettings, get_telemetry_settings
    from codeweaver.config.types import (
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
    "AWSProviderSettings": (__spec__.parent, "providers"),
    "AgentModelSettings": (__spec__.parent, "providers"),
    "AgentProviderSettings": (__spec__.parent, "providers"),
    "AzureCohereProviderSettings": (__spec__.parent, "providers"),
    "AzureOpenAIProviderSettings": (__spec__.parent, "providers"),
    "ChunkerSettings": (__spec__.parent, "chunker"),
    "ChunkerSettingsDict": (__spec__.parent, "chunker"),
    "CodeWeaverMCPConfig": (__spec__.parent, "mcp"),
    "CodeWeaverMCPConfigDict": (__spec__.parent, "types"),
    "CodeWeaverSettings": (__spec__.parent, "settings"),
    "CodeWeaverSettingsDict": (__spec__.parent, "types"),
    "ConnectionConfiguration": (__spec__.parent, "providers"),
    "ConnectionRateLimitConfig": (__spec__.parent, "providers"),
    "CustomDelimiter": (__spec__.parent, "chunker"),
    "CustomLanguage": (__spec__.parent, "chunker"),
    "DataProviderSettings": (__spec__.parent, "providers"),
    "EmbeddingModelSettings": (__spec__.parent, "providers"),
    "EmbeddingProviderSettings": (__spec__.parent, "providers"),
    "ErrorHandlingMiddlewareSettings": (__spec__.parent, "middleware"),
    "FastMcpHttpRunArgs": (__spec__.parent, "types"),
    "FastMcpHttpServerSettings": (__spec__.parent, "settings"),
    "FastMcpServerSettingsDict": (__spec__.parent, "types"),
    "FastMcpStdioServerSettings": (__spec__.parent, "settings"),
    "FastembedGPUProviderSettings": (__spec__.parent, "providers"),
    "FilterID": (__spec__.parent, "logging"),
    "FiltersDict": (__spec__.parent, "logging"),
    "FormatterID": (__spec__.parent, "logging"),
    "FormattersDict": (__spec__.parent, "logging"),
    "HandlerID": (__spec__.parent, "logging"),
    "HandlersDict": (__spec__.parent, "logging"),
    "IndexerSettings": (__spec__.parent, "indexer"),
    "IndexerSettingsDict": (__spec__.parent, "indexer"),
    "LoggerName": (__spec__.parent, "logging"),
    "LoggersDict": (__spec__.parent, "logging"),
    "LoggingConfigDict": (__spec__.parent, "logging"),
    "LoggingMiddlewareSettings": (__spec__.parent, "middleware"),
    "LoggingSettings": (__spec__.parent, "logging"),
    "MCPConfig": (__spec__.parent, "mcp"),
    "MCPConfigDict": (__spec__.parent, "types"),
    "MiddlewareOptions": (__spec__.parent, "middleware"),
    "ModelString": (__spec__.parent, "providers"),
    "ProviderSettingsDict": (__spec__.parent, "providers"),
    "ProviderSettingsView": (__spec__.parent, "providers"),
    "ProviderSpecificSettings": (__spec__.parent, "providers"),
    "RateLimitingMiddlewareSettings": (__spec__.parent, "middleware"),
    "RerankingModelSettings": (__spec__.parent, "providers"),
    "RerankingProviderSettings": (__spec__.parent, "providers"),
    "RetryMiddlewareSettings": (__spec__.parent, "middleware"),
    "RignoreSettings": (__spec__.parent, "indexer"),
    "SerializableLoggingFilter": (__spec__.parent, "logging"),
    "SparseEmbeddingModelSettings": (__spec__.parent, "providers"),
    "StdioCodeWeaverConfig": (__spec__.parent, "mcp"),
    "StdioCodeWeaverConfigDict": (__spec__.parent, "types"),
    "TelemetrySettings": (__spec__.parent, "telemetry"),
    "UvicornServerSettings": (__spec__.parent, "types"),
    "UvicornServerSettingsDict": (__spec__.parent, "types"),
    "VectorStoreProviderSettings": (__spec__.parent, "providers"),
    "get_settings": (__spec__.parent, "settings"),
    "get_settings_map": (__spec__.parent, "settings"),
    "get_telemetry_settings": (__spec__.parent, "telemetry"),
    "update_settings": (__spec__.parent, "settings"),
})
"""Dynamically import submodules and classes for the config package.

Maps class/function/type names to their respective module paths for lazy loading.
"""

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "AVAILABLE_MIDDLEWARE",
    "AWSProviderSettings",
    "AgentModelSettings",
    "AgentProviderSettings",
    "AzureCohereProviderSettings",
    "AzureOpenAIProviderSettings",
    "ChunkerSettings",
    "ChunkerSettingsDict",
    "CodeWeaverMCPConfig",
    "CodeWeaverMCPConfigDict",
    "CodeWeaverSettings",
    "CodeWeaverSettingsDict",
    "ConnectionConfiguration",
    "ConnectionRateLimitConfig",
    "CustomDelimiter",
    "CustomLanguage",
    "DataProviderSettings",
    "EmbeddingModelSettings",
    "EmbeddingProviderSettings",
    "ErrorHandlingMiddlewareSettings",
    "FastMcpHttpRunArgs",
    "FastMcpHttpServerSettings",
    "FastMcpServerSettingsDict",
    "FastMcpStdioServerSettings",
    "FastembedGPUProviderSettings",
    "FilterID",
    "FiltersDict",
    "FormatterID",
    "FormattersDict",
    "HandlerID",
    "HandlersDict",
    "IndexerSettings",
    "IndexerSettingsDict",
    "LoggerName",
    "LoggersDict",
    "LoggingConfigDict",
    "LoggingMiddlewareSettings",
    "LoggingSettings",
    "MCPConfig",
    "MCPConfigDict",
    "MiddlewareOptions",
    "ModelString",
    "ProviderSettingsDict",
    "ProviderSettingsView",
    "ProviderSpecificSettings",
    "RateLimitingMiddlewareSettings",
    "RerankingModelSettings",
    "RerankingProviderSettings",
    "RetryMiddlewareSettings",
    "RignoreSettings",
    "SerializableLoggingFilter",
    "SparseEmbeddingModelSettings",
    "StdioCodeWeaverConfig",
    "StdioCodeWeaverConfigDict",
    "TelemetrySettings",
    "UvicornServerSettings",
    "UvicornServerSettingsDict",
    "VectorStoreProviderSettings",
    "get_settings",
    "get_settings_map",
    "get_telemetry_settings",
    "update_settings",
)


def __dir__() -> list[str]:
    """List available attributes for the config package."""
    return list(__all__)
