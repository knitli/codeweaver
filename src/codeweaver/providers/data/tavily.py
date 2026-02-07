# SPDX-FileCopyrightText: 2025-2026 Pydantic Services Inc.
# SPDX-License-Identifier: MIT
# applies to original file: https://github.com/pydantic/pydantic-ai/blob/0d87ab4a0b7b161f9c8073f7386972d3ecf8acc3/pydantic_ai_slim/pydantic_ai/common_tools/tavily.py
#
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Applies to modifications made to the original file.
"""Tool wrapper for Tavily search.

We take the unusual approach of only exposing curated search results to context agents. This minimizes the risk of context rot and ensures that agents have access to high-quality, relevant information.

We expose our own tailored version of the `search` endpoint. With out settings the search results are filtered and curated to ensure relevance and quality, limiting context rot.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from pydantic import TypeAdapter
from pydantic_ai import Tool

from codeweaver.core.utils import has_package


if TYPE_CHECKING and has_package("tavily") and has_package("pydantic_ai.common_tools.tavily"):
    from tavily.async_tavily import AsyncTavilyClient
else:
    AsyncTavilyClient = Any


class TavilySearchResult(TypedDict):
    """A Tavily search result.

    See [Tavily Search Endpoint documentation](https://docs.tavily.com/api-reference/endpoint/search)
    for more information.
    """

    url: str
    """The URL of the search result.."""
    content: str
    """A short description of the search result."""


tavily_search_ta = TypeAdapter(list[TavilySearchResult])


@dataclass
class TavilySearchContextTool:
    """Tavily tool that only returns relevant search results with no extra information."""

    client: AsyncTavilyClient
    """The Tavily search client."""

    max_results: int = 5
    """The maximum number of search results to return."""

    include_domains: Sequence[str] | None = None
    """A list of domains to include in the search results."""

    exclude_domains: Sequence[str] | None = None
    """A list of domains to exclude from the search results."""

    max_tokens: int | None = 6_000
    """The maximum number of tokens to return in the search results."""

    async def __call__(
        self,
        query: str,
        search_depth: Literal["basic", "advanced"] = "basic",
        time_range: Literal["day", "week", "month", "year"] | None = "year",
        include_domains: Sequence[str] | None = None,
        exclude_domains: Sequence[str] | None = None,
    ) -> list[TavilySearchResult]:
        """Searches Tavily for the given query and returns only relevant snippets.

        Args:
            query: The search query to execute with Tavily.
            search_depth: The depth of the search.
            time_range: The time range back from the current date to filter results.
            include_domains: A list of domains to include in the search results.
            exclude_domains: A list of domains to exclude from the search results.

        Returns:
            A list of search results from Tavily.
        """
        results = await self.client.search(
            query,
            search_depth=search_depth,
            topic="general",
            max_tokens=self.max_tokens,
            time_range=time_range or "year",
            format="markdown",
            include_answer=True,
            include_raw_content=False,
            include_images=False,
            include_domains=include_domains,  # ty:ignore[invalid-argument-type]
            exclude_domains=exclude_domains,  # ty:ignore[invalid-argument-type]
            max_results=self.max_results,
        )
        return tavily_search_ta.validate_python(results["results"])


def tavily_search_tool(
    client: AsyncTavilyClient,
    max_results: int = 5,
    *,
    include_domains: Sequence[str] | None = None,
    exclude_domains: Sequence[str] | None = None,
    max_tokens: int | None = 6_000,
    include_answer: bool | Literal["basic", "advanced"] = "basic",
) -> Tool[TavilySearchContextTool]:
    """Create a Tavily search tool."""
    return Tool[Any](
        TavilySearchContextTool(client, max_results=max_results).__call__,
        name="tavily_search",
        description="Search Tavily and return curated results.",
    )


__all__ = ("TavilySearchContextTool", "tavily_search_tool")
