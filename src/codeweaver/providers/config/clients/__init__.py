# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Client options for various providers."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core.utils.lazy_importer import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.config.clients.agent import (
        AnthropicAgentClientOptionsType,
        AnthropicAzureClientOptions,
        AnthropicBedrockClientOptions,
        AnthropicClientOptions,
        AnthropicGoogleVertexClientOptions,
        GeneralAgentClientOptionsType,
        GroqClientOptions,
        OpenAIAgentClientOptions,
        PydanticGatewayClientOptions,
        SimpleAgentClientOptionsType,
        XAIClientOptions,
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
        HFInferenceClientOptions,
        MistralClientOptions,
        OpenAIClientOptions,
        SentenceTransformersClientOptions,
        VoyageClientOptions,
        discriminate_azure_embedding_client_options,
    )
    from codeweaver.providers.config.clients.vector_store import GrpcParams, QdrantClientOptions

_dynamic_imports = MappingProxyType({
    "AnthropicAgentClientOptionsType": (__spec__.parent, "agent"),
    "AnthropicAzureClientOptions": (__spec__.parent, "agent"),
    "AnthropicClientOptions": (__spec__.parent, "agent"),
    "AnthropicBedrockClientOptions": (__spec__.parent, "agent"),
    "AnthropicGoogleVertexClientOptions": (__spec__.parent, "agent"),
    "GeneralAgentClientOptionsType": (__spec__.parent, "agent"),
    "GroqClientOptions": (__spec__.parent, "agent"),
    "OpenAIAgentClientOptions": (__spec__.parent, "agent"),
    "PydanticGatewayClientOptions": (__spec__.parent, "agent"),
    "SimpleAgentClientOptionsType": (__spec__.parent, "agent"),
    "XAIClientOptions": (__spec__.parent, "agent"),
    "DuckDuckGoClientOptions": (__spec__.parent, "data"),
    "ExaClientOptions": (__spec__.parent, "data"),
    "GeneralDataClientOptionsType": (__spec__.parent, "data"),
    "GeneralEmbeddingClientOptionsType": (__spec__.parent, "multi"),
    "GeneralRerankingClientOptionsType": (__spec__.parent, "multi"),
    "GrpcParams": (__spec__.parent, "vector_store"),
    "TavilyClientOptions": (__spec__.parent, "data"),
    "QdrantClientOptions": (__spec__.parent, "vector_store"),
    "ClientOptions": (__spec__.parent, "base"),
    "BedrockClientOptions": (__spec__.parent, "multi"),
    "CohereClientOptions": (__spec__.parent, "multi"),
    "FastEmbedClientOptions": (__spec__.parent, "multi"),
    "GoogleClientOptions": (__spec__.parent, "multi"),
    "HFInferenceClientOptions": (__spec__.parent, "multi"),
    "MistralClientOptions": (__spec__.parent, "multi"),
    "OpenAIClientOptions": (__spec__.parent, "multi"),
    "SentenceTransformersClientOptions": (__spec__.parent, "multi"),
    "VoyageClientOptions": (__spec__.parent, "multi"),
    "discriminate_azure_embedding_client_options": (__spec__.parent, "multi"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "AnthropicAgentClientOptionsType",
    "AnthropicAzureClientOptions",
    "AnthropicBedrockClientOptions",
    "AnthropicClientOptions",
    "AnthropicGoogleVertexClientOptions",
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
    "HFInferenceClientOptions",
    "MistralClientOptions",
    "OpenAIAgentClientOptions",
    "OpenAIClientOptions",
    "PydanticGatewayClientOptions",
    "QdrantClientOptions",
    "SentenceTransformersClientOptions",
    "SimpleAgentClientOptionsType",
    "TavilyClientOptions",
    "VoyageClientOptions",
    "XAIClientOptions",
    "discriminate_azure_embedding_client_options",
)


def __dir__() -> list[str]:
    return list(__all__)
