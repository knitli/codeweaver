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

from codeweaver.core.utils import create_lazy_getattr


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
    from codeweaver.core.config.core_settings import CodeWeaverCoreSettings
    from codeweaver.core.config.defaults import (
        clear_defaults,
        get_default,
        register_default_provider,
    )
    from codeweaver.core.config.envs import (
        SettingsEnvVars,
        environment_variables,
        get_provider_vars,
    )
    from codeweaver.core.config.loader import get_settings
    from codeweaver.core.config.registry import (
        clear_configurables,
        get_configurable_components,
        get_configurable_values,
        register_configurable,
    )
    from codeweaver.core.config.resolver import (
        ConfigurableComponent,
        ConfigurationValue,
        resolve_all_configs,
    )
    from codeweaver.core.config.telemetry import DefaultTelemetrySettings, TelemetrySettings

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CodeWeaverCoreSettings": (__spec__.parent, "core_settings"),
    "ConfigurableComponent": (__spec__.parent, "resolver"),
    "ConfigurationValue": (__spec__.parent, "resolver"),
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
    "clear_configurables": (__spec__.parent, "registry"),
    "clear_defaults": (__spec__.parent, "defaults"),
    "environment_variables": (__spec__.parent, "envs"),
    "get_configurable_components": (__spec__.parent, "registry"),
    "get_configurable_values": (__spec__.parent, "registry"),
    "get_default": (__spec__.parent, "defaults"),
    "get_provider_vars": (__spec__.parent, "envs"),
    "get_settings": (__spec__.parent, "loader"),
    "register_configurable": (__spec__.parent, "registry"),
    "register_default_provider": (__spec__.parent, "defaults"),
    "resolve_all_configs": (__spec__.parent, "resolver"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CodeWeaverCoreSettings",
    "ConfigurableComponent",
    "ConfigurationValue",
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
    "clear_configurables",
    "clear_defaults",
    "environment_variables",
    "get_configurable_components",
    "get_configurable_values",
    "get_default",
    "get_provider_vars",
    "get_settings",
    "register_configurable",
    "register_default_provider",
    "resolve_all_configs",
)


def __dir__() -> list[str]:
    return list(__all__)
