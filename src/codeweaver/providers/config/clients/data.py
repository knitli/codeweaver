# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Data client options for various data providers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import AnyUrl, Discriminator, Field, PositiveFloat, SecretStr, Tag

from codeweaver.core.constants import DEFAULT_AGENT_TIMEOUT
from codeweaver.core.types import AnonymityConversion, FilteredKey, FilteredKeyT, Provider
from codeweaver.providers.config.clients.base import ClientOptions


class TavilyClientOptions(ClientOptions):
    """Client options for the Tavily data provider."""

    _core_provider: Provider = Provider.TAVILY
    _providers: tuple[Provider, ...] = (Provider.TAVILY,)
    tag: Literal["tavily"] = "tavily"

    api_key: SecretStr | str | None = None
    company_info_tags: Sequence[str] | None = None
    proxies: dict[str, str] | None = None
    api_base_url: AnyUrl | None = None
    timeout: PositiveFloat | None = DEFAULT_AGENT_TIMEOUT

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("api_key"): AnonymityConversion.BOOLEAN,
            FilteredKey("proxies"): AnonymityConversion.BOOLEAN,
            FilteredKey("api_base_url"): AnonymityConversion.HASH,
        }


class DuckDuckGoClientOptions(ClientOptions):
    """Client options for the DuckDuckGo data provider."""

    _core_provider: Provider = Provider.DUCKDUCKGO
    _providers: tuple[Provider, ...] = (Provider.DUCKDUCKGO,)
    tag: Literal["duckduckgo"] = "duckduckgo"

    proxy: str | None = None
    timeout: PositiveFloat | None = None
    verify: bool = True

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        return {FilteredKey("proxy"): AnonymityConversion.BOOLEAN} if self.proxy else None


class ExaClientOptions(ClientOptions):
    """Client options for the Exa data provider."""

    _core_provider: Provider = Provider.EXA
    _providers: tuple[Provider, ...] = (Provider.EXA,)
    tag: Literal["exa"] = "exa"

    api_key: SecretStr | str | None = None
    api_base: AnyUrl | None = AnyUrl("https://api.exa.ai")

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("api_key"): AnonymityConversion.BOOLEAN,
            FilteredKey("api_base"): AnonymityConversion.HASH,
        }


def _data_client_options_discriminator(v: Any) -> str:
    """Identify the data client provider settings type for discriminator field."""
    fields = list(v if isinstance(v, dict) else type(v).model_fields)
    if any(
        field in fields for field in ("company_info_tags", "api_base_url", "proxies", "api_key")
    ):
        return "tavily"
    return "duckduckgo"


type GeneralDataClientOptionsType = Annotated[
    Annotated[TavilyClientOptions, Tag(Provider.TAVILY.variable)]
    | Annotated[DuckDuckGoClientOptions, Tag(Provider.DUCKDUCKGO.variable)],
    Field(
        description="Data client options type.",
        discriminator=Discriminator(_data_client_options_discriminator),
    ),
]


__all__ = (
    "DuckDuckGoClientOptions",
    "ExaClientOptions",
    "GeneralDataClientOptionsType",
    "TavilyClientOptions",
)
