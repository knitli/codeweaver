# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Client Options for Agent-based Providers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal, override
from urllib.parse import urlparse

import httpx

from pydantic import AnyUrl, Discriminator, Field, PositiveFloat, PositiveInt, SecretStr, Tag

from codeweaver.core import has_package
from codeweaver.core.constants import DEFAULT_AGENT_TIMEOUT, ONE_MINUTE
from codeweaver.core.types import (
    AnonymityConversion,
    FilteredKey,
    FilteredKeyT,
    LiteralProviderType,
    LiteralStringT,
    Provider,
)
from codeweaver.providers.config.clients.base import ClientOptions
from codeweaver.providers.config.clients.multi import (
    BedrockClientOptions,
    CohereClientOptions,
    GoogleClientOptions,
    HuggingFaceClientOptions,
    MistralClientOptions,
    OpenAIClientOptions,
)
from codeweaver.providers.config.clients.utils import (
    ANTHROPIC_CLIENT_OPTIONS_AGENT_DISCRIMINATOR,
    simple_provider_discriminator,
)


if TYPE_CHECKING and has_package("google"):
    from google.auth.credentials import Credentials as GoogleCredentials
else:
    GoogleCredentials = Any


# ===========================================================================
# *                 Options for Agent-only Clients
# ===========================================================================

_DEFAULT_XAI_RPC_TIMEOUT = 27.0 * ONE_MINUTE
"""Default timeout for X_AI API calls. Set to 27 minutes, which is the same as XAI's default timeout (even though their docs say it's 15 minutes...)."""


class XAIClientOptions(ClientOptions):
    """Client options for X_AI-based providers."""

    _core_provider: ClassVar[Literal[Provider.X_AI]] = Provider.X_AI
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.X_AI,)

    api_key: SecretStr | None = None
    management_api_key: SecretStr | None = None

    api_host: Literal["api.x.ai"] | str = "api.x.ai"
    management_api_host: Literal["management-api.x.ai"] | str = "management-api.x.ai"

    channel_options: list[tuple[str, Any]] | None = None
    """gRPC channel options.

    As of 5 February 2026, X_AI's default gRPC channel options are:

    ```python
    [
    ("grpc.max_send_message_length", 20 * _MIB), # _MIB is one megabyte
    ("grpc.max_receive_message_length", 20 * _MIB),
    ("grpc.enable_retries", 1),
    ("grpc.service_config", _DEFAULT_SERVICE_CONFIG_JSON),
    ("grpc.keepalive_time_ms", 30000),  # 30 seconds
    ("grpc.keepalive_timeout_ms", 10000),  # 10 seconds
    ("grpc.keepalive_permit_without_calls", 1),
    ("grpc.http2.max_pings_without_data", 0),
    ]
    ```
    """

    timeout: PositiveFloat = _DEFAULT_XAI_RPC_TIMEOUT
    """Timeout for X_AI API calls. Default is 27 minutes, which is the same as XAI's default timeout (even though their docs say it's 15 minutes...)"""
    use_insecure_channel: bool = False

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey(name): AnonymityConversion.BOOLEAN
            for name in ("api_key", "management_api_key", "channel_options")
        } | {
            FilteredKey(name): AnonymityConversion.HASH
            for name in ("api_host", "management_api_host")
            if not getattr(self, name).endswith("x.ai")
        }


def _test_url_for_provider(url: str, domain: str) -> bool:
    """Test if the given URL is likely to be associated with the given provider based on its domain."""
    try:
        parsed_url = urlparse(url)
        return parsed_url.netloc.endswith(domain)
    except Exception:
        return False


