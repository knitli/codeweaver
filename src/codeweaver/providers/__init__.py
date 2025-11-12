# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The providers package provides definitions and capabilities for various service providers used in CodeWeaver at the root level, and contains subpackages for embedding, reranking, and vector store providers."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.agent import (
        AbstractToolset,
        AgentModel,
        AgentModelSettings,
        AgentProfile,
        AgentProfileSpec,
        AgentProvider,
        CombinedToolset,
        DownloadedItem,
        ExternalToolset,
        FilteredToolset,
        FunctionToolset,
        PrefixedToolset,
        PreparedToolset,
        RenamedToolset,
        ToolsetTool,
        WrapperToolset,
        cached_async_http_client,
        download_item,
        get_agent_model_provider,
        infer_agent_provider_class,
        infer_model,
        load_default_agent_providers,
        override_allow_model_requests,
    )
    from codeweaver.providers.capabilities import (
        CLIENT_MAP,
        PROVIDER_CAPABILITIES,
        VECTOR_PROVIDER_CAPABILITIES,
        get_provider_kinds,
    )
    from codeweaver.providers.data import get_data_provider, load_default_data_providers
    from codeweaver.providers.embedding import (
        BedrockEmbeddingProvider,
        ChunkEmbeddings,
        CohereEmbeddingProvider,
        EmbeddingBatchInfo,
        EmbeddingModelCapabilities,
        EmbeddingProvider,
        FastEmbedEmbeddingProvider,
        FastEmbedSparseProvider,
        GoogleEmbeddingProvider,
        HuggingFaceEmbeddingProvider,
        MistralEmbeddingProvider,
        OpenAIEmbeddingBase,
        RawEmbeddingVectors,
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersSparseProvider,
        SparseEmbedding,
        SparseEmbeddingModelCapabilities,
        StoredEmbeddingVectors,
        VoyageEmbeddingProvider,
    )
    from codeweaver.providers.optimize import (
        AvailableOptimizations,
        OptimizationDecisions,
        decide_fastembed_runtime,
        get_optimizations,
    )
    from codeweaver.providers.provider import (
        Provider,
        ProviderEnvVarInfo,
        ProviderEnvVars,
        ProviderKind,
    )
    from codeweaver.providers.reranking import (
        BedrockRerankingProvider,
        CohereRerankingProvider,
        FastEmbedRerankingProvider,
        QueryType,
        RerankingProvider,
        RerankingResult,
        SentenceTransformersRerankingProvider,
        VoyageRerankingProvider,
    )
    from codeweaver.providers.types import LiteralProvider, LiteralProviderKind
    from codeweaver.providers.vector_stores import (
        CollectionMetadata,
        HybridVectorPayload,
        MemoryVectorStoreProvider,
        QdrantVectorStoreProvider,
        VectorStoreProvider,
        resolve_dimensions,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AbstractToolset": (__spec__.parent, "agent"),
    "AgentModel": (__spec__.parent, "agent"),
    "AgentModelSettings": (__spec__.parent, "agent"),
    "AgentProfile": (__spec__.parent, "agent"),
    "AgentProfileSpec": (__spec__.parent, "agent"),
    "AgentProvider": (__spec__.parent, "agent"),
    "AvailableOptimizations": (__spec__.parent, "optimize"),
    "BedrockEmbeddingProvider": (__spec__.parent, "embedding"),
    "BedrockRerankingProvider": (__spec__.parent, "reranking"),
    "CLIENT_MAP": (__spec__.parent, "capabilities"),
    "ChunkEmbeddings": (__spec__.parent, "embedding"),
    "CohereEmbeddingProvider": (__spec__.parent, "embedding"),
    "CohereRerankingProvider": (__spec__.parent, "reranking"),
    "CollectionMetadata": (__spec__.parent, "vector_stores"),
    "CombinedToolset": (__spec__.parent, "agent"),
    "DownloadedItem": (__spec__.parent, "agent"),
    "EmbeddingBatchInfo": (__spec__.parent, "embedding"),
    "EmbeddingModelCapabilities": (__spec__.parent, "embedding"),
    "EmbeddingProvider": (__spec__.parent, "embedding"),
    "ExternalToolset": (__spec__.parent, "agent"),
    "FastEmbedEmbeddingProvider": (__spec__.parent, "embedding"),
    "FastEmbedRerankingProvider": (__spec__.parent, "reranking"),
    "FastEmbedSparseProvider": (__spec__.parent, "embedding"),
    "FilteredToolset": (__spec__.parent, "agent"),
    "FunctionToolset": (__spec__.parent, "agent"),
    "GoogleEmbeddingProvider": (__spec__.parent, "embedding"),
    "HuggingFaceEmbeddingProvider": (__spec__.parent, "embedding"),
    "HybridVectorPayload": (__spec__.parent, "vector_stores"),
    "LiteralProvider": (__spec__.parent, "types"),
    "LiteralProviderKind": (__spec__.parent, "types"),
    "MemoryVectorStoreProvider": (__spec__.parent, "vector_stores"),
    "MistralEmbeddingProvider": (__spec__.parent, "embedding"),
    "OpenAIEmbeddingBase": (__spec__.parent, "embedding"),
    "OptimizationDecisions": (__spec__.parent, "optimize"),
    "PROVIDER_CAPABILITIES": (__spec__.parent, "capabilities"),
    "PrefixedToolset": (__spec__.parent, "agent"),
    "PreparedToolset": (__spec__.parent, "agent"),
    "Provider": (__spec__.parent, "provider"),
    "ProviderEnvVarInfo": (__spec__.parent, "provider"),
    "ProviderEnvVars": (__spec__.parent, "provider"),
    "ProviderKind": (__spec__.parent, "provider"),
    "QdrantVectorStoreProvider": (__spec__.parent, "vector_stores"),
    "QueryType": (__spec__.parent, "reranking"),
    "RawEmbeddingVectors": (__spec__.parent, "embedding"),
    "RenamedToolset": (__spec__.parent, "agent"),
    "RerankingProvider": (__spec__.parent, "reranking"),
    "RerankingResult": (__spec__.parent, "reranking"),
    "SentenceTransformersEmbeddingProvider": (__spec__.parent, "embedding"),
    "SentenceTransformersRerankingProvider": (__spec__.parent, "reranking"),
    "SentenceTransformersSparseProvider": (__spec__.parent, "embedding"),
    "SparseEmbedding": (__spec__.parent, "embedding"),
    "SparseEmbeddingModelCapabilities": (__spec__.parent, "embedding"),
    "StoredEmbeddingVectors": (__spec__.parent, "embedding"),
    "ToolsetTool": (__spec__.parent, "agent"),
    "VECTOR_PROVIDER_CAPABILITIES": (__spec__.parent, "capabilities"),
    "VectorStoreProvider": (__spec__.parent, "vector_stores.base"),
    "VoyageEmbeddingProvider": (__spec__.parent, "embedding"),
    "VoyageRerankingProvider": (__spec__.parent, "reranking"),
    "WrapperToolset": (__spec__.parent, "agent"),
    "cached_async_http_client": (__spec__.parent, "agent"),
    "decide_fastembed_runtime": (__spec__.parent, "optimize"),
    "download_item": (__spec__.parent, "agent"),
    "get_agent_model_provider": (__spec__.parent, "agent"),
    "get_data_provider": (__spec__.parent, "data"),
    "get_optimizations": (__spec__.parent, "optimize"),
    "get_provider_kinds": (__spec__.parent, "capabilities"),
    "infer_agent_provider_class": (__spec__.parent, "agent"),
    "infer_model": (__spec__.parent, "agent"),
    "load_default_agent_providers": (__spec__.parent, "agent"),
    "load_default_data_providers": (__spec__.parent, "data"),
    "override_allow_model_requests": (__spec__.parent, "agent"),
    "resolve_dimensions": (__spec__.parent, "vector_stores"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the providers package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = (
    "CLIENT_MAP",
    "PROVIDER_CAPABILITIES",
    "VECTOR_PROVIDER_CAPABILITIES",
    "AbstractToolset",
    "AgentModel",
    "AgentModelSettings",
    "AgentProfile",
    "AgentProfileSpec",
    "AgentProvider",
    "AvailableOptimizations",
    "BedrockEmbeddingProvider",
    "BedrockRerankingProvider",
    "ChunkEmbeddings",
    "CohereEmbeddingProvider",
    "CohereRerankingProvider",
    "CollectionMetadata",
    "CombinedToolset",
    "DownloadedItem",
    "EmbeddingBatchInfo",
    "EmbeddingBatchInfo",
    "EmbeddingModelCapabilities",
    "EmbeddingProvider",
    "ExternalToolset",
    "FastEmbedEmbeddingProvider",
    "FastEmbedRerankingProvider",
    "FastEmbedSparseProvider",
    "FilteredToolset",
    "FunctionToolset",
    "GoogleEmbeddingProvider",
    "HuggingFaceEmbeddingProvider",
    "HybridVectorPayload",
    "LiteralProvider",
    "LiteralProviderKind",
    "MemoryVectorStoreProvider",
    "MistralEmbeddingProvider",
    "OpenAIEmbeddingBase",
    "OptimizationDecisions",
    "PrefixedToolset",
    "PreparedToolset",
    "Provider",
    "ProviderEnvVarInfo",
    "ProviderEnvVars",
    "ProviderKind",
    "QdrantVectorStoreProvider",
    "QueryType",
    "RawEmbeddingVectors",
    "RenamedToolset",
    "RerankingProvider",
    "RerankingResult",
    "SentenceTransformersEmbeddingProvider",
    "SentenceTransformersRerankingProvider",
    "SentenceTransformersSparseProvider",
    "SparseEmbedding",
    "SparseEmbeddingModelCapabilities",
    "StoredEmbeddingVectors",
    "ToolsetTool",
    "VectorStoreProvider",
    "VoyageEmbeddingProvider",
    "VoyageRerankingProvider",
    "WrapperToolset",
    "cached_async_http_client",
    "decide_fastembed_runtime",
    "download_item",
    "get_agent_model_provider",
    "get_data_provider",
    "get_optimizations",
    "get_provider_kinds",
    "infer_agent_provider_class",
    "infer_model",
    "load_default_agent_providers",
    "load_default_data_providers",
    "override_allow_model_requests",
    "resolve_dimensions",
)


def __dir__() -> list[str]:
    return list(__all__)
