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
from codeweaver.exceptions import ConfigurationError, QueryError
from codeweaver.providers.embedding.types import QueryResult, RawEmbeddingVectors, SparseEmbedding


if TYPE_CHECKING:
    from codeweaver.agent_api.find_code.results import SearchResult
    from codeweaver.providers.vector_stores.base import VectorStoreProvider


logger = logging.getLogger(__name__)

_query_: str | None = None


def raise_value_error(message: str) -> NoReturn:
    """Raise QueryError with message including current query."""
    global _query_
    q = _query_ if _query_ is not None else ""
    raise QueryError(
        f"{message}",
        details={"query": q},
        suggestions=[
            "Verify embedding provider configuration",
            "Check provider credentials and API keys",
            "Review query format and content",
        ],
    )


async def _embed_dense(
    query: str, dense_provider_enum: Any, context: Any
) -> RawEmbeddingVectors | None:
    """Attempt dense embedding, return None on failure."""
    from codeweaver.common.logging import log_to_client_or_fallback
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    try:
        dense_provider = registry.get_provider_instance(
            dense_provider_enum, "embedding", singleton=True
        )
        result = await dense_provider.embed_query(query)

        if isinstance(result, dict) and "error" in result:
            await log_to_client_or_fallback(
                context,
                "warning",
                {
                    "msg": "Dense embedding returned error",
                    "extra": {
                        "phase": "query_embedding",
                        "embedding_type": "dense",
                        "error": result.get("error"),
                    },
                },
            )
            return None

        await log_to_client_or_fallback(
            context,
            "debug",
            {
                "msg": "Dense embedding successful",
                "extra": {
                    "phase": "query_embedding",
                    "embedding_type": "dense",
                    "embedding_dim": len(result[0]) if result and len(result) > 0 else 0,
                },
            },
        )
    except Exception as e:
        await log_to_client_or_fallback(
            context,
            "warning",
            {
                "msg": "Dense embedding failed",
                "extra": {
                    "phase": "query_embedding",
                    "embedding_type": "dense",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            },
        )
        return None
    else:
        if not result:
            return None
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
            return result  # type: ignore[return-value]
        return [result]  # type: ignore[return-value]


async def _embed_sparse(
    query: str, sparse_provider_enum: Any, context: Any
) -> SparseEmbedding | None:
    """Attempt sparse embedding, return None on failure."""
    from codeweaver.common.logging import log_to_client_or_fallback
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    try:
        sparse_provider = registry.get_provider_instance(
            sparse_provider_enum, "sparse_embedding", singleton=True
        )
        result = await sparse_provider.embed_query(query)

        if isinstance(result, dict) and "error" in result:
            await log_to_client_or_fallback(
                context,
                "warning",
                {
                    "msg": "Sparse embedding returned error",
                    "extra": {
                        "phase": "query_embedding",
                        "embedding_type": "sparse",
                        "error": result.get("error"),
                    },
                },
            )
            return None

        await log_to_client_or_fallback(
            context,
            "debug",
            {
                "msg": "Sparse embedding successful",
                "extra": {"phase": "query_embedding", "embedding_type": "sparse"},
            },
        )
    except Exception as e:
        await log_to_client_or_fallback(
            context,
            "warning",
            {
                "msg": "Sparse embedding failed",
                "extra": {
                    "phase": "query_embedding",
                    "embedding_type": "sparse",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            },
        )
        return None
    else:
        if isinstance(result, SparseEmbedding):
            return result
        # Handle list[SparseEmbedding] from sparse provider's embed_query
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], SparseEmbedding):
            return result[0]
        if isinstance(result, dict) and "indices" in result and "values" in result:
            return SparseEmbedding(**result)
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            return SparseEmbedding(**result[0])
        if (
            isinstance(result, list)
            and len(result) == 2
            and isinstance(result[0], list)
            and isinstance(result[1], list)
        ):
            return SparseEmbedding(indices=result[0], values=result[1])  # ty: ignore[invalid-argument-type]
    return None