class BaseAnthropicClientOptions(ClientOptions):
    """Base client options for Anthropic-based providers."""

    _core_provider: ClassVar[
        Literal[
            Provider.ANTHROPIC, Provider.BEDROCK, Provider.AZURE, Provider.GOOGLE, Provider.GROQ
        ]
    ]
    _providers: ClassVar[tuple[Provider, ...]] = (
        Provider.ANTHROPIC,
        Provider.BEDROCK,
        Provider.AZURE,
        Provider.GOOGLE,
        Provider.GROQ,
    )
    tag: Literal["anthropic", "anthropic-bedrock", "anthropic-azure", "anthropic-google", "groq"]

    base_url: AnyUrl | None = None
    timeout: PositiveFloat | httpx.Timeout | None = DEFAULT_AGENT_TIMEOUT
    max_retries: PositiveInt | None = None
    default_headers: Mapping[str, str] | None = None
    default_query: Mapping[str, object] | None = None
    http_client: httpx.Client | None = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey(name): AnonymityConversion.BOOLEAN
            for name in ("http_client", "default_headers", "default_query")
        } | {
            FilteredKey("base_url"): AnonymityConversion.HASH
            if self.base_url and _test_url_for_provider(str(self.base_url), "anthropic.com")
            else AnonymityConversion.BOOLEAN
        }


class AnthropicClientOptions(BaseAnthropicClientOptions):
    """Client options for Anthropic-based embedding providers."""

    _core_provider: ClassVar[Literal[Provider.ANTHROPIC]] = Provider.ANTHROPIC
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.ANTHROPIC,)
    tag: Literal["anthropic"] = "anthropic"

    api_key: SecretStr | None = None
    auth_token: SecretStr | None = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey(name): AnonymityConversion.BOOLEAN for name in ("api_key", "auth_token")
        } | super()._telemetry_keys()


class AnthropicBedrockClientOptions(BaseAnthropicClientOptions):
    """Client options for Anthropic agents on Bedrock runtime.

    These differ from the standard AWS SDK options because Anthropic's client uses different variable names, which it converts to the standard AWS variable names internally. For example, `aws_secret_key` instead of `aws_secret_access_key`.
    """

    _core_provider: ClassVar[Literal[Provider.BEDROCK]] = Provider.BEDROCK
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.BEDROCK,)
    tag: Literal["anthropic-bedrock"] = "anthropic-bedrock"

    aws_secret_key: SecretStr | None = None
    aws_access_key: SecretStr | None = None
    aws_region: str | None = None
    aws_profile: str | None = None
    aws_session_token: SecretStr | None = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return (
            {
                FilteredKey(name): AnonymityConversion.BOOLEAN
                for name in ("aws_secret_key", "aws_access_key", "aws_session_token")
            }
            | {
                FilteredKey("aws_region"): AnonymityConversion.HASH,
                FilteredKey("aws_profile"): AnonymityConversion.HASH,
            }
            | super()._telemetry_keys()
        )


class AnthropicAzureClientOptions(BaseAnthropicClientOptions):
    """Client options for Anthropic agents on Azure Foundry."""

    _core_provider: ClassVar[Literal[Provider.AZURE]] = Provider.AZURE
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.AZURE,)
    tag: Literal["anthropic-azure"] = "anthropic-azure"

    resource: str | None = None
    api_key: SecretStr | None = None
    azure_ad_token_provider: Callable[[], Awaitable[str]] | None = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return (
            {
                FilteredKey(name): AnonymityConversion.BOOLEAN
                for name in ("api_key", "azure_ad_token_provider")
            }
            | {FilteredKey("resource"): AnonymityConversion.HASH}
            | super()._telemetry_keys()
        )


class AnthropicGoogleVertexClientOptions(BaseAnthropicClientOptions):
    """Client options for Anthropic agents on Google Vertex AI runtime."""

    _core_provider: ClassVar[Literal[Provider.GOOGLE]] = Provider.GOOGLE
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.GOOGLE,)
    tag: Literal["anthropic-google"] = "anthropic-google"

    region: str | None = None
    project_id: str | None = None
    access_token: SecretStr | None = None
    credentials: GoogleCredentials | None = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return (
            {
                FilteredKey(name): AnonymityConversion.BOOLEAN
                for name in ("credentials", "access_token")
            }
            | {FilteredKey("project_id"): AnonymityConversion.HASH}
            | super()._telemetry_keys()
        )


# Groq's client is a carbon copy of Anthropic's client, so we can just inherit from it.
class GroqClientOptions(BaseAnthropicClientOptions):
    """Client options for Groq-based agent providers."""

    _core_provider: ClassVar[Literal[Provider.GROQ]] = Provider.GROQ
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.GROQ,)
    tag: Literal["groq"] = "groq"

    api_key: SecretStr | None = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {FilteredKey("api_key"): AnonymityConversion.BOOLEAN} | super()._telemetry_keys()


