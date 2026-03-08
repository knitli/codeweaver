# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Data providers for CodeWeaver.

CodeWeaver's data providers add outside context to improve code search and analysis. These data sources are only exposed to specialized internal agents, which we call Context Agents. These agents use the tools exposed by the data providers to gather relevant information and improve the information we return to either the user or the user's agent.
"""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.data.duckduckgo import (
        DdgsResultItem,
        DdgsResults,
        DuckDuckGoSearchTool,
        duckduckgo_search_tool,
    )
    from codeweaver.providers.data.exa import (
        ExaAnswerResult,
        ExaAnswerTool,
        ExaContentResult,
        ExaFindSimilarTool,
        ExaGetContentsTool,
        ExaSearchResult,
        ExaSearchTool,
        ExaToolType,
        exa_answer_tool,
        exa_find_similar_tool,
        exa_get_contents_tool,
        exa_search_tool,
        register_exa_tools,
    )
    from codeweaver.providers.data.providers import (
        DataProviderType,
        LiteralProviderType,
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
        LiteralProviderCategoryType,
        build_data_tool,
        get_provider_names_for_category,
        get_schema_for_type,
        get_serializer_for_type,
        get_type_adapter,
        register_data_tool,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DdgsResultItem": (__spec__.parent, "duckduckgo"),
    "DuckDuckGoSearchTool": (__spec__.parent, "duckduckgo"),
    "ExaAnswerResult": (__spec__.parent, "exa"),
    "ExaAnswerTool": (__spec__.parent, "exa"),
    "ExaContentResult": (__spec__.parent, "exa"),
    "ExaFindSimilarTool": (__spec__.parent, "exa"),
    "ExaGetContentsTool": (__spec__.parent, "exa"),
    "ExaSearchResult": (__spec__.parent, "exa"),
    "ExaSearchTool": (__spec__.parent, "exa"),
    "LiteralProviderCategoryType": (__spec__.parent, "utils"),
    "DataProviderType": (__spec__.parent, "providers"),
    "LiteralProviderType": (__spec__.parent, "providers"),
    "TavilyResults": (__spec__.parent, "tavily"),
    "TavilySearchContextTool": (__spec__.parent, "tavily"),
    "TavilySearchResult": (__spec__.parent, "tavily"),
    "build_data_tool": (__spec__.parent, "utils"),
    "duckduckgo_search_tool": (__spec__.parent, "duckduckgo"),
    "exa_answer_tool": (__spec__.parent, "exa"),
    "exa_find_similar_tool": (__spec__.parent, "exa"),
    "exa_get_contents_tool": (__spec__.parent, "exa"),
    "exa_search_tool": (__spec__.parent, "exa"),
    "get_data_provider": (__spec__.parent, "providers"),
    "get_provider_names_for_category": (__spec__.parent, "utils"),
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
    "DdgsResultItem",
    "DdgsResults",
    "DuckDuckGoSearchTool",
    "ExaAnswerResult",
    "ExaAnswerTool",
    "ExaContentResult",
    "ExaFindSimilarTool",
    "ExaGetContentsTool",
    "ExaSearchResult",
    "ExaSearchTool",
    "ExaToolType",
    "LiteralProviderCategoryType",
    "LiteralProviderType",
    "MappingProxyType",
    "TavilyResults",
    "TavilySearchContextTool",
    "TavilySearchResult",
    "build_data_tool",
    "duckduckgo_search_tool",
    "exa_answer_tool",
    "exa_find_similar_tool",
    "exa_get_contents_tool",
    "exa_search_tool",
    "get_data_provider",
    "get_provider_names_for_category",
    "get_schema_for_type",
    "get_serializer_for_type",
    "get_type_adapter",
    "load_default_data_providers",
    "register_data_tool",
    "register_exa_tools",
    "tavily_search_tool",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