async def embed_query(query: str, context: Any = None) -> QueryResult:
    """Embed query using configured embedding providers.

    Tries dense embedding first, then sparse. Returns result with whichever
    succeeded. If both fail, raises ValueError.

    Args:
        query: Natural language query to embed
        context: Optional FastMCP context for structured logging

    Returns:
        QueryResult with dense and/or sparse embeddings

    Raises:
        ValueError: If no embedding providers configured or both fail
    """
    from codeweaver.common.logging import log_to_client_or_fallback
    from codeweaver.common.registry import get_provider_registry
    from codeweaver.providers.embedding.types import QueryResult

    registry = get_provider_registry()
    global _query_
    _query_ = query.strip()
    dense_provider_enum = registry.get_provider_enum_for("embedding")
    sparse_provider_enum = registry.get_provider_enum_for("sparse_embedding")

    await log_to_client_or_fallback(
        context,
        "info",
        {
            "msg": "Starting query embedding",
            "extra": {
                "phase": "query_embedding",
                "query_length": len(query),
                "dense_provider_available": dense_provider_enum is not None,
                "sparse_provider_available": sparse_provider_enum is not None,
            },
        },
    )

    if not dense_provider_enum and not sparse_provider_enum:
        await log_to_client_or_fallback(
            context,
            "error",
            {
                "msg": "No embedding providers configured",
                "extra": {"phase": "query_embedding", "error": "no_providers"},
            },
        )
        raise ConfigurationError(
            "No embedding providers configured",
            details={
                "dense_provider_available": False,
                "sparse_provider_available": False,
                "available_providers": ["voyage", "openai", "fastembed", "bm25"],
            },
            suggestions=[
                "Set VOYAGE_API_KEY environment variable for cloud embeddings",
                "Or configure local provider in codeweaver.toml: embedding_provider = 'fastembed'",
                "See docs: https://codeweaver.ai/config/providers",
            ],
        )

    # Attempt embeddings
    dense_query_embedding = None
    if dense_provider_enum:
        dense_query_embedding = await _embed_dense(query, dense_provider_enum, context)

    sparse_query_embedding = None
    if sparse_provider_enum:
        sparse_query_embedding = await _embed_sparse(query, sparse_provider_enum, context)

    # Validate at least one succeeded
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
        # Unwrap batch results (embed_query returns list[list[float]], we need list[float])
        dense_vector = (
            query_result.dense[0] if isinstance(query_result.dense[0], list) else query_result.dense
        )

        if query_result.sparse:
            return StrategizedQuery(
                query=query,
                dense=dense_vector,
                sparse=query_result.sparse,
                strategy=SearchStrategy.HYBRID_SEARCH,
            )
        logger.warning("Using dense-only search (sparse embeddings unavailable)")
        return StrategizedQuery(
            query=query, dense=dense_vector, sparse=None, strategy=SearchStrategy.DENSE_ONLY
        )
    if query_result.sparse:
        logger.warning("Using sparse-only search (dense embeddings unavailable - degraded mode)")
        # Unwrap batch results (take first element) and ensure float type
        return StrategizedQuery(
            query=query, dense=None, sparse=query_result.sparse, strategy=SearchStrategy.SPARSE_ONLY
        )
    # Both failed - should not reach here due to earlier validation
    raise QueryError(
        "Both dense and sparse embeddings are None",
        details={"dense_embedding": None, "sparse_embedding": None, "query": query},
        suggestions=[
            "Check embedding provider logs for errors",
            "Verify provider credentials are valid",
            "Try with a different embedding provider",
        ],
    )


async def execute_vector_search(
    query_vector: StrategizedQuery, context: Any = None
) -> list[SearchResult]:
    """Execute vector search against configured vector store.

    Args:
        query_vector: Query vector (dense, sparse, or hybrid)
        context: Optional FastMCP context for structured logging

    Returns:
        List of search results from vector store

    Raises:
        ValueError: If no vector store provider configured
    """
    from codeweaver.common.logging import log_to_client_or_fallback
    from codeweaver.common.registry import get_provider_registry  # Lazy import

    registry = get_provider_registry()
    vector_store_enum = registry.get_provider_enum_for("vector_store")

    await log_to_client_or_fallback(
        context,
        "info",
        {
            "msg": "Starting vector search",
            "extra": {
                "phase": "vector_search",
                "search_strategy": query_vector.strategy.variable,
                "has_dense": query_vector.dense is not None,
                "has_sparse": query_vector.sparse is not None,
            },
        },
    )

    if not vector_store_enum:
        await log_to_client_or_fallback(
            context,
            "error",
            {
                "msg": "No vector store provider configured",
                "extra": {"phase": "vector_search", "error": "no_provider"},
            },
        )
        raise ConfigurationError(
            "No vector store provider configured",
            details={"available_providers": ["qdrant", "in_memory"], "configured_provider": None},
            suggestions=[
                "Configure vector store in codeweaver.toml: vector_store_provider = 'qdrant'",
                "Or use in-memory provider for testing: vector_store_provider = 'in_memory'",
                "See docs: https://codeweaver.ai/config/vector-stores",
            ],
        )

    vector_store: VectorStoreProvider[Any] = registry.get_provider_instance(
        vector_store_enum, "vector_store", singleton=True
    )  # type: ignore

    # Execute search (returns max 100 results)
    # Note: Filter support deferred to v0.2 - we over-fetch and filter post-search
    results = await vector_store.search(vector=query_vector, query_filter=None)

    await log_to_client_or_fallback(
        context,
        "info",
        {
            "msg": "Vector search complete",
            "extra": {
                "phase": "vector_search",
                "results_count": len(results),
                "vector_store": type(vector_store).__name__,
            },
        },
    )

    return results


