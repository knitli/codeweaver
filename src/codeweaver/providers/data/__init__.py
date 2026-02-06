# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""MCP tools for CodeWeaver."""

from __future__ import annotations

import contextlib

from typing import TYPE_CHECKING, Any

from codeweaver.core.types import LiteralProviderType
from codeweaver.core.types.provider import Provider
from codeweaver.core.utils import has_package


if TYPE_CHECKING and has_package("pydantic_ai.common_tools.duckduckgo") and has_package("ddgs"):
    from pydantic_ai.common_tools.duckduckgo import DuckDuckGoSearchTool as DuckDuckGoSearchTool
else:
    DuckDuckGoSearchTool = Any
if TYPE_CHECKING and has_package("pydantic_ai.common_tools.tavily") and has_package("tavily"):
    from pydantic_ai.common_tools.tavily import TavilySearchTool as TavilySearchTool
else:
    TavilySearchTool = Any
if TYPE_CHECKING and has_package("pydantic_ai.common_tools.exa") and has_package("exa_py"):
    from pydantic_ai.common_tools.exa import ExaToolset as ExaToolset
else:
    ExaToolset = Any

type DataProviderType = DuckDuckGoSearchTool | TavilySearchTool | ExaToolset


def get_data_provider(provider: LiteralProviderType) -> DataProviderType | None:
    """Get available tools."""
    if isinstance(provider, str):
        provider: Provider = Provider.from_string(provider)
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


__all__ = ("DataProviderType", "get_data_provider", "load_default_data_providers")
