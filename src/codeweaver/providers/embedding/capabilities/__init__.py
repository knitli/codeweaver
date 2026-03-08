# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Entrypoint for CodeWeaver's embedding model capabilities.

Provides access to embedding model capabilities through the dependency injection system.
Use EmbeddingCapabilityResolver for capability lookup and management.
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
    from codeweaver.providers.embedding.capabilities.alibaba_nlp import (
        ALIBABA_NLP_GTE_MODERNBERT_BASE_CAPABILITIES,
        ALIBABA_NLP_GTE_MULTILINGUAL_BASE_CAPABILITIES,
        ALL_CAPABILITIES,
        CAP_MAP,
        AlibabaNlpEmbeddingCapabilities,
        AlibabaNlpProvider,
        get_alibaba_nlp_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.amazon import (
        AmazonEmbeddingCapabilities,
        get_amazon_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.baai import (
        BAAI_BGE_BASE_EN_V1_5_CAPABILITIES,
        BAAI_BGE_SMALL_EN_V1_5_CAPABILITIES,
        BGE_LARGE_EN_335M_CAPABILITIES,
        BaaiEmbeddingCapabilities,
        BaaiProvider,
        get_baai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.base import (
        HAS_FASTEMBED,
        HAS_ST,
        EmbeddingModelCapabilities,
        ModelFamily,
        SparseCapabilities,
        SparseEmbeddingModelCapabilities,
        get_sparse_caps,
    )
    from codeweaver.providers.embedding.capabilities.cohere import (
        MODEL_MAP,
        CohereEmbeddingCapabilities,
        get_cohere_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.google import (
        GoogleEmbeddingCapabilities,
        get_google_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.ibm_granite import (
        GRANITE_EMBEDDING_30M_CAPABILITIES,
        GRANITE_EMBEDDING_278M_CAPABILITIES,
        GRANITE_EMBEDDING_ENGLISH_R2_CAPABILITIES,
        GRANITE_EMBEDDING_SMALL_ENGLISH_R2_CAPABILITIES,
        IbmGraniteEmbeddingCapabilities,
        IbmGraniteProvider,
        get_ibm_granite_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.intfloat import (
        INTFLOAT_MULTILINGUAL_E5_LARGE_CAPABILITIES,
        INTFLOAT_MULTILINGUAL_E5_LARGE_INSTRUCT_CAPABILITIES,
        IntfloatEmbeddingCapabilities,
        IntfloatProvider,
        get_intfloat_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.jinaai import (
        JINAAI_JINA_EMBEDDINGS_V2_BASE_CODE_CAPABILITIES,
        JINAAI_JINA_EMBEDDINGS_V2_SMALL_EN_CAPABILITIES,
        JINAAI_JINA_EMBEDDINGS_V3_CAPABILITIES,
        JINAAI_JINA_EMBEDDINGS_V4_CAPABILITIES,
        JinaaiEmbeddingCapabilities,
        JinaaiProvider,
        get_jinaai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.minishlab import (
        MINISHLAB_M2V_BASE_GLOVE_CAPABILITIES,
        MINISHLAB_M2V_BASE_GLOVE_SUBWORD_CAPABILITIES,
        MINISHLAB_M2V_BASE_OUTPUT_CAPABILITIES,
        MINISHLAB_M2V_MULTILINGUAL_OUTPUT_CAPABILITIES,
        MINISHLAB_POTION_BASE_2M_CAPABILITIES,
        MINISHLAB_POTION_BASE_4M_CAPABILITIES,
        MINISHLAB_POTION_BASE_8M_CAPABILITIES,
        MinishlabEmbeddingCapabilities,
        MinishlabProvider,
        get_minishlab_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.mistral import (
        MistralEmbeddingCapabilities,
        get_mistral_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.mixedbread_ai import (
        MXBAI_EMBED_LARGE_CAPABILITIES,
        MixedbreadAiEmbeddingCapabilities,
        MixedbreadAiProvider,
        get_mixedbread_ai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.morph import (
        MORPH_LLM_EMBEDDING_V4_CAPABILITIES,
        get_morph_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.nomic_ai import (
        NOMIC_AI_MODERNBERT_EMBED_BASE_CAPABILITIES,
        NOMIC_AI_NOMIC_EMBED_TEXT_V2_MOE_CAPABILITIES,
        NomicAiEmbeddingCapabilities,
        NomicAiProvider,
        get_nomic_ai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.openai import (
        OpenaiEmbeddingCapabilities,
        get_openai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.qwen import (
        QWEN_QWEN3_EMBEDDING_0_6B_CAPABILITIES,
        QWEN_QWEN3_EMBEDDING_4B_CAPABILITIES,
        QWEN_QWEN3_EMBEDDING_8B_CAPABILITIES,
        QwenEmbeddingCapabilities,
        QwenProvider,
        get_qwen_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.resolver import (
        EmbeddingCapabilityResolver,
        SparseEmbeddingCapabilityResolver,
    )
    from codeweaver.providers.embedding.capabilities.sentence_transformers import (
        SENTENCE_TRANSFORMERS_ALL_MINILM_L6_V2_CAPABILITIES,
        SENTENCE_TRANSFORMERS_ALL_MINILM_L12_V2_CAPABILITIES,
        SENTENCE_TRANSFORMERS_ALL_MPNET_BASE_V2_CAPABILITIES,
        SENTENCE_TRANSFORMERS_GTR_T5_BASE_CAPABILITIES,
        SENTENCE_TRANSFORMERS_MULTI_QA_MINILM_L6_COS_V1_CAPABILITIES,
        SENTENCE_TRANSFORMERS_PARAPHRASE_MULTILINGUAL_MINILM_L12_V2_CAPABILITIES,
        SENTENCE_TRANSFORMERS_PARAPHRASE_MULTILINGUAL_MPNET_BASE_V2_CAPABILITIES,
        VOYAGE_4_NANO_CAPABILITIES,
        SentenceTransformersEmbeddingCapabilities,
        SentenceTransformersProvider,
        get_sentence_transformers_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.snowflake import (
        SNOWFLAKE_ARCTIC_EMBED2_568M_CAPABILITIES,
        SNOWFLAKE_ARCTIC_EMBED_L_V2_0_CAPABILITIES,
        SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_L_CAPABILITIES,
        SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_CAPABILITIES,
        SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_LONG_CAPABILITIES,
        SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_V2_0_CAPABILITIES,
        SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_S_CAPABILITIES,
        SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_XS_CAPABILITIES,
        SnowflakeEmbeddingCapabilities,
        SnowflakeProvider,
        get_snowflake_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.thenlper import (
        THENLPER_GTE_BASE_CAPABILITIES,
        THENLPER_GTE_LARGE_CAPABILITIES,
        ThenlperEmbeddingCapabilities,
        ThenlperProvider,
        get_thenlper_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.types import (
        EmbeddingCapabilitiesDict,
        PartialCapabilities,
    )
    from codeweaver.providers.embedding.capabilities.voyage import (
        VOYAGE_4_FAMILY,
        Voyage4ModelFamily,
        VoyageEmbeddingCapabilities,
        get_voyage_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.whereisai import (
        WHEREISAI_UAE_CODE_LARGE_V1_CAPABILITIES,
        WHEREISAI_UAE_LARGE_V1_CAPABILITIES,
        WhereisaiEmbeddingCapabilities,
        WhereisaiProvider,
        get_whereisai_embedding_capabilities,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ALIBABA_NLP_GTE_MODERNBERT_BASE_CAPABILITIES": (__spec__.parent, "alibaba_nlp"),
    "ALIBABA_NLP_GTE_MULTILINGUAL_BASE_CAPABILITIES": (__spec__.parent, "alibaba_nlp"),
    "ALL_CAPABILITIES": (__spec__.parent, "alibaba_nlp"),
    "CAP_MAP": (__spec__.parent, "alibaba_nlp"),
    "HAS_FASTEMBED": (__spec__.parent, "base"),
    "HAS_ST": (__spec__.parent, "base"),
    "MODEL_MAP": (__spec__.parent, "cohere"),
    "MXBAI_EMBED_LARGE_CAPABILITIES": (__spec__.parent, "mixedbread_ai"),
    "NOMIC_AI_MODERNBERT_EMBED_BASE_CAPABILITIES": (__spec__.parent, "nomic_ai"),
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_L_CAPABILITIES": (__spec__.parent, "snowflake"),
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_CAPABILITIES": (__spec__.parent, "snowflake"),
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_LONG_CAPABILITIES": (__spec__.parent, "snowflake"),
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_S_CAPABILITIES": (__spec__.parent, "snowflake"),
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_XS_CAPABILITIES": (__spec__.parent, "snowflake"),
    "THENLPER_GTE_BASE_CAPABILITIES": (__spec__.parent, "thenlper"),
    "THENLPER_GTE_LARGE_CAPABILITIES": (__spec__.parent, "thenlper"),
    "VOYAGE_4_FAMILY": (__spec__.parent, "voyage"),
    "VOYAGE_4_NANO_CAPABILITIES": (__spec__.parent, "sentence_transformers"),
    "AlibabaNlpEmbeddingCapabilities": (__spec__.parent, "alibaba_nlp"),
    "AmazonEmbeddingCapabilities": (__spec__.parent, "amazon"),
    "BaaiEmbeddingCapabilities": (__spec__.parent, "baai"),
    "CohereEmbeddingCapabilities": (__spec__.parent, "cohere"),
    "EmbeddingCapabilitiesDict": (__spec__.parent, "types"),
    "EmbeddingCapabilityResolver": (__spec__.parent, "resolver"),
    "EmbeddingModelCapabilities": (__spec__.parent, "base"),
    "GoogleEmbeddingCapabilities": (__spec__.parent, "google"),
    "IbmGraniteEmbeddingCapabilities": (__spec__.parent, "ibm_granite"),
    "IntfloatEmbeddingCapabilities": (__spec__.parent, "intfloat"),
    "JinaaiEmbeddingCapabilities": (__spec__.parent, "jinaai"),
    "MinishlabEmbeddingCapabilities": (__spec__.parent, "minishlab"),
    "MistralEmbeddingCapabilities": (__spec__.parent, "mistral"),
    "MixedbreadAiEmbeddingCapabilities": (__spec__.parent, "mixedbread_ai"),
    "ModelFamily": (__spec__.parent, "base"),
    "NomicAiEmbeddingCapabilities": (__spec__.parent, "nomic_ai"),
    "OpenaiEmbeddingCapabilities": (__spec__.parent, "openai"),
    "QwenEmbeddingCapabilities": (__spec__.parent, "qwen"),
    "SentenceTransformersEmbeddingCapabilities": (__spec__.parent, "sentence_transformers"),
    "SnowflakeEmbeddingCapabilities": (__spec__.parent, "snowflake"),
    "SparseCapabilities": (__spec__.parent, "base"),
    "SparseEmbeddingCapabilityResolver": (__spec__.parent, "resolver"),
    "SparseEmbeddingModelCapabilities": (__spec__.parent, "base"),
    "ThenlperEmbeddingCapabilities": (__spec__.parent, "thenlper"),
    "Voyage4ModelFamily": (__spec__.parent, "voyage"),
    "VoyageEmbeddingCapabilities": (__spec__.parent, "voyage"),
    "WhereisaiEmbeddingCapabilities": (__spec__.parent, "whereisai"),
    "BAAI_BGE_BASE_EN_V1_5_CAPABILITIES": (__spec__.parent, "baai"),
    "BAAI_BGE_SMALL_EN_V1_5_CAPABILITIES": (__spec__.parent, "baai"),
    "BGE_LARGE_EN_335M_CAPABILITIES": (__spec__.parent, "baai"),
    "get_alibaba_nlp_embedding_capabilities": (__spec__.parent, "alibaba_nlp"),
    "get_amazon_embedding_capabilities": (__spec__.parent, "amazon"),
    "get_baai_embedding_capabilities": (__spec__.parent, "baai"),
    "get_cohere_embedding_capabilities": (__spec__.parent, "cohere"),
    "get_google_embedding_capabilities": (__spec__.parent, "google"),
    "get_ibm_granite_embedding_capabilities": (__spec__.parent, "ibm_granite"),
    "get_intfloat_embedding_capabilities": (__spec__.parent, "intfloat"),
    "get_jinaai_embedding_capabilities": (__spec__.parent, "jinaai"),
    "get_minishlab_embedding_capabilities": (__spec__.parent, "minishlab"),
    "get_mistral_embedding_capabilities": (__spec__.parent, "mistral"),
    "get_mixedbread_ai_embedding_capabilities": (__spec__.parent, "mixedbread_ai"),
    "get_morph_embedding_capabilities": (__spec__.parent, "morph"),
    "get_nomic_ai_embedding_capabilities": (__spec__.parent, "nomic_ai"),
    "get_openai_embedding_capabilities": (__spec__.parent, "openai"),
    "get_qwen_embedding_capabilities": (__spec__.parent, "qwen"),
    "get_sentence_transformers_embedding_capabilities": (__spec__.parent, "sentence_transformers"),
    "get_snowflake_embedding_capabilities": (__spec__.parent, "snowflake"),
    "get_sparse_caps": (__spec__.parent, "base"),
    "get_thenlper_embedding_capabilities": (__spec__.parent, "thenlper"),
    "get_voyage_embedding_capabilities": (__spec__.parent, "voyage"),
    "get_whereisai_embedding_capabilities": (__spec__.parent, "whereisai"),
    "GRANITE_EMBEDDING_278M_CAPABILITIES": (__spec__.parent, "ibm_granite"),
    "GRANITE_EMBEDDING_30M_CAPABILITIES": (__spec__.parent, "ibm_granite"),
    "GRANITE_EMBEDDING_ENGLISH_R2_CAPABILITIES": (__spec__.parent, "ibm_granite"),
    "GRANITE_EMBEDDING_SMALL_ENGLISH_R2_CAPABILITIES": (__spec__.parent, "ibm_granite"),
    "INTFLOAT_MULTILINGUAL_E5_LARGE_CAPABILITIES": (__spec__.parent, "intfloat"),
    "INTFLOAT_MULTILINGUAL_E5_LARGE_INSTRUCT_CAPABILITIES": (__spec__.parent, "intfloat"),
    "JINAAI_JINA_EMBEDDINGS_V2_BASE_CODE_CAPABILITIES": (__spec__.parent, "jinaai"),
    "JINAAI_JINA_EMBEDDINGS_V2_SMALL_EN_CAPABILITIES": (__spec__.parent, "jinaai"),
    "JINAAI_JINA_EMBEDDINGS_V3_CAPABILITIES": (__spec__.parent, "jinaai"),
    "JINAAI_JINA_EMBEDDINGS_V4_CAPABILITIES": (__spec__.parent, "jinaai"),
    "MINISHLAB_M2V_BASE_GLOVE_CAPABILITIES": (__spec__.parent, "minishlab"),
    "MINISHLAB_M2V_BASE_GLOVE_SUBWORD_CAPABILITIES": (__spec__.parent, "minishlab"),
    "MINISHLAB_M2V_BASE_OUTPUT_CAPABILITIES": (__spec__.parent, "minishlab"),
    "MINISHLAB_M2V_MULTILINGUAL_OUTPUT_CAPABILITIES": (__spec__.parent, "minishlab"),
    "MINISHLAB_POTION_BASE_2M_CAPABILITIES": (__spec__.parent, "minishlab"),
    "MINISHLAB_POTION_BASE_4M_CAPABILITIES": (__spec__.parent, "minishlab"),
    "MINISHLAB_POTION_BASE_8M_CAPABILITIES": (__spec__.parent, "minishlab"),
    "MORPH_LLM_EMBEDDING_V4_CAPABILITIES": (__spec__.parent, "morph"),
    "NOMIC_AI_NOMIC_EMBED_TEXT_V2_MOE_CAPABILITIES": (__spec__.parent, "nomic_ai"),
    "QWEN_QWEN3_EMBEDDING_0_6B_CAPABILITIES": (__spec__.parent, "qwen"),
    "QWEN_QWEN3_EMBEDDING_4B_CAPABILITIES": (__spec__.parent, "qwen"),
    "QWEN_QWEN3_EMBEDDING_8B_CAPABILITIES": (__spec__.parent, "qwen"),
    "SENTENCE_TRANSFORMERS_ALL_MINILM_L12_V2_CAPABILITIES": (
        __spec__.parent,
        "sentence_transformers",
    ),
    "SENTENCE_TRANSFORMERS_ALL_MINILM_L6_V2_CAPABILITIES": (
        __spec__.parent,
        "sentence_transformers",
    ),
    "SENTENCE_TRANSFORMERS_ALL_MPNET_BASE_V2_CAPABILITIES": (
        __spec__.parent,
        "sentence_transformers",
    ),
    "SENTENCE_TRANSFORMERS_GTR_T5_BASE_CAPABILITIES": (__spec__.parent, "sentence_transformers"),
    "SENTENCE_TRANSFORMERS_MULTI_QA_MINILM_L6_COS_V1_CAPABILITIES": (
        __spec__.parent,
        "sentence_transformers",
    ),
    "SENTENCE_TRANSFORMERS_PARAPHRASE_MULTILINGUAL_MINILM_L12_V2_CAPABILITIES": (
        __spec__.parent,
        "sentence_transformers",
    ),
    "SENTENCE_TRANSFORMERS_PARAPHRASE_MULTILINGUAL_MPNET_BASE_V2_CAPABILITIES": (
        __spec__.parent,
        "sentence_transformers",
    ),
    "SNOWFLAKE_ARCTIC_EMBED2_568M_CAPABILITIES": (__spec__.parent, "snowflake"),
    "SNOWFLAKE_ARCTIC_EMBED_L_V2_0_CAPABILITIES": (__spec__.parent, "snowflake"),
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_V2_0_CAPABILITIES": (__spec__.parent, "snowflake"),
    "WHEREISAI_UAE_CODE_LARGE_V1_CAPABILITIES": (__spec__.parent, "whereisai"),
    "WHEREISAI_UAE_LARGE_V1_CAPABILITIES": (__spec__.parent, "whereisai"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "ALIBABA_NLP_GTE_MODERNBERT_BASE_CAPABILITIES",
    "ALIBABA_NLP_GTE_MULTILINGUAL_BASE_CAPABILITIES",
    "ALL_CAPABILITIES",
    "BAAI_BGE_BASE_EN_V1_5_CAPABILITIES",
    "BAAI_BGE_SMALL_EN_V1_5_CAPABILITIES",
    "BGE_LARGE_EN_335M_CAPABILITIES",
    "CAP_MAP",
    "GRANITE_EMBEDDING_30M_CAPABILITIES",
    "GRANITE_EMBEDDING_278M_CAPABILITIES",
    "GRANITE_EMBEDDING_ENGLISH_R2_CAPABILITIES",
    "GRANITE_EMBEDDING_SMALL_ENGLISH_R2_CAPABILITIES",
    "HAS_FASTEMBED",
    "HAS_ST",
    "INTFLOAT_MULTILINGUAL_E5_LARGE_CAPABILITIES",
    "INTFLOAT_MULTILINGUAL_E5_LARGE_INSTRUCT_CAPABILITIES",
    "JINAAI_JINA_EMBEDDINGS_V2_BASE_CODE_CAPABILITIES",
    "JINAAI_JINA_EMBEDDINGS_V2_SMALL_EN_CAPABILITIES",
    "JINAAI_JINA_EMBEDDINGS_V3_CAPABILITIES",
    "JINAAI_JINA_EMBEDDINGS_V4_CAPABILITIES",
    "MINISHLAB_M2V_BASE_GLOVE_CAPABILITIES",
    "MINISHLAB_M2V_BASE_GLOVE_SUBWORD_CAPABILITIES",
    "MINISHLAB_M2V_BASE_OUTPUT_CAPABILITIES",
    "MINISHLAB_M2V_MULTILINGUAL_OUTPUT_CAPABILITIES",
    "MINISHLAB_POTION_BASE_2M_CAPABILITIES",
    "MINISHLAB_POTION_BASE_4M_CAPABILITIES",
    "MINISHLAB_POTION_BASE_8M_CAPABILITIES",
    "MODEL_MAP",
    "MORPH_LLM_EMBEDDING_V4_CAPABILITIES",
    "MXBAI_EMBED_LARGE_CAPABILITIES",
    "NOMIC_AI_MODERNBERT_EMBED_BASE_CAPABILITIES",
    "NOMIC_AI_NOMIC_EMBED_TEXT_V2_MOE_CAPABILITIES",
    "QWEN_QWEN3_EMBEDDING_0_6B_CAPABILITIES",
    "QWEN_QWEN3_EMBEDDING_4B_CAPABILITIES",
    "QWEN_QWEN3_EMBEDDING_8B_CAPABILITIES",
    "SENTENCE_TRANSFORMERS_ALL_MINILM_L6_V2_CAPABILITIES",
    "SENTENCE_TRANSFORMERS_ALL_MINILM_L12_V2_CAPABILITIES",
    "SENTENCE_TRANSFORMERS_ALL_MPNET_BASE_V2_CAPABILITIES",
    "SENTENCE_TRANSFORMERS_GTR_T5_BASE_CAPABILITIES",
    "SENTENCE_TRANSFORMERS_MULTI_QA_MINILM_L6_COS_V1_CAPABILITIES",
    "SENTENCE_TRANSFORMERS_PARAPHRASE_MULTILINGUAL_MINILM_L12_V2_CAPABILITIES",
    "SENTENCE_TRANSFORMERS_PARAPHRASE_MULTILINGUAL_MPNET_BASE_V2_CAPABILITIES",
    "SNOWFLAKE_ARCTIC_EMBED2_568M_CAPABILITIES",
    "SNOWFLAKE_ARCTIC_EMBED_L_V2_0_CAPABILITIES",
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_L_CAPABILITIES",
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_CAPABILITIES",
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_LONG_CAPABILITIES",
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_V2_0_CAPABILITIES",
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_S_CAPABILITIES",
    "SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_XS_CAPABILITIES",
    "THENLPER_GTE_BASE_CAPABILITIES",
    "THENLPER_GTE_LARGE_CAPABILITIES",
    "VOYAGE_4_FAMILY",
    "VOYAGE_4_NANO_CAPABILITIES",
    "WHEREISAI_UAE_CODE_LARGE_V1_CAPABILITIES",
    "WHEREISAI_UAE_LARGE_V1_CAPABILITIES",
    "AlibabaNlpEmbeddingCapabilities",
    "AlibabaNlpProvider",
    "AmazonEmbeddingCapabilities",
    "BaaiEmbeddingCapabilities",
    "BaaiProvider",
    "CohereEmbeddingCapabilities",
    "EmbeddingCapabilitiesDict",
    "EmbeddingCapabilityResolver",
    "EmbeddingModelCapabilities",
    "GoogleEmbeddingCapabilities",
    "IbmGraniteEmbeddingCapabilities",
    "IbmGraniteProvider",
    "IntfloatEmbeddingCapabilities",
    "IntfloatProvider",
    "JinaaiEmbeddingCapabilities",
    "JinaaiProvider",
    "MinishlabEmbeddingCapabilities",
    "MinishlabProvider",
    "MistralEmbeddingCapabilities",
    "MixedbreadAiEmbeddingCapabilities",
    "MixedbreadAiProvider",
    "ModelFamily",
    "NomicAiEmbeddingCapabilities",
    "NomicAiProvider",
    "OpenaiEmbeddingCapabilities",
    "PartialCapabilities",
    "QwenEmbeddingCapabilities",
    "QwenProvider",
    "SentenceTransformersEmbeddingCapabilities",
    "SentenceTransformersProvider",
    "SnowflakeEmbeddingCapabilities",
    "SnowflakeProvider",
    "SparseCapabilities",
    "SparseEmbeddingCapabilityResolver",
    "SparseEmbeddingModelCapabilities",
    "ThenlperEmbeddingCapabilities",
    "ThenlperProvider",
    "Voyage4ModelFamily",
    "VoyageEmbeddingCapabilities",
    "WhereisaiEmbeddingCapabilities",
    "WhereisaiProvider",
    "get_alibaba_nlp_embedding_capabilities",
    "get_amazon_embedding_capabilities",
    "get_baai_embedding_capabilities",
    "get_cohere_embedding_capabilities",
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
    "get_thenlper_embedding_capabilities",
    "get_voyage_embedding_capabilities",
    "get_whereisai_embedding_capabilities",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
