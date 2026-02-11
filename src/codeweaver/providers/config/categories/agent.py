# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Top-level settings for agent providers."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import Field, Tag, computed_field

from codeweaver.core.types import (
    LiteralProvider,
    LiteralSDKClient,
    Provider,
    ProviderCategory,
    SDKClient,
)
from codeweaver.providers import CohereAgentModelConfig
from codeweaver.providers.config.categories.base import BaseProviderCategorySettings
from codeweaver.providers.config.categories.mixins import AzureProviderMixin, BedrockProviderMixin
from codeweaver.providers.config.categories.utils import (
    ANTHROPIC_PROVIDER_DISCRIMINATOR,
    NON_ANTHROPIC_AGENT_PROVIDER_DISCRIMINATOR,
    PROVIDER_DISCRIMINATOR,
    is_cloud_provider,
)
from codeweaver.providers.config.clients import (
    AnthropicAzureClientOptions,
    AnthropicBedrockClientOptions,
    AnthropicClientOptions,
    AnthropicGoogleVertexClientOptions,
    CohereClientOptions,
    GeneralAgentClientOptionsType,
    GoogleClientOptions,
    GroqClientOptions,
    HuggingFaceClientOptions,
    MistralClientOptions,
    OpenAIClientOptions,
    PydanticGatewayClientOptions,
)
from codeweaver.providers.config.sdk import (
    AgentModelConfig,
    AnthropicAgentModelConfig,
    CerebrasAgentModelConfig,
    GoogleAgentModelConfig,
    GroqAgentModelConfig,
    HuggingFaceAgentModelConfig,
    MistralAgentModelConfig,
    OpenAIAgentModelConfig,
    OpenRouterAgentModelConfig,
)
from codeweaver.providers.config.types import AgentModelNameString


class BaseAgentProviderSettings(BaseProviderCategorySettings):
    """Settings for agent providers."""

    model_name: Annotated[
        AgentModelNameString,
        Field(
            description="The model string for the agent model. This should follow the pattern in `codeweaver.providers.agent.capabilities.KnownAgentModelName`, which is typically in the format `provider:model`, but may vary for certain providers. This field is used to determine the capabilities of the model and to infer the provider if not explicitly specified. Models don't have to be in that type, but they should follow a similar format that includes the provider name for proper resolution."
        ),
    ]
    agent_config: AgentModelConfig | None = None
    "Settings for the agent model(s)."
    client_options: Annotated[
        GeneralAgentClientOptionsType | None,
        Field(description="Client options for the provider's client."),
    ] = None

    category: ClassVar[Literal[ProviderCategory.AGENT]] = ProviderCategory.AGENT

    @computed_field(repr=False)
    @property
    def client(self) -> LiteralSDKClient:
        """Return the agent SDKClient enum member."""
        raise NotImplementedError("Agent provider client resolution is not yet implemented.")

    def is_cloud(self) -> bool:
        """Return True if the provider is a cloud provider, False otherwise."""
        return is_cloud_provider(self)


class OpenRouterAgentProviderSettings(BaseAgentProviderSettings):
    """Settings for OpenRouter agent provider."""

    provider: Literal[Provider.OPENROUTER]

    agent_config: OpenRouterAgentModelConfig | None = None
    client_options: OpenAIClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.OPENAI]:
        """Return the agent SDKClient enum member."""
        return SDKClient.OPENAI


class CerebrasAgentProviderSettings(BaseAgentProviderSettings):
    """Settings for Cerebras agent provider."""

    provider: Literal[Provider.CEREBRAS]

    agent_config: CerebrasAgentModelConfig | None = None
    client_options: OpenAIClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.OPENAI]:
        """Return the agent SDKClientenum member."""
        return SDKClient.OPENAI


class OpenAIAgentProviderSettings(BaseAgentProviderSettings):
    """Settings for the OpenAI agent provider.

    Note: This is a catchall that does not only cover OpenAI as a provider, but also any provider that doesn't have its own settings class.
    """

    provider: LiteralProvider

    agent_config: OpenAIAgentModelConfig | None = None
    client_options: OpenAIClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.OPENAI]:
        """Return the agent SDKClient enum member."""
        return SDKClient.OPENAI


