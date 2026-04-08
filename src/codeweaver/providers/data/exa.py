# SPDX-FileCopyrightText: 2026 Pydantic Services Inc.
# SPDX-License-Identifier: MIT
# Applies to: original file: https://github.com/pydantic/pydantic-ai/blob/99fa3d9c86315408c6a14336499bc0919a102453/pydantic_ai_slim/pydantic_ai/common_tools/exa.py
#
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# SPDX-License-Identifier: MIT OR Apache-2.0
# Applies to: modifications made by Knitli Inc. to the original file and any additions (all modifications are in this module).
"""Customized Exa data provider implementation for CodeWeaver."""

from __future__ import annotations

import asyncio
import logging

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast, overload

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from pydantic import PositiveFloat, PositiveInt

from codeweaver.core.constants import CONTEXT_AGENT_TAGS
from codeweaver.core.types import LiteralStringT
from codeweaver.core.utils import has_package
from codeweaver.providers.config.sdk import ExaContentsOptions, ExaToolConfig
from codeweaver.providers.data.utils import (
    build_data_tool,
    get_schema_for_type,
    get_serializer_for_type,
    get_type_adapter,
    register_data_tool,
)
from codeweaver.server.mcp.types import ToolRegistrationDict


if TYPE_CHECKING and has_package("exa_py"):
    from exa_py import AsyncExa as AsyncExa
    from exa_py.api import Result as Result
    from exa_py.api import ResultWithText as ResultWithText
    from exa_py.api import SearchResponse as SearchResponse
else:
    SearchResponse = Any
    Result = Any
    ResultWithText = Any

    class AsyncExa:
        """Mock AsyncExa client for type checking."""

        api_key: str


logger = logging.getLogger(__name__)


_ONE_DAY_IN_HRS = 24


def _get_from_date() -> str:
    """Get the default from_date value (6 months ago)."""
    one_year_ago = datetime.now(UTC) - timedelta(days=360)
    return one_year_ago.date().isoformat()


_ONE_YEAR_AGO = _get_from_date()


class ExaSearchResult(TypedDict):
    """An Exa search result with content.

    See [Exa Search API documentation](https://docs.exa.ai/reference/search)
    for more information.
    """

    title: str
    """The title of the search result."""
    id: str
    """The unique identifier of the search result."""
    url: str
    """The URL of the search result."""
    score: float | None
    """The relevance score of the search result, if available."""
    published_date: str | None
    """The published date of the content, if available."""
    author: str | None
    """The author of the content, if available."""
    summary: str | None
    """A brief summary of the search result, if available."""
    text: str
    """The text content of the search result."""
    cost: PositiveFloat | None
    """The cost incurred for retrieving this search result, if available."""


class ExaAnswerResult(TypedDict):
    """An Exa answer result with citations.

    See [Exa Answer API documentation](https://docs.exa.ai/reference/answer)
    for more information.
    """

    answer: str
    """The AI-generated answer to the query."""
    citations: list[dict[str, Any]]
    """Citations supporting the answer."""

    cost: PositiveFloat | None
    """The cost incurred for generating the answer, if available."""


class ExaContentResult(TypedDict):
    """Content retrieved from a URL.

    See [Exa Contents API documentation](https://docs.exa.ai/reference/get-contents)
    for more information.
    """

    url: str
    """The URL of the content."""
    title: str
    """The title of the page."""
    summary: str | None
    """A brief summary of the content, if available."""
    text: str
    """The text content of the page."""
    author: str | None
    """The author of the content, if available."""
    published_date: str | None
    """The published date of the content, if available."""
    cost: PositiveFloat | None
    """The cost incurred for retrieving the content, if available."""


def _resolve_contents_options(
    options: ExaContentsOptions | Literal[True] | None,
    max_characters: int | None = None,
    max_age_hours: int | None = None,
) -> ExaContentsOptions | Literal[True] | None:
    """Resolve the contents options, applying defaults if necessary."""
    if (not options and not max_characters and not max_age_hours) or options is True:
        return None
    options = options or ExaContentsOptions()
    resolved_options: ExaContentsOptions = options.copy() if isinstance(options, dict) else {}
    if options.get("text") is True and max_characters is not None:
        resolved_options["text"] = cast(
            dict[Literal["max_characters"], int], {"max_characters": max_characters}
        )
    elif isinstance(options.get("text"), dict):
        resolved_options["text"] = cast(dict, options)["text"]
    if max_age_hours and not options.get("max_age_hours"):
        resolved_options["max_age_hours"] = max_age_hours
    return resolved_options


