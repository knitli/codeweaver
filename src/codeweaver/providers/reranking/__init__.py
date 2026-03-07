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
    from codeweaver.providers.reranking.capabilities import MappingProxyType
    from codeweaver.providers.reranking.capabilities.alibaba_nlp import (
        AlibabaNlpRerankingCapabilities,
    )
    from codeweaver.providers.reranking.capabilities.amazon import AmazonRerankingCapabilities
    from codeweaver.providers.reranking.capabilities.baai import BaaiRerankingCapabilities
    from codeweaver.providers.reranking.capabilities.base import (
        CodeWeaverValidationError,
        RerankingModelCapabilities,
    )
    from codeweaver.providers.reranking.capabilities.cohere import CohereRerankingCapabilities
    from codeweaver.providers.reranking.capabilities.jinaai import JinaaiRerankingCapabilities
    from codeweaver.providers.reranking.capabilities.mixed_bread_ai import (
        MixedBreadAiRerankingCapabilities,
    )
    from codeweaver.providers.reranking.capabilities.ms_marco import MsMarcoRerankingCapabilities
    from codeweaver.providers.reranking.capabilities.qwen import QwenRerankingCapabilities
    from codeweaver.providers.reranking.capabilities.resolver import (
        RerankingCapabilityResolver,
        RerankingCapabilityType,
    )
    from codeweaver.providers.reranking.capabilities.types import (
        PartialRerankingCapabilitiesDict,
        RerankingCapabilitiesDict,
    )
    from codeweaver.providers.reranking.capabilities.voyage import VoyageRerankingCapabilities
    from codeweaver.providers.reranking.providers.base import (
        CircuitBreakerOpenError,
        PydanticValidationError,
        RerankingProvider,
        RerankingProviderError,
        RetryError,
        StatisticsDep,
        ValidationError,
    )
    from codeweaver.providers.reranking.providers.bedrock import (
        BaseBedrockModel,
        BedrockInlineDocumentSource,
        BedrockRerankConfiguration,
        BedrockRerankingProvider,
        BedrockRerankingResult,
        BedrockRerankModelConfiguration,
        BedrockRerankRequest,
        BedrockRerankResultItem,
        BedrockTextQuery,
        ConfigurationError,
        DocumentSource,
        RerankConfiguration,
    )
    from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider
    from codeweaver.providers.reranking.providers.fastembed import (
        FastEmbedRerankingProvider,
        ProviderError,
        np,
    )
    from codeweaver.providers.reranking.providers.sentence_transformers import (
        SentenceTransformersRerankingProvider,
    )
    from codeweaver.providers.reranking.providers.types import RerankingResult
    from codeweaver.providers.reranking.providers.voyage import VoyageRerankingProvider

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
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
    "CircuitBreakerOpenError": (__spec__.parent, "providers.base"),
    "CodeWeaverValidationError": (__spec__.parent, "capabilities.base"),
    "CohereRerankingCapabilities": (__spec__.parent, "capabilities.cohere"),
    "CohereRerankingProvider": (__spec__.parent, "providers.cohere"),
    "ConfigurationError": (__spec__.parent, "providers.bedrock"),
    "DocumentSource": (__spec__.parent, "providers.bedrock"),
    "FastEmbedRerankingProvider": (__spec__.parent, "providers.fastembed"),
    "JinaaiRerankingCapabilities": (__spec__.parent, "capabilities.jinaai"),
    "MappingProxyType": (__spec__.parent, "capabilities"),
    "MixedBreadAiRerankingCapabilities": (__spec__.parent, "capabilities.mixed_bread_ai"),
    "MsMarcoRerankingCapabilities": (__spec__.parent, "capabilities.ms_marco"),
    "ProviderError": (__spec__.parent, "providers.fastembed"),
    "PydanticValidationError": (__spec__.parent, "providers.base"),
    "QwenRerankingCapabilities": (__spec__.parent, "capabilities.qwen"),
    "RerankConfiguration": (__spec__.parent, "providers.bedrock"),
    "RerankingCapabilitiesDict": (__spec__.parent, "capabilities.types"),
    "RerankingCapabilityResolver": (__spec__.parent, "capabilities.resolver"),
    "RerankingCapabilityType": (__spec__.parent, "capabilities.resolver"),
    "RerankingModelCapabilities": (__spec__.parent, "capabilities.base"),
    "RerankingProvider": (__spec__.parent, "providers.base"),
    "RerankingProviderError": (__spec__.parent, "providers.base"),
    "RerankingResult": (__spec__.parent, "providers.types"),
    "RetryError": (__spec__.parent, "providers.base"),
    "SentenceTransformersRerankingProvider": (__spec__.parent, "providers.sentence_transformers"),
    "StatisticsDep": (__spec__.parent, "providers.base"),
    "ValidationError": (__spec__.parent, "providers.base"),
    "VoyageRerankingCapabilities": (__spec__.parent, "capabilities.voyage"),
    "VoyageRerankingProvider": (__spec__.parent, "providers.voyage"),
    "np": (__spec__.parent, "providers.fastembed"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
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
    "CircuitBreakerOpenError",
    "CodeWeaverValidationError",
    "CohereRerankingCapabilities",
    "CohereRerankingProvider",
    "ConfigurationError",
    "DocumentSource",
    "FastEmbedRerankingProvider",
    "JinaaiRerankingCapabilities",
    "MappingProxyType",
    "MixedBreadAiRerankingCapabilities",
    "MsMarcoRerankingCapabilities",
    "PartialRerankingCapabilitiesDict",
    "ProviderError",
    "PydanticValidationError",
    "QwenRerankingCapabilities",
    "RerankConfiguration",
    "RerankingCapabilitiesDict",
    "RerankingCapabilityResolver",
    "RerankingCapabilityType",
    "RerankingModelCapabilities",
    "RerankingProvider",
    "RerankingProviderError",
    "RerankingResult",
    "RetryError",
    "SentenceTransformersRerankingProvider",
    "StatisticsDep",
    "ValidationError",
    "VoyageRerankingCapabilities",
    "VoyageRerankingProvider",
    "np",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
