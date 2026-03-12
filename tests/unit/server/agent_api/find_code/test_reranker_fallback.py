# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for reranker fallback logic in pipeline.py.

This module tests the cascading fallback mechanism in rerank_results(),
ensuring proper handling of:
- Multiple provider fallback
- Circuit breaker state management
- Provider failure handling
- Empty results handling
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from codeweaver.core import SearchStrategy
from codeweaver.providers.exceptions import CircuitBreakerOpenError
from codeweaver.server.agent_api.search.pipeline import rerank_results


if TYPE_CHECKING:
    from codeweaver.core import CodeChunk, SearchResult


@pytest.fixture
def sample_chunk():
    """Create a sample CodeChunk for testing."""
    from pathlib import Path

    from codeweaver.core import ChunkKind, CodeChunk, ExtCategory, Span, uuid7

    chunk_id = uuid7()
    return CodeChunk(
        chunk_id=chunk_id,
        ext_category=ExtCategory.from_language("python", ChunkKind.CODE),
        chunk_name="test.py:func",
        file_path=Path("test.py"),
        language="python",
        content="def test(): pass",
        line_range=Span(start=1, end=1, source_id=chunk_id),
    )


@pytest.fixture
def mock_candidates(sample_chunk: CodeChunk) -> list[SearchResult]:
    """Create mock search result candidates."""
    from pathlib import Path

    from codeweaver.core import SearchResult

    return [
        SearchResult(
            content=sample_chunk,
            file_path=Path("test/file.py"),
            score=0.9,
            dense_score=0.85,
            sparse_score=0.05,
        ),
        SearchResult(
            content=sample_chunk,
            file_path=Path("test/file.py"),
            score=0.8,
            dense_score=0.75,
            sparse_score=0.05,
        ),
    ]


@pytest.fixture
def mock_reranking_result(sample_chunk: CodeChunk):
    """Create mock reranking result."""
    from codeweaver.providers import RerankingResult

    return RerankingResult(original_index=0, batch_rank=1, score=0.95, chunk=sample_chunk)


