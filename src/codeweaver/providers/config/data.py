# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Data provider configuration.

This module provides types for configuring data providers, which in fact are internal MCP tools. These tools are used by CodeWeaver's internal context agents to fetch, verify, and tailor information for the user's agent or the user.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

from pydantic import Field, PositiveInt
from pydantic_ai import Tool

from codeweaver.core.exceptions import ConfigurationError
from codeweaver.core.types import BasedModel, LiteralStringT, Provider, ProviderLiteralString
from codeweaver.core.utils import has_package


if TYPE_CHECKING and has_package("exa_py"):
    from exa_py import AsyncExa as AsyncExa
else:
    AsyncExa = Any

if TYPE_CHECKING:
    from codeweaver.providers.data.exa import ExaToolset
    from codeweaver.providers.data.tavily import TavilySearchContextTool


class ExaContentsOptions(TypedDict, total=False):
    """Options for content retrieval in Exa tools."""

    text: NotRequired[Literal[True] | dict[Literal["max_characters"], PositiveInt]]
    """We set the options here from the corresponding ToolOptions (ExaSearchTool and ExaFindSimilarTool)."""
    summary: NotRequired[Literal[True]]
    """Whether to include a summary of the content."""
    max_age_hours: NotRequired[PositiveInt]
    """Maximum age of content to return in hours. This can be used to ensure that the content returned is up-to-date and relevant, especially for rapidly changing topics. If set to None, there will be no age filtering on the content."""


class ExaSearchToolOptions(TypedDict, total=False):
    """Configuration options for Exa's search tool.

    These parameters are passed as instance attributes to the ExaSearchTool. Any settings here will override settings passed to the function call. We do this to allow you to override and prevent certain agent behaviors, such as the number of results returned (because agents are calling the function).
    """

    num_results: NotRequired[PositiveInt]
    """The number of results to return."""

    max_characters: NotRequired[PositiveInt]
    """Maximum characters of text content per result, or None for no limit."""

    contents_options: NotRequired[ExaContentsOptions]
    """Options for content retrieval."""

    include_domains: NotRequired[list[str]]
    """An optional list of domains to include in search results."""

    exclude_domains: NotRequired[list[str]]
    """An optional list of domains to exclude from search results."""

    moderation: NotRequired[bool]
    """Whether to enable Exa's moderation features for this search tool. If True, Exa will process the results through its moderation system to remove potentially harmful or low-quality content. We suggest enabling this, but don't make it a default because of its potential impact on latency."""


class ExaFindSimilarToolOptions(TypedDict, total=False):
    """Configuration options for Exa's find similar tool."""

    num_results: NotRequired[PositiveInt]
    """The number of similar pages to return."""

    max_characters: NotRequired[PositiveInt]
    """Maximum characters of text content per result, or None for no limit."""

    contents_options: NotRequired[ExaContentsOptions | Literal[True]]
    """Options for content retrieval."""

    include_domains: NotRequired[list[str]]
    """An optional list of domains to include in similar page results."""

    exclude_domains: NotRequired[list[str]]
    """An optional list of domains to exclude from similar page results."""


class ExaGetContentsToolOptions(TypedDict, total=False):
    """Configuration options for Exa's get contents tool."""

    summary: NotRequired[Literal[True]]
    """Whether to include a summary of the content."""

    max_characters: NotRequired[PositiveInt]
    """Maximum characters of text content to return, or None for no limit."""

    filter_empty_results: NotRequired[bool]
    """Whether to filter out results that have no content after retrieval. Defaults to True."""


class ExaAnswerToolOptions(TypedDict, total=False):
    """Configuration options for Exa's answer tool."""

    system_prompt: NotRequired[str]
    """A system prompt to provide context and instructions for the answer tool. This can be used to guide the tool's behavior and the style of answers it provides."""

    model: NotRequired[Literal["exa", "exa-pro"] | LiteralStringT]
    """The Exa model to use for answering. "exa" is the default. Currently only 'exa' and 'exa-pro' are valid options, but this is designed to allow for future models to be added as they are released."""


class BaseToolConfig(BasedModel, ABC):
    """Base configuration for data providers."""

    tag: ProviderLiteralString
    provider: Provider

    @abstractmethod
    async def to_call(self, *args: Any, **kwargs: Any) -> Any:
        """Convert the data config to a tool call.

        For example, most tools expect to receive either an api_key or a client instance. The data config should be able to convert itself into the appropriate tool call format, which may involve instantiating a client with the stored API key or other configuration parameters. The context parameter can be used to access any relevant contextual information that may be needed to construct the tool call, such as user information, session data, other relevant state, or flags to specify which tool is called for multi-tool providers.
        """


