# SPDX-FileCopyrightText: 2026 Knitli Inc.
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
from typing import Any, NoReturn

from codeweaver.core import (
    ConfigurationError,
    QueryError,
    QueryResult,
    RawEmbeddingVectors,
    SearchResult,
    SearchStrategy,
    SparseEmbedding,
    StrategizedQuery,
)
from codeweaver.core.constants import ZERO
from codeweaver.core.di import INJECTED
from codeweaver.providers import (
    EmbeddingProviderDep,
    RerankingProviderDep,
    SparseEmbeddingProviderDep,
    VectorStoreProviderDep,
)


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
    query: str, dense_provider: EmbeddingProviderDep, context: Any
) -> RawEmbeddingVectors | None:
    """Attempt dense embedding, return None on failure."""
    from codeweaver.core import log_to_client_or_fallback

    try:
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
        assert not isinstance(result, dict)  # noqa: S101
        assert "error" not in result  # noqa: S101
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
            return result
        return [result]


async def _embed_sparse(
    query: str, context: Any, sparse_provider: SparseEmbeddingProviderDep = INJECTED
) -> SparseEmbedding | None:
    """Attempt sparse embedding, return None on failure."""
    from codeweaver.core import log_to_client_or_fallback

    try:
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
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], SparseEmbedding):
            return result[0]
        if isinstance(result, dict) and "indices" in result and ("values" in result):
            return SparseEmbedding(**result)
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            return SparseEmbedding(**result[0])
        if (
            isinstance(result, list)
            and len(result) == 2
            and isinstance(result[0], list)
            and isinstance(result[1], list)
        ):
            return SparseEmbedding(indices=result[0], values=result[1])
    return None


def _normalize_dense_embedding(embedding: Any) -> RawEmbeddingVectors | None:
    """Normalize dense embedding to list[list[float]] format.

    Args:
        embedding: Raw embedding from provider

    Returns:
        Normalized embedding or None if invalid
    """
    if not embedding:
        return None
    if isinstance(embedding, list) and len(embedding) > 0 and isinstance(embedding[0], list):
        return embedding
    return [embedding]


def _normalize_sparse_embedding(result: Any) -> SparseEmbedding | None:
    """Normalize sparse embedding result to SparseEmbedding format.

    Handles multiple provider return formats:
    - SparseEmbedding object
    - list[SparseEmbedding]
    - dict with indices/values
    - list[dict] with indices/values
    - list[list, list] tuple format

    Args:
        result: Raw result from sparse provider

    Returns:
        Normalized SparseEmbedding or None if invalid format
    """
    if isinstance(result, SparseEmbedding):
        return result
    if isinstance(result, list) and len(result) > 0:
        return _transform_to_sparse_embedding(result)
    if isinstance(result, dict) and "indices" in result and ("values" in result):
        return SparseEmbedding(**result)
    logger.warning("Unexpected sparse embedding format: %s", type(result))
    return None


def _transform_to_sparse_embedding(result):
    """Transform list result to SparseEmbedding."""
    item = result[0]
    if isinstance(item, SparseEmbedding):
        return item
    if isinstance(item, dict) and "indices" in item and ("values" in item):
        return SparseEmbedding(**item)
    if isinstance(item, list) and len(result) == 2 and isinstance(result[1], list):
        return SparseEmbedding(indices=result[0], values=result[1])
    logger.warning("Unexpected sparse embedding format in list: %s", type(item))
    return None


def _build_vectors_dict(
    dense_embedding: RawEmbeddingVectors | None, sparse_embedding: SparseEmbedding | None
) -> dict[str, Any]:
    """Build vectors dictionary from embeddings.

    Args:
        dense_embedding: Normalized dense embedding
        sparse_embedding: Normalized sparse embedding

    Returns:
        Dictionary with intent-based keys for available embeddings
    """
    vectors = {}
    if dense_embedding is not None:
        vectors["primary"] = dense_embedding
    if sparse_embedding is not None:
        vectors["sparse"] = sparse_embedding
    return vectors


