# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Data providers for CodeWeaver.

CodeWeaver's data providers add outside context to improve code search and analysis. These data sources are only exposed to specialized internal agents, which we call Context Agents. These agents use the tools exposed by the data providers to gather relevant information and improve the information we return to either the user or the user's agent.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.data.exa import (
        ExaAnswerResult,
        ExaAnswerTool,
        ExaContentResult,
        ExaFindSimilarTool,
        ExaGetContentsTool,
        ExaSearchResult,
        ExaSearchTool,
        ExaToolType,
        register_exa_tools,
    )
    from codeweaver.providers.data.providers import (
        DataProviderType,
        DuckDuckGoSearchTool,
        duckduckgo_search_tool,
        get_data_provider,
        load_default_data_providers,
    )
    from codeweaver.providers.data.tavily import (
        TavilyResults,
        TavilySearchContextTool,
        TavilySearchResult,
        tavily_search_tool,
    )
    from codeweaver.providers.data.utils import (
        build_data_tool,
        get_schema_for_type,
        get_serializer_for_type,
        get_type_adapter,
        register_data_tool,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DataProviderType": (__spec__.parent, "providers"),
    "DuckDuckGoSearchTool": (__spec__.parent, "providers"),
    "ExaAnswerResult": (__spec__.parent, "exa"),
    "ExaAnswerTool": (__spec__.parent, "exa"),
    "ExaContentResult": (__spec__.parent, "exa"),
    "ExaFindSimilarTool": (__spec__.parent, "exa"),
    "ExaGetContentsTool": (__spec__.parent, "exa"),
    "ExaSearchResult": (__spec__.parent, "exa"),
    "ExaSearchTool": (__spec__.parent, "exa"),
    "ExaToolType": (__spec__.parent, "exa"),
    "TavilyResults": (__spec__.parent, "tavily"),
    "TavilySearchContextTool": (__spec__.parent, "tavily"),
    "TavilySearchResult": (__spec__.parent, "tavily"),
    "build_data_tool": (__spec__.parent, "utils"),
    "duckduckgo_search_tool": (__spec__.parent, "providers"),
    "get_data_provider": (__spec__.parent, "providers"),
    "get_schema_for_type": (__spec__.parent, "utils"),
    "get_serializer_for_type": (__spec__.parent, "utils"),
    "get_type_adapter": (__spec__.parent, "utils"),
    "load_default_data_providers": (__spec__.parent, "providers"),
    "register_data_tool": (__spec__.parent, "utils"),
    "register_exa_tools": (__spec__.parent, "exa"),
    "tavily_search_tool": (__spec__.parent, "tavily"),
})


__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "DataProviderType",
    "DuckDuckGoSearchTool",
    "ExaAnswerResult",
    "ExaAnswerTool",
    "ExaContentResult",
    "ExaFindSimilarTool",
    "ExaGetContentsTool",
    "ExaSearchResult",
    "ExaSearchTool",
    "ExaToolType",
    "TavilyResults",
    "TavilySearchContextTool",
    "TavilySearchResult",
    "build_data_tool",
    "duckduckgo_search_tool",
    "get_data_provider",
    "get_schema_for_type",
    "get_serializer_for_type",
    "get_type_adapter",
    "load_default_data_providers",
    "register_data_tool",
    "register_exa_tools",
    "tavily_search_tool",
)


def __dir__() -> list[str]:
    return list(__all__)