@dataclass
class ExaSearchTool:
    """The Exa search tool.

    Class-level options will **override** options provided at call time. This is to prevent agents from overriding important configuration options or restrictions.
    """

    client: AsyncExa
    """The Exa async client."""

    num_results: int
    """The number of results to return."""

    max_characters: int | None
    """Maximum characters of text content per result, or None for no limit."""

    contents_options: ExaContentsOptions | None = None
    """Options for content retrieval."""

    include_domains: list[str] | None = None
    """An optional list of domains to include in search results."""

    exclude_domains: list[str] | None = None
    """An optional list of domains to exclude from search results."""

    moderation: bool = False
    """Whether to enable Exa's moderation features for this search tool. If True, Exa will process the results through its moderation system to remove potentially harmful or low-quality content. We suggest enabling this, but don't make it a default because of its potential impact on latency."""

    iden: str | None = None
    """An optional identifier for the tool. This can be used to differentiate multiple instances of the Exa search tool with different configurations when they are shared in the same context (e.g. with an agent). If not provided, the tool will have a default identifier based on its configuration."""

    async def __call__(
        self,
        query: str,
        search_type: Literal["auto", "keyword", "neural", "fast", "deep"] = "auto",
        include_text: list[str] | None = None,
        max_age_hours: PositiveInt | None = _ONE_DAY_IN_HRS * 7,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        from_date: str | None = _ONE_YEAR_AGO,
        additional_queries: list[str] | None = None,
    ) -> list[ExaSearchResult]:
        """Searches Exa for the given query and returns the results with content.

        Args:
            query: The search query to execute with Exa.
            search_type: The type of search to perform. 'auto' automatically chooses
                the best search type, 'keyword' for exact matches, 'neural' for
                semantic search, 'fast' for speed-optimized search, 'deep' for
                comprehensive multi-query search.
            include_text: An optional list of exact strings that results must include.
            max_age_hours: Maximum age of cached content in hours. If provided and results are older than this, Exa will attempt to retrieve a fresh version of the content. CodeWeaver's default is one week (168 hours). This value is applied to the `max_age_hours` field in the `ContentsOptions` of the search tool.
            include_domains: An optional list of domains to include in search results.
            exclude_domains: An optional list of domains to exclude from search results.
            from_date: The maximum age of content that should be included in the search. Anything before the provided date will be excluded from results. We apply this value to `start_published_date` in Exa's API, so the restriction is on the age of the content itself, not the age of the search results. This is useful for ensuring that search results are based on up-to-date information, especially for topics where information changes rapidly. The value is an ISO 8601 date string (e.g. "2024-01-01" for January 1, 2024). CodeWeaver's default is one year ago from the current date.
            additional_queries: An optional list of additional queries to run alongside the main query. This is only applicable if `search_type` is set to 'deep', which performs a comprehensive search using multiple queries. The additional queries can be used to provide more context or explore related topics in the search. You can provide up to **5** additional queries.

        Returns:
            The search results with text content.
        """
        text_config = _resolve_contents_options(
            self.contents_options, max_characters=self.max_characters, max_age_hours=max_age_hours
        )
        response = await self.client.search(
            query,
            num_results=self.num_results,
            type=search_type,
            contents=text_config,
            include_domains=(self.include_domains or []) + (include_domains or []),
            exclude_domains=(self.exclude_domains or []) + (exclude_domains or []),
            start_published_date=from_date,
            moderation=self.moderation,
        )
        return [
            ExaSearchResult(
                title=result.title or "",
                id=result.id,
                url=result.url,
                score=result.score,
                published_date=result.published_date,
                author=result.author,
                summary=result.summary,
                cost=response.cost_dollars.total if response.cost_dollars else None,
                text=result.text or "",
            )
            for result in response.results
        ]


