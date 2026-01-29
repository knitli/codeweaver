# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Pydantic models for CodeWeaver."""

# re-export pydantic-ai models for codeweaver
from __future__ import annotations

from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.core import SearchStrategy
    from codeweaver.server.agent_api.find_code import IntentType, find_code
    from codeweaver.server.agent_api.find_code.types import (
        CodeMatch,
        CodeMatchType,
        FindCodeResponseSummary,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CodeMatch": (__spec__.parent, "find_code.types"),
    "CodeMatchType": (__spec__.parent, "find_code.types"),
    "FindCodeResponseSummary": (__spec__.parent, "find_code.types"),
    "IntentType": (__spec__.parent, "find_code.intent"),
    "SearchStrategy": ("codeweaver.core", "types"),
    "find_code": (__spec__.parent, "find_code"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


@cache
def get_user_agent() -> str:
    """Get the user agent string for CodeWeaver."""
    from codeweaver import __version__

    return f"CodeWeaver/{__version__}"


__all__ = (
    "CodeMatch",
    "CodeMatchType",
    "FindCodeResponseSummary",
    "IntentType",
    "SearchStrategy",
    "find_code",
    "get_user_agent",
)


def __dir__() -> list[str]:
    return list(__all__)
