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

from typing import TYPE_CHECKING, Any, NoReturn

from codeweaver.agent_api.find_code.types import SearchStrategy, StrategizedQuery
from codeweaver.providers.embedding.types import QueryResult


if TYPE_CHECKING:
    from codeweaver.agent_api.find_code.results import SearchResult
    from codeweaver.providers.vector_stores.base import VectorStoreProvider


logger = logging.getLogger(__name__)

_query_: str | None = None


def raise_value_error(message: str) -> NoReturn:
    """Raise ValueError with message including current query."""
    global _query_
    q = _query_ if _query_ is not None else ""
    raise ValueError(f"{message} (query: '{q}')")


async def embed_query(query: str) -> QueryResult:
    """Embed query using configured embedding providers.

    Tries dense embedding first, then sparse. Returns result with whichever
    succeeded. If both fail, raises ValueError.

    Args:
        query: Natural language query to embed

    Returns:
        QueryResult with dense and/or sparse embeddings

    Raises:
        ValueError: If no embedding providers configured or both fail
    """
    from codeweaver.common.registry import get_provider_registry  # Lazy import
    from codeweaver.providers.embedding.types import QueryResult

    registry = get_provider_registry()
    global _query_
    _query_ = query.strip()
    dense_provider_enum = registry.get_provider_enum_for("embedding")
    sparse_provider_enum = registry.get_provider_enum_for("sparse_embedding")

    if not dense_provider_enum and not sparse_provider_enum:
        raise ValueError("No embedding providers configured (neither dense nor sparse)")

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
                    return raise_value_error(
                        "Dense embedding returned error and no sparse provider available"
                    )
            else:
                dense_query_embedding = result
        except Exception as e:
            logger.warning("Dense embedding failed: %s", e)
            if not sparse_provider_enum:
                return raise_value_error(f"Dense embedding failed: {e}")

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
                if not dense_query_embedding:
                    return raise_value_error(
                        "Sparse embedding returned error and dense embedding unavailable"
                    )
            else:
                sparse_query_embedding = result
        except Exception as e:
            logger.warning("Sparse embedding failed: %s", e)
            if not dense_query_embedding:
                return raise_value_error(f"Sparse embedding failed: {e}")

    # Return whatever we got (at least one must have succeeded)
    if dense_query_embedding is None and sparse_query_embedding is None:
        return raise_value_error("Both dense and sparse embedding failed")

    return QueryResult(dense=dense_query_embedding, sparse=sparse_query_embedding)


def build_query_vector(query_result: QueryResult, query: str) -> StrategizedQuery:
    """Build query vector for search from embeddings.

    Args:
        dense_embedding: Dense embedding vector (batch result from provider)
        sparse_embedding: Sparse embedding vector (batch result from provider)

    Returns:
        A StrategizedQuery containing sparse and/or dense vectors and the chosen strategy

    Raises:
        ValueError: If both embeddings are None
    """
    if query_result.dense:
        if query_result.sparse:
            return StrategizedQuery(
                query=query,
                dense=query_result.dense,
                sparse=query_result.sparse,
                strategy=SearchStrategy.HYBRID_SEARCH,
            )
        logger.warning("Using dense-only search (sparse embeddings unavailable)")
        # Unwrap batch results (take first element) and ensure float type
        return StrategizedQuery(
            query=query, dense=query_result.dense, sparse=None, strategy=SearchStrategy.DENSE_ONLY
        )
    if query_result.sparse:
        logger.warning("Using sparse-only search (dense embeddings unavailable - degraded mode)")
        # Unwrap batch results (take first element) and ensure float type
        return StrategizedQuery(
            query=query, dense=None, sparse=query_result.sparse, strategy=SearchStrategy.SPARSE_ONLY
        )
    # Both failed - should not reach here due to earlier validation
    raise ValueError("Both dense and sparse embeddings are None")


async def execute_vector_search(query_vector: StrategizedQuery) -> list[SearchResult]:
    """Execute vector search against configured vector store.

    Args:
        query_vector: Query vector (dense, sparse, or hybrid)

    Returns:
        List of search results from vector store

    Raises:
        ValueError: If no vector store provider configured
    """
    from codeweaver.common.registry import get_provider_registry  # Lazy import

    registry = get_provider_registry()
    vector_store_enum = registry.get_provider_enum_for("vector_store")
    if not vector_store_enum:
        raise_value_error("No vector store provider configured")

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
        query: Original search query
        candidates: Initial search results to rerank

    Returns:
        Tuple of (reranked_results, strategy) where:
        - reranked_results is None if reranking unavailable or fails
        - strategy is SEMANTIC_RERANK if successful, None otherwise
    """
    from codeweaver.common.registry import get_provider_registry  # Lazy import
    from codeweaver.core.chunks import CodeChunk

    registry = get_provider_registry()
    reranking_enum = registry.get_provider_enum_for("reranking")

    if not reranking_enum or not candidates:
        return None, None

    try:
        reranking = registry.get_provider_instance(reranking_enum, "reranking", singleton=True)
        chunks_for_reranking = [c.content for c in candidates if isinstance(c.content, CodeChunk)]

        if not chunks_for_reranking:
            logger.warning("No CodeChunk objects available for reranking, skipping")
            return None, None

        reranked_results = await reranking.rerank(query, chunks_for_reranking)
        logger.info("Reranked %d results", len(reranked_results) if reranked_results else 0)
        return reranked_results, SearchStrategy.SEMANTIC_RERANK

    except Exception as e:
        logger.warning("Reranking failed: %s, using unranked results", e)
        return None, None


__all__ = (
    "build_query_vector",
    "embed_query",
    "execute_vector_search",
    "raise_value_error",
    "rerank_results",
)
