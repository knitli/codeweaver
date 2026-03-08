# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Base class for reranking providers."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities.alibaba_nlp import (
        AlibabaNlpRerankingCapabilities,
        get_alibaba_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.amazon import (
        AmazonRerankingCapabilities,
        get_amazon_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.baai import (
        BaaiRerankingCapabilities,
        get_baai_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
    from codeweaver.providers.reranking.capabilities.cohere import (
        CohereRerankingCapabilities,
        cohere_max_input,
        get_cohere_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.jinaai import (
        JinaaiRerankingCapabilities,
        get_jinaai_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.mixed_bread_ai import (
        MixedBreadAiRerankingCapabilities,
        get_mixed_bread_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.ms_marco import (
        MsMarcoRerankingCapabilities,
        get_marco_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.qwen import (
        QwenRerankingCapabilities,
        get_qwen_reranking_capabilities,
    )
    from codeweaver.providers.reranking.capabilities.resolver import RerankingCapabilityResolver
    from codeweaver.providers.reranking.capabilities.types import (
        PartialRerankingCapabilitiesDict,
        RerankingCapabilitiesDict,
    )
    from codeweaver.providers.reranking.capabilities.voyage import (
        VoyageRerankingCapabilities,
        get_voyage_reranking_capabilities,
    )
    from codeweaver.providers.reranking.providers.base import (
        RerankingProvider,
        default_reranking_input_transformer,
        default_reranking_output_transformer,
    )
    from codeweaver.providers.reranking.providers.bedrock import (
        VALID_REGION_PATTERN,
        VALID_REGIONS,
        BaseBedrockModel,
        BedrockInlineDocumentSource,
        BedrockRerankConfiguration,
        BedrockRerankingProvider,
        BedrockRerankingResult,
        BedrockRerankModelConfiguration,
        BedrockRerankRequest,
        BedrockRerankResultItem,
        BedrockTextQuery,
        DocumentSource,
        RerankConfiguration,
        bedrock_reranking_input_transformer,
        bedrock_reranking_output_transformer,
    )
    from codeweaver.providers.reranking.providers.cohere import (
        CohereRerankingProvider,
        cohere_reranking_output_transformer,
    )
    from codeweaver.providers.reranking.providers.fastembed import FastEmbedRerankingProvider
    from codeweaver.providers.reranking.providers.sentence_transformers import (
        SentenceTransformersRerankingProvider,
        preprocess_for_qwen,
    )
    from codeweaver.providers.reranking.providers.types import RerankingResult
    from codeweaver.providers.reranking.providers.voyage import (
        VoyageRerankingProvider,
        voyage_reranking_output_transformer,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "VALID_REGION_PATTERN": (__spec__.parent, "providers.bedrock"),
    "VALID_REGIONS": (__spec__.parent, "providers.bedrock"),
    "AlibabaNlpRerankingCapabilities": (__spec__.parent, "capabilities.alibaba_nlp"),
    "AmazonRerankingCapabilities": (__spec__.parent, "capabilities.amazon"),
    "BaaiRerankingCapabilities": (__spec__.parent, "capabilities.baai"),
    "BaseBedrockModel": (__spec__.parent, "providers.bedrock"),
    "BedrockInlineDocumentSource": (__spec__.parent, "providers.bedrock"),
    "BedrockRerankConfiguration": (__spec__.parent, "providers.bedrock"),
    "BedrockRerankingProvider": (__spec__.parent, "providers.bedrock"),
    "BedrockRerankingResult": (__spec__.parent, "providers.bedrock"),
    "BedrockRerankModelConfiguration": (__spec__.parent, "providers.bedrock"),
    "BedrockRerankRequest": (__spec__.parent, "providers.bedrock"),
    "BedrockRerankResultItem": (__spec__.parent, "providers.bedrock"),
    "BedrockTextQuery": (__spec__.parent, "providers.bedrock"),
    "CohereRerankingCapabilities": (__spec__.parent, "capabilities.cohere"),
    "CohereRerankingProvider": (__spec__.parent, "providers.cohere"),
    "DocumentSource": (__spec__.parent, "providers.bedrock"),
    "FastEmbedRerankingProvider": (__spec__.parent, "providers.fastembed"),
    "JinaaiRerankingCapabilities": (__spec__.parent, "capabilities.jinaai"),
    "MixedBreadAiRerankingCapabilities": (__spec__.parent, "capabilities.mixed_bread_ai"),
    "MsMarcoRerankingCapabilities": (__spec__.parent, "capabilities.ms_marco"),
    "QwenRerankingCapabilities": (__spec__.parent, "capabilities.qwen"),
    "RerankConfiguration": (__spec__.parent, "providers.bedrock"),
    "RerankingCapabilitiesDict": (__spec__.parent, "capabilities.types"),
    "RerankingCapabilityResolver": (__spec__.parent, "capabilities.resolver"),
    "RerankingModelCapabilities": (__spec__.parent, "capabilities.base"),
    "RerankingProvider": (__spec__.parent, "providers.base"),
    "RerankingResult": (__spec__.parent, "providers.types"),
    "SentenceTransformersRerankingProvider": (__spec__.parent, "providers.sentence_transformers"),
    "VoyageRerankingCapabilities": (__spec__.parent, "capabilities.voyage"),
    "VoyageRerankingProvider": (__spec__.parent, "providers.voyage"),
    "bedrock_reranking_input_transformer": (__spec__.parent, "providers.bedrock"),
    "bedrock_reranking_output_transformer": (__spec__.parent, "providers.bedrock"),
    "cohere_max_input": (__spec__.parent, "capabilities.cohere"),
    "cohere_reranking_output_transformer": (__spec__.parent, "providers.cohere"),
    "default_reranking_input_transformer": (__spec__.parent, "providers.base"),
    "default_reranking_output_transformer": (__spec__.parent, "providers.base"),
    "get_alibaba_reranking_capabilities": (__spec__.parent, "capabilities.alibaba_nlp"),
    "get_amazon_reranking_capabilities": (__spec__.parent, "capabilities.amazon"),
    "get_baai_reranking_capabilities": (__spec__.parent, "capabilities.baai"),
    "get_cohere_reranking_capabilities": (__spec__.parent, "capabilities.cohere"),
    "get_jinaai_reranking_capabilities": (__spec__.parent, "capabilities.jinaai"),
    "get_marco_reranking_capabilities": (__spec__.parent, "capabilities.ms_marco"),
    "get_mixed_bread_reranking_capabilities": (__spec__.parent, "capabilities.mixed_bread_ai"),
    "get_qwen_reranking_capabilities": (__spec__.parent, "capabilities.qwen"),
    "get_voyage_reranking_capabilities": (__spec__.parent, "capabilities.voyage"),
    "preprocess_for_qwen": (__spec__.parent, "providers.sentence_transformers"),
    "voyage_reranking_output_transformer": (__spec__.parent, "providers.voyage"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "VALID_REGIONS",
    "VALID_REGION_PATTERN",
    "AlibabaNlpRerankingCapabilities",
    "AmazonRerankingCapabilities",
    "BaaiRerankingCapabilities",
    "BaseBedrockModel",
    "BedrockInlineDocumentSource",
    "BedrockRerankConfiguration",
    "BedrockRerankModelConfiguration",
    "BedrockRerankRequest",
    "BedrockRerankResultItem",
    "BedrockRerankingProvider",
    "BedrockRerankingResult",
    "BedrockTextQuery",
    "CohereRerankingCapabilities",
    "CohereRerankingProvider",
    "DocumentSource",
    "FastEmbedRerankingProvider",
    "JinaaiRerankingCapabilities",
    "MixedBreadAiRerankingCapabilities",
    "MsMarcoRerankingCapabilities",
    "PartialRerankingCapabilitiesDict",
    "QwenRerankingCapabilities",
    "RerankConfiguration",
    "RerankingCapabilitiesDict",
    "RerankingCapabilityResolver",
    "RerankingModelCapabilities",
    "RerankingProvider",
    "RerankingResult",
    "SentenceTransformersRerankingProvider",
    "VoyageRerankingCapabilities",
    "VoyageRerankingProvider",
    "bedrock_reranking_input_transformer",
    "bedrock_reranking_output_transformer",
    "cohere_max_input",
    "cohere_reranking_output_transformer",
    "default_reranking_input_transformer",
    "default_reranking_output_transformer",
    "get_alibaba_reranking_capabilities",
    "get_amazon_reranking_capabilities",
    "get_baai_reranking_capabilities",
    "get_cohere_reranking_capabilities",
    "get_jinaai_reranking_capabilities",
    "get_marco_reranking_capabilities",
    "get_mixed_bread_reranking_capabilities",
    "get_qwen_reranking_capabilities",
    "get_voyage_reranking_capabilities",
    "preprocess_for_qwen",
    "voyage_reranking_output_transformer",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