@dataclass
class ExaFindSimilarTool:
    """The Exa find similar tool."""

    client: AsyncExa
    """The Exa async client."""

    num_results: int
    """The number of results to return."""

    max_characters: int | None = None
    """The maximum number of characters to retrieve from each page."""

    include_domains: list[str] | None = None
    """An optional list of domains to include in search results."""

    exclude_domains: list[str] | None = None
    """An optional list of domains to exclude from search results."""

    contents_options: ExaContentsOptions | Literal[True] | None = None
    """Options for content retrieval."""

    iden: str | None = None
    """An optional identifier for the tool. This can be used to differentiate multiple instances of the Exa search tool with different configurations when they are shared in the same context (e.g. with an agent). If not provided, the tool will have a default identifier based on its configuration."""

    async def __call__(
        self,
        url: str,
        *,
        exclude_source_domain: bool = True,
        max_age_hours: PositiveInt | None = _ONE_DAY_IN_HRS * 7,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        from_date: str | None = _ONE_YEAR_AGO,
    ) -> list[ExaSearchResult]:
        """Finds pages similar to the given URL and returns them with content.

        Args:
            url: The URL to find similar pages for.
            exclude_source_domain: Whether to exclude results from the same domain
                as the input URL. Defaults to True.
            max_age_hours: Maximum age of cached content in hours. If provided and results are older than this, Exa will attempt to retrieve a fresh version of the content. CodeWeaver's default is one week (168 hours). This value is applied to the `max_age_hours` field in the `ContentsOptions` of the search tool.
            include_domains: An optional list of domains to include in search results.
            exclude_domains: An optional list of domains to exclude from search results.
            from_date: The maximum age of content that should be included in the search. Anything before the provided date will be excluded from results. We apply this value to `start_published_date` in Exa's API, so the restriction is on the age of the content itself, not the age of the search results. This is useful for ensuring that search results are based on up-to-date information, especially for topics where information changes rapidly. The value is an ISO 8601 date string (e.g. "2024-01-01" for January 1, 2024). CodeWeaver's default is one year ago from the current date.

        Returns:
            Similar pages with text content.
        """
        contents_config = _resolve_contents_options(
            self.contents_options, max_characters=self.max_characters, max_age_hours=max_age_hours
        )
        response = await self.client.find_similar(  # pyright: ignore[reportUnknownMemberType]
            url,
            num_results=self.num_results,
            exclude_source_domain=exclude_source_domain,
            contents=contents_config,
            include_domains=(self.include_domains or []) + (include_domains or []),
            exclude_domains=(self.exclude_domains or []) + (exclude_domains or []),
            start_published_date=from_date,
        )

        return [
            ExaSearchResult(
                title=result.title or "",
                id=result.id,
                score=result.score,
                url=result.url,
                summary=result.summary,
                published_date=result.published_date,
                cost=response.cost_dollars.total if response.cost_dollars else None,
                author=result.author,
                text=result.text or "",
            )
            for result in response.results
        ]


