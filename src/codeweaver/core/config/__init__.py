# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Init for the core's config package.
"""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.core.config._logging import (
        DefaultLoggingSettings,
        FilterID,
        FiltersDict,
        FormatterID,
        FormattersDict,
        HandlerID,
        HandlersDict,
        LoggerName,
        LoggersDict,
        LoggingConfigDict,
        LoggingSettingsDict,
        SerializableLoggingFilter,
    )
    from codeweaver.core.config.core_settings import (
        SCHEMA_VERSION,
        SUPPORTED_CONFIG_FILE_EXTENSIONS,
        CodeWeaverCoreSettings,
        aws_secret_store_configured,
        azure_key_vault_configured,
        get_config_locations,
        get_dotenv_locations,
        get_possible_config_paths,
        google_secret_manager_configured,
    )
    from codeweaver.core.config.envs import (
        ProviderKey,
        SetProviderEnvVarsDict,
        SettingsEnvVars,
        as_cloud_string,
        environment_variables,
        get_provider_vars,
    )
    from codeweaver.core.config.loader import (
        CodeWeaverSettingsType,
        get_settings,
        get_settings_async,
    )
    from codeweaver.core.config.telemetry import (
        DefaultTelemetrySettings,
        TelemetrySettings,
        TelemetrySettingsDict,
    )
    from codeweaver.core.config.types import ROOT_PACKAGE, BaseCodeWeaverSettingsDict

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ROOT_PACKAGE": (__spec__.parent, "types"),
    "SCHEMA_VERSION": (__spec__.parent, "core_settings"),
    "SUPPORTED_CONFIG_FILE_EXTENSIONS": (__spec__.parent, "core_settings"),
    "BaseCodeWeaverSettingsDict": (__spec__.parent, "types"),
    "CodeWeaverCoreSettings": (__spec__.parent, "core_settings"),
    "CodeWeaverSettingsType": (__spec__.parent, "loader"),
    "DefaultLoggingSettings": (__spec__.parent, "_logging"),
    "DefaultTelemetrySettings": (__spec__.parent, "telemetry"),
    "FiltersDict": (__spec__.parent, "_logging"),
    "FormattersDict": (__spec__.parent, "_logging"),
    "HandlersDict": (__spec__.parent, "_logging"),
    "LoggerName": (__spec__.parent, "_logging"),
    "LoggersDict": (__spec__.parent, "_logging"),
    "LoggingConfigDict": (__spec__.parent, "_logging"),
    "LoggingSettingsDict": (__spec__.parent, "_logging"),
    "ProviderKey": (__spec__.parent, "envs"),
    "SerializableLoggingFilter": (__spec__.parent, "_logging"),
    "SetProviderEnvVarsDict": (__spec__.parent, "envs"),
    "SettingsEnvVars": (__spec__.parent, "envs"),
    "TelemetrySettings": (__spec__.parent, "telemetry"),
    "TelemetrySettingsDict": (__spec__.parent, "telemetry"),
    "as_cloud_string": (__spec__.parent, "envs"),
    "aws_secret_store_configured": (__spec__.parent, "core_settings"),
    "azure_key_vault_configured": (__spec__.parent, "core_settings"),
    "environment_variables": (__spec__.parent, "envs"),
    "FilterID": (__spec__.parent, "_logging"),
    "FormatterID": (__spec__.parent, "_logging"),
    "get_config_locations": (__spec__.parent, "core_settings"),
    "get_dotenv_locations": (__spec__.parent, "core_settings"),
    "get_possible_config_paths": (__spec__.parent, "core_settings"),
    "get_provider_vars": (__spec__.parent, "envs"),
    "get_settings": (__spec__.parent, "loader"),
    "get_settings_async": (__spec__.parent, "loader"),
    "google_secret_manager_configured": (__spec__.parent, "core_settings"),
    "HandlerID": (__spec__.parent, "_logging"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "ROOT_PACKAGE",
    "SCHEMA_VERSION",
    "SUPPORTED_CONFIG_FILE_EXTENSIONS",
    "BaseCodeWeaverSettingsDict",
    "CodeWeaverCoreSettings",
    "CodeWeaverSettingsType",
    "DefaultLoggingSettings",
    "DefaultTelemetrySettings",
    "FilterID",
    "FiltersDict",
    "FormatterID",
    "FormattersDict",
    "HandlerID",
    "HandlersDict",
    "LoggerName",
    "LoggersDict",
    "LoggingConfigDict",
    "LoggingSettingsDict",
    "ProviderKey",
    "SerializableLoggingFilter",
    "SetProviderEnvVarsDict",
    "SettingsEnvVars",
    "TelemetrySettings",
    "TelemetrySettingsDict",
    "as_cloud_string",
    "aws_secret_store_configured",
    "azure_key_vault_configured",
    "environment_variables",
    "get_config_locations",
    "get_dotenv_locations",
    "get_possible_config_paths",
    "get_provider_vars",
    "get_settings",
    "get_settings_async",
    "google_secret_manager_configured",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
