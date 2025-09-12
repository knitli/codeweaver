# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""MCP tools for CodeWeaver."""

import contextlib

from codeweaver.provider import Provider


def get_data_provider(provider: Provider) -> type | None:
    """Get available tools."""
    if provider == Provider.DUCKDUCKGO:
        with contextlib.suppress(ImportError):
            from pydantic_ai.common_tools.duckduckgo import DuckDuckGoSearchTool

            return DuckDuckGoSearchTool
    if provider == Provider.TAVILY:
        with contextlib.suppress(ImportError):
            from pydantic_ai.common_tools.tavily import TavilySearchTool

            return TavilySearchTool
    return None


def load_default_data_providers() -> tuple[type, ...]:
    """Load all available data providers."""
    providers: list[type] = []
    for provider in (Provider.DUCKDUCKGO, Provider.TAVILY):
        data_provider = get_data_provider(provider)
        if data_provider is not None:
            providers.append(data_provider)
    return tuple(providers)


from codeweaver.tools.find_code import basic_text_search, find_code_implementation


__all__ = (
    "basic_text_search",
    "find_code_implementation",
    "get_data_provider",
    "load_default_data_providers",
)
