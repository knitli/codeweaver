# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Entrypoint for CodeWeaver's embedding model system.

We wanted to mirror `pydantic-ai`'s handling of LLM models, but we had to make a lot of adjustments to fit the embedding use case.
"""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager
    from codeweaver.providers.embedding.capabilities import MappingProxyType
    from codeweaver.providers.embedding.capabilities.alibaba_nlp import (
        AlibabaNlpEmbeddingCapabilities,
        AlibabaNlpProvider,
    )
    from codeweaver.providers.embedding.capabilities.amazon import AmazonEmbeddingCapabilities
    from codeweaver.providers.embedding.capabilities.baai import (
        BaaiEmbeddingCapabilities,
        BaaiProvider,
    )
    from codeweaver.providers.embedding.capabilities.base import (
        EmbeddingModelCapabilities,
        ModelFamily,
        SparseCapabilities,
        SparseEmbeddingModelCapabilities,
    )
    from codeweaver.providers.embedding.capabilities.cohere import CohereEmbeddingCapabilities
    from codeweaver.providers.embedding.capabilities.google import GoogleEmbeddingCapabilities
    from codeweaver.providers.embedding.capabilities.ibm_granite import (
        IbmGraniteEmbeddingCapabilities,
        IbmGraniteProvider,
    )
    from codeweaver.providers.embedding.capabilities.intfloat import (
        IntfloatEmbeddingCapabilities,
        IntfloatProvider,
    )
    from codeweaver.providers.embedding.capabilities.jinaai import (
        JinaaiEmbeddingCapabilities,
        JinaaiProvider,
    )
    from codeweaver.providers.embedding.capabilities.minishlab import (
        MinishlabEmbeddingCapabilities,
        MinishlabProvider,
    )
    from codeweaver.providers.embedding.capabilities.mistral import MistralEmbeddingCapabilities
    from codeweaver.providers.embedding.capabilities.mixedbread_ai import (
        MixedbreadAiEmbeddingCapabilities,
        MixedbreadAiProvider,
    )
    from codeweaver.providers.embedding.capabilities.nomic_ai import (
        NomicAiEmbeddingCapabilities,
        NomicAiProvider,
    )
    from codeweaver.providers.embedding.capabilities.openai import OpenaiEmbeddingCapabilities
    from codeweaver.providers.embedding.capabilities.qwen import (
        QwenEmbeddingCapabilities,
        QwenProvider,
    )
    from codeweaver.providers.embedding.capabilities.resolver import (
        EmbeddingCapabilityResolver,
        EmbeddingCapabilityType,
        SparseEmbeddingCapabilityResolver,
    )
    from codeweaver.providers.embedding.capabilities.sentence_transformers import (
        SentenceTransformersEmbeddingCapabilities,
        SentenceTransformersProvider,
    )
    from codeweaver.providers.embedding.capabilities.snowflake import (
        SnowflakeEmbeddingCapabilities,
        SnowflakeProvider,
    )
    from codeweaver.providers.embedding.capabilities.thenlper import (
        ThenlperEmbeddingCapabilities,
        ThenlperProvider,
    )
    from codeweaver.providers.embedding.capabilities.types import (
        EmbeddingCapabilitiesDict,
        PartialCapabilities,
    )
    from codeweaver.providers.embedding.capabilities.voyage import (
        Voyage4ModelFamily,
        VoyageEmbeddingCapabilities,
    )
    from codeweaver.providers.embedding.capabilities.whereisai import (
        WhereisaiEmbeddingCapabilities,
        WhereisaiProvider,
    )
    from codeweaver.providers.embedding.fastembed_extensions import (
        DENSE_MODELS,
        RERANKING_MODELS,
        add_models,
        get_cross_encoder,
        get_sparse_embedder,
        get_text_embedder,
    )
    from codeweaver.providers.embedding.providers.base import (
        CircuitBreakerOpenError,
        EmbeddingCustomDeps,
        EmbeddingErrorInfo,
        EmbeddingImplementationDeps,
        EmbeddingProvider,
        ProviderError,
        RetryError,
        SparseEmbeddingProvider,
        StatisticsDep,
        np,
    )
    from codeweaver.providers.embedding.providers.bedrock import (
        BaseBedrockModel,
        BedrockEmbeddingProvider,
        BedrockInvokeEmbeddingRequest,
        BedrockInvokeEmbeddingResponse,
        CohereEmbeddingRequestBody,
        CohereEmbeddingResponse,
        CohereRequestHandler,
        ImageDescription,
        InvokeRequestDict,
        TitanEmbeddingV2RequestBody,
        TitanEmbeddingV2Response,
    )
    from codeweaver.providers.embedding.providers.cohere import (
        CohereEmbeddingProvider,
        ConfigurationError,
    )
    from codeweaver.providers.embedding.providers.fastembed import (
        FastEmbedEmbeddingProvider,
        FastEmbedSparseProvider,
    )
    from codeweaver.providers.embedding.providers.google import (
        GoogleEmbeddingProvider,
        GoogleEmbeddingTasks,
    )
    from codeweaver.providers.embedding.providers.huggingface import HuggingFaceEmbeddingProvider
    from codeweaver.providers.embedding.providers.litellm import LiteLLMModelSpec
    from codeweaver.providers.embedding.providers.mistral import MistralEmbeddingProvider
    from codeweaver.providers.embedding.providers.openai_factory import OpenAIEmbeddingBase
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersSparseProvider,
    )
    from codeweaver.providers.embedding.providers.voyage import VoyageEmbeddingProvider
    from codeweaver.providers.embedding.registry import (
        CodeWeaverValidationError,
        EmbeddingRegistry,
        InvalidEmbeddingModelError,
        get_embedding_registry,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DENSE_MODELS": (__spec__.parent, "fastembed_extensions"),
    "RERANKING_MODELS": (__spec__.parent, "fastembed_extensions"),
    "AlibabaNlpEmbeddingCapabilities": (__spec__.parent, "capabilities.alibaba_nlp"),
    "AmazonEmbeddingCapabilities": (__spec__.parent, "capabilities.amazon"),
    "BaaiEmbeddingCapabilities": (__spec__.parent, "capabilities.baai"),
    "BaseBedrockModel": (__spec__.parent, "providers.bedrock"),
    "BedrockEmbeddingProvider": (__spec__.parent, "providers.bedrock"),
    "BedrockInvokeEmbeddingRequest": (__spec__.parent, "providers.bedrock"),
    "BedrockInvokeEmbeddingResponse": (__spec__.parent, "providers.bedrock"),
    "CircuitBreakerOpenError": (__spec__.parent, "providers.base"),
    "CodeWeaverValidationError": (__spec__.parent, "registry"),
    "CohereEmbeddingCapabilities": (__spec__.parent, "capabilities.cohere"),
    "CohereEmbeddingProvider": (__spec__.parent, "providers.cohere"),
    "CohereEmbeddingRequestBody": (__spec__.parent, "providers.bedrock"),
    "CohereEmbeddingResponse": (__spec__.parent, "providers.bedrock"),
    "CohereRequestHandler": (__spec__.parent, "providers.bedrock"),
    "ConfigurationError": (__spec__.parent, "providers.cohere"),
    "EmbeddingCacheManager": (__spec__.parent, "cache_manager"),
    "EmbeddingCapabilitiesDict": (__spec__.parent, "capabilities.types"),
    "EmbeddingCapabilityResolver": (__spec__.parent, "capabilities.resolver"),
    "EmbeddingCapabilityType": (__spec__.parent, "capabilities.resolver"),
    "EmbeddingErrorInfo": (__spec__.parent, "providers.base"),
    "EmbeddingModelCapabilities": (__spec__.parent, "capabilities.base"),
    "EmbeddingProvider": (__spec__.parent, "providers.base"),
    "EmbeddingRegistry": (__spec__.parent, "registry"),
    "FastEmbedEmbeddingProvider": (__spec__.parent, "providers.fastembed"),
    "FastEmbedSparseProvider": (__spec__.parent, "providers.fastembed"),
    "GoogleEmbeddingCapabilities": (__spec__.parent, "capabilities.google"),
    "GoogleEmbeddingProvider": (__spec__.parent, "providers.google"),
    "GoogleEmbeddingTasks": (__spec__.parent, "providers.google"),
    "HuggingFaceEmbeddingProvider": (__spec__.parent, "providers.huggingface"),
    "IbmGraniteEmbeddingCapabilities": (__spec__.parent, "capabilities.ibm_granite"),
    "ImageDescription": (__spec__.parent, "providers.bedrock"),
    "IntfloatEmbeddingCapabilities": (__spec__.parent, "capabilities.intfloat"),
    "InvalidEmbeddingModelError": (__spec__.parent, "registry"),
    "InvokeRequestDict": (__spec__.parent, "providers.bedrock"),
    "JinaaiEmbeddingCapabilities": (__spec__.parent, "capabilities.jinaai"),
    "MappingProxyType": (__spec__.parent, "capabilities"),
    "MinishlabEmbeddingCapabilities": (__spec__.parent, "capabilities.minishlab"),
    "MistralEmbeddingCapabilities": (__spec__.parent, "capabilities.mistral"),
    "MistralEmbeddingProvider": (__spec__.parent, "providers.mistral"),
    "MixedbreadAiEmbeddingCapabilities": (__spec__.parent, "capabilities.mixedbread_ai"),
    "ModelFamily": (__spec__.parent, "capabilities.base"),
    "NomicAiEmbeddingCapabilities": (__spec__.parent, "capabilities.nomic_ai"),
    "OpenaiEmbeddingCapabilities": (__spec__.parent, "capabilities.openai"),
    "ProviderError": (__spec__.parent, "providers.base"),
    "QwenEmbeddingCapabilities": (__spec__.parent, "capabilities.qwen"),
    "RetryError": (__spec__.parent, "providers.base"),
    "SentenceTransformersEmbeddingCapabilities": (
        __spec__.parent,
        "capabilities.sentence_transformers",
    ),
    "SentenceTransformersEmbeddingProvider": (__spec__.parent, "providers.sentence_transformers"),
    "SentenceTransformersSparseProvider": (__spec__.parent, "providers.sentence_transformers"),
    "SnowflakeEmbeddingCapabilities": (__spec__.parent, "capabilities.snowflake"),
    "SparseCapabilities": (__spec__.parent, "capabilities.base"),
    "SparseEmbeddingCapabilityResolver": (__spec__.parent, "capabilities.resolver"),
    "SparseEmbeddingModelCapabilities": (__spec__.parent, "capabilities.base"),
    "SparseEmbeddingProvider": (__spec__.parent, "providers.base"),
    "StatisticsDep": (__spec__.parent, "providers.base"),
    "ThenlperEmbeddingCapabilities": (__spec__.parent, "capabilities.thenlper"),
    "TitanEmbeddingV2RequestBody": (__spec__.parent, "providers.bedrock"),
    "TitanEmbeddingV2Response": (__spec__.parent, "providers.bedrock"),
    "Voyage4ModelFamily": (__spec__.parent, "capabilities.voyage"),
    "VoyageEmbeddingCapabilities": (__spec__.parent, "capabilities.voyage"),
    "VoyageEmbeddingProvider": (__spec__.parent, "providers.voyage"),
    "WhereisaiEmbeddingCapabilities": (__spec__.parent, "capabilities.whereisai"),
    "add_models": (__spec__.parent, "fastembed_extensions"),
    "get_cross_encoder": (__spec__.parent, "fastembed_extensions"),
    "get_embedding_registry": (__spec__.parent, "registry"),
    "get_sparse_embedder": (__spec__.parent, "fastembed_extensions"),
    "get_text_embedder": (__spec__.parent, "fastembed_extensions"),
    "LiteLLMModelSpec": (__spec__.parent, "providers.litellm"),
    "np": (__spec__.parent, "providers.base"),
    "OpenAIEmbeddingBase": (__spec__.parent, "providers.openai_factory"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "DENSE_MODELS",
    "RERANKING_MODELS",
    "AlibabaNlpEmbeddingCapabilities",
    "AlibabaNlpProvider",
    "AmazonEmbeddingCapabilities",
    "BaaiEmbeddingCapabilities",
    "BaaiProvider",
    "BaseBedrockModel",
    "BedrockEmbeddingProvider",
    "BedrockInvokeEmbeddingRequest",
    "BedrockInvokeEmbeddingResponse",
    "CircuitBreakerOpenError",
    "CodeWeaverValidationError",
    "CohereEmbeddingCapabilities",
    "CohereEmbeddingProvider",
    "CohereEmbeddingRequestBody",
    "CohereEmbeddingResponse",
    "CohereRequestHandler",
    "ConfigurationError",
    "EmbeddingCacheManager",
    "EmbeddingCapabilitiesDict",
    "EmbeddingCapabilityResolver",
    "EmbeddingCapabilityType",
    "EmbeddingCustomDeps",
    "EmbeddingErrorInfo",
    "EmbeddingImplementationDeps",
    "EmbeddingModelCapabilities",
    "EmbeddingProvider",
    "EmbeddingRegistry",
    "FastEmbedEmbeddingProvider",
    "FastEmbedSparseProvider",
    "GoogleEmbeddingCapabilities",
    "GoogleEmbeddingProvider",
    "GoogleEmbeddingTasks",
    "HuggingFaceEmbeddingProvider",
    "IbmGraniteEmbeddingCapabilities",
    "IbmGraniteProvider",
    "ImageDescription",
    "IntfloatEmbeddingCapabilities",
    "IntfloatProvider",
    "InvalidEmbeddingModelError",
    "InvokeRequestDict",
    "JinaaiEmbeddingCapabilities",
    "JinaaiProvider",
    "LiteLLMModelSpec",
    "MappingProxyType",
    "MinishlabEmbeddingCapabilities",
    "MinishlabProvider",
    "MistralEmbeddingCapabilities",
    "MistralEmbeddingProvider",
    "MixedbreadAiEmbeddingCapabilities",
    "MixedbreadAiProvider",
    "ModelFamily",
    "NomicAiEmbeddingCapabilities",
    "NomicAiProvider",
    "OpenAIEmbeddingBase",
    "OpenaiEmbeddingCapabilities",
    "PartialCapabilities",
    "ProviderError",
    "QwenEmbeddingCapabilities",
    "QwenProvider",
    "RetryError",
    "SentenceTransformersEmbeddingCapabilities",
    "SentenceTransformersEmbeddingProvider",
    "SentenceTransformersProvider",
    "SentenceTransformersSparseProvider",
    "SnowflakeEmbeddingCapabilities",
    "SnowflakeProvider",
    "SparseCapabilities",
    "SparseEmbeddingCapabilityResolver",
    "SparseEmbeddingModelCapabilities",
    "SparseEmbeddingProvider",
    "StatisticsDep",
    "ThenlperEmbeddingCapabilities",
    "ThenlperProvider",
    "TitanEmbeddingV2RequestBody",
    "TitanEmbeddingV2Response",
    "Voyage4ModelFamily",
    "VoyageEmbeddingCapabilities",
    "VoyageEmbeddingProvider",
    "WhereisaiEmbeddingCapabilities",
    "WhereisaiProvider",
    "add_models",
    "get_cross_encoder",
    "get_embedding_registry",
    "get_sparse_embedder",
    "get_text_embedder",
    "np",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