_anthropic_model_pattern = r".*anthropic.*|.*claude.*|.*opus.*|.*sonnet.*|.*haiku.*"


class AnthropicBedrockAgentProviderSettings(BedrockProviderMixin, BaseAgentProviderSettings):
    """Settings for Anthropic models on AWS Bedrock."""

    provider: Literal[Provider.BEDROCK]

    model_name: Annotated[
        AgentModelNameString,
        Field(
            description="The model string for Bedrock Anthropic models.",
            pattern=_anthropic_model_pattern,
        ),
    ]
    agent_config: AnthropicAgentModelConfig | None = None
    client_options: Annotated[
        AnthropicBedrockClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.ANTHROPIC]:
        """Return the agent SDKClient enum member."""
        return SDKClient.ANTHROPIC


class AnthropicAzureAgentProviderSettings(AzureProviderMixin, BaseAgentProviderSettings):
    """Settings for Anthropic models on Azure."""

    provider: Literal[Provider.AZURE]

    model_name: Annotated[
        AgentModelNameString,
        Field(
            description="The model string for Azure Anthropic models.",
            pattern=_anthropic_model_pattern,
        ),
    ]
    agent_config: AnthropicAgentModelConfig | None = None
    client_options: Annotated[
        AnthropicAzureClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.ANTHROPIC]:
        """Return the agent SDKClient enum member."""
        return SDKClient.ANTHROPIC


class AnthropicGoogleVertexAgentProviderSettings(BaseAgentProviderSettings):
    """Settings for Anthropic models on Google Vertex."""

    provider: Literal[Provider.GOOGLE]

    model_name: Annotated[
        AgentModelNameString,
        Field(
            description="The model string for Google Vertex Anthropic models.",
            pattern=_anthropic_model_pattern,
        ),
    ]
    agent_config: AnthropicAgentModelConfig | None = None
    client_options: Annotated[
        AnthropicGoogleVertexClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.ANTHROPIC]:
        """Return the agent SDKClient enum member."""
        return SDKClient.ANTHROPIC


class GroqAgentProviderSettings(BaseAgentProviderSettings):
    """Settings for Groq agent provider."""

    provider: Literal[Provider.GROQ]

    model_name: Annotated[
        AgentModelNameString, Field(description="The model string for Groq Anthropic models.")
    ]
    agent_config: GroqAgentModelConfig | None = None
    client_options: Annotated[
        GroqClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.GROQ]:
        """Return the agent SDKClient enum member."""
        return SDKClient.GROQ


class AnthropicAgentProviderSettings(BaseAgentProviderSettings):
    """Settings for Anthropic agent provider."""

    provider: Literal[Provider.ANTHROPIC]

    model_name: Annotated[
        AgentModelNameString,
        Field(
            description="The model string for Anthropic models.", pattern=_anthropic_model_pattern
        ),
    ]
    agent_config: AnthropicAgentModelConfig | None = None
    client_options: Annotated[
        AnthropicClientOptions | None,
        Field(description="Client options for the Anthropic provider's client."),
    ] = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.ANTHROPIC]:
        """Return the agent SDKClient enum member."""
        return SDKClient.ANTHROPIC


class GoogleAgentProviderSettings(BaseAgentProviderSettings):
    """Settings for the Google agent provider (non-Anthropic)."""

    provider: Literal[Provider.GOOGLE]

    agent_config: GoogleAgentModelConfig | None = None
    client_options: GoogleClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.GOOGLE]:
        """Return the agent SDKClient enum member."""
        return SDKClient.GOOGLE


class CohereAgentProviderSettings(BaseAgentProviderSettings):
    """Settings for the Cohere agent provider."""

    provider: Literal[Provider.COHERE]

    agent_config: CohereAgentModelConfig | None = None
    client_options: CohereClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.COHERE]:
        """Return the agent SDKClient enum member."""
        return SDKClient.COHERE


