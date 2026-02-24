# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Init for the core's config package.
"""

from __future__ import annotations

from types import MappingProxyType
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
        CodeWeaverCoreSettings,
        get_config_locations,
        get_dotenv_locations,
        get_possible_config_paths,
    )
    from codeweaver.core.config.envs import (
        SettingsEnvVars,
        environment_variables,
        get_provider_vars,
    )
    from codeweaver.core.config.loader import get_settings, get_settings_async
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType
    from codeweaver.core.config.telemetry import (
        DefaultTelemetrySettings,
        TelemetrySettings,
        TelemetrySettingsDict,
    )
    from codeweaver.core.config.types import CodeWeaverSettingsDict

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CodeWeaverCoreSettings": (__spec__.parent, "core_settings"),
    "CodeWeaverSettingsDict": (__spec__.parent, "types"),
    "CodeWeaverSettingsType": (__spec__.parent, "settings_type"),
    "DefaultLoggingSettings": (__spec__.parent, "_logging"),
    "DefaultTelemetrySettings": (__spec__.parent, "telemetry"),
    "FilterID": (__spec__.parent, "_logging"),
    "FiltersDict": (__spec__.parent, "_logging"),
    "FormatterID": (__spec__.parent, "_logging"),
    "FormattersDict": (__spec__.parent, "_logging"),
    "HandlerID": (__spec__.parent, "_logging"),
    "HandlersDict": (__spec__.parent, "_logging"),
    "LoggerName": (__spec__.parent, "_logging"),
    "LoggersDict": (__spec__.parent, "_logging"),
    "LoggingConfigDict": (__spec__.parent, "_logging"),
    "LoggingSettingsDict": (__spec__.parent, "_logging"),
    "SerializableLoggingFilter": (__spec__.parent, "_logging"),
    "SettingsEnvVars": (__spec__.parent, "envs"),
    "TelemetrySettings": (__spec__.parent, "telemetry"),
    "TelemetrySettingsDict": (__spec__.parent, "telemetry"),
    "environment_variables": (__spec__.parent, "envs"),
    "get_config_locations": (__spec__.parent, "core_settings"),
    "get_dotenv_locations": (__spec__.parent, "core_settings"),
    "get_possible_config_paths": (__spec__.parent, "core_settings"),
    "get_provider_vars": (__spec__.parent, "envs"),
    "get_settings": (__spec__.parent, "loader"),
    "get_settings_async": (__spec__.parent, "loader"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CodeWeaverCoreSettings",
    "CodeWeaverSettingsDict",
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
    "SerializableLoggingFilter",
    "SettingsEnvVars",
    "TelemetrySettings",
    "TelemetrySettingsDict",
    "environment_variables",
    "get_config_locations",
    "get_dotenv_locations",
    "get_possible_config_paths",
    "get_provider_vars",
    "get_settings",
    "get_settings_async",
)


def __dir__() -> list[str]:
    return list(__all__)
