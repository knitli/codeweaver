# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Pydantic models for CodeWeaver."""

# re-export pydantic-ai models for codeweaver

from functools import cache

from codeweaver.agent_api.find_code import find_code  # find_code is now a subpackage


@cache
def get_user_agent() -> str:
    """Get the user agent string for CodeWeaver."""
    from codeweaver import __version__

    return f"CodeWeaver/{__version__}"


__all__ = ("find_code", "get_user_agent")
