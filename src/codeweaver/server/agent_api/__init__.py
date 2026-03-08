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
    from codeweaver.server.agent_api.find_code import MatchedSection, find_code
    from codeweaver.server.agent_api.find_code.intent import (
        IntentResult,
        IntentType,
        QueryComplexity,
        QueryIntent,
    )
    from codeweaver.server.agent_api.find_code.types import (
        CodeMatch,
        CodeMatchType,
        FindCodeResponseSummary,
        FindCodeSubmission,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CodeMatch": (__spec__.parent, "find_code.types"),
    "CodeMatchType": (__spec__.parent, "find_code.types"),
    "FindCodeResponseSummary": (__spec__.parent, "find_code.types"),
    "FindCodeSubmission": (__spec__.parent, "find_code.types"),
    "IntentResult": (__spec__.parent, "find_code.intent"),
    "IntentType": (__spec__.parent, "find_code.intent"),
    "MatchedSection": (__spec__.parent, "find_code"),
    "QueryComplexity": (__spec__.parent, "find_code.intent"),
    "QueryIntent": (__spec__.parent, "find_code.intent"),
    "find_code": (__spec__.parent, "find_code"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "CodeMatch",
    "CodeMatchType",
    "FindCodeResponseSummary",
    "FindCodeSubmission",
    "IntentResult",
    "IntentType",
    "MatchedSection",
    "QueryComplexity",
    "QueryIntent",
    "find_code",
    "get_user_agent",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
