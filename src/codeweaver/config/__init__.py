# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# pyright: reportUnsupportedDunderAll=none
"""Configuration module for CodeWeaver."""

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Import everything for IDE and type checker support
    # These imports are never executed at runtime, only during type checking
    from codeweaver.config.chunker import (
        ChunkerSettings,
        ChunkerSettingsDict,
        CustomDelimiter,
        CustomLanguage,
    )
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
    from codeweaver.config.middleware import (
        AVAILABLE_MIDDLEWARE,
        ErrorHandlingMiddlewareSettings,
        LoggingMiddlewareSettings,
        MiddlewareOptions,
        RateLimitingMiddlewareSettings,
        RetryMiddlewareSettings,
    )
    from codeweaver.config.providers import (
        AWSProviderSettings,
        AgentModelSettings,
        AgentProviderSettings,
        AzureCohereProviderSettings,
        AzureOpenAIProviderSettings,
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
    )
    from codeweaver.config.settings import (
        CodeWeaverSettings,
        CodeWeaverSettingsDict,
        FastMcpServerSettings,
        get_settings,
        get_settings_map,
        update_settings,
    )
    from codeweaver.config.types import (
        ConnectionConfiguration,
        ConnectionRateLimitConfig,
        FastMcpHttpRunArgs,
        FastMcpServerSettingsDict,
        FileFilterSettingsDict,
        RignoreSettings,
        UvicornServerSettings,
        UvicornServerSettingsDict,
        default_config_file_locations,
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
    "CodeWeaverSettings": (__spec__.parent, "settings"),
    "CodeWeaverSettingsDict": (__spec__.parent, "settings"),
    "ConnectionConfiguration": (__spec__.parent, "types"),
    "ConnectionRateLimitConfig": (__spec__.parent, "types"),
    "CustomDelimiter": (__spec__.parent, "chunker"),
    "CustomLanguage": (__spec__.parent, "chunker"),
    "DataProviderSettings": (__spec__.parent, "providers"),
    "EmbeddingModelSettings": (__spec__.parent, "providers"),
    "EmbeddingProviderSettings": (__spec__.parent, "providers"),
    "ErrorHandlingMiddlewareSettings": (__spec__.parent, "middleware"),
    "FastMcpHttpRunArgs": (__spec__.parent, "types"),
    "FastMcpServerSettings": (__spec__.parent, "settings"),
    "FastMcpServerSettingsDict": (__spec__.parent, "types"),
    "FastembedGPUProviderSettings": (__spec__.parent, "providers"),
    "FileFilterSettingsDict": (__spec__.parent, "types"),
    "FilterID": (__spec__.parent, "logging"),
    "FiltersDict": (__spec__.parent, "logging"),
    "FormatterID": (__spec__.parent, "logging"),
    "FormattersDict": (__spec__.parent, "logging"),
    "HandlerID": (__spec__.parent, "logging"),
    "HandlersDict": (__spec__.parent, "logging"),
    "LoggerName": (__spec__.parent, "logging"),
    "LoggersDict": (__spec__.parent, "logging"),
    "LoggingConfigDict": (__spec__.parent, "logging"),
    "LoggingMiddlewareSettings": (__spec__.parent, "middleware"),
    "LoggingSettings": (__spec__.parent, "logging"),
    "MiddlewareOptions": (__spec__.parent, "middleware"),
    "ModelString": (__spec__.parent, "providers"),
    "ProviderSettingsDict": (__spec__.parent, "providers"),
    "ProviderSettingsView": (__spec__.parent, "providers"),
    "ProviderSpecificSettings": (__spec__.parent, "providers"),
    "RateLimitingMiddlewareSettings": (__spec__.parent, "middleware"),
    "RerankingModelSettings": (__spec__.parent, "providers"),
    "RerankingProviderSettings": (__spec__.parent, "providers"),
    "RetryMiddlewareSettings": (__spec__.parent, "middleware"),
    "RignoreSettings": (__spec__.parent, "types"),
    "SerializableLoggingFilter": (__spec__.parent, "logging"),
    "UvicornServerSettings": (__spec__.parent, "types"),
    "UvicornServerSettingsDict": (__spec__.parent, "types"),
    "default_config_file_locations": (__spec__.parent, "types"),
    "get_settings": (__spec__.parent, "settings"),
    "get_settings_map": (__spec__.parent, "settings"),
    "update_settings": (__spec__.parent, "settings"),
})
"""Dynamically import submodules and classes for the config package.

Maps class/function/type names to their respective module paths for lazy loading.
"""


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the config package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = (
    "AVAILABLE_MIDDLEWARE",
    "AWSProviderSettings",
    "AgentModelSettings",
    "AgentProviderSettings",
    "AzureCohereProviderSettings",
    "AzureOpenAIProviderSettings",
    "ChunkerSettings",
    "ChunkerSettingsDict",
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
    "FastMcpServerSettings",
    "FastMcpServerSettingsDict",
    "FastembedGPUProviderSettings",
    "FileFilterSettingsDict",
    "FilterID",
    "FiltersDict",
    "FormatterID",
    "FormattersDict",
    "HandlerID",
    "HandlersDict",
    "LoggerName",
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
    "RerankingModelSettings",
    "RerankingProviderSettings",
    "RetryMiddlewareSettings",
    "RignoreSettings",
    "SerializableLoggingFilter",
    "UvicornServerSettings",
    "UvicornServerSettingsDict",
    "default_config_file_locations",
    "get_settings",
    "get_settings_map",
    "update_settings",
)


def __dir__() -> list[str]:
    """List available attributes for the semantic package."""
    return list(__all__)
