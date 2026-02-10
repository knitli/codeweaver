# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""MCP tools for CodeWeaver."""

from __future__ import annotations

import logging

from collections.abc import Callable, Sequence
from typing import Any

from fastmcp.tools import Tool

from codeweaver.core.constants import PREFERRED_SEARCH_PROVIDER_ORDER
from codeweaver.core.types import LiteralProviderType
from codeweaver.core.types.provider import Provider
from codeweaver.core.utils import has_package
from codeweaver.providers.data.duckduckgo import DuckDuckGoSearchTool, duckduckgo_search_tool
from codeweaver.providers.data.exa import ExaToolType, register_exa_tools
from codeweaver.providers.data.tavily import TavilySearchContextTool, tavily_search_tool


logger = logging.getLogger(__name__)


type DataProviderType = type[DuckDuckGoSearchTool | TavilySearchContextTool | ExaToolType]


def get_data_provider(
    provider: LiteralProviderType, *, has_required_auth: bool = False
) -> DataProviderType | Callable[..., Tool[Any]] | None:
    """Get available tools."""
    if isinstance(provider, str):
        provider: Provider = Provider.from_string(provider)
    if provider == Provider.DUCKDUCKGO and has_package("ddgs"):
        return duckduckgo_search_tool
    if provider == Provider.TAVILY and has_required_auth and has_package("tavily"):
        return tavily_search_tool
    if provider == Provider.EXA and has_required_auth and has_package("exa"):
        return register_exa_tools
    data_providers = [provider for provider in Provider if provider.is_data_provider()]
    if provider in data_providers:
        logger.warning(
            "You requested a valid data provider, but it is not available. This probably means you need to install the corresponding package. Install `uv pip install code-weaver[%s]`",
            provider.variable,
        )
    else:
        logger.warning(
            "The provider %s isn't a recognized valid data provider. If we have it listed as one, then it's probably our mistake. Please report this issue at https://github.com/knitli/codeweaver/issues",
            provider.variable,
        )
    return None


def load_default_data_providers(
    providers_with_api_keys: Sequence[LiteralProviderType] | None = None,
) -> tuple[DataProviderType, ...]:
    """Load the first available (preferred) search data provider."""
    normalized_api_providers: list[LiteralProviderType] = (
        list(providers_with_api_keys) if providers_with_api_keys is not None else []
    )
    normalized_api_providers: list[Provider] = [
        provider if isinstance(provider, Provider) else Provider.from_string(provider)
        for provider in normalized_api_providers
        if provider
    ]
    normalized_api_providers.extend(
        provider
        for provider in Provider
        if provider.is_data_provider() and (not provider.requires_auth or provider.has_env_auth)
    )
    possible_providers = sorted(
        set(normalized_api_providers),
        key=lambda p: (
            PREFERRED_SEARCH_PROVIDER_ORDER.index(p.variable)
            if p.variable in PREFERRED_SEARCH_PROVIDER_ORDER
            else len(PREFERRED_SEARCH_PROVIDER_ORDER) + 1
        ),
    )
    if not possible_providers:
        logger.warning("No available search data providers found.")
        return ()
    return (
        (prov,)
        if (
            prov := (
                next(
                    (
                        get_data_provider(provider, has_required_auth=True)
                        for provider in possible_providers
                        if get_data_provider(provider, has_required_auth=True)
                    ),
                    None,
                )
            )
        )
        else ()
    )


__all__ = (
    "DataProviderType",
    "DuckDuckGoSearchTool",
    "duckduckgo_search_tool",
    "get_data_provider",
    "load_default_data_providers",
)
