# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Entrypoint for reranking providers."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.reranking.providers.base import (
        CircuitBreakerOpenError,
        PydanticValidationError,
        RerankingProvider,
        RerankingProviderError,
        RetryError,
        StatisticsDep,
        ValidationError,
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
        CodeWeaverValidationError,
        ConfigurationError,
        DocumentSource,
        RerankConfiguration,
        bedrock_reranking_input_transformer,
        bedrock_reranking_output_transformer,
    )
    from codeweaver.providers.reranking.providers.cohere import (
        CohereRerankingProvider,
        cohere_reranking_output_transformer,
    )
    from codeweaver.providers.reranking.providers.fastembed import (
        FastEmbedRerankingProvider,
        ProviderError,
        np,
    )
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
    "VALID_REGION_PATTERN": (__spec__.parent, "bedrock"),
    "VALID_REGIONS": (__spec__.parent, "bedrock"),
    "BaseBedrockModel": (__spec__.parent, "bedrock"),
    "BedrockInlineDocumentSource": (__spec__.parent, "bedrock"),
    "BedrockRerankConfiguration": (__spec__.parent, "bedrock"),
    "BedrockRerankingProvider": (__spec__.parent, "bedrock"),
    "BedrockRerankingResult": (__spec__.parent, "bedrock"),
    "BedrockRerankModelConfiguration": (__spec__.parent, "bedrock"),
    "BedrockRerankRequest": (__spec__.parent, "bedrock"),
    "BedrockRerankResultItem": (__spec__.parent, "bedrock"),
    "BedrockTextQuery": (__spec__.parent, "bedrock"),
    "CircuitBreakerOpenError": (__spec__.parent, "base"),
    "CodeWeaverValidationError": (__spec__.parent, "bedrock"),
    "CohereRerankingProvider": (__spec__.parent, "cohere"),
    "ConfigurationError": (__spec__.parent, "bedrock"),
    "DocumentSource": (__spec__.parent, "bedrock"),
    "FastEmbedRerankingProvider": (__spec__.parent, "fastembed"),
    "ProviderError": (__spec__.parent, "fastembed"),
    "PydanticValidationError": (__spec__.parent, "base"),
    "RerankConfiguration": (__spec__.parent, "bedrock"),
    "RerankingProvider": (__spec__.parent, "base"),
    "RerankingProviderError": (__spec__.parent, "base"),
    "RerankingResult": (__spec__.parent, "types"),
    "RetryError": (__spec__.parent, "base"),
    "SentenceTransformersRerankingProvider": (__spec__.parent, "sentence_transformers"),
    "StatisticsDep": (__spec__.parent, "base"),
    "ValidationError": (__spec__.parent, "base"),
    "VoyageRerankingProvider": (__spec__.parent, "voyage"),
    "bedrock_reranking_input_transformer": (__spec__.parent, "bedrock"),
    "bedrock_reranking_output_transformer": (__spec__.parent, "bedrock"),
    "cohere_reranking_output_transformer": (__spec__.parent, "cohere"),
    "default_reranking_input_transformer": (__spec__.parent, "base"),
    "default_reranking_output_transformer": (__spec__.parent, "base"),
    "np": (__spec__.parent, "fastembed"),
    "preprocess_for_qwen": (__spec__.parent, "sentence_transformers"),
    "voyage_reranking_output_transformer": (__spec__.parent, "voyage"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "VALID_REGIONS",
    "VALID_REGION_PATTERN",
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
    "CohereRerankingProvider",
    "ConfigurationError",
    "DocumentSource",
    "FastEmbedRerankingProvider",
    "MappingProxyType",
    "ProviderError",
    "PydanticValidationError",
    "RerankConfiguration",
    "RerankingProvider",
    "RerankingProviderError",
    "RerankingResult",
    "RetryError",
    "SentenceTransformersRerankingProvider",
    "StatisticsDep",
    "ValidationError",
    "VoyageRerankingProvider",
    "bedrock_reranking_input_transformer",
    "bedrock_reranking_output_transformer",
    "cohere_reranking_output_transformer",
    "default_reranking_input_transformer",
    "default_reranking_output_transformer",
    "np",
    "preprocess_for_qwen",
    "voyage_reranking_output_transformer",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
