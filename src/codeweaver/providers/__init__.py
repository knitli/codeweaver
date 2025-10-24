# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The providers package provides definitions and capabilities for various service providers used in CodeWeaver at the root level, and contains subpackages for embedding, reranking, and vector store providers."""

from codeweaver.providers.agent import (
    AbstractToolset,
    AgentModelSettings,
    AgentProvider,
    CombinedToolset,
    DownloadedItem,
    ExternalToolset,
    FilteredToolset,
    FunctionToolset,
    KnownAgentModelName,
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
    PROVIDER_CAPABILITIES,
    VECTOR_PROVIDER_CAPABILITIES,
    get_provider_kinds,
)
from codeweaver.providers.embedding import (
    EmbeddingModelCapabilities,
    EmbeddingProvider,
    SparseEmbeddingModelCapabilities,
    get_embedding_model_provider,
    user_settings_to_provider_settings,
)
from codeweaver.providers.embedding import (
    load_default_capabilities as load_embedding_default_capabilities,
)
from codeweaver.providers.optimize import (
    AvailableOptimizations,
    OptimizationDecisions,
    decide_fastembed_runtime,
    get_optimizations,
)
from codeweaver.providers.provider import (
    LiteralProvider,
    LiteralProviderKind,
    Provider,
    ProviderEnvVars,
    ProviderKind,
)
from codeweaver.providers.reranking import (
    KnownRerankModelName,
    RerankingProvider,
    get_rerank_model_provider,
)
from codeweaver.providers.reranking import dependency_map as reranking_dependency_map
from codeweaver.providers.reranking import (
    load_default_capabilities as load_reranking_default_capabilities,
)
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.providers.tools import get_data_provider, load_default_data_providers
from codeweaver.providers.vector_stores import VectorStoreProvider


__all__ = (
    "PROVIDER_CAPABILITIES",
    "VECTOR_PROVIDER_CAPABILITIES",
    "AbstractToolset",
    "AgentModelSettings",
    "AgentProvider",
    "AvailableOptimizations",
    "CombinedToolset",
    "DownloadedItem",
    "EmbeddingModelCapabilities",
    "EmbeddingProvider",
    "ExternalToolset",
    "FilteredToolset",
    "FunctionToolset",
    "KnownAgentModelName",
    "KnownRerankModelName",
    "LiteralProvider",
    "LiteralProviderKind",
    "OptimizationDecisions",
    "PrefixedToolset",
    "PreparedToolset",
    "Provider",
    "ProviderEnvVars",
    "ProviderKind",
    "RenamedToolset",
    "RerankingModelCapabilities",
    "RerankingProvider",
    "SparseEmbeddingModelCapabilities",
    "SparseEmbeddingModelCapabilities",
    "ToolsetTool",
    "VectorStoreProvider",
    "WrapperToolset",
    "cached_async_http_client",
    "decide_fastembed_runtime",
    "download_item",
    "get_agent_model_provider",
    "get_data_provider",
    "get_embedding_model_provider",
    "get_optimizations",
    "get_provider_kinds",
    "get_rerank_model_provider",
    "infer_agent_provider_class",
    "infer_model",
    "load_default_agent_providers",
    "load_default_data_providers",
    "load_embedding_default_capabilities",
    "load_reranking_default_capabilities",
    "override_allow_model_requests",
    "reranking_dependency_map",
    "user_settings_to_provider_settings",
)
