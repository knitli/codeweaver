# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Search pipeline orchestration.

This module handles the core search pipeline including:
- Query embedding (dense and sparse)
- Vector store search
- Reranking (when provider available)
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING, Any

from codeweaver.agent_api.models import SearchStrategy
from codeweaver.common.registry import get_provider_registry
from codeweaver.core.chunks import CodeChunk, SearchResult


if TYPE_CHECKING:
    from codeweaver.providers.vector_stores.base import VectorStoreProvider


logger = logging.getLogger(__name__)


def raise_value_error(message: str) -> None:
    """Helper function to raise ValueError with a message."""
    raise ValueError(message)


async def embed_query(query: str) -> tuple[list[float] | None, list[float] | None]:
    """Embed query using configured embedding providers.

    Args:
        query: Natural language query string

    Returns:
        Tuple of (dense_embedding, sparse_embedding), either can be None

    Raises:
        ValueError: If no embedding providers configured or both fail
    """
    registry = get_provider_registry()

    dense_provider_enum = registry.get_provider_enum_for("embedding")
    sparse_provider_enum = registry.get_provider_enum_for("sparse_embedding")

    if not dense_provider_enum and not sparse_provider_enum:
        raise_value_error("No embedding providers configured (neither dense nor sparse)")

    # Dense embedding
    dense_query_embedding = None
    if dense_provider_enum:
        try:
            dense_provider = registry.get_provider_instance(
                dense_provider_enum, "embedding", singleton=True
            )
            result = await dense_provider.embed_query(query)
            # Check for embedding error
            if isinstance(result, dict) and "error" in result:
                logger.warning("Dense embedding returned error: %s", result.get("error"))
                if not sparse_provider_enum:
                    raise_value_error(
                        f"Dense embedding failed: {result.get('error')} (no sparse fallback)"
                    )
            else:
                dense_query_embedding = result
        except Exception as e:
            logger.warning("Dense embedding failed: %s", e)
            if not sparse_provider_enum:
                # No fallback available - must fail
                raise ValueError("Dense embedding failed and no sparse provider available") from e

    # Sparse embedding
    sparse_query_embedding = None
    if sparse_provider_enum:
        try:
            sparse_provider = registry.get_provider_instance(
                sparse_provider_enum, "sparse_embedding", singleton=True
            )
            result = await sparse_provider.embed_query(query)
            # Check for embedding error
            if isinstance(result, dict) and "error" in result:
                logger.warning("Sparse embedding returned error: %s", result.get("error"))
            else:
                sparse_query_embedding = result
        except Exception as e:
            logger.warning("Sparse embedding failed, continuing with dense only: %s", e)

    return dense_query_embedding, sparse_query_embedding


def build_query_vector(
    dense_embedding: list[float] | None, sparse_embedding: list[float] | None
) -> tuple[list[float] | dict[str, list[float] | Any], SearchStrategy]:
    """Build query vector for search from embeddings.

    Args:
        dense_embedding: Dense embedding vector (batch result from provider)
        sparse_embedding: Sparse embedding vector (batch result from provider)

    Returns:
        Tuple of (query_vector, strategy) where query_vector can be:
        - list[float] for dense-only search
        - dict with 'dense' and 'sparse' keys for hybrid search
        - dict with 'sparse' key only for sparse-only search

    Raises:
        ValueError: If both embeddings are None
    """
    # Build query vector (unified search API) with graceful degradation
    # Note: embed_query returns list[list[float|int]] (batch results), unwrap to list[float]
    if dense_embedding and sparse_embedding:
        # Unwrap batch results (take first element) and ensure float type
        dense_vec: list[float] = [float(x) for x in dense_embedding[0]]
        sparse_vec: list[float] = [float(x) for x in sparse_embedding[0]]
        return {"dense": dense_vec, "sparse": sparse_vec}, SearchStrategy.HYBRID_SEARCH
    elif dense_embedding:
        logger.warning("Using dense-only search (sparse embeddings unavailable)")
        # Unwrap batch results (take first element) and ensure float type
        query_vector: list[float] = [float(x) for x in dense_embedding[0]]
        return query_vector, SearchStrategy.DENSE_ONLY
    elif sparse_embedding:
        logger.warning(
            "Using sparse-only search (dense embeddings unavailable - degraded mode)"
        )
        # Unwrap batch results (take first element) and ensure float type
        sparse_vec_unwrapped: list[float] = [float(x) for x in sparse_embedding[0]]
        return {"sparse": sparse_vec_unwrapped}, SearchStrategy.SPARSE_ONLY
    else:
        # Both failed - should not reach here due to earlier validation
        raise_value_error("Both dense and sparse embeddings failed")


async def execute_vector_search(
    query_vector: list[float] | dict[str, list[float] | Any],
) -> list[SearchResult]:
    """Execute vector search using configured vector store.

    Args:
        query_vector: Query vector (dense, sparse, or hybrid)

    Returns:
        List of search results from vector store

    Raises:
        ValueError: If no vector store provider configured
    """
    registry = get_provider_registry()
    vector_store_enum = registry.get_provider_enum_for("vector_store")
    if not vector_store_enum:
        raise_value_error("No vector store provider configured")
    assert isinstance(vector_store_enum, type)  # noqa: S101

    vector_store: VectorStoreProvider[Any] = registry.get_provider_instance(
        vector_store_enum, "vector_store", singleton=True
    )  # type: ignore

    # Execute search (returns max 100 results)
    # Note: Filter support deferred to v0.2 - we over-fetch and filter post-search
    return await vector_store.search(vector=query_vector, query_filter=None)


async def rerank_results(
    query: str, candidates: list[SearchResult]
) -> tuple[list[Any] | None, SearchStrategy | None]:
    """Rerank search results using configured reranking provider.

    Args:
        query: Original query string
        candidates: Search results to rerank

    Returns:
        Tuple of (reranked_results, strategy) where:
        - reranked_results is None if reranking unavailable or fails
        - strategy is SEMANTIC_RERANK if successful, None otherwise
    """
    registry = get_provider_registry()
    reranking_enum = registry.get_provider_enum_for("reranking")

    if not reranking_enum or not candidates:
        return None, None

    try:
        reranking = registry.get_provider_instance(reranking_enum, "reranking", singleton=True)
        chunks_for_reranking = [
            c.content for c in candidates if isinstance(c.content, CodeChunk)
        ]

        if not chunks_for_reranking:
            logger.warning("No CodeChunk objects available for reranking, skipping")
            return None, None

        reranked_results = await reranking.rerank(query, chunks_for_reranking)
        logger.info("Reranked to %d candidates", len(reranked_results))
        return reranked_results, SearchStrategy.SEMANTIC_RERANK

    except Exception as e:
        logger.warning("Reranking failed, continuing without: %s", e)
        return None, None


__all__ = (
    "embed_query",
    "build_query_vector",
    "execute_vector_search",
    "rerank_results",
    "raise_value_error",
)
