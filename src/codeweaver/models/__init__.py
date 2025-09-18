# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Pydantic models for CodeWeaver."""

# re-export pydantic-ai models for codeweaver

from functools import cache

from codeweaver.models.core import CodeMatch, FindCodeResponseSummary
from codeweaver.models.intent import IntentResult, QueryIntent


@cache
def get_user_agent() -> str:
    """Get the user agent string for CodeWeaver."""
    from codeweaver import __version__

    return f"CodeWeaver/{__version__}"


__all__ = ("CodeMatch", "FindCodeResponseSummary", "IntentResult", "QueryIntent", "get_user_agent")
