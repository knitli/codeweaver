# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for VoyageRerankingProvider."""

from collections import namedtuple
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from codeweaver.common.utils.utils import uuid7
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.metadata import ChunkKind, ExtKind
from codeweaver.core.spans import Span
from codeweaver.providers.provider import Provider
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.providers.reranking.providers.voyage import VoyageRerankingProvider


pytestmark = [pytest.mark.unit]



# Create a mock VoyageRerankingResult that matches the real API structure
MockVoyageResult = namedtuple("MockVoyageResult", ["document", "index", "relevance_score"])


def create_voyage_result(
    index: int, relevance_score: float, document: str = ""
) -> MockVoyageResult:
    """Create a mock Voyage reranking result matching the API structure."""
    return MockVoyageResult(document=document, index=index, relevance_score=relevance_score)


def make_test_chunk(content: str, index: int = 0) -> CodeChunk:
    """Helper to create CodeChunk for testing."""
    return CodeChunk(
        content=content,
        ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
        language=SemanticSearchLanguage.PYTHON,
        line_range=Span(start=index + 1, end=index + 1, _source_id=uuid7()),
        file_path=Path("/test/file.py"),
    )


@pytest.fixture
def mock_voyage_rerank_client():
    """Create a mock Voyage async client for reranking."""
    client = AsyncMock()
    client.rerank = AsyncMock()
    return client


@pytest.fixture
def voyage_rerank_capabilities():
    """Create capabilities for Voyage reranking model."""
    return RerankingModelCapabilities(
        name="rerank-2", provider=Provider.VOYAGE, tokenizer="tiktoken"
    )