@dataclass
class ExaGetContentsTool:
    """The Exa get contents tool."""

    client: AsyncExa
    """The Exa async client."""

    max_characters: PositiveInt | None = None
    """Maximum characters of text content to return. If the content exceeds this limit, it will be truncated. Defaults to None for no limit."""

    summary: Literal[True] | None = None
    """Whether to include a summary of the content in the results. Defaults to None. If set to True, a brief summary will be included."""

    contents_options: ExaContentsOptions | None = None
    """Options for content retrieval."""

    filter_empty_results: bool = True
    """Whether to filter out results that have empty text content. Defaults to True."""

    iden: str | None = None
    """An optional identifier for the tool. This can be used to differentiate multiple instances of the Exa search tool with different configurations when they are shared in the same context (e.g. with an agent). If not provided, the tool will have a default identifier based on its configuration."""

    async def __call__(
        self,
        urls: list[str] | str,
        *,
        subpage_target: str | list[str] | None = None,
        max_age_hours: PositiveInt | None = _ONE_DAY_IN_HRS * 7,
    ) -> list[ExaContentResult]:
        """Gets the content of the specified URLs.

        Args:
            urls: A list of URLs to get content for.

            subpage_target: An optional string or list of strings specifying subpages to target for content retrieval. If provided, Exa will attempt to retrieve content from these specific subpages of the input URLs. This is useful for cases where you want to retrieve content from a specific section of a website (e.g. "blog" or "docs").
            max_age_hours: Maximum age of cached content in hours. If provided and content is older than this, Exa will attempt to retrieve a fresh version of the content. CodeWeaver's default is one week (168 hours).

        Returns:
            The content of each URL.
        """
        text_config = _resolve_contents_options(self.contents_options, self.max_characters)
        response = await self.client.get_contents(
            urls,
            text=text_config,
            summary=self.summary,
            filter_empty_results=self.filter_empty_results,
            subpage_target=subpage_target,
            max_age_hours=max_age_hours,
        )
        return [
            ExaContentResult(
                url=result.url,
                title=result.title or "",
                summary=result.summary,
                text=result.text or "",
                author=result.author,
                published_date=result.published_date,
                cost=response.cost_dollars.total if response.cost_dollars else None,
            )
            for result in response.results
        ]


@dataclass
class ExaAnswerTool:
    """The Exa answer tool."""

    client: AsyncExa
    """The Exa async client."""

    system_prompt: str | None = None
    """An optional system prompt to provide to the Exa answer tool. This can be used to guide the behavior of the tool. For example, you could provide a prompt that instructs the tool to focus on certain types of sources. If not provided, the tool will use its default behavior."""

    model: Literal["exa", "exa-pro"] | LiteralStringT | None = None
    """The Exa model to use for answering. "exa" is the default. Currently only 'exa' and 'exa-pro' are valid options, but you can pass a custom model name when exa makes new models available."""

    iden: str | None = None
    """An optional identifier for the tool. This can be used to differentiate multiple instances of the Exa answer tool with different configurations when they are shared in the same context (e.g. with an agent). If not provided, the tool will have a default identifier based on its configuration."""

    async def __call__(self, query: str, *, text: bool = False) -> ExaAnswerResult:
        """Generates an AI-powered answer to the query with citations.

        Args:
            query: The question to answer.
            text: Whether to include the text content of the sources in the citations. Defaults to False.

        Returns:
            An answer with supporting citations from web sources.
        """
        response = await self.client.answer(
            query, text=text, system_prompt=self.system_prompt, model=self.model
        )

        return ExaAnswerResult(
            answer=response.answer,
            citations=[
                {
                    "id": citation.id,
                    "url": citation.url,
                    "title": citation.title or "",
                    "published_date": citation.published_date,
                    "author": citation.author,
                    "text": citation.text or "",
                }
                for citation in response.citations
            ],
            cost=response.cost_dollars.total if response.cost_dollars else None,
        )


def exa_search_tool(
    client: AsyncExa,
    num_results: int = 5,
    max_characters: int | None = None,
    contents_options: ExaContentsOptions | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    *,
    moderation: bool = False,
    iden: str | None = None,
) -> ExaSearchTool:
    """Creates an Exa search tool.

    Args:
        client: The Exa async client. Required.

        num_results: The number of results to return. Defaults to 5.
        max_characters: Maximum characters of text content per result. Use this to limit
            token usage. Defaults to None (no limit).
    """
    return ExaSearchTool(
        client=client,
        num_results=num_results,
        max_characters=max_characters,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        contents_options=contents_options,
        moderation=moderation,
        iden=iden,
    )


def exa_find_similar_tool(
    client: AsyncExa,
    num_results: int = 5,
    max_characters: int | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    contents_options: ExaContentsOptions | None = None,
    *,
    iden: str | None = None,
) -> ExaFindSimilarTool:
    """Creates an Exa find similar tool.

    Args:
        client: The Exa async client. Required.

        num_results: The number of similar results to return. Defaults to 5.
        include_domains: An optional list of domains to include in the results.
        exclude_domains: An optional list of domains to exclude from the results.
        contents_options: Optional content retrieval options.
    """
    return ExaFindSimilarTool(
        client=client,
        num_results=num_results,
        max_characters=max_characters,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        contents_options=contents_options,
        iden=iden,
    )


