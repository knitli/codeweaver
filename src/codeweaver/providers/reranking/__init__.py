# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Base class for reranking providers."""

from typing import Any, Literal

from codeweaver.providers.provider import Provider
from codeweaver.providers.reranking.capabilities import dependency_map, load_default_capabilities
from codeweaver.providers.reranking.providers.base import RerankingProvider


# TODO: Implement the same system we have for Embedding models

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
    "fastembed:BAAI/bge-reranker-base",
    "fastembed:jinaai/jina-reranker-v2-base-multilingual",
    "sentence-transformers:Qwen/Qwen3-Reranker-0.6B",
    "sentence-transformers:Qwen/Qwen3-Reranker-4B",
    "sentence-transformers:Qwen/Qwen3-Reranker-8B",
    "sentence-transformers:mixedbread-ai/mxbai-rerank-large-v2",
    "sentence-transformers:mixedbread-ai/mxbai-rerank-base-v2",
    "sentence-transformers:jinaai/jina-reranker-m0",
    "sentence-transformers:BAAI/bge-reranker-v2-m3",
    "sentence-transformers:BAAI/bge-reranker-large",
    "sentence-transformers:cross-encoder/ms-marco-MiniLM-L6-v2",
    "sentence-transformers:cross-encoder/ms-marco-MiniLM-L12-v2",
    "sentence-transformers:Alibaba-NLP/gte-multilingual-reranker-base",
    "sentence-transformers:mixedbread-ai/mxbai-rerank-xsmall-v1",
    "sentence-transformers:mixedbread-ai/mxbai-rerank-base-v1",
]


def get_rerank_model_provider(provider: Provider) -> type[RerankingProvider[Any]]:
    """Get rerank model provider."""
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
    raise ValueError(f"Unknown reranking provider: {provider}")


__all__ = (
    "KnownRerankModelName",
    "RerankingProvider",
    "dependency_map",
    "get_rerank_model_provider",
    "load_default_capabilities",
)
