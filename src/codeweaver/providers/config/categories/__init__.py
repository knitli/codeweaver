# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Entrypoint for provider categories' settings.  A category, in this context, is a specific type of provider (e.g., embedding, re-ranking) that has its own unique settings and configuration requirements. This package has the top-level settings classes for each provider category (such as `RerankingProviderSettings`), which are used to define the configuration for providers of that category. Most categories also have multiple mixins and subclasses for specific providers (e.g., `FastEmbedRerankingProviderSettings`), which are used to define the configuration for specific providers within that category. The mixins are used to provide common functionality and settings for providers that share similar characteristics (e.g., cloud providers, Bedrock providers).

Design principles for adding new provider implementations in a category:
1. **Evaluate the root implementation**: Each category has an implemented base class (e.g. `EmbeddingProviderSettings` from `BaseEmbeddingProviderSettings`). For simple cases, you may not need to create a new class at all. It may be sufficient to just add a new provider enum and handle it in the factory methods.
2. **Create a mixin for provider-specific top-level settings**: If the provider has unique settings that are shared across multiple categories or implementations (e.g., Bedrock-specific settings), or if it requires special handling, create a mixin class.
3. **Creating a new class**: If you need to create a new class for the provider, inherit from the root implementation for the category and any relevant mixins. Your implementation should:
    - Define but not set the `provider` field to your provider's enum member (which you can create dynamically or statically define in the provider enum).
    - Type the category's configuration fields with narrowed types that only apply to the provider (e.g. `BedrockEmbeddingConfig` instead of `EmbeddingConfig`).
    - Inject common settings. There are some settings that are common across the configurations within the provider (in its config class or client options; often from its mixin), such as credentials or connection settings. Don't make users type out nested config settings multiple times. When instantiating the provider's settings, these settings should be injected down into the relevant fields automatically, so users only have to provide them once at the top level of the provider's settings. The base class handles things like the `Provider` field, but anything else is on you.
4. **Special handling**: If your provider requires special handling for initialization that you can't address in the common `_initialize` method. You can provide a callable to its service card (codeweaver.core.types.service_cards.ServiceCard) that will be called during provider initialization.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core.utils.lazy_importer import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.config.categories.agent import (
        AgentProviderSettingsType,
        AnthropicAgentProviderSettings,
        AnthropicAzureAgentProviderSettings,
        AnthropicBedrockAgentProviderSettings,
        AnthropicGoogleVertexAgentProviderSettings,
        BaseAgentProviderSettings,
        CerebrasAgentProviderSettings,
        CohereAgentProviderSettings,
        GoogleAgentProviderSettings,
        GroqAgentProviderSettings,
        HuggingFaceAgentProviderSettings,
        MistralAgentProviderSettings,
        OpenAIAgentProviderSettings,
        OpenRouterAgentProviderSettings,
        PydanticGatewayProviderSettings,
    )
    from codeweaver.providers.config.categories.base import (
        BaseProviderCategorySettings,
        BaseProviderCategorySettingsDict,
        ConnectionConfiguration,
        ConnectionRateLimitConfig,
    )
    from codeweaver.providers.config.categories.data import (
        BaseDataProviderSettings,
        DataProviderSettingsType,
        DuckDuckGoProviderSettings,
        ExaProviderSettings,
        TavilyProviderSettings,
    )
    from codeweaver.providers.config.categories.embedding import (
        AsymmetricEmbeddingProviderSettings,
        AsymmetricEmbeddingProviderSettingsDict,
        AzureEmbeddingProviderSettings,
        BaseEmbeddingProviderSettings,
        BedrockEmbeddingProviderSettings,
        CohereEmbeddingProviderSettings,
        EmbeddingProviderSettings,
        EmbeddingProviderSettingsType,
        FastEmbedEmbeddingProviderSettings,
        GoogleEmbeddingProviderSettings,
        HuggingFaceEmbeddingProviderSettings,
        MistralEmbeddingProviderSettings,
        SentenceTransformersEmbeddingProviderSettings,
        VoyageEmbeddingProviderSettings,
    )
    from codeweaver.providers.config.categories.mixins import (
        AzureProviderMixin,
        BedrockProviderMixin,
        FastEmbedProviderMixin,
    )
    from codeweaver.providers.config.categories.reranking import (
        BaseRerankingProviderSettings,
        BedrockRerankingProviderSettings,
        CohereRerankingProviderSettings,
        FastEmbedRerankingProviderSettings,
        RerankingProviderSettings,
        RerankingProviderSettingsType,
        VoyageRerankingProviderSettings,
    )
    from codeweaver.providers.config.categories.sparse_embedding import (
        BaseSparseEmbeddingProviderSettings,
        FastEmbedSparseEmbeddingProviderSettings,
        SparseEmbeddingProviderSettings,
        SparseEmbeddingProviderSettingsType,
    )
    from codeweaver.providers.config.categories.utils import (
        ANTHROPIC_PROVIDER_DISCRIMINATOR,
        CORE_EMBEDDING_PROVIDER_DISCRIMINATOR,
        NON_ANTHROPIC_AGENT_PROVIDER_DISCRIMINATOR,
        PROVIDER_DISCRIMINATOR,
        RERANKING_PROVIDER_DISCRIMINATOR,
        is_cloud_provider,
    )
    from codeweaver.providers.config.categories.vector_store import (
        BaseVectorStoreProviderSettings,
        MemoryConfig,
        MemoryVectorStoreProviderSettings,
        QdrantVectorStoreProviderSettings,
        VectorStoreProviderSettings,
        VectorStoreProviderSettingsType,
    )


