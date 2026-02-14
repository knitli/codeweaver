# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Data client options for various data providers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, ClassVar, Literal

from pydantic import AnyUrl, Field, PositiveFloat, SecretStr

from codeweaver.core.constants import DEFAULT_AGENT_TIMEOUT
from codeweaver.core.types import AnonymityConversion, FilteredKey, FilteredKeyT, Provider
from codeweaver.providers.config.clients.base import ClientOptions


class TavilyClientOptions(ClientOptions):
    """Client options for the Tavily data provider."""

    _core_provider: ClassVar[Literal[Provider.TAVILY]] = Provider.TAVILY
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.TAVILY,)

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

    _core_provider: ClassVar[Literal[Provider.DUCKDUCKGO]] = Provider.DUCKDUCKGO
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.DUCKDUCKGO,)

    proxy: str | None = None
    timeout: PositiveFloat | None = None
    verify: bool = True

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        return {FilteredKey("proxy"): AnonymityConversion.BOOLEAN} if self.proxy else None


class ExaClientOptions(ClientOptions):
    """Client options for the Exa data provider."""

    _core_provider: ClassVar[Literal[Provider.EXA]] = Provider.EXA
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.EXA,)

    api_key: SecretStr | str | None = None
    api_base: AnyUrl | None = AnyUrl("https://api.exa.ai")

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("api_key"): AnonymityConversion.BOOLEAN,
            FilteredKey("api_base"): AnonymityConversion.HASH,
        }


type GeneralDataClientOptionsType = Annotated[
    DuckDuckGoClientOptions | ExaClientOptions | TavilyClientOptions,
    Field(description="Data client options type."),
]


__all__ = (
    "DuckDuckGoClientOptions",
    "ExaClientOptions",
    "GeneralDataClientOptionsType",
    "TavilyClientOptions",
)