def exa_get_contents_tool(
    client: AsyncExa,
    max_characters: PositiveInt | None = None,
    contents_options: ExaContentsOptions | None = None,
    *,
    summary: Literal[True] | None = None,
    filter_empty_results: bool = True,
    iden: str | None = None,
) -> ExaGetContentsTool:
    """Creates an Exa get contents tool.

    Args:
        client: The Exa async client. Required.
        max_characters: Maximum characters of text content per result. Use this to limit
            token usage. Defaults to None (no limit).
        contents_options: Optional content retrieval options.
        filter_empty_results: Whether to filter out empty results. Defaults to True.
        summary: Whether to include a summary of the content. Defaults to None.

    """
    return ExaGetContentsTool(
        client=client,
        max_characters=max_characters,
        contents_options=contents_options,
        summary=summary,
        filter_empty_results=filter_empty_results,
        iden=iden,
    )


def exa_answer_tool(
    client: AsyncExa,
    system_prompt: str | None = None,
    model: Literal["exa", "exa-pro"] | LiteralStringT | None = None,
    iden: str | None = None,
) -> ExaAnswerTool:
    """Creates an Exa answer tool.

    Args:
        client: The Exa async client. Required.
        system_prompt: An optional system prompt to provide to the Exa answer tool. This can be used to guide the behavior of the tool. For example, you could provide a prompt that instructs the tool to focus on certain types of sources. If not provided, the tool will use its default behavior.
            This is useful for sharing a client across multiple tools.
    """
    return ExaAnswerTool(client=client, system_prompt=system_prompt, iden=iden, model=model)


_annotations = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
)


async def _get_exa_search_tool(instance: ExaSearchTool) -> Tool[ExaSearchResult]:
    """Gets an Exa search tool."""
    adapter = get_type_adapter(list[ExaSearchResult], module=__name__)
    return await build_data_tool(
        ToolRegistrationDict(
            fn=instance.__call__,
            name="exa_web_search",
            description="Get web and database search results from Exa. Use this tool to get up-to-date information on external APIs, usage examples, and language updates/changes.",
            tags=CONTEXT_AGENT_TAGS | {"exa", "web_search_tool"},
            output_schema=get_schema_for_type(adapter=adapter),
            serializer=get_serializer_for_type(adapter=adapter),
            annotations=_annotations,
        )
    )


async def _get_exa_find_similar_tool(instance: ExaFindSimilarTool) -> Tool[ExaFindSimilarTool]:
    """Gets an Exa find similar tool."""
    adapter = get_type_adapter(list[ExaSearchResult], module=__name__)
    return await build_data_tool(
        ToolRegistrationDict(
            fn=instance.__call__,
            name="exa_find_similar",
            description="Provide a URL or list of URLs and get similar content from other sources.",
            tags=CONTEXT_AGENT_TAGS | {"exa", "find_similar_tool"},
            output_schema=get_schema_for_type(adapter=adapter),
            serializer=get_serializer_for_type(adapter=adapter),
            annotations=_annotations,
        )
    )


async def _get_exa_get_contents_tool(instance: ExaGetContentsTool) -> Tool[ExaGetContentsTool]:
    """Gets an Exa get contents tool."""
    adapter = get_type_adapter(list[ExaContentResult], module=__name__)
    return await build_data_tool(
        ToolRegistrationDict(
            fn=instance.__call__,
            name="exa_get_contents",
            description="Get the contents of a URL or list of URLs.",
            tags=CONTEXT_AGENT_TAGS | {"exa", "get_contents_tool"},
            output_schema=get_schema_for_type(adapter=adapter),
            serializer=get_serializer_for_type(adapter=adapter),
            annotations=_annotations,
        )
    )