class OpenAIAgentClientOptions(OpenAIClientOptions):
    """Client options for OpenAI-based agent providers."""

    _core_provider: ClassVar[Literal[Provider.OPENAI]] = Provider.OPENAI
    _providers: ClassVar[tuple[Provider, ...]] = tuple(
        provider for provider in Provider if provider.uses_openai_api and provider != Provider.GROQ
    )
    tag: Literal["openai"] = "openai"

    def computed_base_url(self, provider: LiteralProviderType) -> str | None:
        """Return the default base URL for the OpenAI agent client based on the provider."""
        if self.base_url:
            return str(self.base_url)
        provider = provider if isinstance(provider, Provider) else Provider.from_string(provider)  # ty:ignore[invalid-assignment]
        if found_provider_url := super().computed_base_url(provider):
            return found_provider_url
        if found_agent_provider_url := {
            Provider.ALIBABA: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            Provider.CEREBRAS: "https://api.cerebras.ai/v1",
            Provider.DEEPSEEK: "https://api.deepseek.com/v1",
            Provider.FIREWORKS: "https://api.fireworks.ai/inference/v1",
            Provider.GITHUB: "https://models.github.ai/inference/v1",
            # We have no reliable way of getting a litellm cloud endpoint, so we just try for the local proxy url
            # This is usually how folks use litellm, so it's a reasonable default, and if it doesn't work, they can always set the base_url explicitly.
            Provider.LITELLM: "http://0.0.0.0:4000",
            Provider.MOONSHOT: "https://api.moonshot.ai/v1",
            Provider.NEBIUS: "https://api.studio.nebius.com/v1",
            Provider.OPENROUTER: "https://openrouter.ai/api/v1",
            Provider.OVHCLOUD: "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
            Provider.SAMBANOVA: "https://api.sambanova.ai/v1",
        }.get(provider):
            self.base_url = AnyUrl(found_agent_provider_url)
            return found_agent_provider_url
        return None


class PydanticGatewayClientOptions(ClientOptions):
    """Client options for Pydantic Gateway-based agent providers.

    Pydantic Gateway is a proxy service that routes requests to various upstream LLM providers. It isn't actually a client itself, but we treat it like one for the purposes of configuration. In reality, your options here configure how Pydantic-AI connects to the Pydantic Gateway, and which upstream provider it uses.

    In practice, these values are passed to a factory function in Pydantic-AI that creates the *client and provider* instances based on the upstream provider selected.

    ## Providing Provider-Specific Options

    If you want to define provider-specific options, like for Cohere or OpenAI, you **should not use this class**.
    Instead:
      - Use the provider's options class directly (e.g., `CohereClientOptions` or `OpenAIClientOptions`).
      - Set the base_url (or equivalent) to point to your Pydantic Gateway region.
      - Provide your Pydantic Gateway API key in the `api_key` field.
      - **Set your provider as the upstream_provider**.

    In practice these steps do what pydantic's factory function does, but gives you more customization.

    If you use this class and set Pydantic Gateway as your provider, you can still provide provider-specific ModelConfig settings. These will be passed through to the upstream provider by Pydantic Gateway.
    """

    _core_provider: ClassVar[Literal[Provider.PYDANTIC_GATEWAY]] = Provider.PYDANTIC_GATEWAY
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.PYDANTIC_GATEWAY,)
    tag: Literal["gateway"] = "gateway"

    upstream_provider: (
        Literal["openai", "groq", "anthropic", "bedrock", "gemini", "google-vertex"]
        | LiteralStringT
    )
    """The name of the upstream provider to use (e.g., 'openai'). The Literal type's values are the currently accepted values. We also allow any literal string for future compatibility."""
    route: str | None = None
    api_key: SecretStr | None = None
    base_url: AnyUrl | None = None
    http_client: httpx.Client | None = None

    @override
    def as_settings(self) -> tuple[str, dict[str, Any]]:
        """Return the client options as a dictionary suitable for passing as settings to the client constructor."""
        settings = self.model_dump(exclude={"_core_provider", "_providers", "tag"})
        upstream_provider = settings.pop("upstream_provider")
        return upstream_provider, {k: self._filter_values(v) for k, v in settings.items()}

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey(name): AnonymityConversion.BOOLEAN
            for name in ("api_key", "http_client", "default_headers", "default_query")
        } | (
            {}
            if "pydantic" in str(self.base_url)
            else {FilteredKey("base_url"): AnonymityConversion.HASH}
        )