async def embed_query(
    query: str,
    context: Any = None,
    dense_provider: EmbeddingProviderDep = INJECTED,
    sparse_provider: SparseEmbeddingProviderDep = INJECTED,
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
    from codeweaver.core import log_to_client_or_fallback

    _query_cv.set(query.strip())
    dense_query_embedding = None
    if dense_provider:
        try:
            raw_embedding = await dense_provider.embed_query(query)
            dense_query_embedding = _normalize_dense_embedding(raw_embedding)
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
    sparse_query_embedding = None
    if sparse_provider:
        try:
            result = await sparse_provider.embed_query(query)
            sparse_query_embedding = _normalize_sparse_embedding(result)
        except Exception as e:
            await log_to_client_or_fallback(
                context,
                "warning",
                {
                    "msg": "Sparse embedding failed",
                    "extra": {"phase": "query_embedding", "error": str(e)},
                },
            )
    if dense_query_embedding is None and sparse_query_embedding is None:
        return raise_value_error("Both dense and sparse embedding failed")
    vectors = _build_vectors_dict(dense_query_embedding, sparse_query_embedding)
    return QueryResult(vectors=vectors)


def build_query_vector(query_result: QueryResult, query: str) -> StrategizedQuery:
    """Build query vector for search from embeddings.

    Args:
        query_result: QueryResult containing embeddings keyed by intent
        query: Natural language query string

    Returns:
        A StrategizedQuery containing sparse and/or dense vectors and the chosen strategy

    Raises:
        ValueError: If both embeddings are None
    """
    dense_embedding_raw = query_result.get("primary")
    sparse_embedding_raw = query_result.get("sparse")
    dense_embedding: RawEmbeddingVectors | None = None
    if dense_embedding_raw is not None and (not isinstance(dense_embedding_raw, SparseEmbedding)):
        dense_embedding = dense_embedding_raw
    sparse_embedding: SparseEmbedding | None = None
    if sparse_embedding_raw is not None and isinstance(sparse_embedding_raw, SparseEmbedding):
        sparse_embedding = sparse_embedding_raw
    if dense_embedding:
        dense_vector: RawEmbeddingVectors = (
            dense_embedding[0] if isinstance(dense_embedding[0], list) else dense_embedding
        )
        if sparse_embedding:
            return StrategizedQuery(
                query=query,
                dense=dense_vector,
                sparse=sparse_embedding,
                strategy=SearchStrategy.HYBRID_SEARCH,
            )
        logger.warning("Using dense-only search (sparse embeddings unavailable)")
        return StrategizedQuery(
            query=query, dense=dense_vector, sparse=None, strategy=SearchStrategy.DENSE_ONLY
        )
    if sparse_embedding:
        logger.warning("Using sparse-only search (dense embeddings unavailable - degraded mode)")
        return StrategizedQuery(
            query=query, dense=None, sparse=sparse_embedding, strategy=SearchStrategy.SPARSE_ONLY
        )
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
    query_vector: StrategizedQuery,
    context: Any = None,
    vector_store: VectorStoreProviderDep = INJECTED,
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
    from codeweaver.core import log_to_client_or_fallback

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


async def _resolve_reranking_providers(
    reranking: tuple[RerankingProviderDep, ...] | RerankingProviderDep | None,
) -> tuple[RerankingProviderDep, ...]:
    """Resolve injected reranking provider(s) into a tuple of providers."""
    if reranking is None or hasattr(reranking, "__pydantic_serializer__"):
        try:
            from codeweaver.core import get_container
            from codeweaver.providers import RerankingProvider

            reranking = await get_container().resolve(RerankingProvider)
        except Exception as e:
            logger.warning("Failed to resolve reranking provider: %s", e)
            return ()
    if isinstance(reranking, tuple):
        return reranking
    return (reranking,) if reranking else ()


async def _try_rerank_with_provider(
    provider: RerankingProviderDep,
    idx: int,
    total_providers: int,
    query: str,
    chunks_for_reranking: list[Any],
    metadata_map: dict[str, SearchResult],
    context: Any,
) -> tuple[list[Any] | None, Exception | None]:
    """Attempt reranking with a single provider and return results or error."""
    from codeweaver.core import log_to_client_or_fallback
    from codeweaver.providers import RerankingResult
    from codeweaver.providers.exceptions import CircuitBreakerOpenError

    provider_name = type(provider).__name__
    try:
        await log_to_client_or_fallback(
            context,
            "debug",
            {
                "msg": f"Attempting reranking with provider {idx + 1}/{total_providers}",
                "extra": {
                    "phase": "reranking",
                    "provider_name": provider_name,
                    "provider_index": idx,
                },
            },
        )
        reranked_results = await provider.rerank(query, chunks_for_reranking)
        if not reranked_results:
            await log_to_client_or_fallback(
                context,
                "warning",
                {
                    "msg": f"Provider {provider_name} returned no results",
                    "extra": {
                        "phase": "reranking",
                        "provider_name": provider_name,
                        "provider_index": idx,
                        "trying_next": idx < total_providers - 1,
                    },
                },
            )
            return None, None

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
        await log_to_client_or_fallback(
            context,
            "info",
            {
                "msg": f"Reranking successful with {provider_name}",
                "extra": {
                    "phase": "reranking",
                    "provider_name": provider_name,
                    "provider_index": idx,
                    "reranked_count": len(enriched_results),
                    "used_fallback": idx > 0,
                },
            },
        )
        return list(enriched_results), None
    except CircuitBreakerOpenError as e:
        await log_to_client_or_fallback(
            context,
            "warning",
            {
                "msg": f"Provider {provider_name} circuit breaker open",
                "extra": {
                    "phase": "reranking",
                    "provider_name": provider_name,
                    "provider_index": idx,
                    "error_type": "CircuitBreakerOpen",
                    "trying_next": idx < total_providers - 1,
                },
            },
        )
        return None, e
    except Exception as e:
        await log_to_client_or_fallback(
            context,
            "warning",
            {
                "msg": f"Provider {provider_name} failed",
                "extra": {
                    "phase": "reranking",
                    "provider_name": provider_name,
                    "provider_index": idx,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "trying_next": idx < total_providers - 1,
                },
            },
        )
        return None, e


async def rerank_results(
    query: str,
    candidates: list[SearchResult],
    context: Any = None,
    reranking: tuple[RerankingProviderDep, ...] | RerankingProviderDep | None = INJECTED,
) -> tuple[list[Any] | None, SearchStrategy | None]:
    """Rerank search results using configured reranking provider(s) with cascading fallback."""
    from codeweaver.core import log_to_client_or_fallback

    providers = await _resolve_reranking_providers(reranking)
    if not providers or not candidates:
        await log_to_client_or_fallback(
            context,
            "debug",
            {
                "msg": "Reranking skipped",
                "extra": {
                    "phase": "reranking",
                    "reason": "no_candidates" if providers else "no_provider",
                    "candidates_count": len(candidates) if candidates else ZERO,
                },
            },
        )
        return (None, None)

    await log_to_client_or_fallback(
        context,
        "info",
        {
            "msg": "Starting reranking with fallback chain",
            "extra": {
                "phase": "reranking",
                "candidates_count": len(candidates),
                "provider_count": len(providers),
            },
        },
    )

    metadata_map: dict[str, SearchResult] = {str(c.content.chunk_id): c for c in candidates}
    chunks_for_reranking = [c.content for c in candidates]
    if not chunks_for_reranking:
        logger.warning("No CodeChunk objects available for reranking, skipping")
        return (None, None)

    last_error: Exception | None = None
    for idx, provider in enumerate(providers):
        enriched_results, error = await _try_rerank_with_provider(
            provider, idx, len(providers), query, chunks_for_reranking, metadata_map, context
        )
        if enriched_results is not None:
            return (enriched_results, SearchStrategy.SEMANTIC_RERANK)
        if error is not None:
            last_error = error

    await log_to_client_or_fallback(
        context,
        "warning",
        {
            "msg": "All reranking providers failed",
            "extra": {
                "phase": "reranking",
                "provider_count": len(providers),
                "fallback": "using_unranked_results",
                "last_error": str(last_error) if last_error else "no_results",
                "last_error_type": type(last_error).__name__ if last_error else None,
            },
        },
    )
    return (None, None)


__all__ = (
    "_build_vectors_dict",
    "_normalize_dense_embedding",
    "_normalize_sparse_embedding",
    "build_query_vector",
    "embed_query",
    "execute_vector_search",
    "raise_value_error",
    "rerank_results",
)
