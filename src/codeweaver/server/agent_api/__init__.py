# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Pydantic models for CodeWeaver."""

from __future__ import annotations


def get_user_agent() -> str:
    """Get the user agent string for CodeWeaver."""
    from codeweaver import __version__

    return f"CodeWeaver/{__version__}"


# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.server.agent_api.find_code import (
        CodeWeaverSettingsType,
        IndexingServiceDep,
        IntentType,
        MappingProxyType,
        MatchedSection,
        SearchPackageDep,
        SettingsDep,
        TelemetryServiceDep,
        TelemetrySettingsDep,
        find_code,
    )
    from codeweaver.server.agent_api.find_code.conversion import CodeMatchType
    from codeweaver.server.agent_api.find_code.intent import (
        IntentResult,
        QueryComplexity,
        QueryIntent,
    )
    from codeweaver.server.agent_api.find_code.pipeline import ConfigurationError, QueryError
    from codeweaver.server.agent_api.find_code.response import CodeWeaverStateDep
    from codeweaver.server.agent_api.find_code.types import (
        CodeMatch,
        FindCodeResponseSummary,
        FindCodeSubmission,
        ValidationError,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CodeMatch": (__spec__.parent, "find_code.types"),
    "CodeMatchType": (__spec__.parent, "find_code.conversion"),
    "CodeWeaverSettingsType": (__spec__.parent, "find_code"),
    "CodeWeaverStateDep": (__spec__.parent, "find_code.response"),
    "ConfigurationError": (__spec__.parent, "find_code.pipeline"),
    "FindCodeResponseSummary": (__spec__.parent, "find_code.types"),
    "FindCodeSubmission": (__spec__.parent, "find_code.types"),
    "IndexingServiceDep": (__spec__.parent, "find_code"),
    "IntentResult": (__spec__.parent, "find_code.intent"),
    "IntentType": (__spec__.parent, "find_code"),
    "MappingProxyType": (__spec__.parent, "find_code"),
    "MatchedSection": (__spec__.parent, "find_code"),
    "QueryComplexity": (__spec__.parent, "find_code.intent"),
    "QueryError": (__spec__.parent, "find_code.pipeline"),
    "QueryIntent": (__spec__.parent, "find_code.intent"),
    "SearchPackageDep": (__spec__.parent, "find_code"),
    "SearchStrategy": ("codeweaver.core", "types.search"),
    "SettingsDep": (__spec__.parent, "find_code"),
    "TelemetryServiceDep": (__spec__.parent, "find_code"),
    "TelemetrySettingsDep": (__spec__.parent, "find_code"),
    "ValidationError": (__spec__.parent, "find_code.types"),
    "find_code": (__spec__.parent, "find_code"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CodeMatch",
    "CodeMatchType",
    "CodeWeaverSettingsType",
    "CodeWeaverStateDep",
    "ConfigurationError",
    "FindCodeResponseSummary",
    "FindCodeSubmission",
    "IndexingServiceDep",
    "IntentResult",
    "IntentType",
    "MappingProxyType",
    "MatchedSection",
    "QueryComplexity",
    "QueryError",
    "QueryIntent",
    "SearchPackageDep",
    "SettingsDep",
    "TelemetryServiceDep",
    "TelemetrySettingsDep",
    "ValidationError",
    "find_code",
    "get_user_agent",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