_dynamic_imports = MappingProxyType({
    "ANTHROPIC_PROVIDER_DISCRIMINATOR": (__spec__.parent, "utils"),
    "AgentProviderSettingsType": (__spec__.parent, "agent"),
    "AnthropicAgentProviderSettings": (__spec__.parent, "agent"),
    "AnthropicAzureAgentProviderSettings": (__spec__.parent, "agent"),
    "AnthropicBedrockAgentProviderSettings": (__spec__.parent, "agent"),
    "AnthropicGoogleVertexAgentProviderSettings": (__spec__.parent, "agent"),
    "AsymmetricEmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "AsymmetricEmbeddingProviderSettingsDict": (__spec__.parent, "embedding"),
    "AzureEmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "AzureProviderMixin": (__spec__.parent, "mixins"),
    "BaseAgentProviderSettings": (__spec__.parent, "agent"),
    "BaseDataProviderSettings": (__spec__.parent, "data"),
    "BaseEmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "BaseProviderCategorySettings": (__spec__.parent, "base"),
    "BaseProviderCategorySettingsDict": (__spec__.parent, "base"),
    "BaseRerankingProviderSettings": (__spec__.parent, "reranking"),
    "BaseSparseEmbeddingProviderSettings": (__spec__.parent, "sparse_embedding"),
    "BaseVectorStoreProviderSettings": (__spec__.parent, "vector_store"),
    "BedrockEmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "BedrockProviderMixin": (__spec__.parent, "mixins"),
    "BedrockRerankingProviderSettings": (__spec__.parent, "reranking"),
    "CORE_EMBEDDING_PROVIDER_DISCRIMINATOR": (__spec__.parent, "utils"),
    "CerebrasAgentProviderSettings": (__spec__.parent, "agent"),
    "CohereAgentProviderSettings": (__spec__.parent, "agent"),
    "CohereEmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "CohereRerankingProviderSettings": (__spec__.parent, "reranking"),
    "ConnectionConfiguration": (__spec__.parent, "base"),
    "ConnectionRateLimitConfig": (__spec__.parent, "base"),
    "DataProviderSettingsType": (__spec__.parent, "data"),
    "DuckDuckGoProviderSettings": (__spec__.parent, "data"),
    "EmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "EmbeddingProviderSettingsType": (__spec__.parent, "embedding"),
    "ExaProviderSettings": (__spec__.parent, "data"),
    "FastEmbedEmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "FastEmbedProviderMixin": (__spec__.parent, "mixins"),
    "FastEmbedRerankingProviderSettings": (__spec__.parent, "reranking"),
    "FastEmbedSparseEmbeddingProviderSettings": (__spec__.parent, "sparse_embedding"),
    "GoogleAgentProviderSettings": (__spec__.parent, "agent"),
    "GoogleEmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "GroqAgentProviderSettings": (__spec__.parent, "agent"),
    "HuggingFaceAgentProviderSettings": (__spec__.parent, "agent"),
    "HuggingFaceEmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "MemoryConfig": (__spec__.parent, "vector_store"),
    "MemoryVectorStoreProviderSettings": (__spec__.parent, "vector_store"),
    "MistralAgentProviderSettings": (__spec__.parent, "agent"),
    "MistralEmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "NON_ANTHROPIC_AGENT_PROVIDER_DISCRIMINATOR": (__spec__.parent, "utils"),
    "OpenAIAgentProviderSettings": (__spec__.parent, "agent"),
    "OpenRouterAgentProviderSettings": (__spec__.parent, "agent"),
    "PROVIDER_DISCRIMINATOR": (__spec__.parent, "utils"),
    "PydanticGatewayProviderSettings": (__spec__.parent, "agent"),
    "QdrantVectorStoreProviderSettings": (__spec__.parent, "vector_store"),
    "RERANKING_PROVIDER_DISCRIMINATOR": (__spec__.parent, "utils"),
    "RerankingProviderSettings": (__spec__.parent, "reranking"),
    "RerankingProviderSettingsType": (__spec__.parent, "reranking"),
    "SentenceTransformersEmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "SparseEmbeddingProviderSettings": (__spec__.parent, "sparse_embedding"),
    "SparseEmbeddingProviderSettingsType": (__spec__.parent, "sparse_embedding"),
    "TavilyProviderSettings": (__spec__.parent, "data"),
    "VectorStoreProviderSettings": (__spec__.parent, "vector_store"),
    "VectorStoreProviderSettingsType": (__spec__.parent, "vector_store"),
    "VoyageEmbeddingProviderSettings": (__spec__.parent, "embedding"),
    "VoyageRerankingProviderSettings": (__spec__.parent, "reranking"),
    "is_cloud_provider": (__spec__.parent, "utils"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "ANTHROPIC_PROVIDER_DISCRIMINATOR",
    "CORE_EMBEDDING_PROVIDER_DISCRIMINATOR",
    "NON_ANTHROPIC_AGENT_PROVIDER_DISCRIMINATOR",
    "PROVIDER_DISCRIMINATOR",
    "RERANKING_PROVIDER_DISCRIMINATOR",
    "AgentProviderSettingsType",
    "AnthropicAgentProviderSettings",
    "AnthropicAzureAgentProviderSettings",
    "AnthropicBedrockAgentProviderSettings",
    "AnthropicGoogleVertexAgentProviderSettings",
    "AsymmetricEmbeddingProviderSettings",
    "AsymmetricEmbeddingProviderSettingsDict",
    "AzureEmbeddingProviderSettings",
    "AzureProviderMixin",
    "BaseAgentProviderSettings",
    "BaseDataProviderSettings",
    "BaseEmbeddingProviderSettings",
    "BaseProviderCategorySettings",
    "BaseProviderCategorySettingsDict",
    "BaseRerankingProviderSettings",
    "BaseSparseEmbeddingProviderSettings",
    "BaseVectorStoreProviderSettings",
    "BedrockEmbeddingProviderSettings",
    "BedrockEmbeddingProviderSettings",
    "BedrockProviderMixin",
    "BedrockProviderMixin",
    "BedrockRerankingProviderSettings",
    "CerebrasAgentProviderSettings",
    "CohereAgentProviderSettings",
    "CohereEmbeddingProviderSettings",
    "CohereRerankingProviderSettings",
    "ConnectionConfiguration",
    "ConnectionRateLimitConfig",
    "DataProviderSettingsType",
    "DuckDuckGoProviderSettings",
    "EmbeddingProviderSettings",
    "EmbeddingProviderSettingsType",
    "ExaProviderSettings",
    "FastEmbedEmbeddingProviderSettings",
    "FastEmbedProviderMixin",
    "FastEmbedRerankingProviderSettings",
    "FastEmbedSparseEmbeddingProviderSettings",
    "GoogleAgentProviderSettings",
    "GoogleEmbeddingProviderSettings",
    "GroqAgentProviderSettings",
    "HuggingFaceAgentProviderSettings",
    "HuggingFaceEmbeddingProviderSettings",
    "MemoryConfig",
    "MemoryVectorStoreProviderSettings",
    "MistralAgentProviderSettings",
    "MistralEmbeddingProviderSettings",
    "OpenAIAgentProviderSettings",
    "OpenRouterAgentProviderSettings",
    "PydanticGatewayProviderSettings",
    "QdrantVectorStoreProviderSettings",
    "RerankingProviderSettings",
    "RerankingProviderSettingsType",
    "SentenceTransformersEmbeddingProviderSettings",
    "SparseEmbeddingProviderSettings",
    "SparseEmbeddingProviderSettingsType",
    "TavilyProviderSettings",
    "VectorStoreProviderSettings",
    "VectorStoreProviderSettingsType",
    "VoyageEmbeddingProviderSettings",
    "VoyageRerankingProviderSettings",
    "is_cloud_provider",
)


def __dir__() -> list[str]:
    """Return the list of attributes for the module, including dynamically imported ones."""
    return list(__all__)
