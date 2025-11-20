# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Base class for reranking providers."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal


if TYPE_CHECKING:
    from codeweaver.exceptions import ConfigurationError
    from codeweaver.providers.provider import Provider
    from codeweaver.providers.reranking.capabilities import (
        dependency_map,
        get_alibaba_reranking_capabilities,
        get_amazon_reranking_capabilities,
        get_baai_reranking_capabilities,
        get_cohere_reranking_capabilities,
        get_jinaai_reranking_capabilities,
        get_marco_reranking_capabilities,
        get_qwen_reranking_capabilities,
        get_voyage_reranking_capabilities,
        load_default_capabilities,
    )
    from codeweaver.providers.reranking.providers import (
        BedrockRerankingProvider,
        CohereRerankingProvider,
        FastEmbedRerankingProvider,
        QueryType,
        RerankingProvider,
        RerankingResult,
        SentenceTransformersRerankingProvider,
        VoyageRerankingProvider,
    )


type KnownRerankModelName = Literal[
    "voyage:voyage-rerank-2.5",
    "voyage:voyage-rerank-2.5-lite",
    "cohere:rerank-v3.5",
    "cohere:rerank-english-v3.0",
    "cohere:rerank-multilingual-v3.0",
    "bedrock:amazon.rerank-v1:0",
    "bedrock:cohere.rerank-v3-5:0",
    "fastembed:Xenova/ms-marco-MiniLM-L-6-v2",
    "fastembed:Xenova/ms-marco-MiniLM-L-12-v2",
    "fastembed:BAAI/bge-reranking-base",
    "fastembed:jinaai/jina-reranking-v2-base-multilingual",
    "sentence-transformers:Qwen/Qwen3-Reranking-0.6B",
    "sentence-transformers:Qwen/Qwen3-Reranking-4B",
    "sentence-transformers:Qwen/Qwen3-Reranking-8B",
    "sentence-transformers:mixedbread-ai/mxbai-rerank-large-v2",
    "sentence-transformers:mixedbread-ai/mxbai-rerank-base-v2",
    "sentence-transformers:jinaai/jina-reranking-m0",
    "sentence-transformers:BAAI/bge-reranking-v2-m3",
    "sentence-transformers:BAAI/bge-reranking-large",
    "sentence-transformers:cross-encoder/ms-marco-MiniLM-L6-v2",
    "sentence-transformers:cross-encoder/ms-marco-MiniLM-L12-v2",
    "sentence-transformers:Alibaba-NLP/gte-multilingual-reranking-base",
    "sentence-transformers:mixedbread-ai/mxbai-rerank-xsmall-v1",
    "sentence-transformers:mixedbread-ai/mxbai-rerank-base-v1",
]


def get_rerank_model_provider(provider: Provider) -> type[RerankingProvider[Any]]:
    """Get rerank model provider."""
    from codeweaver.providers.provider import Provider

    if provider in {Provider.VOYAGE}:
        from codeweaver.providers.reranking.providers.voyage import VoyageRerankingProvider

        return VoyageRerankingProvider  # type: ignore[return-value]

    if provider == Provider.COHERE:
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        return CohereRerankingProvider  # type: ignore[return-value]

    if provider == Provider.BEDROCK:
        from codeweaver.providers.reranking.providers.bedrock import BedrockRerankingProvider

        return BedrockRerankingProvider  # type: ignore[return-value]

    if provider == Provider.FASTEMBED:
        from codeweaver.providers.reranking.providers.fastembed import FastEmbedRerankingProvider

        return FastEmbedRerankingProvider  # type: ignore[return-value]

    if provider == Provider.SENTENCE_TRANSFORMERS:
        from codeweaver.providers.reranking.providers.sentence_transformers import (
            SentenceTransformersRerankingProvider,
        )

        return SentenceTransformersRerankingProvider

    # Get list of supported reranking providers dynamically
    supported_providers = [
        p.value
        for p in [
            Provider.VOYAGE,
            Provider.COHERE,
            Provider.BEDROCK,
            Provider.FASTEMBED,
            Provider.SENTENCE_TRANSFORMERS,
        ]
    ]

    raise ConfigurationError(
        f"Unknown reranking provider: {provider}",
        details={"provided_provider": str(provider), "supported_providers": supported_providers},
        suggestions=[
            "Check provider name spelling in configuration",
            "Install required reranking provider package",
            "Review available providers in documentation",
        ],
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "RerankingProvider": (__spec__.parent, "providers"),
    "VoyageRerankingProvider": (__spec__.parent, "providers"),
    "CohereRerankingProvider": (__spec__.parent, "providers"),
    "BedrockRerankingProvider": (__spec__.parent, "providers"),
    "FastEmbedRerankingProvider": (__spec__.parent, "providers"),
    "SentenceTransformersRerankingProvider": (__spec__.parent, "providers"),
    "QueryType": (__spec__.parent, "providers"),
    "RerankingResult": (__spec__.parent, "providers"),
    "dependency_map": (__spec__.parent, "capabilities"),
    "load_default_capabilities": (__spec__.parent, "capabilities"),
    "get_alibaba_reranking_capabilities": (__spec__.parent, "capabilities"),
    "get_amazon_reranking_capabilities": (__spec__.parent, "capabilities"),
    "get_baai_reranking_capabilities": (__spec__.parent, "capabilities"),
    "get_cohere_reranking_capabilities": (__spec__.parent, "capabilities"),
    "get_jinaai_reranking_capabilities": (__spec__.parent, "capabilities"),
    "get_marco_reranking_capabilities": (__spec__.parent, "capabilities"),
    "get_qwen_reranking_capabilities": (__spec__.parent, "capabilities"),
    "get_voyage_reranking_capabilities": (__spec__.parent, "capabilities"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the reranking providers package."""
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
    "BedrockRerankingProvider",
    "CohereRerankingProvider",
    "FastEmbedRerankingProvider",
    "KnownRerankModelName",
    "QueryType",
    "RerankingProvider",
    "RerankingResult",
    "SentenceTransformersRerankingProvider",
    "VoyageRerankingProvider",
    "dependency_map",
    "get_alibaba_reranking_capabilities",
    "get_amazon_reranking_capabilities",
    "get_baai_reranking_capabilities",
    "get_cohere_reranking_capabilities",
    "get_jinaai_reranking_capabilities",
    "get_marco_reranking_capabilities",
    "get_qwen_reranking_capabilities",
    "get_rerank_model_provider",
    "get_voyage_reranking_capabilities",
    "load_default_capabilities",
)


def __dir__() -> list[str]:
    """List available attributes in the reranking providers package."""
    return list(__all__)
