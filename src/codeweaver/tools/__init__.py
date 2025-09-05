# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""MCP tools for CodeWeaver."""

import contextlib

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.provider import Provider


def get_data_provider(provider: Provider) -> type | None:
    """Get available tools."""
    from codeweaver.provider import Provider

    if provider == Provider.DUCKDUCKGO:
        with contextlib.suppress(ImportError):
            from pydantic_ai.common_tools.duckduckgo import DuckDuckGoSearchTool

            return DuckDuckGoSearchTool
    if provider == Provider.TAVILY:
        with contextlib.suppress(ImportError):
            from pydantic_ai.common_tools.tavily import TavilySearchTool

            return TavilySearchTool
    return None


from codeweaver.tools.find_code import basic_text_search, find_code_implementation


__all__ = ("basic_text_search", "find_code_implementation")
