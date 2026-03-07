# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Entry point for embedding providers. Defines the abstract base class and includes a utility for retrieving specific provider implementations."""

from __future__ import annotations

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.embedding.providers.base import (
        DEFAULT_MAX_BATCH_TOKENS,
        CircuitBreakerOpenError,
        CodeWeaverValidationError,
        EmbeddingCustomDeps,
        EmbeddingErrorInfo,
        EmbeddingImplementationDeps,
        EmbeddingProvider,
        ProviderError,
        RetryError,
        SparseEmbeddingProvider,
        StatisticsDep,
        default_input_transformer,
        default_output_transformer,
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
        is_cohere_request,
        is_cohere_response,
        is_one_of_valid_types,
        is_titan_response,
        shared_serializer,
        shared_validator,
    )
    from codeweaver.providers.embedding.providers.cohere import (
        CohereEmbeddingProvider,
        ConfigurationError,
    )
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

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DEFAULT_MAX_BATCH_TOKENS": (__spec__.parent, "base"),
    "LITELLM_OPENAI_PROVIDERS": (__spec__.parent, "litellm"),
    "BaseBedrockModel": (__spec__.parent, "bedrock"),
    "BedrockEmbeddingProvider": (__spec__.parent, "bedrock"),
    "BedrockInvokeEmbeddingRequest": (__spec__.parent, "bedrock"),
    "BedrockInvokeEmbeddingResponse": (__spec__.parent, "bedrock"),
    "CircuitBreakerOpenError": (__spec__.parent, "base"),
    "CodeWeaverValidationError": (__spec__.parent, "base"),
    "CohereEmbeddingProvider": (__spec__.parent, "cohere"),
    "CohereEmbeddingRequestBody": (__spec__.parent, "bedrock"),
    "CohereEmbeddingResponse": (__spec__.parent, "bedrock"),
    "CohereRequestHandler": (__spec__.parent, "bedrock"),
    "ConfigurationError": (__spec__.parent, "cohere"),
    "EmbeddingErrorInfo": (__spec__.parent, "base"),
    "EmbeddingProvider": (__spec__.parent, "base"),
    "FastEmbedEmbeddingProvider": (__spec__.parent, "fastembed"),
    "FastEmbedSparseProvider": (__spec__.parent, "fastembed"),
    "GoogleEmbeddingProvider": (__spec__.parent, "google"),
    "GoogleEmbeddingTasks": (__spec__.parent, "google"),
    "HuggingFaceEmbeddingProvider": (__spec__.parent, "huggingface"),
    "ImageDescription": (__spec__.parent, "bedrock"),
    "InvokeRequestDict": (__spec__.parent, "bedrock"),
    "MistralEmbeddingProvider": (__spec__.parent, "mistral"),
    "ProviderError": (__spec__.parent, "base"),
    "RetryError": (__spec__.parent, "base"),
    "SentenceTransformersEmbeddingProvider": (__spec__.parent, "sentence_transformers"),
    "SentenceTransformersSparseProvider": (__spec__.parent, "sentence_transformers"),
    "SparseEmbeddingProvider": (__spec__.parent, "base"),
    "StatisticsDep": (__spec__.parent, "base"),
    "TitanEmbeddingV2RequestBody": (__spec__.parent, "bedrock"),
    "TitanEmbeddingV2Response": (__spec__.parent, "bedrock"),
    "VoyageEmbeddingProvider": (__spec__.parent, "voyage"),
    "default_input_transformer": (__spec__.parent, "base"),
    "default_output_transformer": (__spec__.parent, "base"),
    "fastembed_output_transformer": (__spec__.parent, "fastembed"),
    "fastembed_sparse_output_transformer": (__spec__.parent, "fastembed"),
    "huggingface_hub_input_transformer": (__spec__.parent, "huggingface"),
    "huggingface_hub_output_transformer": (__spec__.parent, "huggingface"),
    "is_cohere_request": (__spec__.parent, "bedrock"),
    "is_cohere_response": (__spec__.parent, "bedrock"),
    "is_one_of_valid_types": (__spec__.parent, "bedrock"),
    "is_titan_response": (__spec__.parent, "bedrock"),
    "LiteLLMModelSpec": (__spec__.parent, "litellm"),
    "np": (__spec__.parent, "base"),
    "OpenAIEmbeddingBase": (__spec__.parent, "openai_factory"),
    "process_for_instruction_model": (__spec__.parent, "sentence_transformers"),
    "shared_serializer": (__spec__.parent, "bedrock"),
    "shared_validator": (__spec__.parent, "bedrock"),
    "voyage_context_output_transformer": (__spec__.parent, "voyage"),
    "voyage_output_transformer": (__spec__.parent, "voyage"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "DEFAULT_MAX_BATCH_TOKENS",
    "LITELLM_OPENAI_PROVIDERS",
    "BaseBedrockModel",
    "BedrockEmbeddingProvider",
    "BedrockInvokeEmbeddingRequest",
    "BedrockInvokeEmbeddingResponse",
    "CircuitBreakerOpenError",
    "CodeWeaverValidationError",
    "CohereEmbeddingProvider",
    "CohereEmbeddingRequestBody",
    "CohereEmbeddingResponse",
    "CohereRequestHandler",
    "ConfigurationError",
    "EmbeddingCustomDeps",
    "EmbeddingErrorInfo",
    "EmbeddingImplementationDeps",
    "EmbeddingProvider",
    "FastEmbedEmbeddingProvider",
    "FastEmbedSparseProvider",
    "GoogleEmbeddingProvider",
    "GoogleEmbeddingTasks",
    "HuggingFaceEmbeddingProvider",
    "ImageDescription",
    "InvokeRequestDict",
    "LiteLLMModelSpec",
    "MappingProxyType",
    "MistralEmbeddingProvider",
    "OpenAIEmbeddingBase",
    "ProviderError",
    "RetryError",
    "SentenceTransformersEmbeddingProvider",
    "SentenceTransformersSparseProvider",
    "SparseEmbeddingProvider",
    "StatisticsDep",
    "TitanEmbeddingV2RequestBody",
    "TitanEmbeddingV2Response",
    "VoyageEmbeddingProvider",
    "default_input_transformer",
    "default_output_transformer",
    "fastembed_output_transformer",
    "fastembed_sparse_output_transformer",
    "huggingface_hub_input_transformer",
    "huggingface_hub_output_transformer",
    "is_cohere_request",
    "is_cohere_response",
    "is_one_of_valid_types",
    "is_titan_response",
    "np",
    "process_for_instruction_model",
    "shared_serializer",
    "shared_validator",
    "voyage_context_output_transformer",
    "voyage_output_transformer",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
