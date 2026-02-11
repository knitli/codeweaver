# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Base settings class for provider categories (e.g. agent, embedding, etc.).

The base class here defines the top-level settings for all provider categories, and is extended by the specific provider category settings classes (e.g. BaseAgentProviderSettings, EmbeddingProviderSettings, etc.).
"""

from __future__ import annotations

import asyncio
import logging

from abc import ABC, abstractmethod
from typing import Annotated, Any, NotRequired, Required, Self, TypedDict, cast

from beartype.typing import ClassVar
from pydantic import Field, PositiveFloat, PositiveInt, computed_field, model_validator

from codeweaver.core import ProviderCategory
from codeweaver.core.exceptions import CodeWeaverDeveloperError
from codeweaver.core.types import (
    AnonymityConversion,
    BasedModel,
    FilteredKey,
    FilteredKeyT,
    LiteralSDKClient,
    ModelName,
    Provider,
    ProviderLiteralString,
    SDKClient,
)
from codeweaver.providers.config.clients.base import ClientOptions
from codeweaver.providers.config.clients.utils import ensure_endpoint_version
from codeweaver.providers.config.types import HttpxClientParams


logger = logging.getLogger(__name__)


class ConnectionRateLimitConfig(BasedModel):
    """Settings for connection rate limiting."""

    max_requests_per_second: PositiveInt | None
    burst_capacity: PositiveInt | None
    backoff_multiplier: PositiveFloat | None
    max_retries: PositiveInt | None


class ConnectionConfiguration(BasedModel):
    """Settings for connection configuration. You probably don't need to set these unless you're doing something special."""

    headers: Annotated[
        dict[str, str] | None, Field(description="HTTP headers to include in requests.")
    ] = None
    rate_limits: Annotated[
        ConnectionRateLimitConfig | None,
        Field(description="Rate limit configuration for the connection."),
    ] = None
    httpx_config: Annotated[
        HttpxClientParams | None,
        Field(
            description="You may optionally provide custom client parameters for the httpx client. CodeWeaver will use your parameters when it constructs its http client pool. You probably don't need this unless you need to handle unique auth or similar requirements."
        ),
    ] = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("headers"): AnonymityConversion.BOOLEAN,
            FilteredKey("httpx_config"): AnonymityConversion.BOOLEAN,
        }


def _resolve_tag(data: dict[str, Any]) -> ProviderLiteralString:
    provider: Provider = (
        prov
        if (prov := data.get("provider")) and isinstance(prov, Provider)
        else Provider.from_string(prov)
        if prov
        else Provider.NOT_SET
    )
    return cast(ProviderLiteralString, provider.variable)


_provider_explanation = """\
The provider for these settings.

For cloud providers, this is the answer to the question "who do you pay for this service?" Like `bedrock` (AWS) or `voyage`. With free tiers, you may not actually pay. Another way to think of it is: "who do I authenticate with?". If you need Azure authentication, for example, the provider is `azure`.

For local providers, this is the answer to the question "who do you use for this service?" Like `sentence-transformers` or `fastembed`. One exception is `duckduckgo`, a data provider which doesn't require authentication but is still a cloud provider, so its provider is `duckduckgo`.