async def _get_exa_answer_tool(instance: ExaAnswerTool) -> Tool[ExaAnswerTool]:
    """Gets an Exa answer tool."""
    adapter = get_type_adapter(ExaAnswerResult, module=__name__)
    return await build_data_tool(
        ToolRegistrationDict(
            fn=instance.__call__,
            name="exa_answer",
            description="Get a researched answer to a question from Exa. Use this to get a precise and well-supported response for a specific need. For example: 'What is the call signature and associated types for version 2.2 of Pydantic's `TypeAdapter` and its methods?'",
            tags=CONTEXT_AGENT_TAGS | {"exa", "answer_tool"},
            output_schema=get_schema_for_type(adapter=adapter),
            serializer=get_serializer_for_type(adapter=adapter),
            annotations=_annotations,
        )
    )


@overload
async def register_exa_tools(
    *, client: AsyncExa, config: ExaToolConfig, register: bool = True, return_tools: Literal[True]
) -> list[Tool]: ...
@overload
async def register_exa_tools(*, client: AsyncExa, config: ExaToolConfig) -> None: ...
async def register_exa_tools(
    *, client: AsyncExa, config: ExaToolConfig, register: bool = True, return_tools: bool = False
) -> None | list[Tool]:
    # sourcery skip: dict-assign-update-to-union
    """Registers Exa tools with the given FastMCP app."""
    if not has_package("exa_py"):
        logger.info("exa_py package not found, skipping Exa toolset registration.")
        return None
    tools = []
    if config.include_search:
        logger.debug("Registering Exa tool: search")
        instance = exa_search_tool(client, **((config.search_config) or {} | {"iden": config.iden}))
        tools.append(await _get_exa_search_tool(instance))
    if config.include_find_similar:
        logger.debug("Registering Exa tool: find_similar")
        instance = exa_find_similar_tool(
            client, **((config.find_similar_config) or {} | {"iden": config.iden})
        )
        tools.append(await _get_exa_find_similar_tool(instance))
    if config.include_get_contents:
        logger.debug("Registering Exa tool: get_contents")
        instance = exa_get_contents_tool(
            client, **((config.get_contents_config) or {} | {"iden": config.iden})
        )
        tools.append(await _get_exa_get_contents_tool(instance))
    if config.include_answer:
        logger.debug("Registering Exa tool: answer")
        instance = exa_answer_tool(client, **((config.answer_config) or {} | {"iden": config.iden}))
        tools.append(await _get_exa_answer_tool(instance))
    if tools and register:
        # Run all registrations and aggregate any failures so that
        # registration behavior is deterministic and does not depend on timing.
        results = await asyncio.gather(
            *(register_data_tool(tool) for tool in tools), return_exceptions=True
        )
        errors = [exc for exc in results if isinstance(exc, Exception)]
        if errors:
            # Raise a single error summarizing all registration failures.
            error_messages = "; ".join(f"{type(e).__name__}: {e}" for e in errors)
            raise RuntimeError(
                f"One or more Exa tool registrations failed: {error_messages}"
            ) from errors[0]
    return tools if return_tools else None


type ExaToolType = ExaSearchTool | ExaFindSimilarTool | ExaGetContentsTool | ExaAnswerTool


async def exa_toolset(
    client: AsyncExa,
    *,
    config: ExaToolConfig | None = None,
    register: bool = True,
) -> list[Tool]:
    """Create and optionally register Exa tools based on configuration.

    This is the main entry point for the Exa data provider, used by the
    service card system. It creates all configured Exa tools based on the
    provided configuration.

    Args:
        client: The Exa async client.
        config: Tool configuration. If None, uses `ExaToolConfig()` defaults
            (both answer and get-contents tools enabled by default).
        register: Whether to register the tools. Defaults to True.

    Returns:
        List of created Tool instances.
    """
    if config is None:
        # Default config: uses ExaToolConfig defaults (answer + get-contents enabled)
        config = ExaToolConfig()

    tools = await register_exa_tools(
        client=client,
        config=config,
        register=register,
        return_tools=True,
    )
    return tools or []


__all__ = (
    "ExaAnswerResult",
    "ExaAnswerTool",
    "ExaContentResult",
    "ExaFindSimilarTool",
    "ExaGetContentsTool",
    "ExaSearchResult",
    "ExaSearchTool",
    "ExaToolType",
    "exa_answer_tool",
    "exa_find_similar_tool",
    "exa_get_contents_tool",
    "exa_search_tool",
    "exa_toolset",
    "register_exa_tools",
)
