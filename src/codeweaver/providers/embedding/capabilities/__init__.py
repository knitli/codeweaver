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

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AlibabaNlpEmbeddingCapabilities": (__spec__.parent, "alibaba_nlp"),
    "AlibabaNlpProvider": (__spec__.parent, "alibaba_nlp"),
    "AmazonEmbeddingCapabilities": (__spec__.parent, "amazon"),
    "BaaiEmbeddingCapabilities": (__spec__.parent, "baai"),
    "BaaiProvider": (__spec__.parent, "baai"),
    "CohereEmbeddingCapabilities": (__spec__.parent, "cohere"),
    "EmbeddingCapabilitiesDict": (__spec__.parent, "types"),
    "EmbeddingCapabilityResolver": (__spec__.parent, "resolver"),
    "EmbeddingModelCapabilities": (__spec__.parent, "base"),
    "GoogleEmbeddingCapabilities": (__spec__.parent, "google"),
    "IbmGraniteEmbeddingCapabilities": (__spec__.parent, "ibm_granite"),
    "IbmGraniteProvider": (__spec__.parent, "ibm_granite"),
    "IntfloatEmbeddingCapabilities": (__spec__.parent, "intfloat"),
    "IntfloatProvider": (__spec__.parent, "intfloat"),
    "JinaaiEmbeddingCapabilities": (__spec__.parent, "jinaai"),
    "JinaaiProvider": (__spec__.parent, "jinaai"),
    "MinishlabEmbeddingCapabilities": (__spec__.parent, "minishlab"),
    "MinishlabProvider": (__spec__.parent, "minishlab"),
    "MistralEmbeddingCapabilities": (__spec__.parent, "mistral"),
    "MixedbreadAiEmbeddingCapabilities": (__spec__.parent, "mixedbread_ai"),
    "MixedbreadAiProvider": (__spec__.parent, "mixedbread_ai"),
    "ModelFamily": (__spec__.parent, "base"),
    "NomicAiEmbeddingCapabilities": (__spec__.parent, "nomic_ai"),
    "NomicAiProvider": (__spec__.parent, "nomic_ai"),
    "OpenaiEmbeddingCapabilities": (__spec__.parent, "openai"),
    "PartialCapabilities": (__spec__.parent, "types"),
    "QwenEmbeddingCapabilities": (__spec__.parent, "qwen"),
    "QwenProvider": (__spec__.parent, "qwen"),
    "SentenceTransformersEmbeddingCapabilities": (__spec__.parent, "sentence_transformers"),
    "SentenceTransformersProvider": (__spec__.parent, "sentence_transformers"),
    "SnowflakeEmbeddingCapabilities": (__spec__.parent, "snowflake"),
    "SnowflakeProvider": (__spec__.parent, "snowflake"),
    "SparseCapabilities": (__spec__.parent, "base"),
    "SparseEmbeddingCapabilityResolver": (__spec__.parent, "resolver"),
    "SparseEmbeddingModelCapabilities": (__spec__.parent, "base"),
    "ThenlperEmbeddingCapabilities": (__spec__.parent, "thenlper"),
    "ThenlperProvider": (__spec__.parent, "thenlper"),
    "Voyage4ModelFamily": (__spec__.parent, "voyage"),
    "VoyageEmbeddingCapabilities": (__spec__.parent, "voyage"),
    "WhereisaiEmbeddingCapabilities": (__spec__.parent, "whereisai"),
    "WhereisaiProvider": (__spec__.parent, "whereisai"),
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
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
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