async def rerank_results(
    query: str, candidates: list[SearchResult], context: Any = None
) -> tuple[list[Any] | None, SearchStrategy | None]:
    """Rerank search results using configured reranking provider.

    Args:
        query: Original search query
        candidates: Initial search results to rerank
        context: Optional FastMCP context for structured logging

    Returns:
        Tuple of (reranked_results, strategy) where:
        - reranked_results is None if reranking unavailable or fails
        - strategy is SEMANTIC_RERANK if successful, None otherwise
    """
    from codeweaver.common.logging import log_to_client_or_fallback
    from codeweaver.common.registry import get_provider_registry  # Lazy import

    registry = get_provider_registry()
    reranking_enum = registry.get_provider_enum_for("reranking")

    if not reranking_enum or not candidates:
        await log_to_client_or_fallback(
            context,
            "debug",
            {
                "msg": "Reranking skipped",
                "extra": {
                    "phase": "reranking",
                    "reason": "no_candidates" if reranking_enum else "no_provider",
                    "candidates_count": len(candidates) if candidates else 0,
                },
            },
        )
        return None, None

    await log_to_client_or_fallback(
        context,
        "info",
        {
            "msg": "Starting reranking",
            "extra": {"phase": "reranking", "candidates_count": len(candidates)},
        },
    )

    try:
        reranking = registry.get_provider_instance(reranking_enum, "reranking", singleton=True)

        # Create mapping to preserve search metadata through reranking
        # Map chunk_id to SearchResult to lookup original scores after reranking
        metadata_map: dict[str, SearchResult] = {str(c.content.chunk_id): c for c in candidates}

        chunks_for_reranking = [c.content for c in candidates]

        if not chunks_for_reranking:
            logger.warning("No CodeChunk objects available for reranking, skipping")
            return None, None

        reranked_results = await reranking.rerank(query, chunks_for_reranking)

        # Enrich reranked results with preserved search metadata
        from codeweaver.providers.reranking.providers.base import RerankingResult

        enriched_results = [
            RerankingResult(
                original_index=r.original_index,
                batch_rank=r.batch_rank,
                score=r.score,
                chunk=r.chunk,
                original_score=metadata_map[str(r.chunk.chunk_id)].score
                if str(r.chunk.chunk_id) in metadata_map
                else None,
                dense_score=metadata_map[str(r.chunk.chunk_id)].dense_score
                if str(r.chunk.chunk_id) in metadata_map
                else None,
                sparse_score=metadata_map[str(r.chunk.chunk_id)].sparse_score
                if str(r.chunk.chunk_id) in metadata_map
                else None,
            )
            for r in reranked_results
        ]
        reranked_results = enriched_results

        await log_to_client_or_fallback(
            context,
            "info",
            {
                "msg": "Reranking complete",
                "extra": {
                    "phase": "reranking",
                    "reranked_count": len(reranked_results) if reranked_results else 0,
                },
            },
        )

    except Exception as e:
        await log_to_client_or_fallback(
            context,
            "warning",
            {
                "msg": "Reranking failed",
                "extra": {
                    "phase": "reranking",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "fallback": "using_unranked_results",
                },
            },
        )
        return None, None
    else:
        return list(reranked_results), SearchStrategy.SEMANTIC_RERANK


__all__ = (
    "build_query_vector",
    "embed_query",
    "execute_vector_search",
    "raise_value_error",
    "rerank_results",
)