class HuggingFaceAgentProviderSettings(BaseAgentProviderSettings):
    """Settings for Hugging Face Inference agent models."""

    provider: Literal[Provider.HUGGINGFACE_INFERENCE]

    agent_config: HuggingFaceAgentModelConfig | None = None
    client_options: HuggingFaceClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.HUGGINGFACE_INFERENCE]:
        """Return the agent SDKClient enum member."""
        return SDKClient.HUGGINGFACE_INFERENCE


class MistralAgentProviderSettings(BaseAgentProviderSettings):
    """Settings for Mistral agent provider."""

    provider: Literal[Provider.MISTRAL]

    agent_config: MistralAgentModelConfig | None = None
    client_options: MistralClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.MISTRAL]:
        """Return the agent SDKClient enum member."""
        return SDKClient.MISTRAL


class PydanticGatewayProviderSettings(BaseAgentProviderSettings):
    """Settings for Pydantic Gateway agent provider."""

    provider: Literal[Provider.PYDANTIC_GATEWAY]

    agent_config: AgentModelConfig | None = None
    client_options: PydanticGatewayClientOptions | None = None

    @computed_field(repr=False)
    @property
    def client(self) -> Literal[SDKClient.PYDANTIC_GATEWAY]:
        """Return the agent SDKClient enum member."""
        return SDKClient.PYDANTIC_GATEWAY


type NonAnthropicAgentProviderSettingsType = Annotated[
    Annotated[OpenRouterAgentProviderSettings, Tag("openrouter")]
    | Annotated[CerebrasAgentProviderSettings, Tag("cerebras")]
    | Annotated[OpenAIAgentProviderSettings, Tag("openai")]
    | Annotated[GoogleAgentProviderSettings, Tag("google")]
    | Annotated[CohereAgentProviderSettings, Tag("cohere")]
    | Annotated[HuggingFaceAgentProviderSettings, Tag("hf_inference")]
    | Annotated[MistralAgentProviderSettings, Tag("mistral")]
    | Annotated[PydanticGatewayProviderSettings, Tag("gateway")],
    Field(
        description="A provider settings type for agent providers that do not use the Anthropic client",
        discriminator=NON_ANTHROPIC_AGENT_PROVIDER_DISCRIMINATOR,
    ),
]
"""An Annotated type representing the union of all non-Anthropic agent provider settings types, tagged with their respective provider tags."""

type AnthropicAgentProviderSettingsType = Annotated[
    Annotated[AnthropicAgentProviderSettings, Tag("anthropic")]
    | Annotated[AnthropicBedrockAgentProviderSettings, Tag("bedrock")]
    | Annotated[AnthropicAzureAgentProviderSettings, Tag("azure")]
    | Annotated[AnthropicGoogleVertexAgentProviderSettings, Tag("google")],
    Field(
        description="A provider settings type for agent providers that use the Anthropic client",
        discriminator=PROVIDER_DISCRIMINATOR,
    ),
]

type AgentProviderSettingsType = Annotated[
    Annotated[AnthropicAgentProviderSettingsType, Tag("anthropic")]
    | Annotated[NonAnthropicAgentProviderSettingsType, Tag("other")],
    Field(
        description="The settings for an agent provider, which includes the provider type and its specific configuration.",
        discriminator=ANTHROPIC_PROVIDER_DISCRIMINATOR,
    ),
]
"""An Annotated type representing the union of all agent provider settings types, tagged with "anthropic" for providers that use the Anthropic client and "other" for providers that do not."""


__all__ = (
    "AgentProviderSettingsType",
    "AnthropicAgentProviderSettings",
    "AnthropicAzureAgentProviderSettings",
    "AnthropicBedrockAgentProviderSettings",
    "AnthropicGoogleVertexAgentProviderSettings",
    "BaseAgentProviderSettings",
    "CerebrasAgentProviderSettings",
    "CohereAgentProviderSettings",
    "GoogleAgentProviderSettings",
    "GroqAgentProviderSettings",
    "HuggingFaceAgentProviderSettings",
    "MistralAgentProviderSettings",
    "OpenAIAgentProviderSettings",
    "OpenRouterAgentProviderSettings",
    "PydanticGatewayProviderSettings",
)
