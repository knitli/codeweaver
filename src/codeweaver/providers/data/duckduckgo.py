# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""DuckDuckGo data provider tool implementation."""

from __future__ import annotations

import asyncio

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from pydantic import PositiveInt

from codeweaver.core import uuid7
from codeweaver.core.constants import CONTEXT_AGENT_TAGS
from codeweaver.core.utils import has_package
from codeweaver.providers import register_data_tool
from codeweaver.providers.data.utils import (
    build_data_tool,
    get_schema_for_type,
    get_serializer_for_type,
    get_type_adapter,
)
from codeweaver.server import ToolRegistrationDict


if TYPE_CHECKING:
    pass


if TYPE_CHECKING and has_package("ddgs"):
    from ddgs import DDGS
else:
    DDGS = Any


class DdgsResultItem(TypedDict, total=False):
    """A single DuckDuckGo search result item."""

    title: str
    """A title of the search result."""
    href: str
    """The URL of the search result."""
    body: str
    """A brief description or snippet from the search result."""


type DdgsResults = list[DdgsResultItem]
"""A list of DuckDuckGo search result items."""


@dataclass
class DuckDuckGoSearchTool:
    """A tool for searching DuckDuckGo."""

    client: DDGS
    """The DDGS client instance used to perform searches."""

    safesearch: Literal["on", "moderate", "off"] = "moderate"
    """The safesearch setting for the search. Can be "on", "moderate", or "off". Defaults to "moderate"."""

    max_results: PositiveInt = 10
    """The maximum number of search results to return. Defaults to 10."""

    iden: str | None = None
    """An optional identifier for the tool instance. Can be used to distinguish between multiple instances of the tool."""

    async def __call__(
        self,
        query: str,
        *,
        timelimit: Literal["day", "week", "month", "year", "None"] | None = "year",
    ) -> list[dict[str, Any]]:
        """Perform a search using the DDGS client.

        Args:
            query: The search query string.
            timelimit: The time limit for the search results. Can be "day", "week", "month", "year", or None. Defaults to "year". Pass 'None' for no time limit.

        Returns:
            A list of dictionaries containing the search results.
        """
        # using the full words is more intuitive for an agent, so we map them here
        actual_timelimit = {"day": "d", "week": "w", "month": "m", "year": "y", "None": None}.get(
            timelimit
        )
        return await asyncio.to_thread(
            self.client.search,
            category="text",
            query=query,
            safesearch=self.safesearch,
            max_results=self.max_results,
            timelimit=actual_timelimit,
        )


async def _get_ddgs_search_tool(instance: DuckDuckGoSearchTool) -> Tool[DuckDuckGoSearchTool]:
    """Create and return a DuckDuckGo search tool wrapped in a FastMCP Tool."""
    adapter = get_type_adapter(list[DdgsResultItem], module=__name__)
    return await build_data_tool(
        ToolRegistrationDict(
            fn=instance.__call__,
            name="duckduckgo_search",
            description="Search DuckDuckGo for relevant information.",
            tags=CONTEXT_AGENT_TAGS | {"search", "duckduckgo"},
            output_schema=get_schema_for_type(adapter=adapter),
            serializer=get_serializer_for_type(adapter=adapter),
            annotations=ToolAnnotations(
                readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
            ),
        )
    )


async def duckduckgo_search_tool(
    client: DDGS,
    *,
    safesearch: Literal["on", "moderate", "off"] = "moderate",
    max_results: PositiveInt = 10,
    iden: str | None = None,
    register: bool = True,
) -> Tool[DuckDuckGoSearchTool]:
    """Factory function to create a DuckDuckGoSearchTool instance."""
    instance = DuckDuckGoSearchTool(
        client=client, safesearch=safesearch, max_results=max_results, iden=iden or uuid7().hex
    )
    tool = await _get_ddgs_search_tool(instance)
    if register:
        await register_data_tool(tool)
    return tool


__all__ = ("DuckDuckGoSearchTool", "duckduckgo_search_tool")
