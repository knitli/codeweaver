# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Core dependencies for CodeWeaver, including settings and services factories."""

from __future__ import annotations

from codeweaver.core.dependencies.utils import ensure_container_initialized


ensure_container_initialized()

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core.utils.lazy_importer import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.core.dependencies.component_settings import (
        LoggerDep,
        LoggingSettingsDep,
        ResolvedGitBranchDep,
        ResolvedProjectNameDep,
        ResolvedProjectPathDep,
        ResolvedProjectPathHashDep,
        ServiceCardsDep,
        TelemetrySettingsDep,
    )
    from codeweaver.core.dependencies.core_settings import (
        SettingsDep,
        SettingsMapDep,
        bootstrap_settings,
    )
    from codeweaver.core.dependencies.services import (
        ProgressReporterDep,
        StatisticsDep,
        TelemetryServiceDep,
    )

_dynamic_imports = MappingProxyType({
    "LoggerDep": (__spec__.parent, "component_settings"),
    "LoggingSettingsDep": (__spec__.parent, "component_settings"),
    "ProgressReporterDep": (__spec__.parent, "services"),
    "ResolvedGitBranchDep": (__spec__.parent, "component_settings"),
    "ResolvedProjectNameDep": (__spec__.parent, "component_settings"),
    "ResolvedProjectPathDep": (__spec__.parent, "component_settings"),
    "ResolvedProjectPathHashDep": (__spec__.parent, "component_settings"),
    "ServiceCardsDep": (__spec__.parent, "component_settings"),
    "SettingsDep": (__spec__.parent, "core_settings"),
    "SettingsMapDep": (__spec__.parent, "core_settings"),
    "StatisticsDep": (__spec__.parent, "services"),
    "TelemetryServiceDep": (__spec__.parent, "services"),
    "TelemetrySettingsDep": (__spec__.parent, "component_settings"),
    "bootstrap_settings": (__spec__.parent, "core_settings"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "LoggerDep",
    "LoggingSettingsDep",
    "ProgressReporterDep",
    "ResolvedGitBranchDep",
    "ResolvedProjectNameDep",
    "ResolvedProjectPathDep",
    "ResolvedProjectPathHashDep",
    "ServiceCardsDep",
    "SettingsDep",
    "SettingsMapDep",
    "StatisticsDep",
    "TelemetryServiceDep",
    "TelemetrySettingsDep",
    "bootstrap_settings",
)


def __dir__() -> list[str]:
    return list(__all__)