def discriminate_anthropic_agent_client_options(v: Any) -> str:
    """Identify the Anthropic agent provider settings type for discriminator field."""
    fields = list(v if isinstance(v, dict) else type(v).model_fields)
    if any(field in fields if "aws" in field else False for field in fields):
        return "anthropic-bedrock"
    if "resource" in fields or "azure_ad_token_provider" in fields:
        return "anthropic-azure"
    if any(field in fields for field in ("region", "project_id", "access_token", "credentials")):
        return "anthropic-google"
    if "auth_token" in fields:
        return "anthropic"
    if base_url := str(v.get("base_url") if isinstance(v, dict) else getattr(v, "base_url", None)):
        if _test_url_for_provider(base_url, "groq.ai"):
            return "groq"
        if _test_url_for_provider(base_url, "azure.com"):
            return "anthropic-azure"
        if _test_url_for_provider(base_url, "googleapis.com"):
            return "anthropic-google"
    return "anthropic"


type AnthropicAgentClientOptionsType = Annotated[
    Annotated[AnthropicClientOptions, Tag(Provider.ANTHROPIC.variable)]
    | Annotated[AnthropicBedrockClientOptions, Tag(Provider.BEDROCK.variable)]
    | Annotated[AnthropicAzureClientOptions, Tag(Provider.AZURE.variable)]
    | Annotated[AnthropicGoogleVertexClientOptions, Tag(Provider.GOOGLE.variable)],
    Field(description="Anthropic agent client options type.", discriminator="tag"),
]


type SimpleAgentClientOptionsType = Annotated[
    Annotated[CohereClientOptions, Tag(Provider.COHERE.variable)]
    | Annotated[BedrockClientOptions, Tag(Provider.BEDROCK.variable)]
    | Annotated[OpenAIClientOptions, Tag(Provider.OPENAI.variable)]
    | Annotated[GoogleClientOptions, Tag(Provider.GOOGLE.variable)]
    | Annotated[GroqClientOptions, Tag(Provider.GROQ.variable)]
    | Annotated[HuggingFaceClientOptions, Tag(Provider.HUGGINGFACE_INFERENCE.variable)]
    | Annotated[MistralClientOptions, Tag(Provider.MISTRAL.variable)]
    | Annotated[PydanticGatewayClientOptions, Tag(Provider.PYDANTIC_GATEWAY.variable)]
    | Annotated[XAIClientOptions, Tag(Provider.X_AI.variable)],
    Field(
        description="Agent client options type.",
        discriminator=Discriminator(
            lambda v: (
                simple_provider_discriminator(v)
                if simple_provider_discriminator(v)
                in {
                    "cohere",
                    "openai",
                    "google",
                    "hf_inference",
                    "mistral",
                    "gateway",
                    "x_ai",
                    "groq",
                    "bedrock",
                }
                else "openai"
            )
        ),
    ),
]


type GeneralAgentClientOptionsType = Annotated[
    Annotated[AnthropicAgentClientOptionsType, Tag("anthropic")]
    | Annotated[SimpleAgentClientOptionsType, Tag("other")],
    Field(
        description="General agent client options type.",
        discriminator=ANTHROPIC_CLIENT_OPTIONS_AGENT_DISCRIMINATOR,
    ),
]


__all__ = (
    "AnthropicAgentClientOptionsType",
    "AnthropicAzureClientOptions",
    "AnthropicBedrockClientOptions",
    "AnthropicClientOptions",
    "AnthropicGoogleVertexClientOptions",
    "BaseAnthropicClientOptions",
    "GeneralAgentClientOptionsType",
    "GroqClientOptions",
    "OpenAIAgentClientOptions",
    "PydanticGatewayClientOptions",
    "SimpleAgentClientOptionsType",
    "XAIClientOptions",
    "discriminate_anthropic_agent_client_options",
)