>[!Important] The provider is **not necessarily the same as**:
> - **the client** used to connect to the service (e.g. you might use an OpenAI client to connect to Azure OpenAI, in which case the provider is `azure` but the client is `openai`),
> - **the provider class in CodeWeaver** that implements the provider or its configuration (e.g. you might use `OpenAIAgentProviderSettings` to connect to a non-OpenAI service that mimics OpenAI's API, in which case the provider might be `azure` but the provider class is still `OpenAIAgentProviderSettings`).
> - **the model family**. You can use Anthropic models on Azure, Bedrock, OpenRouter, and many others, for example, so the provider of an Anthropic model might be `azure`, `bedrock`, `openrouter`, etc. depending on where you access it, and is not necessarily `anthropic`.
> A provider **can** be the same as the client, model, and class, but not always.

For any top-level subclass of `BaseProviderCategorySettings`, like `EmbeddingProviderSettings`, the `provider` field **is required**, even if it can only be one value for that class. That's because it's how we figure out that's the class you want. For example, if you create an `EmbeddingProviderSettings` with `provider=Provider.FASTEMBED`, we know to create a `FastEmbedEmbeddingProviderSettings` instance.
"""


class BaseProviderCategorySettings(BasedModel, ABC):
    """Base settings for all providers."""

    provider: Annotated[Provider, Field(description=_provider_explanation)]

    connection: ConnectionConfiguration | None = None
    client_options: Annotated[
        ClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None
    tag: ProviderLiteralString = Field(
        default_factory=_resolve_tag,
        description="A tag to differentiate between multiple providers of the same type. You don't need to provide this, we'll figure it out from the provider, provider category, and other context.",
    )

    category: ClassVar[ProviderCategory]
    """The provider category for these settings. This is set in the subclasses and used to determine which provider class to instantiate when loading from config."""

    def __init__(self, **data: Any) -> None:
        """Initialize base provider settings."""
        from codeweaver.core.di import get_container

        try:
            container = get_container()
            container.register(type(self), lambda: self)
        except Exception as e:
            logger.debug(
                "Dependency injection container not available, skipping registration of ProviderSettings: %s",
                e,
            )
        data.pop("as_backup", None)
        data.pop("_as_backup", None)
        object.__setattr__(self, "client_options", data.get("client_options"))
        data |= {"client_options": self.client_options}
        if (
            "model_name" in type(self).model_fields
            and "model_name" not in data
            and (
                category_config := (
                    getattr(self, "embedding_config", None)
                    or getattr(self, "sparse_embedding_config", None)
                    or getattr(self, "reranking_config", None)
                )
            )
            and category_config.model_name
        ):
            object.__setattr__(self, "model_name", category_config.model_name)
        elif (
            "model_name" in type(self).model_fields
            and "model_name" not in data
            and self.client_options
            and (
                model_name := next(
                    (
                        getattr(self.client_options, k, None)
                        for k in ("model_name", "model", "model_id", "model_name_or_path")
                        if getattr(self.client_options, k, None)
                    ),
                    None,
                )
            )
        ):
            object.__setattr__(self, "model_name", ModelName(model_name))
        data = self._initialize(data)
        super().__init__(**data)

    def _initialize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Perform any additional initialization steps. Happens before pydantic initialization and the model's post_init."""
        client_options = data.get("client_options")
        if isinstance(client_options, dict):
            data["client_options"]["tag"] = cast(SDKClient, self.client).variable
        elif client_options:
            data["client_options"].tag = cast(SDKClient, self.client).variable
        return data

    def _set_client_option(
        self, data: dict[str, Any], field_name: str, value: Any
    ) -> dict[str, Any]:
        """Helper method to set a client option value in the input data dictionary during initialization."""
        if client_options := data.get("client_options") or getattr(self, "client_options", None):
            if isinstance(client_options, dict):
                client_options[field_name] = value
            else:
                setattr(client_options, field_name, value)
            data["client_options"] = client_options
        return data

    def __model_post_init__(self) -> None:
        """Post-initialization to register in DI container and config registry."""
        try:
            from codeweaver.core.di import get_container

            container = get_container()
            container.register(type(self), lambda: self)
        except Exception as e:
            logger.debug(
                "Failed to register %s in DI container (monorepo mode): %s", type(self).__name__, e
            )

    @model_validator(mode="after")
    def _ensure_endpoint_version(self) -> Self:
        """Ensure that any endpoints in client_options have the correct version suffix."""
        if not self.client_options:
            return self
        if (
            self.client_options
            and self.client_options._core_provider in {Provider.COHERE, Provider.OPENAI}
            and (endpoint := getattr(self.client_options, "base_url", None))
        ):
            object.__setattr__(
                self,
                "client_options",
                self.client_options.model_copy(
                    update={
                        "base_url": ensure_endpoint_version(
                            endpoint, cohere=self.client_options._core_provider == Provider.COHERE
                        )
                    }
                ),
            )
        return self

    def _telemetry_keys(self) -> None:
        return None

    @abstractmethod
    def is_cloud(self) -> bool:
        """Return True if the provider settings are for a cloud deployment."""
        raise NotImplementedError("is_cloud must be implemented by subclasses.")

    def is_local(self) -> bool:
        """Return True if the provider settings are for a local deployment."""
        return not self.is_cloud

    @abstractmethod
    @computed_field
    def client(self) -> LiteralSDKClient:
        """Return an SDKClient enum member corresponding to this provider settings instance.  Often this is the same as `self.provider`, but not always, and sometimes must be computed (e.g., Azure embedding models)."""
        raise NotImplementedError("client must be implemented by subclasses.")

    async def get_client(self) -> Any:
        """Construct and return the client instance based on the provider settings."""
        options = (
            self.client_options.as_settings()
            if isinstance(self.client_options, ClientOptions)
            else {}
        )
        client_import = cast(SDKClient, self.client).client
        category = next(
            (
                name
                for name in ("agent", "data", "sparse", "embed", "rerank")  # order matters here
                if name in type(self).__name__.lower()
            ),
            None,
        )
        if self.provider == Provider.BEDROCK:
            if not category:
                raise CodeWeaverDeveloperError(
                    "Kind must be one of 'agent', 'data', 'sparse', 'embed', or 'rerank' for Bedrock provider. File an issue. This is unexpected."
                )
            return client_import._resolve()(
                "bedrock-runtime" if category == "embed" else "bedrock-agent-runtime", **options
            )
        if (self.provider in (Provider.SENTENCE_TRANSFORMERS, Provider.FASTEMBED)) or (
            self.provider in (Provider.BEDROCK) and self.client != SDKClient.ANTHROPIC
        ):
            return await asyncio.to_thread(client_import._resolve(), **options)
        if not isinstance(client_import, dict):
            return client_import._resolve()(**options)
        client_class = client_import.get(category)._resolve()
        return client_class(**options)


class BaseProviderCategorySettingsDict(TypedDict, total=False):
    """Base settings for all providers. Represents `BaseProviderCategorySettings` in a TypedDict form."""

    provider: Required[Provider]
    connection: NotRequired[ConnectionConfiguration | None]
    tag: NotRequired[ProviderLiteralString]
    client_options: NotRequired[ClientOptions | None]


__all__ = (
    "BaseProviderCategorySettings",
    "BaseProviderCategorySettingsDict",
    "ConnectionConfiguration",
    "ConnectionRateLimitConfig",
)