class ExaToolConfig(BaseToolConfig):
    """Configuration for Exa data provider. Exa is an ai-tailored search service that provides curated web search and deep research capabilities.

    The Exa provider is actually 4 tools:
    - `ExaSearchTool`: Performs web and database (i.e. academic) searches using Exa's search capabilities, returning results and content in a structured format.
    - `ExaFindSimilarTool`: Find pages similar to the given **URL** and returns them with content.
    - `ExaGetContentsTool`: Returns scraped content for a given list of **URLs**.
    - `ExaAnswerTool`: Returns direct answers to specific plain language questions using Exa's search and research capabilities. All answers include citations and links to sources.

    *Not implemented, but this is where we're going:*
    - CodeWeaver's internal context agents use the `GetContentsTool` to retrieve API research and documentation content for inclusion in CodeWeaver's internal knowledge base. This is part of CodeWeaver's latent retrieval and data curation capabilities and happens in between user interactions.
    - They use the `AnswerTool` to augment answers as needed when responding to user or user agent queries with up-to-date information from the web or databases.
    - For now, we don't plan to default to enabling the `SearchTool` and `FindSimilarTool` for internal context agents. The search tool may be worth exposing -- it has multiple modes wit the two most likely useful being `neural` and `deep`. The former is a semantic search mode against a large index of web content, and the latter is a deep multi-agent research tool that can perform complex searches and synthesize information from multiple sources.

    We're very conservative about what tools we expose to the internal context agents; we want to make sure they stay focused on their core competency of tailoring and curating information for the user and the user's agent, and we don't want to overwhelm them with too many tools or capabilities that could lead them astray. The `GetContentsTool` and `AnswerTool` are the most directly relevant to their core competency, so those are the ones we're prioritizing for now.
    """

    tag: ProviderLiteralString = Field(
        "exa",
        description="The provider tag for the Exa data provider. Used for discriminated unions.",
        exclude=True,
        frozen=True,
    )
    provider: Literal[Provider.EXA] = Field(
        Provider.EXA, description="The provider for the Exa data provider.", frozen=True
    )

    include_search: bool = Field(
        False,
        description="Whether to include the search tool in the data provider. Defaults to False.",
    )
    search_config: ExaSearchToolOptions | None = Field(
        None,
        description="Configuration for the ExaSearchTool. Only applicable if include_search is True.",
    )

    include_find_similar: bool = Field(
        False,
        description="Whether to include the find similar tool in the data provider. Defaults to False.",
    )
    find_similar_config: ExaFindSimilarToolOptions | None = Field(
        None,
        description="Configuration for the ExaFindSimilarTool. Only applicable if include_find_similar is True.",
    )

    include_get_contents: bool = Field(
        True,
        description="Whether to include the get contents tool in the data provider. Defaults to True.",
    )
    get_contents_config: ExaGetContentsToolOptions | None = Field(
        None,
        description="Configuration for the ExaGetContentsTool. Only applicable if include_get_contents is True.",
    )

    include_answer: bool = Field(
        True,
        description="Whether to include the answer tool in the data provider. Defaults to True.",
    )
    answer_config: ExaAnswerToolOptions | None = Field(
        None,
        description="Configuration for the ExaAnswerTool. Only applicable if include_answer is True.",
    )

    iden: str | None = Field(
        None,
        description="An optional identifier for this tool configuration. This can be used to specify which tool is being called for multi-tool providers. CodeWeaver will generate a UUID7 if not provided.",
    )

    def _set_contents_options(self) -> None:
        """Set the contents options for search and find similar configs based on the get contents config."""
        for config in (self.search_config, self.find_similar_config):
            if (
                config is not None
                and (contents_options := config.get("contents_options"))
                and contents_options is True
                and (max_characters := config.get("max_characters"))
            ):
                config["contents_options"] = {"max_characters": max_characters}

    def __model_post_init__(self) -> None:
        """Post-initialization processing for the ExaToolConfig."""
        self._set_contents_options()

    def _telemetry_keys(self) -> None:
        """Get the telemetry keys for the Exa data provider."""
        return

    async def to_call(self, *args: Any, **kwargs: Any) -> ExaToolset:
        """Convert the Exa data config to an ExaToolset call."""
        from codeweaver.providers.data.exa import ExaToolset

        if not (client := kwargs.get("client")) and (
            api_key := kwargs.get("api_key") or self.provider.get_env_api_key()
        ):
            try:
                from exa_py import AsyncExa

                client = AsyncExa(api_key=api_key)
            except ImportError as e:
                raise ImportError(
                    "The `exa_py` package is required to use the Exa data provider. Please install it with `pip install code-weaver[exa]`."
                ) from e
        if not client:
            raise ConfigurationError(
                "No client or API key provided for Exa data provider. Please provide either a client instance or an API key."
            )
        return ExaToolset(
            client=client, **self.model_dump(exclude={"tag", "provider"}, exclude_none=True)
        )


class TavilySearchContextToolConfig(BaseToolConfig):
    """Configuration for the TavilySearchContextTool."""

    tag: Literal["tavily"] = Field("tavily", frozen=True, exclude=True)
    provider: Literal[Provider.TAVILY] = Field(Provider.TAVILY, frozen=True)

    max_results: PositiveInt = Field(
        5, description="The maximum number of search results to return.", frozen=True
    )

    include_answer: Literal["basic", "advanced"] = Field(
        "basic",
        description="Whether to include the answer tool in the data provider. Defaults to True.",
    )

    def _telemetry_keys(self) -> None:
        """Get the telemetry keys for the Tavily data provider."""
        return

    async def to_call(self, *args: Any, **kwargs: Any) -> Tool[TavilySearchContextTool]:
        """Convert the Tavily data config to a TavilySearchContextTool call."""
        from codeweaver.providers.data.tavily import tavily_search_tool

        if not (client := kwargs.get("client")) and (
            api_key := kwargs.get("api_key") or self.provider.get_env_api_key()
        ):
            try:
                from tavily import AsyncTavilyClient

                client = AsyncTavilyClient(api_key=api_key)
            except ImportError as e:
                raise ImportError(
                    "The `tavily` package is required to use the Tavily data provider. Please install it with `[uv] pip install code-weaver[tavily]`."
                ) from e
        if not client:
            raise ConfigurationError(
                "No client or API key provided for Tavily data provider. Please provide either a client instance or an API key."
            )
        return tavily_search_tool(client)


type DataToolConfigT = BaseToolConfig | ExaToolConfig | TavilySearchContextToolConfig

__all__ = (
    "BaseToolConfig",
    DataToolConfigT,
    "ExaAnswerToolOptions",
    "ExaContentsOptions",
    "ExaFindSimilarToolOptions",
    "ExaGetContentsToolOptions",
    "ExaSearchToolOptions",
    "ExaToolConfig",
    "TavilySearchContextToolConfig",
)
