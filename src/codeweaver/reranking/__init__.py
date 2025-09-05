# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Base class for reranking providers."""

from typing import Literal

from codeweaver.provider import Provider
from codeweaver.reranking.providers.base import RerankingProvider


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


def get_rerank_model_provider(provider: Provider) -> type[RerankingProvider]:
    """Get rerank model provider."""
    if provider in {Provider.VOYAGE}:
        from codeweaver.reranking.providers.voyage import VoyageRerankingProvider

        return VoyageRerankingProvider  # type: ignore[return-value]

    if provider == Provider.COHERE:
        from codeweaver.reranking.providers.cohere import CohereRerankingProvider

        return CohereRerankingProvider  # type: ignore[return-value]

    if provider == Provider.BEDROCK:
        from codeweaver.reranking.providers.bedrock import BedrockRerankingProvider

        return BedrockRerankingProvider  # type: ignore[return-value]

    if provider == Provider.FASTEMBED:
        from codeweaver.reranking.providers.fastembed import FastEmbedRerankingProvider

        return FastEmbedRerankingProvider  # type: ignore[return-value]

    if provider == Provider.SENTENCE_TRANSFORMERS:
        from codeweaver.reranking.providers.sentence_transformers import (
            SentenceTransformersRerankingProvider,
        )

        return SentenceTransformersRerankingProvider
    raise ValueError(f"Unknown reranking provider: {provider}")


__all__ = ("KnownRerankModelName", "RerankingProvider")
