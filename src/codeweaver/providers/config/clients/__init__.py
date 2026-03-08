# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Client options for various providers."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.config.clients.agent import (
        AnthropicAgentClientOptionsType,
        AnthropicAzureClientOptions,
        AnthropicBedrockClientOptions,
        AnthropicClientOptions,
        AnthropicGoogleVertexClientOptions,
        BaseAnthropicClientOptions,
        GeneralAgentClientOptionsType,
        GroqClientOptions,
        OpenAIAgentClientOptions,
        PydanticGatewayClientOptions,
        SimpleAgentClientOptionsType,
        XAIClientOptions,
        discriminate_anthropic_agent_client_options,
    )
    from codeweaver.providers.config.clients.base import ClientOptions
    from codeweaver.providers.config.clients.data import (
        DuckDuckGoClientOptions,
        ExaClientOptions,
        GeneralDataClientOptionsType,
        TavilyClientOptions,
    )
    from codeweaver.providers.config.clients.multi import (
        BedrockClientOptions,
        CohereClientOptions,
        FastEmbedClientOptions,
        GeneralEmbeddingClientOptionsType,
        GeneralRerankingClientOptionsType,
        GoogleClientOptions,
        HuggingFaceClientOptions,
        MistralClientOptions,
        OpenAIClientOptions,
        SentenceTransformersClientOptions,
        SentenceTransformersModelOptions,
        VoyageClientOptions,
        discriminate_azure_embedding_client_options,
    )
    from codeweaver.providers.config.clients.utils import (
        ANTHROPIC_CLIENT_OPTIONS_AGENT_DISCRIMINATOR,
        discriminate_embedding_clients,
        ensure_endpoint_version,
        simple_provider_discriminator,
        try_for_azure_endpoint,
        try_for_heroku_endpoint,
    )
    from codeweaver.providers.config.clients.vector_store import GrpcParams, QdrantClientOptions

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ANTHROPIC_CLIENT_OPTIONS_AGENT_DISCRIMINATOR": (__spec__.parent, "utils"),
    "AnthropicAzureClientOptions": (__spec__.parent, "agent"),
    "AnthropicBedrockClientOptions": (__spec__.parent, "agent"),
    "AnthropicClientOptions": (__spec__.parent, "agent"),
    "AnthropicGoogleVertexClientOptions": (__spec__.parent, "agent"),
    "BaseAnthropicClientOptions": (__spec__.parent, "agent"),
    "BedrockClientOptions": (__spec__.parent, "multi"),
    "ClientOptions": (__spec__.parent, "base"),
    "CohereClientOptions": (__spec__.parent, "multi"),
    "DuckDuckGoClientOptions": (__spec__.parent, "data"),
    "ExaClientOptions": (__spec__.parent, "data"),
    "FastEmbedClientOptions": (__spec__.parent, "multi"),
    "GoogleClientOptions": (__spec__.parent, "multi"),
    "GroqClientOptions": (__spec__.parent, "agent"),
    "GrpcParams": (__spec__.parent, "vector_store"),
    "HuggingFaceClientOptions": (__spec__.parent, "multi"),
    "MistralClientOptions": (__spec__.parent, "multi"),
    "PydanticGatewayClientOptions": (__spec__.parent, "agent"),
    "QdrantClientOptions": (__spec__.parent, "vector_store"),
    "SentenceTransformersClientOptions": (__spec__.parent, "multi"),
    "SentenceTransformersModelOptions": (__spec__.parent, "multi"),
    "TavilyClientOptions": (__spec__.parent, "data"),
    "VoyageClientOptions": (__spec__.parent, "multi"),
    "discriminate_anthropic_agent_client_options": (__spec__.parent, "agent"),
    "discriminate_azure_embedding_client_options": (__spec__.parent, "multi"),
    "discriminate_embedding_clients": (__spec__.parent, "utils"),
    "ensure_endpoint_version": (__spec__.parent, "utils"),
    "OpenAIAgentClientOptions": (__spec__.parent, "agent"),
    "OpenAIClientOptions": (__spec__.parent, "multi"),
    "simple_provider_discriminator": (__spec__.parent, "utils"),
    "try_for_azure_endpoint": (__spec__.parent, "utils"),
    "try_for_heroku_endpoint": (__spec__.parent, "utils"),
    "XAIClientOptions": (__spec__.parent, "agent"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "ANTHROPIC_CLIENT_OPTIONS_AGENT_DISCRIMINATOR",
    "AnthropicAgentClientOptionsType",
    "AnthropicAzureClientOptions",
    "AnthropicBedrockClientOptions",
    "AnthropicClientOptions",
    "AnthropicGoogleVertexClientOptions",
    "BaseAnthropicClientOptions",
    "BedrockClientOptions",
    "ClientOptions",
    "CohereClientOptions",
    "DuckDuckGoClientOptions",
    "ExaClientOptions",
    "FastEmbedClientOptions",
    "GeneralAgentClientOptionsType",
    "GeneralDataClientOptionsType",
    "GeneralEmbeddingClientOptionsType",
    "GeneralRerankingClientOptionsType",
    "GoogleClientOptions",
    "GroqClientOptions",
    "GrpcParams",
    "HuggingFaceClientOptions",
    "MistralClientOptions",
    "OpenAIAgentClientOptions",
    "OpenAIClientOptions",
    "PydanticGatewayClientOptions",
    "QdrantClientOptions",
    "SentenceTransformersClientOptions",
    "SentenceTransformersModelOptions",
    "SimpleAgentClientOptionsType",
    "TavilyClientOptions",
    "VoyageClientOptions",
    "XAIClientOptions",
    "discriminate_anthropic_agent_client_options",
    "discriminate_azure_embedding_client_options",
    "discriminate_embedding_clients",
    "ensure_endpoint_version",
    "simple_provider_discriminator",
    "try_for_azure_endpoint",
    "try_for_heroku_endpoint",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
