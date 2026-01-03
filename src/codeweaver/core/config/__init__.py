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
        LoggingSettings,
        SerializableLoggingFilter,
    )
    from codeweaver.core.config.envs import (
        SettingsEnvVars,
        environment_variables,
        get_provider_vars,
        get_skeleton_provider_dict,
    )
    from codeweaver.core.config.telemetry import TelemetrySettings, get_telemetry_settings

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DefaultLoggingSettings": (__spec__.parent, "_logging"),
    "FilterID": (__spec__.parent, "_logging"),
    "FiltersDict": (__spec__.parent, "_logging"),
    "FormatterID": (__spec__.parent, "_logging"),
    "FormattersDict": (__spec__.parent, "_logging"),
    "HandlerID": (__spec__.parent, "_logging"),
    "HandlersDict": (__spec__.parent, "_logging"),
    "LoggerName": (__spec__.parent, "_logging"),
    "LoggersDict": (__spec__.parent, "_logging"),
    "LoggingConfigDict": (__spec__.parent, "_logging"),
    "LoggingSettings": (__spec__.parent, "_logging"),
    "SerializableLoggingFilter": (__spec__.parent, "_logging"),
    "SettingsEnvVars": (__spec__.parent, "envs"),
    "TelemetrySettings": (__spec__.parent, "telemetry"),
    "environment_variables": (__spec__.parent, "envs"),
    "get_provider_vars": (__spec__.parent, "envs"),
    "get_skeleton_provider_dict": (__spec__.parent, "envs"),
    "get_telemetry_settings": (__spec__.parent, "telemetry"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "DefaultLoggingSettings",
    "FilterID",
    "FiltersDict",
    "FormatterID",
    "FormattersDict",
    "HandlerID",
    "HandlersDict",
    "LoggerName",
    "LoggersDict",
    "LoggingConfigDict",
    "LoggingSettings",
    "SerializableLoggingFilter",
    "SettingsEnvVars",
    "TelemetrySettings",
    "environment_variables",
    "get_provider_vars",
    "get_skeleton_provider_dict",
    "get_telemetry_settings",
)


def __dir__() -> list[str]:
    return list(__all__)