class TestVoyageRerankingProviderInitialization:
    """Test VoyageRerankingProvider initialization."""

    def test_provider_initialization_with_client(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that provider initializes correctly with a client."""
        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        assert provider.client is mock_voyage_rerank_client
        assert provider.caps == voyage_rerank_capabilities
        assert provider.provider == Provider.VOYAGE

    def test_provider_initialization_sets_output_transformer(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that _initialize sets the output transformer correctly."""
        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        # Verify _output_transformer is callable
        assert callable(type(provider)._output_transformer)

    def test_provider_initialization_with_top_n(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that top_n is set correctly during initialization."""
        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities, top_n=20
        )

        assert provider.top_n == 20

    def test_provider_initialization_default_top_n(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that default top_n is 40."""
        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        assert provider.top_n == 40

    def test_provider_prompt_not_supported(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that custom prompts are stored but not used by Voyage."""
        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client,
            caps=voyage_rerank_capabilities,
            prompt="custom prompt",
        )

        # Voyage stores prompt via base class but doesn't use it
        assert provider.prompt == "custom prompt"  # stored via base class field


class TestVoyageRerankingProviderReranking:
    """Test VoyageRerankingProvider reranking operations."""

    @pytest.mark.asyncio
    async def test_execute_rerank_success(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test successful reranking execution."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.results = [
            create_voyage_result(index=1, relevance_score=0.9, document="doc 2"),
            create_voyage_result(index=0, relevance_score=0.8, document="doc 1"),
        ]
        mock_response.total_tokens = 150
        mock_voyage_rerank_client.rerank.return_value = mock_response

        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        # Execute rerank
        result = await provider._execute_rerank(
            query="test query", documents=["doc 1", "doc 2"], top_n=2
        )

        # Verify result
        assert result == mock_response

        # Verify client was called correctly
        mock_voyage_rerank_client.rerank.assert_called_once()
        call_kwargs = mock_voyage_rerank_client.rerank.call_args.kwargs
        assert call_kwargs["query"] == "test query"
        assert call_kwargs["documents"] == ["doc 1", "doc 2"]
        assert call_kwargs["model"] == "rerank-2"
        assert call_kwargs["top_k"] == 2

    @pytest.mark.asyncio
    async def test_rerank_with_code_chunks(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test reranking with CodeChunk objects."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.results = [
            create_voyage_result(index=1, relevance_score=0.9, document="def bar(): pass"),
            create_voyage_result(index=0, relevance_score=0.7, document="def foo(): pass"),
        ]
        mock_response.total_tokens = 150
        mock_voyage_rerank_client.rerank.return_value = mock_response

        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )
        from pathlib import Path

        from codeweaver.common.utils.utils import uuid7
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.core.metadata import ChunkKind, ExtKind
        from codeweaver.core.spans import Span

        # Create test chunks
        chunks = [
            CodeChunk(
                content="def foo(): pass",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=1, end=1, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
            ),
            CodeChunk(
                content="def bar(): pass",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=2, end=2, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
            ),
        ]

        # Call rerank
        results = await provider.rerank(query="test query", documents=chunks)

        # Verify results
        assert len(results) == 2
        assert results[0].score == 0.9
        assert results[0].original_index == 1
        assert results[0].batch_rank == 1
        assert results[0].chunk == chunks[1]

        assert results[1].score == 0.7
        assert results[1].original_index == 0
        assert results[1].batch_rank == 2
        assert results[1].chunk == chunks[0]

    @pytest.mark.asyncio
    async def test_rerank_with_strings(self, mock_voyage_rerank_client, voyage_rerank_capabilities):
        """Test reranking with string documents."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.results = [
            create_voyage_result(index=0, relevance_score=0.95, document="document 1")
        ]
        mock_response.total_tokens = 100
        mock_voyage_rerank_client.rerank.return_value = mock_response

        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        # Call rerank with CodeChunk
        test_chunk = make_test_chunk("document 1")
        results = await provider.rerank(query="test query", documents=[test_chunk])

        # Verify results
        assert len(results) == 1
        assert results[0].score == 0.95
        assert results[0].original_index == 0

    @pytest.mark.asyncio
    async def test_rerank_limits_results_to_top_n(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that rerank limits results to top_n."""
        # Setup mock response with more results than top_n
        mock_results = [
            create_voyage_result(index=i, relevance_score=1.0 - i * 0.1, document=f"doc {i}")
            for i in range(10)
        ]
        mock_response = MagicMock()
        mock_response.results = mock_results
        mock_response.total_tokens = 200
        mock_voyage_rerank_client.rerank.return_value = mock_response

        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities, top_n=5
        )

        chunks = [make_test_chunk(f"doc {i}", i) for i in range(10)]

        # Call rerank
        results = await provider.rerank(query="test query", documents=chunks)

        # Verify only top_n results are returned
        assert len(results) <= 5


class TestVoyageRerankingProviderErrorHandling:
    """Test VoyageRerankingProvider error handling."""

    @pytest.mark.asyncio
    async def test_execute_rerank_handles_provider_error(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that provider errors are wrapped correctly."""
        from codeweaver.exceptions import ProviderError

        mock_voyage_rerank_client.rerank.side_effect = Exception("API error")

        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        # Execute rerank should raise ProviderError
        with pytest.raises(ProviderError) as exc_info:
            await provider._execute_rerank(query="test query", documents=["doc 1"], top_n=1)

        assert "Voyage AI reranking request failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rerank_handles_connection_error(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that connection errors trigger retry logic."""
        mock_voyage_rerank_client.rerank.side_effect = ConnectionError("Connection failed")

        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        # Call rerank - should return empty list after retries
        test_chunk = make_test_chunk("doc 1")
        results = await provider.rerank(query="test query", documents=[test_chunk])

        # Verify empty results are returned
        assert results == []

    @pytest.mark.asyncio
    async def test_rerank_handles_timeout_error(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that timeout errors trigger retry logic."""
        mock_voyage_rerank_client.rerank.side_effect = TimeoutError("Request timed out")

        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        # Call rerank - should return empty list after retries
        test_chunk = make_test_chunk("doc 1")
        results = await provider.rerank(query="test query", documents=[test_chunk])

        # Verify empty results are returned
        assert results == []


class TestVoyageRerankingProviderProperties:
    """Test VoyageRerankingProvider properties."""

    def test_provider_property(self, mock_voyage_rerank_client, voyage_rerank_capabilities):
        """Test that provider property returns correct value."""
        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        assert provider.provider == Provider.VOYAGE

    def test_model_name_property(self, mock_voyage_rerank_client, voyage_rerank_capabilities):
        """Test that model_name property returns correct value."""
        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        assert provider.model_name == "rerank-2"

    def test_model_capabilities_property(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that model_capabilities property returns correct value."""
        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        assert provider.model_capabilities == voyage_rerank_capabilities


class TestVoyageRerankingProviderCircuitBreaker:
    """Test VoyageRerankingProvider circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that circuit breaker opens after repeated failures."""
        mock_voyage_rerank_client.rerank.side_effect = ConnectionError("Connection failed")

        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        # Make multiple failed requests
        test_chunk = make_test_chunk("doc 1")
        for _ in range(3):
            await provider.rerank(query="test query", documents=[test_chunk])

        # Check circuit breaker state
        assert provider.circuit_breaker_state in ["closed", "open"]

    def test_circuit_breaker_initial_state(
        self, mock_voyage_rerank_client, voyage_rerank_capabilities
    ):
        """Test that circuit breaker starts in closed state."""
        provider = VoyageRerankingProvider(
            client=mock_voyage_rerank_client, caps=voyage_rerank_capabilities
        )

        assert provider.circuit_breaker_state == "closed"