class TestRerankResultsFallback:
    """Test suite for rerank_results fallback logic."""

    @pytest.mark.unit
    @pytest.mark.async_test
    async def test_single_provider_success(
        self, mock_candidates: list[SearchResult], mock_reranking_result
    ) -> None:
        """Test successful reranking with single provider."""
        # Setup mock provider
        mock_provider = AsyncMock()
        mock_provider.rerank.return_value = [mock_reranking_result]

        # Execute
        results, strategy = await rerank_results(
            query="test query", candidates=mock_candidates, context=None, reranking=mock_provider
        )

        # Verify
        assert results is not None
        assert len(results) > 0
        assert strategy == SearchStrategy.SEMANTIC_RERANK
        mock_provider.rerank.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.async_test
    async def test_fallback_to_second_provider(
        self, mock_candidates: list[SearchResult], mock_reranking_result
    ) -> None:
        """Test fallback when first provider fails, second succeeds."""
        # Setup mock providers
        mock_provider1 = AsyncMock()
        mock_provider1.rerank.side_effect = Exception("Provider 1 failed")

        mock_provider2 = AsyncMock()
        mock_provider2.rerank.return_value = [mock_reranking_result]

        # Execute
        results, strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=(mock_provider1, mock_provider2),
        )

        # Verify
        assert results is not None
        assert len(results) > 0
        assert strategy == SearchStrategy.SEMANTIC_RERANK
        mock_provider1.rerank.assert_called_once()
        mock_provider2.rerank.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.async_test
    async def test_circuit_breaker_fallback(
        self, mock_candidates: list[SearchResult], mock_reranking_result
    ) -> None:
        """Test fallback when first provider circuit breaker is open."""
        # Setup mock providers
        mock_provider1 = AsyncMock()
        mock_provider1.rerank.side_effect = CircuitBreakerOpenError("Circuit open")

        mock_provider2 = AsyncMock()
        mock_provider2.rerank.return_value = [mock_reranking_result]

        # Execute
        results, strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=(mock_provider1, mock_provider2),
        )

        # Verify
        assert results is not None
        assert strategy == SearchStrategy.SEMANTIC_RERANK
        mock_provider1.rerank.assert_called_once()
        mock_provider2.rerank.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.async_test
    async def test_all_providers_fail(self, mock_candidates: list[SearchResult]) -> None:
        """Test when all providers fail - should return None."""
        # Setup mock providers - all fail
        mock_provider1 = AsyncMock()
        mock_provider1.rerank.side_effect = Exception("Provider 1 failed")

        mock_provider2 = AsyncMock()
        mock_provider2.rerank.side_effect = Exception("Provider 2 failed")

        # Execute
        results, strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=(mock_provider1, mock_provider2),
        )

        # Verify - should return None when all providers fail
        assert results is None
        assert strategy is None
        mock_provider1.rerank.assert_called_once()
        mock_provider2.rerank.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.async_test
    async def test_provider_returns_empty_results(
        self, mock_candidates: list[SearchResult], mock_reranking_result
    ) -> None:
        """Test fallback when first provider returns empty results."""
        # Setup mock providers
        mock_provider1 = AsyncMock()
        mock_provider1.rerank.return_value = []  # Empty results

        mock_provider2 = AsyncMock()
        mock_provider2.rerank.return_value = [mock_reranking_result]

        # Execute
        results, strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=(mock_provider1, mock_provider2),
        )

        # Verify - should fallback to provider 2
        assert results is not None
        assert len(results) > 0
        assert strategy == SearchStrategy.SEMANTIC_RERANK
        mock_provider1.rerank.assert_called_once()
        mock_provider2.rerank.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.async_test
    async def test_metadata_preservation_through_fallback(
        self, mock_candidates: list[SearchResult], mock_reranking_result
    ) -> None:
        """Test that search metadata is preserved when using fallback provider."""
        # Setup mock providers - first fails, second succeeds
        mock_provider1 = AsyncMock()
        mock_provider1.rerank.side_effect = Exception("Provider 1 failed")

        mock_provider2 = AsyncMock()
        mock_provider2.rerank.return_value = [mock_reranking_result]

        # Execute
        results, _strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=(mock_provider1, mock_provider2),
        )

        # Verify metadata preservation
        assert results is not None
        assert len(results) > 0

        # Check that enriched results have original metadata
        enriched_result = results[0]
        assert hasattr(enriched_result, "original_score")
        assert hasattr(enriched_result, "dense_score")
        assert hasattr(enriched_result, "sparse_score")
        assert enriched_result.score == 0.95  # Reranker score
        assert enriched_result.original_score is not None  # Original metadata preserved

    @pytest.mark.unit
    @pytest.mark.async_test
    async def test_no_providers_returns_none(self, mock_candidates: list[SearchResult]) -> None:
        """Test that None is returned when no providers available."""
        # Execute with None provider
        results, strategy = await rerank_results(
            query="test query", candidates=mock_candidates, context=None, reranking=None
        )

        # Verify
        assert results is None
        assert strategy is None

    @pytest.mark.unit
    @pytest.mark.async_test
    async def test_empty_candidates_returns_none(self) -> None:
        """Test that None is returned when candidates list is empty."""
        # Setup mock provider
        mock_provider = AsyncMock()

        # Execute with empty candidates
        results, strategy = await rerank_results(
            query="test query", candidates=[], context=None, reranking=mock_provider
        )

        # Verify - provider should not be called
        assert results is None
        assert strategy is None
        mock_provider.rerank.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.async_test
    async def test_tuple_normalization_single_provider(
        self, mock_candidates: list[SearchResult], mock_reranking_result
    ) -> None:
        """Test that single provider is normalized to tuple correctly."""
        # Setup mock provider
        mock_provider = AsyncMock()
        mock_provider.rerank.return_value = [mock_reranking_result]

        # Execute with single provider (not tuple)
        results, strategy = await rerank_results(
            query="test query",
            candidates=mock_candidates,
            context=None,
            reranking=mock_provider,  # Single provider, not tuple
        )

        # Verify - should work the same as tuple with one provider
        assert results is not None
        assert strategy == SearchStrategy.SEMANTIC_RERANK
        mock_provider.rerank.assert_called_once()
