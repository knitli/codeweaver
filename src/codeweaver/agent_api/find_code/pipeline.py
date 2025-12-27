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

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, NoReturn

from codeweaver.core.types.search import SearchStrategy, StrategizedQuery
from codeweaver.di.providers import EmbeddingDep, RerankingDep, SparseEmbeddingDep, VectorStoreDep
from codeweaver.exceptions import ConfigurationError, QueryError
from codeweaver.providers.embedding.types import QueryResult, RawEmbeddingVectors, SparseEmbedding


if TYPE_CHECKING:
    from codeweaver.core.types.search import SearchResult


logger = logging.getLogger(__name__)

_query_cv: ContextVar[str | None] = ContextVar("_query_cv", default=None)


def raise_value_error(message: str) -> NoReturn:
    """Raise QueryError with message including current query."""
    q = _query_cv.get() or ""
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
    from codeweaver.common._logging import log_to_client_or_fallback
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
    from codeweaver.common._logging import log_to_client_or_fallback
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


async def embed_query(
    query: str,
    context: Any = None,
    dense_provider: EmbeddingDep | None = None,
    sparse_provider: SparseEmbeddingDep | None = None,
) -> QueryResult:
    """Embed query using configured embedding providers.

    Tries dense embedding first, then sparse. Returns result with whichever
    succeeded. If both fail, raises ValueError.

    Args:
        query: Natural language query to embed
        context: Optional FastMCP context for structured logging
        dense_provider: Injected dense embedding provider
        sparse_provider: Injected sparse embedding provider

    Returns:
        QueryResult with dense and/or sparse embeddings

    Raises:
        ValueError: If no embedding providers configured or both fail
    """
    from codeweaver.common._logging import log_to_client_or_fallback
    from codeweaver.providers.embedding.types import QueryResult

    _query_cv.set(query.strip())

    # Manually resolve providers if not injected (DI fallback)
    from codeweaver.di import get_container
    from codeweaver.providers.embedding.providers.base import EmbeddingProvider

    container = get_container()

    if dense_provider is None or hasattr(
        dense_provider, "__pydantic_serializer__"
    ):  # Handle sentinel
        try:
            dense_provider = await container.resolve(EmbeddingProvider)
        except Exception as e:
            logger.warning("Failed to resolve dense provider: %s", e)
            dense_provider = None

    if sparse_provider is None or hasattr(sparse_provider, "__pydantic_serializer__"):
        try:
            from codeweaver.providers.embedding.providers.base import SparseEmbeddingProvider

            sparse_provider = await container.resolve(SparseEmbeddingProvider)
        except Exception:
            sparse_provider = None

    await log_to_client_or_fallback(
        context,
        "info",
        {
            "msg": "Starting query embedding",
            "extra": {
                "phase": "query_embedding",
                "query_length": len(query),
                "dense_provider_available": dense_provider is not None,
                "sparse_provider_available": sparse_provider is not None,
            },
        },
    )

    # Attempt embeddings
    dense_query_embedding = None
    if dense_provider:
        try:
            dense_query_embedding = await dense_provider.embed_query(query)
            if (
                isinstance(dense_query_embedding, list)
                and len(dense_query_embedding) > 0
                and isinstance(dense_query_embedding[0], list)
            ):
                pass
            elif dense_query_embedding:
                dense_query_embedding = [dense_query_embedding]
        except Exception as e:
            await log_to_client_or_fallback(
                context,
                "warning",
                {
                    "msg": "Dense embedding failed",
                    "extra": {
                        "phase": "query_embedding",
                        "error": str(e),
                        "fallback": "attempting_sparse" if sparse_provider else "none",
                    },
                },
            )
            dense_query_embedding = None

    sparse_query_embedding = None
    if sparse_provider:
        try:
            sparse_query_embedding = await sparse_provider.embed_query(query)
        except Exception as e:
            await log_to_client_or_fallback(
                context,
                "warning",
                {
                    "msg": "Sparse embedding failed",
                    "extra": {"phase": "query_embedding", "error": str(e)},
                },
            )
            sparse_query_embedding = None

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
    query_vector: StrategizedQuery, context: Any = None, vector_store: VectorStoreDep | None = None
) -> list[SearchResult]:
    """Execute vector search against configured vector store.

    Args:
        query_vector: Query vector (dense, sparse, or hybrid)
        context: Optional FastMCP context for structured logging
        vector_store: Injected vector store instance

    Returns:
        List of search results from vector store

    Raises:
        ValueError: If no vector store provider configured
    """
    from codeweaver.common._logging import log_to_client_or_fallback

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

    if vector_store is None:
        raise ConfigurationError("No vector store provider configured")

    # Execute search (returns max 100 results)
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
    query: str,
    candidates: list[SearchResult],
    context: Any = None,
    reranking: RerankingDep | None = None,
) -> tuple[list[Any] | None, SearchStrategy | None]:
    """Rerank search results using configured reranking provider.

    Args:
        query: Original search query
        candidates: Initial search results to rerank
        context: Optional FastMCP context for structured logging
        reranking: Injected reranking provider

    Returns:
        Tuple of (reranked_results, strategy) where:
        - reranked_results is None if reranking unavailable or fails
        - strategy is SEMANTIC_RERANK if successful, None otherwise
    """
    from codeweaver.common._logging import log_to_client_or_fallback

    # Manually resolve provider if not injected (DI fallback)
    if reranking is None or hasattr(reranking, "__pydantic_serializer__"):
        try:
            from codeweaver.di import get_container
            from codeweaver.providers.reranking.providers.base import RerankingProvider

            reranking = await get_container().resolve(RerankingProvider)
        except Exception:
            reranking = None

    if not reranking or not candidates:
        await log_to_client_or_fallback(
            context,
            "debug",
            {
                "msg": "Reranking skipped",
                "extra": {
                    "phase": "reranking",
                    "reason": "no_candidates" if reranking else "no_provider",
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
        # Create mapping to preserve search metadata through reranking
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
