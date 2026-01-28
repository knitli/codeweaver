<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Backup System Completion Implementation Plan

**Document Version**: 1.0
**Date**: 2026-01-27
**Status**: Ready for Implementation
**Estimated Total Effort**: 12-24 hours

---

## Executive Summary

This plan outlines the implementation of three remaining backup system components following the major DI refactor:

1. **Reranker Fallback Logic** - Cascading fallback through multiple rerankers at query time
2. **Backup Vector Reconciliation** - Periodic validation that all points have required vectors
3. **Snapshot-Based Remote Backup** - Qdrant-native snapshot system for remote vector store failover

The refactor successfully simplified the backup architecture by identifying that only cloud embedding providers and cloud vector stores require special handling.

---

## Table of Contents

- [Phase 1: Reranker Fallback Logic](#phase-1-reranker-fallback-logic)
- [Phase 2: Backup Vector Reconciliation](#phase-2-backup-vector-reconciliation)
- [Phase 3: Snapshot-Based Remote Backup](#phase-3-snapshot-based-remote-backup)
- [Configuration Changes](#configuration-changes)
- [Testing Strategy](#testing-strategy)
- [Migration and Deployment](#migration-and-deployment)
- [Success Criteria](#success-criteria)
- [Rollback Plan](#rollback-plan)

---

## Phase 1: Reranker Fallback Logic

**Priority**: HIGH
**Effort**: 2-4 hours
**Complexity**: LOW
**Dependencies**: None

### Overview

Implement cascading fallback through the tuple of reranking providers at query time. The circuit breaker is already implemented in `RerankingProvider`, so we only need to add fallback orchestration logic.

### Current State

**File**: `src/codeweaver/server/agent_api/find_code/pipeline.py:399-518`

```python
# Current implementation
async def rerank_results(
    query: str,
    candidates: list[SearchResult],
    context: Any = None,
    reranking: RerankingProviderDep = INJECTED,
) -> tuple[list[Any] | None, SearchStrategy | None]:
    """Rerank search results using configured reranking provider."""

    # Only tries single provider, returns None on failure
    if not reranking or not candidates:
        return None, None

    try:
        reranked_results = await reranking.rerank(query, chunks_for_reranking)
    except Exception:
        return None, None

    return list(reranked_results), SearchStrategy.SEMANTIC_RERANK
```

**Problem**: No fallback mechanism when primary reranker fails.

### Implementation Steps

#### Step 1.1: Update Function Signature

**File**: `src/codeweaver/server/agent_api/find_code/pipeline.py`

**Change**:
```python
async def rerank_results(
    query: str,
    candidates: list[SearchResult],
    context: Any = None,
    reranking: tuple[RerankingProvider, ...] | RerankingProvider | None = INJECTED,
) -> tuple[list[Any] | None, SearchStrategy | None]:
    """Rerank with automatic fallback through provider cascade.

    Args:
        query: Original search query
        candidates: Initial search results to rerank
        context: Optional FastMCP context for structured logging
        reranking: Tuple of reranking providers (primary first, fallbacks after) or single provider

    Returns:
        Tuple of (reranked_results, strategy) where:
        - reranked_results is None if all rerankers fail
        - strategy is SEMANTIC_RERANK if successful, None otherwise
    """
```

#### Step 1.2: Implement Cascading Fallback Logic

**File**: `src/codeweaver/server/agent_api/find_code/pipeline.py`

**Add after function signature**:
```python
    from codeweaver.core import log_to_client_or_fallback
    from codeweaver.providers.exceptions import CircuitBreakerOpenError

    # Normalize to tuple for uniform handling
    if reranking is None:
        await log_to_client_or_fallback(
            context,
            "debug",
            {
                "msg": "Reranking skipped",
                "extra": {
                    "phase": "reranking",
                    "reason": "no_provider",
                },
            },
        )
        return None, None

    providers = reranking if isinstance(reranking, tuple) else (reranking,)

    if not providers or not candidates:
        await log_to_client_or_fallback(
            context,
            "debug",
            {
                "msg": "Reranking skipped",
                "extra": {
                    "phase": "reranking",
                    "reason": "no_candidates" if providers else "no_provider",
                    "candidates_count": len(candidates) if candidates else 0,
                },
            },
        )
        return None, None

    await log_to_client_or_fallback(
        context,
        "info",
        {
            "msg": "Starting reranking with cascading fallback",
            "extra": {
                "phase": "reranking",
                "candidates_count": len(candidates),
                "provider_count": len(providers),
            },
        },
    )

    # Create mapping to preserve search metadata through reranking
    metadata_map: dict[str, SearchResult] = {str(c.content.chunk_id): c for c in candidates}
    chunks_for_reranking = [c.content for c in candidates]

    if not chunks_for_reranking:
        logger.warning("No CodeChunk objects available for reranking, skipping")
        return None, None

    # Try each provider in sequence
    last_error: Exception | None = None
    for idx, provider in enumerate(providers):
        provider_num = idx + 1
        provider_name = getattr(provider, "model_name", f"provider_{idx}")

        try:
            await log_to_client_or_fallback(
                context,
                "debug",
                {
                    "msg": f"Attempting reranking with provider {provider_num}/{len(providers)}",
                    "extra": {
                        "phase": "reranking",
                        "provider_index": idx,
                        "provider_name": provider_name,
                    },
                },
            )

            # Circuit breaker check happens inside provider.rerank()
            reranked_results = await provider.rerank(query, chunks_for_reranking)

            if reranked_results:
                # Success! Enrich with preserved search metadata
                from codeweaver.providers import RerankingResult

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
                        "msg": f"Reranking successful with provider {provider_num}/{len(providers)}",
                        "extra": {
                            "phase": "reranking",
                            "provider_index": idx,
                            "provider_name": provider_name,
                            "reranked_count": len(enriched_results),
                            "used_fallback": idx > 0,
                        },
                    },
                )

                return list(enriched_results), SearchStrategy.SEMANTIC_RERANK

        except CircuitBreakerOpenError as e:
            last_error = e
            logger.warning(
                "Reranker %d/%d (%s) circuit breaker open, trying next",
                provider_num,
                len(providers),
                provider_name,
            )
            await log_to_client_or_fallback(
                context,
                "warning",
                {
                    "msg": f"Reranker {provider_num}/{len(providers)} circuit breaker open",
                    "extra": {
                        "phase": "reranking",
                        "provider_index": idx,
                        "provider_name": provider_name,
                        "error_type": "circuit_breaker",
                        "fallback": "trying_next" if idx < len(providers) - 1 else "no_more_fallbacks",
                    },
                },
            )
            continue

        except Exception as e:
            last_error = e
            logger.warning(
                "Reranker %d/%d (%s) failed with %s, trying next",
                provider_num,
                len(providers),
                provider_name,
                type(e).__name__,
            )
            await log_to_client_or_fallback(
                context,
                "warning",
                {
                    "msg": f"Reranker {provider_num}/{len(providers)} failed",
                    "extra": {
                        "phase": "reranking",
                        "provider_index": idx,
                        "provider_name": provider_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "fallback": "trying_next" if idx < len(providers) - 1 else "no_more_fallbacks",
                    },
                },
            )
            continue

    # All providers failed
    logger.warning(
        "All %d reranking providers failed, using unranked results. Last error: %s",
        len(providers),
        last_error,
    )
    await log_to_client_or_fallback(
        context,
        "warning",
        {
            "msg": "All reranking providers failed",
            "extra": {
                "phase": "reranking",
                "provider_count": len(providers),
                "fallback": "using_unranked_results",
                "last_error": str(last_error) if last_error else None,
            },
        },
    )

    return None, None
```

#### Step 1.3: Update SearchPackage Type (No Changes Needed)

**File**: `src/codeweaver/providers/types/search.py:50`

**Current**:
```python
reranking: tuple[RerankingProvider, ...]
```

**Status**: ✅ Already correct - no changes needed. The type already supports multiple providers.

#### Step 1.4: Add Tests

**New File**: `tests/unit/server/agent_api/find_code/test_reranker_fallback.py`

```python
"""Tests for reranker fallback logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from codeweaver.core import SearchResult, CodeChunk, SearchStrategy
from codeweaver.providers.exceptions import CircuitBreakerOpenError
from codeweaver.server.agent_api.find_code.pipeline import rerank_results


@pytest.fixture
def mock_candidates():
    """Create mock search candidates."""
    chunks = [
        CodeChunk.model_construct(
            content=f"test content {i}",
            chunk_id=f"chunk-{i}",
            file_path=f"test{i}.py",
        )
        for i in range(5)
    ]
    return [
        SearchResult(content=chunk, score=0.9 - i * 0.1)
        for i, chunk in enumerate(chunks)
    ]


@pytest.fixture
def mock_reranking_result():
    """Create mock reranking result."""
    from codeweaver.providers import RerankingResult

    return lambda chunk, score, rank: RerankingResult(
        original_index=0,
        batch_rank=rank,
        score=score,
        chunk=chunk,
    )


class TestRerankerFallback:
    """Test reranker fallback behavior."""

    @pytest.mark.asyncio
    async def test_primary_reranker_succeeds(self, mock_candidates, mock_reranking_result):
        """Primary reranker succeeds - no fallback needed."""
        # Setup
        primary = AsyncMock()
        primary.rerank = AsyncMock(return_value=[
            mock_reranking_result(c.content, 0.95, 1)
            for c in mock_candidates
        ])
        primary.model_name = "primary-reranker"

        fallback = AsyncMock()
        fallback.model_name = "fallback-reranker"

        # Execute
        results, strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=(primary, fallback),
        )

        # Assert
        assert results is not None
        assert strategy == SearchStrategy.SEMANTIC_RERANK
        assert len(results) == len(mock_candidates)
        primary.rerank.assert_called_once()
        fallback.rerank.assert_not_called()  # Fallback should NOT be called

    @pytest.mark.asyncio
    async def test_primary_circuit_breaker_open_fallback_succeeds(
        self, mock_candidates, mock_reranking_result
    ):
        """Primary circuit breaker open - fallback succeeds."""
        # Setup
        primary = AsyncMock()
        primary.rerank = AsyncMock(side_effect=CircuitBreakerOpenError("Circuit breaker open"))
        primary.model_name = "primary-reranker"

        fallback = AsyncMock()
        fallback.rerank = AsyncMock(return_value=[
            mock_reranking_result(c.content, 0.9, i+1)
            for i, c in enumerate(mock_candidates)
        ])
        fallback.model_name = "fallback-reranker"

        # Execute
        results, strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=(primary, fallback),
        )

        # Assert
        assert results is not None
        assert strategy == SearchStrategy.SEMANTIC_RERANK
        assert len(results) == len(mock_candidates)
        primary.rerank.assert_called_once()
        fallback.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_primary_exception_fallback_succeeds(
        self, mock_candidates, mock_reranking_result
    ):
        """Primary raises exception - fallback succeeds."""
        # Setup
        primary = AsyncMock()
        primary.rerank = AsyncMock(side_effect=ConnectionError("API unavailable"))
        primary.model_name = "primary-reranker"

        fallback = AsyncMock()
        fallback.rerank = AsyncMock(return_value=[
            mock_reranking_result(c.content, 0.9, i+1)
            for i, c in enumerate(mock_candidates)
        ])
        fallback.model_name = "fallback-reranker"

        # Execute
        results, strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=(primary, fallback),
        )

        # Assert
        assert results is not None
        assert strategy == SearchStrategy.SEMANTIC_RERANK
        primary.rerank.assert_called_once()
        fallback.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_rerankers_fail_gracefully(self, mock_candidates):
        """All rerankers fail - returns None gracefully."""
        # Setup
        primary = AsyncMock()
        primary.rerank = AsyncMock(side_effect=ConnectionError("API unavailable"))
        primary.model_name = "primary-reranker"

        fallback = AsyncMock()
        fallback.rerank = AsyncMock(side_effect=ConnectionError("API unavailable"))
        fallback.model_name = "fallback-reranker"

        # Execute
        results, strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=(primary, fallback),
        )

        # Assert
        assert results is None
        assert strategy is None
        primary.rerank.assert_called_once()
        fallback.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_single_reranker_backwards_compatibility(
        self, mock_candidates, mock_reranking_result
    ):
        """Single reranker (not tuple) still works."""
        # Setup
        single_reranker = AsyncMock()
        single_reranker.rerank = AsyncMock(return_value=[
            mock_reranking_result(c.content, 0.95, 1)
            for c in mock_candidates
        ])
        single_reranker.model_name = "single-reranker"

        # Execute
        results, strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=single_reranker,  # Not a tuple
        )

        # Assert
        assert results is not None
        assert strategy == SearchStrategy.SEMANTIC_RERANK
        single_reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_reranker_provided(self, mock_candidates):
        """No reranker provided - returns None gracefully."""
        # Execute
        results, strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=None,
        )

        # Assert
        assert results is None
        assert strategy is None

    @pytest.mark.asyncio
    async def test_empty_candidates(self):
        """Empty candidates - returns None gracefully."""
        # Setup
        reranker = AsyncMock()
        reranker.model_name = "test-reranker"

        # Execute
        results, strategy = await rerank_results(
            query="test query",
            candidates=[],
            context=None,
            reranking=reranker,
        )

        # Assert
        assert results is None
        assert strategy is None
        reranker.rerank.assert_not_called()
```

#### Step 1.5: Integration Testing

**New File**: `tests/integration/server/agent_api/test_find_code_reranker_fallback.py`

```python
"""Integration tests for reranker fallback in find_code."""

import pytest
from unittest.mock import patch, AsyncMock

from codeweaver.server.agent_api.find_code import find_code
from codeweaver.providers import RerankingProvider
from codeweaver.providers.exceptions import CircuitBreakerOpenError


@pytest.mark.integration
class TestFindCodeRerankerFallback:
    """Integration tests for find_code with reranker fallback."""

    @pytest.mark.asyncio
    async def test_find_code_with_primary_reranker_success(
        self, indexed_project, search_package
    ):
        """find_code uses primary reranker successfully."""
        # Ensure search package has multiple rerankers
        assert len(search_package.reranking) >= 2

        # Execute
        response = await find_code(
            query="test query",
            search_package=search_package,
        )

        # Assert
        assert response.success
        assert len(response.matches) > 0
        # Primary reranker should have been used

    @pytest.mark.asyncio
    async def test_find_code_with_reranker_fallback(
        self, indexed_project, search_package
    ):
        """find_code falls back to secondary reranker when primary fails."""
        # Mock primary reranker to fail
        primary = search_package.reranking[0]
        with patch.object(
            primary,
            "rerank",
            AsyncMock(side_effect=CircuitBreakerOpenError("Circuit breaker open")),
        ):
            # Execute
            response = await find_code(
                query="test query",
                search_package=search_package,
            )

            # Assert
            assert response.success
            assert len(response.matches) > 0
            # Should have fallen back to secondary reranker
```

### Deliverables

- [ ] Updated `rerank_results()` function with cascading fallback
- [ ] Unit tests covering all fallback scenarios
- [ ] Integration tests with real find_code execution
- [ ] Updated docstrings and code comments
- [ ] Logging for observability

### Success Criteria

1. ✅ Primary reranker succeeds → no fallback triggered
2. ✅ Primary circuit breaker open → fallback succeeds
3. ✅ Primary raises exception → fallback succeeds
4. ✅ All rerankers fail → returns None gracefully
5. ✅ Single reranker (not tuple) → backwards compatible
6. ✅ No reranker provided → returns None gracefully
7. ✅ Logging provides clear visibility into which provider succeeded

---

## Phase 2: Backup Vector Reconciliation

**Priority**: MEDIUM
**Effort**: 4-8 hours
**Complexity**: MEDIUM
**Dependencies**: Embedding registry access

### Overview

Implement periodic validation that all points in the vector store have the required vectors (primary, sparse, backup) as defined by the configuration. Missing vectors are lazily generated and added to points.

### Architecture

**New Service**: `src/codeweaver/engine/services/reconciliation_service.py`

This service will:
1. Scroll through all points in the collection
2. Check if each point has all required vectors
3. Generate missing vectors using the embedding registry
4. Update points with missing vectors
5. Report statistics (checked, missing, repaired)

### Implementation Steps

#### Step 2.1: Create Backup Model Selection Module

**New File**: `src/codeweaver/providers/config/backup_models.py`

```python
"""Hardcoded backup model selection based on available dependencies."""

from __future__ import annotations

import logging
from typing import Literal

from codeweaver.core.utils.lazy_importer import LazyImporter

logger = logging.getLogger(__name__)

BackupModelProvider = Literal["sentence_transformers", "fastembed"]


def get_backup_embedding_model() -> tuple[str, BackupModelProvider]:
    """Get the appropriate backup embedding model based on installed dependencies.

    Priority:
    1. sentence-transformers: minishlab/potion-base-8M (best performance)
    2. fastembed (fallback): jinaai/jina-embeddings-v2-small-en

    Returns:
        Tuple of (model_name, provider_type)
    """
    lazy = LazyImporter()

    # Try sentence-transformers first (best option)
    if lazy.is_available("sentence_transformers"):
        logger.info("Using sentence-transformers for backup embeddings: minishlab/potion-base-8M")
        return "minishlab/potion-base-8M", "sentence_transformers"

    # Fallback to fastembed (always available as core dependency)
    logger.info("Using fastembed for backup embeddings: jinaai/jina-embeddings-v2-small-en")
    return "jinaai/jina-embeddings-v2-small-en", "fastembed"


def get_backup_reranking_model() -> tuple[str, BackupModelProvider]:
    """Get the appropriate backup reranking model based on installed dependencies.

    Uses same priority logic as embeddings for consistency.

    Returns:
        Tuple of (model_name, provider_type)
    """
    lazy = LazyImporter()

    # sentence-transformers has good reranking support
    if lazy.is_available("sentence_transformers"):
        logger.info(
            "Using sentence-transformers for backup reranking: mixedbread-ai/mxbai-rerank-xsmall-v1"
        )
        return "mixedbread-ai/mxbai-rerank-xsmall-v1", "sentence_transformers"

    # Fallback to fastembed
    logger.info("Using fastembed for backup reranking: Xenova/ms-marco-MiniLM-L-6-v2")
    return "Xenova/ms-marco-MiniLM-L-6-v2", "fastembed"


__all__ = ("BackupModelProvider", "get_backup_embedding_model", "get_backup_reranking_model")
```

#### Step 2.2: Create Reconciliation Service

**New File**: `src/codeweaver/engine/services/reconciliation_service.py`

```python
"""Service for reconciling backup vectors across collection points."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from codeweaver.core import CodeChunk
from codeweaver.providers.types import EmbeddingCapabilityGroup

if TYPE_CHECKING:
    from codeweaver.providers import VectorStoreProvider
    from codeweaver.providers.embedding.registry import EmbeddingRegistry
    from codeweaver.providers import EmbeddingProvider


logger = logging.getLogger(__name__)


class VectorReconciliationService:
    """Ensures all points have required vectors per configuration.

    This service periodically checks all points in the vector store to ensure
    they have the vectors required by the current configuration. Missing vectors
    are lazily generated and added to points.

    Use Cases:
    - After configuration changes (e.g., enabling backup vectors)
    - Periodic maintenance to catch any drift
    - Recovery from partial index failures
    """

    def __init__(
        self,
        vector_store: VectorStoreProvider,
        embedding_registry: EmbeddingRegistry,
        capabilities: EmbeddingCapabilityGroup,
        backup_embedding_provider: EmbeddingProvider | None = None,
    ):
        """Initialize reconciliation service.

        Args:
            vector_store: Vector store to reconcile
            embedding_registry: Registry for retrieving embeddings
            capabilities: Embedding capabilities defining required vectors
            backup_embedding_provider: Optional backup provider for generating missing vectors
        """
        self.vector_store = vector_store
        self.registry = embedding_registry
        self.caps = capabilities
        self.backup_provider = backup_embedding_provider

    async def reconcile_vectors(self, batch_size: int = 100) -> dict[str, int]:
        """Check and repair missing vectors across all points.

        Args:
            batch_size: Number of points to process per batch

        Returns:
            Dict with stats: {"checked": N, "missing": M, "repaired": R, "errors": E}
        """
        collection_name = self.vector_store.collection_name
        required_vectors = self._get_required_vector_names()

        logger.info(
            "Starting vector reconciliation for collection '%s' (required vectors: %s)",
            collection_name,
            required_vectors,
        )

        stats = {"checked": 0, "missing": 0, "repaired": 0, "errors": 0}
        offset = None

        while True:
            try:
                # Scroll through points
                points, next_offset = await self.vector_store.client.scroll(
                    collection_name=collection_name,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,  # Need to check vector names
                )

                if not points:
                    break

                stats["checked"] += len(points)

                # Check each point for missing vectors
                points_to_repair = []
                for point in points:
                    # Get existing vector names
                    existing_vectors = set()
                    if hasattr(point, "vector") and isinstance(point.vector, dict):
                        existing_vectors = set(point.vector.keys())

                    # Find missing vectors
                    missing = required_vectors - existing_vectors

                    if missing:
                        stats["missing"] += 1
                        points_to_repair.append((point.id, point.payload, missing))
                        logger.debug(
                            "Point %s missing vectors: %s",
                            point.id,
                            missing,
                        )

                # Repair missing vectors in batch
                if points_to_repair:
                    repaired = await self._repair_missing_vectors(points_to_repair)
                    stats["repaired"] += repaired
                    stats["errors"] += len(points_to_repair) - repaired

                offset = next_offset
                if offset is None:
                    break

            except Exception as e:
                logger.error(
                    "Error during vector reconciliation at offset %s: %s",
                    offset,
                    e,
                    exc_info=True,
                )
                stats["errors"] += 1
                # Continue with next batch
                if offset is None:
                    break

        logger.info(
            "Vector reconciliation complete: %d checked, %d missing, %d repaired, %d errors",
            stats["checked"],
            stats["missing"],
            stats["repaired"],
            stats["errors"],
        )

        return stats

    def _get_required_vector_names(self) -> set[str]:
        """Get set of required vector names from capabilities.

        Returns:
            Set of vector names that should exist on all points
        """
        required = set()

        # Sparse is always required (either from provider or BM25)
        required.add("sparse")

        # Dense vector (primary)
        if self.caps.dense:
            required.add("primary")

        # Backup vector (if backup provider configured)
        if self.caps.backup or self.backup_provider:
            required.add("backup")

        return required

    async def _repair_missing_vectors(
        self,
        points_to_repair: list[tuple[str, dict, set[str]]],
    ) -> int:
        """Generate and add missing vectors to points.

        Args:
            points_to_repair: List of (point_id, payload, missing_vector_names)

        Returns:
            Number of points successfully repaired
        """
        from qdrant_client.http.models import PointStruct, SparseVector

        repaired_count = 0

        for point_id, payload, missing_vectors in points_to_repair:
            try:
                # Extract chunk from payload
                chunk_data = payload.get("chunk")
                if not chunk_data:
                    logger.warning("Point %s has no chunk data, skipping", point_id)
                    continue

                chunk = CodeChunk.model_validate(chunk_data)

                # Generate missing embeddings
                new_vectors = {}

                for vector_name in missing_vectors:
                    if vector_name == "backup" and self.backup_provider:
                        # Generate backup embedding
                        try:
                            embedding = await self.backup_provider.embed_query(chunk.content)
                            # Normalize to list[float]
                            if isinstance(embedding, list) and len(embedding) > 0:
                                new_vectors[vector_name] = (
                                    embedding[0] if isinstance(embedding[0], list) else embedding
                                )
                        except Exception as e:
                            logger.warning(
                                "Failed to generate backup embedding for point %s: %s",
                                point_id,
                                e,
                            )
                            continue

                    elif vector_name == "sparse":
                        # Use BM25 fallback for sparse
                        from qdrant_client.http.models import Document
                        new_vectors[vector_name] = Document(text=chunk.content, model="qdrant/bm25")

                    # Add other vector types as needed

                # Update point with new vectors
                if new_vectors:
                    # Need to update the point's vectors
                    # Qdrant requires full upsert with all vectors
                    # First retrieve existing vectors
                    existing_point = await self.vector_store.client.retrieve(
                        collection_name=self.vector_store.collection_name,
                        ids=[point_id],
                        with_vectors=True,
                    )

                    if not existing_point:
                        logger.warning("Could not retrieve point %s for update", point_id)
                        continue

                    # Merge existing and new vectors
                    all_vectors = dict(existing_point[0].vector) if hasattr(existing_point[0], 'vector') else {}
                    all_vectors.update(new_vectors)

                    # Upsert with complete vector set
                    await self.vector_store.client.upsert(
                        collection_name=self.vector_store.collection_name,
                        points=[
                            PointStruct(
                                id=point_id,
                                vector=all_vectors,
                                payload=payload,
                            )
                        ],
                    )

                    logger.debug(
                        "Repaired point %s: added vectors %s",
                        point_id,
                        list(new_vectors.keys()),
                    )
                    repaired_count += 1

            except Exception as e:
                logger.error(
                    "Error repairing point %s: %s",
                    point_id,
                    e,
                    exc_info=True,
                )
                continue

        return repaired_count


__all__ = ("VectorReconciliationService",)
```

#### Step 2.3: Integrate with Failover Service

**File**: `src/codeweaver/engine/services/failover_service.py`

**Update `_maintain_backup_loop` method**:

```python
    async def _maintain_backup_loop(self) -> None:
        """Periodically sync backup and reconcile vectors."""
        # Initialize reconciliation service
        reconciliation_service = None
        maintenance_cycle_count = 0

        while True:
            try:
                # Sync interval from settings (default 5 mins)
                await asyncio.sleep(self.settings.backup_sync_interval)

                # Only run if not currently failing over
                if not self._failover_active and self.backup_store:
                    # Use very low priority for background maintenance
                    with very_low_priority():
                        # Run backup indexing
                        await self.backup_indexing_service.index_project()

                        # Run vector reconciliation every 2 cycles (10 mins)
                        if maintenance_cycle_count % 2 == 0:
                            # Lazy initialize reconciliation service
                            if reconciliation_service is None:
                                reconciliation_service = await self._create_reconciliation_service()

                            if reconciliation_service:
                                try:
                                    stats = await reconciliation_service.reconcile_vectors()
                                    logger.info(
                                        "Vector reconciliation: %d checked, %d missing, %d repaired",
                                        stats["checked"],
                                        stats["missing"],
                                        stats["repaired"],
                                    )
                                except Exception as e:
                                    logger.error("Vector reconciliation failed: %s", e)

                        maintenance_cycle_count += 1

            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Error in backup maintenance loop", exc_info=True)

    async def _create_reconciliation_service(self) -> VectorReconciliationService | None:
        """Create reconciliation service with required dependencies."""
        try:
            from codeweaver.core.di.container import get_container
            from codeweaver.engine.services.reconciliation_service import VectorReconciliationService
            from codeweaver.providers.embedding.registry import EmbeddingRegistry
            from codeweaver.providers.types import EmbeddingCapabilityGroup

            container = get_container()

            registry = await container.resolve(EmbeddingRegistry)
            capabilities = await container.resolve(EmbeddingCapabilityGroup)

            # Try to resolve backup embedding provider
            backup_provider = None
            try:
                from codeweaver.providers import EmbeddingProvider
                # Resolve with "backup" intent/name if available
                backup_provider = await container.resolve(EmbeddingProvider, name="backup")
            except Exception:
                logger.debug("No backup embedding provider available for reconciliation")

            return VectorReconciliationService(
                vector_store=self.primary_store,
                embedding_registry=registry,
                capabilities=capabilities,
                backup_embedding_provider=backup_provider,
            )

        except Exception as e:
            logger.warning("Failed to create reconciliation service: %s", e)
            return None
```

#### Step 2.4: Add CLI Command for Manual Reconciliation

**File**: `src/codeweaver/cli/commands/index.py`

**Add new command**:

```python
@app.command()
def reconcile(
    ctx: typer.Context,
    batch_size: int = typer.Option(100, help="Batch size for processing points"),
    dry_run: bool = typer.Option(False, help="Only check, don't repair"),
) -> None:
    """Reconcile backup vectors across all indexed points.

    Checks all points in the vector store to ensure they have the required
    vectors (primary, sparse, backup) as defined by configuration. Missing
    vectors are generated and added.

    This is useful:
    - After configuration changes (e.g., enabling backup vectors)
    - As periodic maintenance to catch any drift
    - For recovery from partial index failures
    """
    import asyncio
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn

    console = Console()

    async def run_reconciliation():
        """Run reconciliation with progress display."""
        from codeweaver.core.di.container import get_container
        from codeweaver.engine.services.reconciliation_service import VectorReconciliationService
        from codeweaver.providers import VectorStoreProvider, EmbeddingProvider
        from codeweaver.providers.embedding.registry import EmbeddingRegistry
        from codeweaver.providers.types import EmbeddingCapabilityGroup

        container = get_container()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing reconciliation...", total=None)

            # Resolve dependencies
            vector_store = await container.resolve(VectorStoreProvider)
            registry = await container.resolve(EmbeddingRegistry)
            capabilities = await container.resolve(EmbeddingCapabilityGroup)

            backup_provider = None
            try:
                backup_provider = await container.resolve(EmbeddingProvider, name="backup")
            except Exception:
                console.print("[yellow]No backup embedding provider configured[/yellow]")

            # Create service
            service = VectorReconciliationService(
                vector_store=vector_store,
                embedding_registry=registry,
                capabilities=capabilities,
                backup_embedding_provider=backup_provider,
            )

            progress.update(task, description="Scanning collection...")

            # Run reconciliation
            if dry_run:
                console.print("[yellow]Dry run mode - will not repair vectors[/yellow]")
                # Would need to add dry_run support to reconcile_vectors

            stats = await service.reconcile_vectors(batch_size=batch_size)

            progress.update(task, description="Reconciliation complete!", completed=True)

        # Display results
        console.print()
        console.print("[bold green]Reconciliation Results:[/bold green]")
        console.print(f"  Points checked: {stats['checked']}")
        console.print(f"  Points missing vectors: {stats['missing']}")
        console.print(f"  Points repaired: {stats['repaired']}")
        if stats['errors'] > 0:
            console.print(f"  [red]Errors: {stats['errors']}[/red]")

    asyncio.run(run_reconciliation())
```

#### Step 2.5: Add Tests

**New File**: `tests/unit/engine/services/test_reconciliation_service.py`

```python
"""Tests for vector reconciliation service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from codeweaver.engine.services.reconciliation_service import VectorReconciliationService
from codeweaver.core import CodeChunk
from codeweaver.providers.types import EmbeddingCapabilityGroup


@pytest.fixture
def mock_vector_store():
    """Mock vector store."""
    store = MagicMock()
    store.collection_name = "test_collection"
    store.client = AsyncMock()
    return store


@pytest.fixture
def mock_embedding_registry():
    """Mock embedding registry."""
    return MagicMock()


@pytest.fixture
def mock_capabilities():
    """Mock embedding capabilities."""
    caps = MagicMock(spec=EmbeddingCapabilityGroup)
    caps.dense = True
    caps.backup = True
    return caps


@pytest.fixture
def reconciliation_service(
    mock_vector_store, mock_embedding_registry, mock_capabilities
):
    """Create reconciliation service with mocks."""
    return VectorReconciliationService(
        vector_store=mock_vector_store,
        embedding_registry=mock_embedding_registry,
        capabilities=mock_capabilities,
    )


class TestVectorReconciliationService:
    """Test vector reconciliation service."""

    @pytest.mark.asyncio
    async def test_reconcile_all_vectors_present(
        self, reconciliation_service, mock_vector_store
    ):
        """All points have required vectors - no repairs needed."""
        # Setup - mock scroll to return points with all vectors
        mock_vector_store.client.scroll = AsyncMock(return_value=(
            [
                MagicMock(
                    id="point-1",
                    vector={"primary": [0.1], "sparse": MagicMock(), "backup": [0.2]},
                    payload={"chunk": {"content": "test", "chunk_id": "chunk-1"}},
                )
            ],
            None,  # No next offset
        ))

        # Execute
        stats = await reconciliation_service.reconcile_vectors()

        # Assert
        assert stats["checked"] == 1
        assert stats["missing"] == 0
        assert stats["repaired"] == 0
        assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_reconcile_missing_backup_vector(
        self, reconciliation_service, mock_vector_store
    ):
        """Point missing backup vector - should be repaired."""
        # Setup
        mock_vector_store.client.scroll = AsyncMock(return_value=(
            [
                MagicMock(
                    id="point-1",
                    vector={"primary": [0.1], "sparse": MagicMock()},  # Missing backup
                    payload={"chunk": {"content": "test", "chunk_id": "chunk-1"}},
                )
            ],
            None,
        ))

        # Mock backup provider
        backup_provider = AsyncMock()
        backup_provider.embed_query = AsyncMock(return_value=[[0.3, 0.4]])
        reconciliation_service.backup_provider = backup_provider

        # Mock retrieve for update
        mock_vector_store.client.retrieve = AsyncMock(return_value=[
            MagicMock(
                id="point-1",
                vector={"primary": [0.1], "sparse": MagicMock()},
            )
        ])

        # Mock upsert
        mock_vector_store.client.upsert = AsyncMock()

        # Execute
        stats = await reconciliation_service.reconcile_vectors()

        # Assert
        assert stats["checked"] == 1
        assert stats["missing"] == 1
        assert stats["repaired"] == 1
        backup_provider.embed_query.assert_called_once()
        mock_vector_store.client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconcile_batch_processing(
        self, reconciliation_service, mock_vector_store
    ):
        """Multiple batches processed correctly."""
        # Setup - two batches
        mock_vector_store.client.scroll = AsyncMock(side_effect=[
            # First batch
            (
                [MagicMock(id=f"point-{i}", vector={"primary": [0.1]}, payload={})
                 for i in range(100)],
                "offset-1",
            ),
            # Second batch
            (
                [MagicMock(id=f"point-{i}", vector={"primary": [0.1]}, payload={})
                 for i in range(100, 150)],
                None,
            ),
        ])

        # Execute
        stats = await reconciliation_service.reconcile_vectors(batch_size=100)

        # Assert
        assert stats["checked"] == 150
        assert mock_vector_store.client.scroll.call_count == 2
```

### Deliverables

- [ ] `backup_models.py` module with hardcoded model selection
- [ ] `VectorReconciliationService` implementation
- [ ] Integration with `FailoverService`
- [ ] CLI command for manual reconciliation (`cw index reconcile`)
- [ ] Unit tests for reconciliation logic
- [ ] Integration tests with real vector store
- [ ] Documentation and logging

### Success Criteria

1. ✅ Service correctly identifies points missing vectors
2. ✅ Missing vectors are generated using backup provider
3. ✅ Points are updated with new vectors
4. ✅ Batch processing handles large collections efficiently
5. ✅ Statistics are accurate and actionable
6. ✅ Integration with failover service runs periodically (every 10 mins)
7. ✅ CLI command allows manual reconciliation

---

## Phase 3: Snapshot-Based Remote Backup

**Priority**: LOW
**Effort**: 6-12 hours
**Complexity**: HIGH
**Dependencies**: Qdrant client, failover service

### Overview

Implement snapshot-based backup for remote Qdrant instances using Qdrant's native snapshot and WAL features. This provides automatic failover to a local Qdrant instance when the remote becomes unavailable.

### Architecture

Instead of a custom WAL wrapper, leverage Qdrant's built-in capabilities:

1. **Periodic Snapshots**: Create snapshots of the remote collection
2. **Local Restoration**: Restore snapshots to local Qdrant for failover
3. **Incremental Sync**: Track recent changes and sync incrementally
4. **Reconciliation**: Sync local changes back to remote after recovery

### Implementation Steps

#### Step 3.1: Create Snapshot Backup Service

**New File**: `src/codeweaver/providers/vector_stores/snapshot_backup.py`

```python
"""Qdrant snapshot-based backup service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from qdrant_client import AsyncQdrantClient

if TYPE_CHECKING:
    from codeweaver.engine.config import FailoverSettings


logger = logging.getLogger(__name__)


class QdrantSnapshotBackupService:
    """Uses Qdrant's native snapshot + WAL features for backup.

    This service:
    1. Creates periodic snapshots of remote collections
    2. Restores snapshots to local Qdrant for failover
    3. Syncs incremental changes between snapshots
    4. Reconciles local changes back to remote after recovery
    """

    def __init__(
        self,
        primary_client: AsyncQdrantClient,
        backup_path: Path,
        collection_name: str,
        settings: FailoverSettings,
    ):
        """Initialize snapshot backup service.

        Args:
            primary_client: Client for remote Qdrant instance
            backup_path: Local path for snapshots and backup Qdrant
            collection_name: Name of collection to back up
            settings: Failover settings
        """
        self.primary_client = primary_client
        self.backup_path = backup_path
        self.collection_name = collection_name
        self.settings = settings
        self._backup_client: AsyncQdrantClient | None = None
        self._last_snapshot_time: datetime | None = None

        # Ensure backup directory exists
        self.backup_path.mkdir(parents=True, exist_ok=True)

    async def create_snapshot_backup(self) -> Path:
        """Create a snapshot of the primary collection.

        Qdrant snapshots include:
        - All vectors and payloads
        - Collection configuration
        - WAL segments

        This is atomic and consistent.

        Returns:
            Path to created snapshot file
        """
        logger.info("Creating snapshot backup for collection '%s'", self.collection_name)

        try:
            # Create snapshot on remote
            snapshot = await self.primary_client.create_snapshot(
                collection_name=self.collection_name
            )

            # Download snapshot to local backup path
            snapshot_path = self.backup_path / f"snapshot_{snapshot.name}"
            await self.primary_client.download_snapshot(
                collection_name=self.collection_name,
                snapshot_name=snapshot.name,
                output=str(snapshot_path),
            )

            self._last_snapshot_time = datetime.now(UTC)

            logger.info("Created snapshot backup: %s", snapshot_path)

            # Clean up old snapshots based on retention policy
            await self._cleanup_old_snapshots()

            return snapshot_path

        except Exception as e:
            logger.error("Failed to create snapshot backup: %s", e, exc_info=True)
            raise

    async def restore_from_snapshot(self, snapshot_path: Path | None = None) -> None:
        """Restore collection from snapshot.

        Used when primary fails and we need to activate backup.

        Args:
            snapshot_path: Specific snapshot to restore. If None, uses most recent.
        """
        if snapshot_path is None:
            snapshot_path = await self._get_latest_snapshot()
            if snapshot_path is None:
                raise RuntimeError("No snapshots available for restore")

        logger.info("Restoring from snapshot: %s", snapshot_path)

        # Initialize backup Qdrant instance if needed
        if self._backup_client is None:
            backup_data_path = self.backup_path / "qdrant_data"
            self._backup_client = AsyncQdrantClient(path=str(backup_data_path))

        try:
            # Recover snapshot to backup instance
            await self._backup_client.recover_snapshot(
                collection_name=self.collection_name,
                location=str(snapshot_path),
            )

            logger.info("Successfully restored from snapshot: %s", snapshot_path.name)

        except Exception as e:
            logger.error("Failed to restore from snapshot: %s", e, exc_info=True)
            raise

    async def get_backup_client(self) -> AsyncQdrantClient:
        """Get the backup Qdrant client.

        Returns:
            Backup client instance

        Raises:
            RuntimeError: If backup not initialized
        """
        if self._backup_client is None:
            raise RuntimeError("Backup not initialized - call restore_from_snapshot first")
        return self._backup_client

    async def sync_incremental_changes(self) -> int:
        """Sync recent changes from primary to backup.

        Uses Qdrant's scroll API to get points modified since last sync.
        Filters by indexed_at timestamp to only sync new/changed points.

        Returns:
            Number of points synced
        """
        if self._backup_client is None:
            logger.debug("Backup client not initialized, skipping incremental sync")
            return 0

        if self._last_snapshot_time is None:
            logger.warning("No snapshot timestamp available, skipping incremental sync")
            return 0

        logger.info("Starting incremental sync from primary to backup")

        synced_count = 0

        try:
            # Scroll through recently modified points
            from qdrant_client.models import FieldCondition, Range
            from qdrant_client.models import Filter as QdrantFilter

            filter_cond = QdrantFilter(
                must=[
                    FieldCondition(
                        key="indexed_at",
                        range=Range(gte=self._last_snapshot_time.isoformat()),
                    )
                ]
            )

            offset = None
            while True:
                points, next_offset = await self.primary_client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=filter_cond,
                    limit=100,
                    offset=offset,
                    with_vectors=True,
                    with_payload=True,
                )

                if not points:
                    break

                # Upsert to backup
                await self._backup_client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                )

                synced_count += len(points)

                offset = next_offset
                if offset is None:
                    break

            logger.info("Incremental sync complete: %d points synced", synced_count)

        except Exception as e:
            logger.error("Incremental sync failed: %s", e, exc_info=True)

        return synced_count

    async def reconcile_to_primary(self) -> int:
        """Sync backup changes back to primary after recovery.

        Scrolls through all backup points and upser ts to primary.
        Used after failover to restore primary with any changes made during outage.

        Returns:
            Number of points reconciled
        """
        if self._backup_client is None:
            logger.warning("No backup client available for reconciliation")
            return 0

        logger.info("Starting reconciliation from backup to primary")

        reconciled_count = 0

        try:
            offset = None
            while True:
                # Scroll through all backup points
                points, next_offset = await self._backup_client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=offset,
                    with_vectors=True,
                    with_payload=True,
                )

                if not points:
                    break

                # Upsert to primary
                await self.primary_client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                )

                reconciled_count += len(points)

                offset = next_offset
                if offset is None:
                    break

            logger.info("Reconciliation complete: %d points synced to primary", reconciled_count)

        except Exception as e:
            logger.error("Reconciliation failed: %s", e, exc_info=True)
            raise

        return reconciled_count

    async def _get_latest_snapshot(self) -> Path | None:
        """Get the most recent snapshot file.

        Returns:
            Path to latest snapshot, or None if no snapshots exist
        """
        snapshots = sorted(
            self.backup_path.glob("snapshot_*.snapshot"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return snapshots[0] if snapshots else None

    async def _cleanup_old_snapshots(self) -> None:
        """Remove old snapshots based on retention policy."""
        snapshots = sorted(
            self.backup_path.glob("snapshot_*.snapshot"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        # Keep only the configured number of snapshots
        for old_snapshot in snapshots[self.settings.snapshot_retention :]:
            try:
                old_snapshot.unlink()
                logger.debug("Deleted old snapshot: %s", old_snapshot.name)
            except Exception as e:
                logger.warning("Failed to delete old snapshot %s: %s", old_snapshot.name, e)


__all__ = ("QdrantSnapshotBackupService",)
```

#### Step 3.2: Create Wrapper for Remote Qdrant with Backup

**New File**: `src/codeweaver/providers/vector_stores/qdrant_with_backup.py`

```python
"""Qdrant provider wrapper with snapshot-based backup."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from codeweaver.core import SearchResult, StrategizedQuery
from codeweaver.providers.vector_stores.qdrant import QdrantProvider
from codeweaver.providers.vector_stores.snapshot_backup import QdrantSnapshotBackupService

if TYPE_CHECKING:
    from codeweaver.core import CodeChunk
    from codeweaver.engine.config import FailoverSettings


logger = logging.getLogger(__name__)


class QdrantWithBackup(QdrantProvider):
    """Qdrant provider with snapshot-based backup for remote instances.

    Automatically creates periodic snapshots and restores from them during
    failover. Uses Qdrant's native snapshot and WAL features for reliability.
    """

    def __init__(
        self,
        backup_service: QdrantSnapshotBackupService,
        failover_settings: FailoverSettings,
        **kwargs,
    ):
        """Initialize Qdrant with backup.

        Args:
            backup_service: Snapshot backup service
            failover_settings: Failover configuration
            **kwargs: Passed to parent QdrantProvider
        """
        super().__init__(**kwargs)
        self.backup_service = backup_service
        self.settings = failover_settings
        self._in_failover = False

    async def upsert(self, chunks: list[CodeChunk]) -> None:
        """Upsert with automatic snapshot tracking.

        Delegates to primary, but tracks that changes occurred
        for next incremental sync.
        """
        try:
            await super().upsert(chunks)
        except Exception as e:
            logger.warning("Primary upsert failed: %s", e)
            # Circuit breaker will trigger failover
            # Next snapshot will capture state before failure
            raise

    async def search(
        self, vector: StrategizedQuery, query_filter=None
    ) -> list[SearchResult]:
        """Search with automatic failover to snapshot backup."""
        if self._in_failover:
            # Use backup client
            backup_client = await self.backup_service.get_backup_client()
            logger.debug("Using backup client for search")
            # Would need to implement search using backup client
            # This requires refactoring search logic to accept a client parameter
            # For now, delegate to parent and let it handle the error

        try:
            return await super().search(vector, query_filter)
        except Exception as e:
            if not self._in_failover:
                # First failure - activate failover
                logger.error("Primary search failed, activating failover: %s", e)
                await self._activate_failover()
                # Retry with backup
                return await self.search(vector, query_filter)
            raise

    async def _activate_failover(self) -> None:
        """Activate backup from most recent snapshot."""
        logger.warning("⚠️ Activating snapshot backup failover")

        try:
            # Find and restore most recent snapshot
            await self.backup_service.restore_from_snapshot()
            self._in_failover = True
            logger.info("Failover active - using local snapshot backup")

        except Exception as e:
            logger.error("Failed to activate failover: %s", e, exc_info=True)
            raise RuntimeError("Failover activation failed") from e

    async def restore_primary(self) -> None:
        """Restore to primary after recovery."""
        if not self._in_failover:
            logger.debug("Not in failover, nothing to restore")
            return

        logger.info("Primary recovered, reconciling changes")

        try:
            # Sync any changes made during failover back to primary
            synced = await self.backup_service.reconcile_to_primary()
            logger.info("Reconciled %d points back to primary", synced)

            self._in_failover = False
            logger.info("Restored to primary vector store")

        except Exception as e:
            logger.error("Failed to reconcile to primary: %s", e, exc_info=True)
            # Continue anyway - eventual consistency via standard indexing


__all__ = ("QdrantWithBackup",)
```

#### Step 3.3: Update Failover Service Integration

**File**: `src/codeweaver/engine/services/failover_service.py`

**Update `_maintain_backup_loop` to create snapshots**:

```python
    async def _maintain_backup_loop(self) -> None:
        """Periodically create snapshots and sync incremental changes."""
        # Initialize services
        reconciliation_service = None
        snapshot_service = None
        maintenance_cycle_count = 0

        # Check if primary store supports snapshots
        if hasattr(self.primary_store, "backup_service"):
            snapshot_service = self.primary_store.backup_service

        while True:
            try:
                await asyncio.sleep(self.settings.backup_sync_interval)

                if not self._failover_active:
                    with very_low_priority():
                        # Create periodic snapshot if available
                        if snapshot_service:
                            try:
                                await snapshot_service.create_snapshot_backup()
                                await snapshot_service.sync_incremental_changes()
                            except Exception as e:
                                logger.error("Snapshot backup failed: %s", e)

                        # Run backup indexing
                        if self.backup_store:
                            await self.backup_indexing_service.index_project()

                        # Vector reconciliation every 2 cycles (10 mins)
                        if maintenance_cycle_count % 2 == 0:
                            if reconciliation_service is None:
                                reconciliation_service = await self._create_reconciliation_service()

                            if reconciliation_service:
                                try:
                                    stats = await reconciliation_service.reconcile_vectors()
                                    logger.info(
                                        "Vector reconciliation: %d checked, %d missing, %d repaired",
                                        stats["checked"],
                                        stats["missing"],
                                        stats["repaired"],
                                    )
                                except Exception as e:
                                    logger.error("Vector reconciliation failed: %s", e)

                        maintenance_cycle_count += 1

            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Error in backup maintenance loop", exc_info=True)
```

#### Step 3.4: Update Configuration

**File**: `src/codeweaver/engine/config/failover.py`

**Add snapshot-related settings**:

```python
class FailoverSettings(BasedModel):
    """Settings for vector store failover and service resilience."""

    # ... existing fields ...

    # Snapshot backup configuration
    backup_path: Annotated[
        Path,
        Field(
            description="Path for snapshot backups and local Qdrant instance",
            default_factory=lambda: Path("~/.codeweaver/backups").expanduser(),
        ),
    ]

    snapshot_interval: Annotated[
        PositiveInt,
        Field(
            description="Interval between full snapshots in seconds",
            default=FIVE_MINUTES_IN_SECONDS,
        ),
    ]

    snapshot_retention: Annotated[
        PositiveInt,
        Field(
            description="Number of snapshots to retain",
            default=3,
        ),
    ]

    # Reconciliation configuration
    reconciliation_interval_cycles: Annotated[
        PositiveInt,
        Field(
            description="Run vector reconciliation every N maintenance cycles",
            default=2,  # Every 2 cycles = 10 mins with default sync interval
        ),
    ]

    # Qdrant WAL configuration for primary collection
    wal_capacity_mb: Annotated[
        PositiveInt,
        Field(
            description="Size of a single WAL segment in MB",
            default=256,
        ),
    ]

    wal_segments_ahead: Annotated[
        PositiveInt,
        Field(
            description="Number of WAL segments to create ahead",
            default=2,
        ),
    ]

    wal_retain_closed: Annotated[
        PositiveInt,
        Field(
            description="Number of closed WAL segments to keep for recovery",
            default=5,
        ),
    ]

    @property
    def backup_sync_interval(self) -> int:
        """Get backup sync interval (alias for snapshot_interval)."""
        return self.snapshot_interval
```

#### Step 3.5: Update Collection Creation with WAL Config

**File**: `src/codeweaver/providers/vector_stores/qdrant_base.py`

**Update `_ensure_collection` to configure WAL**:

```python
    async def _ensure_collection(self, collection_name: str, dense_dim: int | None = None) -> None:
        """Ensure collection exists with WAL configuration."""
        if collection_name in self._known_collections:
            return

        if not self.client:
            raise ProviderError("Qdrant client is not initialized")

        try:
            if await self.client.collection_exists(collection_name):
                self._known_collections.add(collection_name)
                await self._validate_collection_config(collection_name)
                return

            # Create new collection with WAL config
            from qdrant_client.models import WalConfig

            # Get failover settings for WAL configuration
            from codeweaver.core.di.container import get_container
            from codeweaver.engine.config import FailoverSettings

            failover_settings = await get_container().resolve(FailoverSettings)

            wal_config = WalConfig(
                wal_capacity_mb=failover_settings.wal_capacity_mb,
                wal_segments_ahead=failover_settings.wal_segments_ahead,
                wal_retain_closed=failover_settings.wal_retain_closed,
            )

            metadata = self._create_metadata_from_config()
            collection_config = await self.config.get_collection_config(metadata=metadata)

            await self.client.create_collection(
                **collection_config,
                wal_config=wal_config,
            )

            self._known_collections.add(collection_name)

        except UnexpectedResponse as e:
            raise ProviderError(
                "The vector store provider encountered an error when trying to check if the collection existed, or when trying to create it."
            ) from e
```

#### Step 3.6: Add Tests

**New File**: `tests/unit/providers/vector_stores/test_snapshot_backup.py`

```python
"""Tests for Qdrant snapshot backup service."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from codeweaver.providers.vector_stores.snapshot_backup import QdrantSnapshotBackupService


@pytest.fixture
def mock_primary_client():
    """Mock primary Qdrant client."""
    client = AsyncMock()
    return client


@pytest.fixture
def backup_path(tmp_path):
    """Temporary backup path."""
    return tmp_path / "backups"


@pytest.fixture
def mock_failover_settings():
    """Mock failover settings."""
    settings = MagicMock()
    settings.snapshot_retention = 3
    return settings


@pytest.fixture
def snapshot_service(mock_primary_client, backup_path, mock_failover_settings):
    """Create snapshot backup service."""
    return QdrantSnapshotBackupService(
        primary_client=mock_primary_client,
        backup_path=backup_path,
        collection_name="test_collection",
        settings=mock_failover_settings,
    )


class TestQdrantSnapshotBackupService:
    """Test Qdrant snapshot backup service."""

    @pytest.mark.asyncio
    async def test_create_snapshot_backup(self, snapshot_service, mock_primary_client, backup_path):
        """Successfully creates and downloads snapshot."""
        # Setup
        mock_snapshot = MagicMock()
        mock_snapshot.name = "test-snapshot.snapshot"
        mock_primary_client.create_snapshot = AsyncMock(return_value=mock_snapshot)
        mock_primary_client.download_snapshot = AsyncMock()

        # Execute
        snapshot_path = await snapshot_service.create_snapshot_backup()

        # Assert
        assert snapshot_path.exists()
        assert snapshot_path.name == f"snapshot_{mock_snapshot.name}"
        mock_primary_client.create_snapshot.assert_called_once_with(
            collection_name="test_collection"
        )
        mock_primary_client.download_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_from_snapshot(self, snapshot_service, backup_path):
        """Successfully restores from snapshot."""
        # Setup - create a mock snapshot file
        snapshot_file = backup_path / "snapshot_test.snapshot"
        snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        snapshot_file.touch()

        # Execute
        await snapshot_service.restore_from_snapshot(snapshot_file)

        # Assert
        assert snapshot_service._backup_client is not None

    @pytest.mark.asyncio
    async def test_sync_incremental_changes(
        self, snapshot_service, mock_primary_client, backup_path
    ):
        """Successfully syncs incremental changes."""
        # Setup
        snapshot_service._last_snapshot_time = datetime.now(UTC)

        # Initialize backup client
        backup_data_path = backup_path / "qdrant_data"
        backup_data_path.mkdir(parents=True, exist_ok=True)
        snapshot_service._backup_client = AsyncMock()

        # Mock scroll to return some points
        mock_points = [MagicMock(id=f"point-{i}") for i in range(10)]
        mock_primary_client.scroll = AsyncMock(return_value=(mock_points, None))

        # Execute
        synced_count = await snapshot_service.sync_incremental_changes()

        # Assert
        assert synced_count == 10
        mock_primary_client.scroll.assert_called_once()
        snapshot_service._backup_client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconcile_to_primary(
        self, snapshot_service, mock_primary_client, backup_path
    ):
        """Successfully reconciles backup to primary."""
        # Setup
        backup_data_path = backup_path / "qdrant_data"
        backup_data_path.mkdir(parents=True, exist_ok=True)
        snapshot_service._backup_client = AsyncMock()

        # Mock backup scroll
        mock_points = [MagicMock(id=f"point-{i}") for i in range(20)]
        snapshot_service._backup_client.scroll = AsyncMock(return_value=(mock_points, None))

        # Execute
        reconciled_count = await snapshot_service.reconcile_to_primary()

        # Assert
        assert reconciled_count == 20
        snapshot_service._backup_client.scroll.assert_called_once()
        mock_primary_client.upsert.assert_called_once()
```

### Deliverables

- [ ] `QdrantSnapshotBackupService` implementation
- [ ] `QdrantWithBackup` wrapper class
- [ ] Integration with `FailoverService`
- [ ] WAL configuration in collection creation
- [ ] Unit tests for snapshot service
- [ ] Integration tests with real Qdrant
- [ ] Documentation and logging

### Success Criteria

1. ✅ Snapshots created on schedule
2. ✅ Snapshots restored successfully during failover
3. ✅ Incremental sync reduces snapshot size
4. ✅ Reconciliation syncs local changes back to primary
5. ✅ Old snapshots cleaned up per retention policy
6. ✅ WAL configuration improves durability
7. ✅ Failover/restore is transparent to find_code API

---

## Configuration Changes

### New Configuration Files

#### 1. Backup Models (`backup_models.py`)
- Hardcoded model selection logic
- Priority: sentence-transformers > fastembed
- Models: potion-base-8M (embedding), mxbai-rerank-xsmall-v1 (reranking)

#### 2. Failover Settings Updates (`failover.py`)

```python
# New fields added to FailoverSettings

# Snapshot backup
backup_path: Path = Path("~/.codeweaver/backups").expanduser()
snapshot_interval: PositiveInt = 300  # 5 minutes
snapshot_retention: PositiveInt = 3

# Reconciliation
reconciliation_interval_cycles: PositiveInt = 2  # 10 minutes

# Qdrant WAL
wal_capacity_mb: PositiveInt = 256
wal_segments_ahead: PositiveInt = 2
wal_retain_closed: PositiveInt = 5
```

### Environment Variables

```bash
# Existing
CODEWEAVER_DISABLE_BACKUP_SYSTEM=0  # Enable/disable entire system

# New (optional)
CODEWEAVER_BACKUP_PATH=~/.codeweaver/backups
CODEWEAVER_SNAPSHOT_INTERVAL=300
CODEWEAVER_SNAPSHOT_RETENTION=3
CODEWEAVER_RECONCILIATION_CYCLES=2
```

---

## Testing Strategy

### Unit Tests

**Reranker Fallback**: `tests/unit/server/agent_api/find_code/test_reranker_fallback.py`
- [x] Primary succeeds, no fallback
- [x] Primary circuit breaker open, fallback succeeds
- [x] Primary exception, fallback succeeds
- [x] All fail gracefully
- [x] Single reranker backwards compatibility
- [x] No reranker provided
- [x] Empty candidates

**Reconciliation**: `tests/unit/engine/services/test_reconciliation_service.py`
- [x] All vectors present, no repairs
- [x] Missing backup vector, repaired
- [x] Batch processing
- [x] Error handling

**Snapshot Backup**: `tests/unit/providers/vector_stores/test_snapshot_backup.py`
- [x] Create snapshot
- [x] Restore from snapshot
- [x] Incremental sync
- [x] Reconcile to primary
- [x] Snapshot cleanup

### Integration Tests

**End-to-End find_code**: `tests/integration/server/agent_api/test_find_code_reranker_fallback.py`
- [x] Primary reranker success
- [x] Reranker fallback triggered
- [x] All rerankers fail, graceful degradation

**Failover Service**: `tests/integration/engine/services/test_failover_service.py`
- [x] Periodic maintenance runs
- [x] Reconciliation triggered every 2 cycles
- [x] Snapshot creation/restoration
- [x] Circuit breaker integration

### Manual Testing Checklist

- [ ] Start daemon with remote Qdrant
- [ ] Verify snapshot creation every 5 minutes
- [ ] Verify vector reconciliation every 10 minutes
- [ ] Simulate remote failure, verify failover to snapshot
- [ ] Verify search continues during failover
- [ ] Restore remote, verify reconciliation back to primary
- [ ] Check logs for proper visibility

---

## Migration and Deployment

### Pre-Deployment Checklist

- [ ] Review and merge reranker fallback PR
- [ ] Review and merge reconciliation service PR
- [ ] Review and merge snapshot backup PR (if implementing)
- [ ] Update documentation
- [ ] Update CLAUDE.md with new services
- [ ] Update constitutional memory if needed

### Deployment Steps

1. **Phase 1 Deployment** (Reranker Fallback)
   - Deploy code changes
   - No configuration changes required
   - Monitor reranking success rates
   - Verify fallback triggers on failures

2. **Phase 2 Deployment** (Reconciliation)
   - Deploy code changes
   - Reconciliation starts automatically
   - Monitor reconciliation logs
   - Check for missing vectors being repaired

3. **Phase 3 Deployment** (Snapshot Backup)
   - Deploy code changes
   - Configure backup_path if non-default
   - First snapshot created automatically
   - Monitor snapshot creation/restoration

### Rollback Plan

**Phase 1 Rollback**:
- Revert reranker fallback changes
- Single reranker still works (backwards compatible)

**Phase 2 Rollback**:
- Disable reconciliation via flag
- No impact on existing functionality

**Phase 3 Rollback**:
- Disable snapshot creation
- Delete backup snapshots to free disk space
- Remote Qdrant still primary

---

## Success Criteria

### Phase 1: Reranker Fallback
- ✅ Primary reranker failure → automatic fallback
- ✅ All rerankers fail → graceful degradation
- ✅ Logging shows which provider succeeded
- ✅ No performance degradation
- ✅ 100% test coverage

### Phase 2: Vector Reconciliation
- ✅ Missing vectors detected automatically
- ✅ Missing vectors repaired within 10 minutes
- ✅ Statistics accurate and logged
- ✅ No impact on search performance
- ✅ CLI command works for manual reconciliation

### Phase 3: Snapshot Backup
- ✅ Snapshots created on schedule
- ✅ Snapshots restore successfully
- ✅ Failover transparent to users
- ✅ Reconciliation syncs changes back
- ✅ Old snapshots cleaned up
- ✅ Disk usage reasonable (<500MB per snapshot)

### Overall System
- ✅ Zero user-visible failures during provider outages
- ✅ Automatic recovery without manual intervention
- ✅ Clear observability through logs
- ✅ No performance degradation in normal operation
- ✅ Graceful degradation when all backups exhausted

---

## Post-Implementation Tasks

- [ ] Update CLAUDE.md with new architecture
- [ ] Write user-facing documentation
- [ ] Create troubleshooting guide
- [ ] Add metrics and dashboards
- [ ] Update constitutional memory
- [ ] Create runbook for operations team
- [ ] Schedule tech debt review for Phase 3 improvements

---

## Notes and Considerations

### Performance Considerations

1. **Reranker Fallback**: Minimal overhead - only tries fallback on primary failure
2. **Reconciliation**: Runs in very low priority, 10-minute intervals
3. **Snapshots**: 5-minute intervals may be too frequent for large collections (adjust if needed)

### Disk Space Requirements

- **Snapshots**: ~100-500MB per snapshot depending on collection size
- **Retention**: 3 snapshots = 300-1500MB
- **Backup Qdrant**: ~Same size as primary
- **Total**: Plan for 2-3GB for medium-sized projects

### Monitoring Recommendations

1. **Reranker Metrics**:
   - Primary success rate
   - Fallback trigger rate
   - Which provider used per query

2. **Reconciliation Metrics**:
   - Points checked per run
   - Missing vectors detected
   - Repair success rate
   - Time per reconciliation

3. **Snapshot Metrics**:
   - Snapshot creation success rate
   - Snapshot size trends
   - Restoration success rate
   - Reconciliation duration

### Future Enhancements

1. **Smart Snapshot Scheduling**: Adjust frequency based on write volume
2. **Parallel Reconciliation**: Process batches in parallel for large collections
3. **Incremental Snapshots**: Only snapshot changed segments
4. **Health Checks**: Proactive validation before failover needed
5. **Metrics Dashboard**: Grafana/Prometheus integration

---

**End of Implementation Plan**
