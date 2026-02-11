"""Top-level settings for data providers."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import Field, Tag, computed_field

from codeweaver.core.types import LiteralSDKClient, Provider, ProviderCategory, SDKClient
from codeweaver.providers.config.categories.base import BaseProviderCategorySettings
from codeweaver.providers.config.categories.utils import PROVIDER_DISCRIMINATOR, is_cloud_provider
from codeweaver.providers.config.clients import (
    DuckDuckGoClientOptions,
    ExaClientOptions,
    GeneralDataClientOptionsType,
    TavilyClientOptions,
)
from codeweaver.providers.config.data import (
    DuckDuckGoSearchToolConfig,
    ExaToolConfig,
    TavilySearchContextToolConfig,
)


class BaseDataProviderSettings(BaseProviderCategorySettings):
    """Settings for data providers."""

    provider: Literal[Provider.TAVILY, Provider.DUCKDUCKGO, Provider.EXA]

    client_options: GeneralDataClientOptionsType | None = None

    category: ClassVar[Literal[ProviderCategory.DATA]] = ProviderCategory.DATA

    @computed_field(repr=False)
    @property
    def client(self) -> LiteralSDKClient:
        """Return the data SDKClient enum member."""
        return SDKClient.from_string(self.tag)

    def is_cloud(self) -> bool:
        """Return True if the provider is a cloud provider, False otherwise."""
        return is_cloud_provider(self)


class TavilyProviderSettings(BaseDataProviderSettings):
    """Settings for Tavily data provider."""

    provider: Literal[Provider.TAVILY]

    client_options: Annotated[
        TavilyClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None

    tool_config: Annotated[
        TavilySearchContextToolConfig | None,
        Field(description="Tool configuration for Tavily data provider."),
    ] = None

    def __model_post_init__(self) -> None:
        """Post-initialization to set default API key if not provided."""
        if self.client_options is None or not self.client_options.api_key:
            api_key = Provider.TAVILY.get_env_api_key()
            self.client_options = (self.client_options or TavilyClientOptions()).model_copy(
                update={"api_key": api_key}
            )

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.TAVILY]:
        """Return the data SDKClient enum member."""
        return SDKClient.TAVILY


class DuckDuckGoProviderSettings(BaseDataProviderSettings):
    """Settings for DuckDuckGo data provider."""

    provider: Literal[Provider.DUCKDUCKGO]

    client_options: Annotated[
        DuckDuckGoClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    tool_config: Annotated[
        DuckDuckGoSearchToolConfig | None,
        Field(description="Tool configuration for DuckDuckGo data provider."),
    ] = None

    def __model_post_init__(self) -> None:
        """Ensure we have a config."""
        self.client_options = self.client_options or DuckDuckGoClientOptions()

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.DUCKDUCKGO]:
        """Return the data SDKClient enum member."""
        return SDKClient.DUCKDUCKGO


class ExaProviderSettings(BaseDataProviderSettings):
    """Settings for Exa data provider."""

    provider: Literal[Provider.EXA]

    client_options: Annotated[
        ExaClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None

    tool_config: Annotated[
        ExaToolConfig | None, Field(description="Tool configuration for Exa data provider.")
    ] = None

    def __model_post_init__(self) -> None:
        """Ensure we have a config."""
        self.client_options = self.client_options or ExaClientOptions()
        self.tool_config = self.tool_config or ExaToolConfig()

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.EXA]:
        """Return the data SDKClient enum member."""
        return SDKClient.EXA


def _discriminate_data_provider_settings(data: dict) -> Literal["tavily", "duckduckgo", "exa"]:
    """Discriminator function for data provider settings."""
    provider = data["provider"] if isinstance(data, dict) else data.provider
    return provider.variable


type DataProviderSettingsType = Annotated[
    Annotated[TavilyProviderSettings, Tag("tavily")]
    | Annotated[DuckDuckGoProviderSettings, Tag("duckduckgo")]
    | Annotated[ExaProviderSettings, Tag("exa")],
    Field(
        description="The settings for a data provider, which includes the provider type and its specific configuration.",
        discriminator=PROVIDER_DISCRIMINATOR,
    ),
]


__all__ = (
    "BaseDataProviderSettings",
    "DuckDuckGoProviderSettings",
    "ExaProviderSettings",
    "TavilyProviderSettings",
)
