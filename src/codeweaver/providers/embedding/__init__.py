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
    from codeweaver.providers.embedding.capabilities.alibaba_nlp import (
        AlibabaNlpEmbeddingCapabilities,
        AlibabaNlpProvider,
        get_alibaba_nlp_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.amazon import (
        AmazonEmbeddingCapabilities,
        get_amazon_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.baai import (
        BaaiEmbeddingCapabilities,
        BaaiProvider,
        get_baai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.base import (
        EmbeddingModelCapabilities,
        ModelFamily,
        SparseCapabilities,
        SparseEmbeddingModelCapabilities,
        get_sparse_caps,
    )
    from codeweaver.providers.embedding.capabilities.cohere import (
        CohereEmbeddingCapabilities,
        get_cohere_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.google import (
        GoogleEmbeddingCapabilities,
        get_google_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.ibm_granite import (
        IbmGraniteEmbeddingCapabilities,
        IbmGraniteProvider,
        get_ibm_granite_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.intfloat import (
        IntfloatEmbeddingCapabilities,
        IntfloatProvider,
        get_intfloat_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.jinaai import (
        JinaaiEmbeddingCapabilities,
        JinaaiProvider,
        get_jinaai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.minishlab import (
        MinishlabEmbeddingCapabilities,
        MinishlabProvider,
        get_minishlab_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.mistral import (
        MistralEmbeddingCapabilities,
        get_mistral_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.mixedbread_ai import (
        MixedbreadAiEmbeddingCapabilities,
        MixedbreadAiProvider,
        get_mixedbread_ai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.morph import get_morph_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.nomic_ai import (
        NomicAiEmbeddingCapabilities,
        NomicAiProvider,
        get_nomic_ai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.openai import (
        OpenaiEmbeddingCapabilities,
        get_openai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.qwen import (
        QwenEmbeddingCapabilities,
        QwenProvider,
        get_qwen_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.resolver import (
        EmbeddingCapabilityResolver,
        SparseEmbeddingCapabilityResolver,
    )
    from codeweaver.providers.embedding.capabilities.sentence_transformers import (
        SentenceTransformersEmbeddingCapabilities,
        SentenceTransformersProvider,
        get_sentence_transformers_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.snowflake import (
        SnowflakeEmbeddingCapabilities,
        SnowflakeProvider,
        get_snowflake_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.thenlper import (
        ThenlperEmbeddingCapabilities,
        ThenlperProvider,
        get_thenlper_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.types import (
        EmbeddingCapabilitiesDict,
        PartialCapabilities,
    )
    from codeweaver.providers.embedding.capabilities.voyage import (
        Voyage4ModelFamily,
        VoyageEmbeddingCapabilities,
        get_voyage_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.whereisai import (
        WhereisaiEmbeddingCapabilities,
        WhereisaiProvider,
        get_whereisai_embedding_capabilities,
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
        DEFAULT_MAX_BATCH_TOKENS,
        EmbeddingCustomDeps,
        EmbeddingErrorInfo,
        EmbeddingImplementationDeps,
        EmbeddingProvider,
        SparseEmbeddingProvider,
        default_input_transformer,
        default_output_transformer,
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
        is_cohere_request,
        is_cohere_response,
        is_one_of_valid_types,
        is_titan_response,
        shared_serializer,
        shared_validator,
    )
    from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider
    from codeweaver.providers.embedding.providers.fastembed import (
        FastEmbedEmbeddingProvider,
        FastEmbedSparseProvider,
        fastembed_output_transformer,
        fastembed_sparse_output_transformer,
    )
    from codeweaver.providers.embedding.providers.google import (
        GoogleEmbeddingProvider,
        GoogleEmbeddingTasks,
    )
    from codeweaver.providers.embedding.providers.huggingface import (
        HuggingFaceEmbeddingProvider,
        huggingface_hub_input_transformer,
        huggingface_hub_output_transformer,
    )
    from codeweaver.providers.embedding.providers.litellm import (
        LITELLM_OPENAI_PROVIDERS,
        LiteLLMModelSpec,
    )
    from codeweaver.providers.embedding.providers.mistral import MistralEmbeddingProvider
    from codeweaver.providers.embedding.providers.openai_factory import OpenAIEmbeddingBase
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersSparseProvider,
        process_for_instruction_model,
    )
    from codeweaver.providers.embedding.providers.voyage import (
        VoyageEmbeddingProvider,
        voyage_context_output_transformer,
        voyage_output_transformer,
    )
    from codeweaver.providers.embedding.registry import EmbeddingRegistry, get_embedding_registry

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DEFAULT_MAX_BATCH_TOKENS": (__spec__.parent, "providers.base"),
    "DENSE_MODELS": (__spec__.parent, "fastembed_extensions"),
    "LITELLM_OPENAI_PROVIDERS": (__spec__.parent, "providers.litellm"),
    "RERANKING_MODELS": (__spec__.parent, "fastembed_extensions"),
    "AlibabaNlpEmbeddingCapabilities": (__spec__.parent, "capabilities.alibaba_nlp"),
    "AlibabaNlpProvider": (__spec__.parent, "capabilities.alibaba_nlp"),
    "AmazonEmbeddingCapabilities": (__spec__.parent, "capabilities.amazon"),
    "BaaiEmbeddingCapabilities": (__spec__.parent, "capabilities.baai"),
    "BaaiProvider": (__spec__.parent, "capabilities.baai"),
    "BaseBedrockModel": (__spec__.parent, "providers.bedrock"),
    "BedrockEmbeddingProvider": (__spec__.parent, "providers.bedrock"),
    "BedrockInvokeEmbeddingRequest": (__spec__.parent, "providers.bedrock"),
    "BedrockInvokeEmbeddingResponse": (__spec__.parent, "providers.bedrock"),
    "CohereEmbeddingCapabilities": (__spec__.parent, "capabilities.cohere"),
    "CohereEmbeddingProvider": (__spec__.parent, "providers.cohere"),
    "CohereEmbeddingRequestBody": (__spec__.parent, "providers.bedrock"),
    "CohereEmbeddingResponse": (__spec__.parent, "providers.bedrock"),
    "CohereRequestHandler": (__spec__.parent, "providers.bedrock"),
    "EmbeddingCacheManager": (__spec__.parent, "cache_manager"),
    "EmbeddingCapabilitiesDict": (__spec__.parent, "capabilities.types"),
    "EmbeddingCapabilityResolver": (__spec__.parent, "capabilities.resolver"),
    "EmbeddingCustomDeps": (__spec__.parent, "providers.base"),
    "EmbeddingErrorInfo": (__spec__.parent, "providers.base"),
    "EmbeddingImplementationDeps": (__spec__.parent, "providers.base"),
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
    "IbmGraniteProvider": (__spec__.parent, "capabilities.ibm_granite"),
    "ImageDescription": (__spec__.parent, "providers.bedrock"),
    "IntfloatEmbeddingCapabilities": (__spec__.parent, "capabilities.intfloat"),
    "IntfloatProvider": (__spec__.parent, "capabilities.intfloat"),
    "InvokeRequestDict": (__spec__.parent, "providers.bedrock"),
    "JinaaiEmbeddingCapabilities": (__spec__.parent, "capabilities.jinaai"),
    "JinaaiProvider": (__spec__.parent, "capabilities.jinaai"),
    "MinishlabEmbeddingCapabilities": (__spec__.parent, "capabilities.minishlab"),
    "MinishlabProvider": (__spec__.parent, "capabilities.minishlab"),
    "MistralEmbeddingCapabilities": (__spec__.parent, "capabilities.mistral"),
    "MistralEmbeddingProvider": (__spec__.parent, "providers.mistral"),
    "MixedbreadAiEmbeddingCapabilities": (__spec__.parent, "capabilities.mixedbread_ai"),
    "MixedbreadAiProvider": (__spec__.parent, "capabilities.mixedbread_ai"),
    "ModelFamily": (__spec__.parent, "capabilities.base"),
    "NomicAiEmbeddingCapabilities": (__spec__.parent, "capabilities.nomic_ai"),
    "NomicAiProvider": (__spec__.parent, "capabilities.nomic_ai"),
    "OpenaiEmbeddingCapabilities": (__spec__.parent, "capabilities.openai"),
    "PartialCapabilities": (__spec__.parent, "capabilities.types"),
    "QwenEmbeddingCapabilities": (__spec__.parent, "capabilities.qwen"),
    "QwenProvider": (__spec__.parent, "capabilities.qwen"),
    "SentenceTransformersEmbeddingCapabilities": (
        __spec__.parent,
        "capabilities.sentence_transformers",
    ),
    "SentenceTransformersEmbeddingProvider": (__spec__.parent, "providers.sentence_transformers"),
    "SentenceTransformersProvider": (__spec__.parent, "capabilities.sentence_transformers"),
    "SentenceTransformersSparseProvider": (__spec__.parent, "providers.sentence_transformers"),
    "SnowflakeEmbeddingCapabilities": (__spec__.parent, "capabilities.snowflake"),
    "SnowflakeProvider": (__spec__.parent, "capabilities.snowflake"),
    "SparseCapabilities": (__spec__.parent, "capabilities.base"),
    "SparseEmbeddingCapabilityResolver": (__spec__.parent, "capabilities.resolver"),
    "SparseEmbeddingModelCapabilities": (__spec__.parent, "capabilities.base"),
    "SparseEmbeddingProvider": (__spec__.parent, "providers.base"),
    "ThenlperEmbeddingCapabilities": (__spec__.parent, "capabilities.thenlper"),
    "ThenlperProvider": (__spec__.parent, "capabilities.thenlper"),
    "TitanEmbeddingV2RequestBody": (__spec__.parent, "providers.bedrock"),
    "TitanEmbeddingV2Response": (__spec__.parent, "providers.bedrock"),
    "Voyage4ModelFamily": (__spec__.parent, "capabilities.voyage"),
    "VoyageEmbeddingCapabilities": (__spec__.parent, "capabilities.voyage"),
    "VoyageEmbeddingProvider": (__spec__.parent, "providers.voyage"),
    "WhereisaiEmbeddingCapabilities": (__spec__.parent, "capabilities.whereisai"),
    "WhereisaiProvider": (__spec__.parent, "capabilities.whereisai"),
    "add_models": (__spec__.parent, "fastembed_extensions"),
    "default_input_transformer": (__spec__.parent, "providers.base"),
    "default_output_transformer": (__spec__.parent, "providers.base"),
    "fastembed_output_transformer": (__spec__.parent, "providers.fastembed"),
    "fastembed_sparse_output_transformer": (__spec__.parent, "providers.fastembed"),
    "get_alibaba_nlp_embedding_capabilities": (__spec__.parent, "capabilities.alibaba_nlp"),
    "get_amazon_embedding_capabilities": (__spec__.parent, "capabilities.amazon"),
    "get_baai_embedding_capabilities": (__spec__.parent, "capabilities.baai"),
    "get_cohere_embedding_capabilities": (__spec__.parent, "capabilities.cohere"),
    "get_cross_encoder": (__spec__.parent, "fastembed_extensions"),
    "get_embedding_registry": (__spec__.parent, "registry"),
    "get_google_embedding_capabilities": (__spec__.parent, "capabilities.google"),
    "get_ibm_granite_embedding_capabilities": (__spec__.parent, "capabilities.ibm_granite"),
    "get_intfloat_embedding_capabilities": (__spec__.parent, "capabilities.intfloat"),
    "get_jinaai_embedding_capabilities": (__spec__.parent, "capabilities.jinaai"),
    "get_minishlab_embedding_capabilities": (__spec__.parent, "capabilities.minishlab"),
    "get_mistral_embedding_capabilities": (__spec__.parent, "capabilities.mistral"),
    "get_mixedbread_ai_embedding_capabilities": (__spec__.parent, "capabilities.mixedbread_ai"),
    "get_morph_embedding_capabilities": (__spec__.parent, "capabilities.morph"),
    "get_nomic_ai_embedding_capabilities": (__spec__.parent, "capabilities.nomic_ai"),
    "get_openai_embedding_capabilities": (__spec__.parent, "capabilities.openai"),
    "get_qwen_embedding_capabilities": (__spec__.parent, "capabilities.qwen"),
    "get_sentence_transformers_embedding_capabilities": (
        __spec__.parent,
        "capabilities.sentence_transformers",
    ),
    "get_snowflake_embedding_capabilities": (__spec__.parent, "capabilities.snowflake"),
    "get_sparse_caps": (__spec__.parent, "capabilities.base"),
    "get_sparse_embedder": (__spec__.parent, "fastembed_extensions"),
    "get_text_embedder": (__spec__.parent, "fastembed_extensions"),
    "get_thenlper_embedding_capabilities": (__spec__.parent, "capabilities.thenlper"),
    "get_voyage_embedding_capabilities": (__spec__.parent, "capabilities.voyage"),
    "get_whereisai_embedding_capabilities": (__spec__.parent, "capabilities.whereisai"),
    "huggingface_hub_input_transformer": (__spec__.parent, "providers.huggingface"),
    "huggingface_hub_output_transformer": (__spec__.parent, "providers.huggingface"),
    "is_cohere_request": (__spec__.parent, "providers.bedrock"),
    "is_cohere_response": (__spec__.parent, "providers.bedrock"),
    "is_one_of_valid_types": (__spec__.parent, "providers.bedrock"),
    "is_titan_response": (__spec__.parent, "providers.bedrock"),
    "LiteLLMModelSpec": (__spec__.parent, "providers.litellm"),
    "OpenAIEmbeddingBase": (__spec__.parent, "providers.openai_factory"),
    "process_for_instruction_model": (__spec__.parent, "providers.sentence_transformers"),
    "shared_serializer": (__spec__.parent, "providers.bedrock"),
    "shared_validator": (__spec__.parent, "providers.bedrock"),
    "voyage_context_output_transformer": (__spec__.parent, "providers.voyage"),
    "voyage_output_transformer": (__spec__.parent, "providers.voyage"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "DEFAULT_MAX_BATCH_TOKENS",
    "DENSE_MODELS",
    "LITELLM_OPENAI_PROVIDERS",
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
    "CohereEmbeddingCapabilities",
    "CohereEmbeddingProvider",
    "CohereEmbeddingRequestBody",
    "CohereEmbeddingResponse",
    "CohereRequestHandler",
    "EmbeddingCacheManager",
    "EmbeddingCapabilitiesDict",
    "EmbeddingCapabilityResolver",
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
    "InvokeRequestDict",
    "JinaaiEmbeddingCapabilities",
    "JinaaiProvider",
    "LiteLLMModelSpec",
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
    "QwenEmbeddingCapabilities",
    "QwenProvider",
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
    "default_input_transformer",
    "default_output_transformer",
    "fastembed_output_transformer",
    "fastembed_sparse_output_transformer",
    "get_alibaba_nlp_embedding_capabilities",
    "get_amazon_embedding_capabilities",
    "get_baai_embedding_capabilities",
    "get_cohere_embedding_capabilities",
    "get_cross_encoder",
    "get_embedding_registry",
    "get_google_embedding_capabilities",
    "get_ibm_granite_embedding_capabilities",
    "get_intfloat_embedding_capabilities",
    "get_jinaai_embedding_capabilities",
    "get_minishlab_embedding_capabilities",
    "get_mistral_embedding_capabilities",
    "get_mixedbread_ai_embedding_capabilities",
    "get_morph_embedding_capabilities",
    "get_nomic_ai_embedding_capabilities",
    "get_openai_embedding_capabilities",
    "get_qwen_embedding_capabilities",
    "get_sentence_transformers_embedding_capabilities",
    "get_snowflake_embedding_capabilities",
    "get_sparse_caps",
    "get_sparse_embedder",
    "get_text_embedder",
    "get_thenlper_embedding_capabilities",
    "get_voyage_embedding_capabilities",
    "get_whereisai_embedding_capabilities",
    "huggingface_hub_input_transformer",
    "huggingface_hub_output_transformer",
    "is_cohere_request",
    "is_cohere_response",
    "is_one_of_valid_types",
    "is_titan_response",
    "process_for_instruction_model",
    "shared_serializer",
    "shared_validator",
    "voyage_context_output_transformer",
    "voyage_output_transformer",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
