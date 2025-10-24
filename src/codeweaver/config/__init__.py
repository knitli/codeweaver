# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# pyright: reportUnsupportedDunderAll=none
"""Configuration module for CodeWeaver."""

from importlib import import_module
from types import MappingProxyType


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "FilterID": (__spec__.parent, "logging"),
    "FiltersDict": (__spec__.parent, "logging"),
    "FormatterID": (__spec__.parent, "logging"),
    "FormattersDict": (__spec__.parent, "logging"),
    "HandlerID": (__spec__.parent, "logging"),
    "HandlersDict": (__spec__.parent, "logging"),
    "LoggerName": (__spec__.parent, "logging"),
    "LoggersDict": (__spec__.parent, "logging"),
    "LoggingConfigDict": (__spec__.parent, "logging"),
    "LoggingSettings": (__spec__.parent, "logging"),
    "SerializableLoggingFilter": (__spec__.parent, "logging"),
    "AVAILABLE_MIDDLEWARE": (__spec__.parent, "middleware"),
    "ErrorHandlingMiddlewareSettings": (__spec__.parent, "middleware"),
    "LoggingMiddlewareSettings": (__spec__.parent, "middleware"),
    "MiddlewareOptions": (__spec__.parent, "middleware"),
    "RateLimitingMiddlewareSettings": (__spec__.parent, "middleware"),
    "RetryMiddlewareSettings": (__spec__.parent, "middleware"),
    "AgentModelSettings": (__spec__.parent, "providers"),
    "AgentProviderSettings": (__spec__.parent, "providers"),
    "AWSProviderSettings": (__spec__.parent, "providers"),
    "AzureCohereProviderSettings": (__spec__.parent, "providers"),
    "AzureOpenAIProviderSettings": (__spec__.parent, "providers"),
    "DataProviderSettings": (__spec__.parent, "providers"),
    "EmbeddingModelSettings": (__spec__.parent, "providers"),
    "EmbeddingProviderSettings": (__spec__.parent, "providers"),
    "FastembedGPUProviderSettings": (__spec__.parent, "providers"),
    "ModelString": (__spec__.parent, "providers"),
    "ProviderSettingsDict": (__spec__.parent, "providers"),
    "ProviderSettingsView": (__spec__.parent, "providers"),
    "ProviderSpecificSettings": (__spec__.parent, "providers"),
    "RerankingModelSettings": (__spec__.parent, "providers"),
    "RerankingProviderSettings": (__spec__.parent, "providers"),
    "CodeWeaverSettings": (__spec__.parent, "settings"),
    "CodeWeaverSettingsDict": (__spec__.parent, "settings"),
    "get_settings": (__spec__.parent, "settings"),
    "get_settings_map": (__spec__.parent, "settings"),
    "update_settings": (__spec__.parent, "settings"),
    "ConnectionConfiguration": (__spec__.parent, "types"),
    "ConnectionRateLimitConfig": (__spec__.parent, "types"),
    "FastMcpHttpRunArgs": (__spec__.parent, "types"),
    "FastMcpServerSettingsDict": (__spec__.parent, "types"),
    "FileFilterSettingsDict": (__spec__.parent, "types"),
    "RignoreSettings": (__spec__.parent, "types"),
    "UvicornServerSettings": (__spec__.parent, "types"),
    "UvicornServerSettingsDict": (__spec__.parent, "types"),
    "default_config_file_locations": (__spec__.parent, "types"),
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
    "FileFilterSettings",
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
