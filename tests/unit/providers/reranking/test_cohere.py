# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for CohereRerankingProvider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codeweaver.core.chunks import CodeChunk
from codeweaver.providers.provider import Provider
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


@pytest.fixture
def mock_cohere_rerank_client():
    """Create a mock Cohere async client for reranking."""
    client = AsyncMock()
    client.rerank = AsyncMock()
    return client


@pytest.fixture
def cohere_rerank_capabilities():
    """Create capabilities for Cohere reranking model."""
    return RerankingModelCapabilities(
        name="rerank-english-v3.0", provider=Provider.COHERE, tokenizer="tiktoken"
    )


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestCohereRerankingProviderInitialization:
    """Test CohereRerankingProvider initialization."""

    @patch.dict("os.environ", {"COHERE_API_KEY": "test-api-key"})
    def test_provider_initialization_with_env_api_key(self, cohere_rerank_capabilities):
        """Test that provider initializes with API key from environment."""
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        provider = CohereRerankingProvider(caps=cohere_rerank_capabilities)

        assert provider.caps == cohere_rerank_capabilities
        assert provider.client is not None
        assert provider._provider == Provider.COHERE

    @patch.dict("os.environ", {}, clear=True)
    def test_provider_initialization_without_api_key_raises_error(self, cohere_rerank_capabilities):
        """Test that provider raises error without API key."""
        from codeweaver.exceptions import ConfigurationError
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        with pytest.raises(ConfigurationError) as exc_info:
            CohereRerankingProvider(caps=cohere_rerank_capabilities)

        assert "API key not found" in str(exc_info.value)

    def test_provider_initialization_with_client(
        self, mock_cohere_rerank_client, cohere_rerank_capabilities
    ):
        """Test that provider initializes correctly with a provided client."""
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        provider = CohereRerankingProvider(
            caps=cohere_rerank_capabilities, client=mock_cohere_rerank_client
        )

        assert provider.client is mock_cohere_rerank_client
        assert provider.caps == cohere_rerank_capabilities

    def test_provider_initialization_with_top_n(
        self, mock_cohere_rerank_client, cohere_rerank_capabilities
    ):
        """Test that top_n is set correctly during initialization."""
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        provider = CohereRerankingProvider(
            caps=cohere_rerank_capabilities, client=mock_cohere_rerank_client, top_n=25
        )

        assert provider.top_n == 25

    def test_provider_base_url(self, mock_cohere_rerank_client, cohere_rerank_capabilities):
        """Test that base_url property returns correct value."""
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        provider = CohereRerankingProvider(
            caps=cohere_rerank_capabilities, client=mock_cohere_rerank_client
        )

        assert provider.base_url == "https://api.cohere.com"


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestCohereRerankingProviderReranking:
    """Test CohereRerankingProvider reranking operations."""

    @pytest.mark.asyncio
    async def test_execute_rerank_success(
        self, mock_cohere_rerank_client, cohere_rerank_capabilities
    ):
        """Test successful reranking execution."""
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        # Setup mock response
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(index=1, relevance_score=0.95),
            MagicMock(index=0, relevance_score=0.85),
        ]
        mock_response.meta = MagicMock()
        mock_response.meta.tokens = MagicMock()
        mock_response.meta.tokens.output_tokens = 150
        mock_response.meta.tokens.input_tokens = None

        mock_cohere_rerank_client.rerank.return_value = mock_response

        provider = CohereRerankingProvider(
            caps=cohere_rerank_capabilities, client=mock_cohere_rerank_client
        )

        # Execute rerank
        result = await provider._execute_rerank(
            query="test query", documents=["doc 1", "doc 2"], top_n=2
        )

        # Verify result
        assert result == mock_response

        # Verify client was called correctly
        mock_cohere_rerank_client.rerank.assert_called_once()
        call_kwargs = mock_cohere_rerank_client.rerank.call_args.kwargs
        assert call_kwargs["query"] == "test query"
        assert call_kwargs["documents"] == ["doc 1", "doc 2"]
        assert call_kwargs["top_n"] == 2

    @pytest.mark.asyncio
    async def test_rerank_with_code_chunks(
        self, mock_cohere_rerank_client, cohere_rerank_capabilities
    ):
        """Test reranking with CodeChunk objects."""
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        # Setup mock response
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(index=1, relevance_score=0.92),
            MagicMock(index=0, relevance_score=0.78),
        ]
        mock_response.meta = MagicMock()
        mock_response.meta.tokens = MagicMock()
        mock_response.meta.tokens.output_tokens = 150
        mock_response.meta.tokens.input_tokens = None

        mock_cohere_rerank_client.rerank.return_value = mock_response

        provider = CohereRerankingProvider(
            caps=cohere_rerank_capabilities, client=mock_cohere_rerank_client
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
                language=SemanticSearchLanguage.PYTHON,
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                line_range=Span(start=2, end=2, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
            ),
        ]

        # Call rerank
        results = await provider.rerank(query="test query", documents=chunks)

        # Verify results are returned in order by score
        assert len(results) == 2
        assert results[0].score == 0.92
        assert results[0].original_index == 1
        assert results[0].batch_rank == 1
        assert results[0].chunk == chunks[1]

        assert results[1].score == 0.78
        assert results[1].original_index == 0
        assert results[1].batch_rank == 2
        assert results[1].chunk == chunks[0]

    @pytest.mark.asyncio
    async def test_process_cohere_output_with_tokens(
        self, mock_cohere_rerank_client, cohere_rerank_capabilities
    ):
        """Test that process_cohere_output correctly handles token counts."""
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        # Setup mock response
        mock_response = MagicMock()
        mock_response.results = [MagicMock(index=0, relevance_score=0.9)]
        mock_response.meta = MagicMock()
        mock_response.meta.tokens = MagicMock()
        mock_response.meta.tokens.output_tokens = 100
        mock_response.meta.tokens.input_tokens = None

        provider = CohereRerankingProvider(
            caps=cohere_rerank_capabilities, client=mock_cohere_rerank_client
        )
        from pathlib import Path

        from codeweaver.core.metadata import ChunkKind, ExtKind

        from codeweaver.common.utils.utils import uuid7
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.core.spans import Span

        chunks = (
            CodeChunk(
                content="test content",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=1, end=1, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
            ),
        )

        # Process output
        results = provider.process_cohere_output(mock_response, chunks)

        # Verify results
        assert len(results) == 1
        assert results[0].score == 0.9
        assert results[0].original_index == 0
        assert results[0].chunk == chunks[0]


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestCohereRerankingProviderErrorHandling:
    """Test CohereRerankingProvider error handling."""

    @pytest.mark.asyncio
    async def test_rerank_handles_connection_error(
        self, mock_cohere_rerank_client, cohere_rerank_capabilities
    ):
        """Test that connection errors trigger retry logic."""
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        mock_cohere_rerank_client.rerank.side_effect = ConnectionError("Connection failed")

        provider = CohereRerankingProvider(
            caps=cohere_rerank_capabilities, client=mock_cohere_rerank_client
        )

        # Call rerank - should return empty list after retries
        results = await provider.rerank(query="test query", documents=["doc 1"])

        # Verify empty results are returned
        assert results == []

    @pytest.mark.asyncio
    async def test_rerank_handles_timeout_error(
        self, mock_cohere_rerank_client, cohere_rerank_capabilities
    ):
        """Test that timeout errors trigger retry logic."""
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        mock_cohere_rerank_client.rerank.side_effect = TimeoutError("Request timed out")

        provider = CohereRerankingProvider(
            caps=cohere_rerank_capabilities, client=mock_cohere_rerank_client
        )

        # Call rerank - should return empty list after retries
        results = await provider.rerank(query="test query", documents=["doc 1"])

        # Verify empty results are returned
        assert results == []


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestCohereRerankingProviderProperties:
    """Test CohereRerankingProvider properties."""

    def test_provider_property(self, mock_cohere_rerank_client, cohere_rerank_capabilities):
        """Test that provider property returns correct value."""
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        provider = CohereRerankingProvider(
            caps=cohere_rerank_capabilities, client=mock_cohere_rerank_client
        )

        assert provider.provider == Provider.COHERE

    def test_model_name_property(self, mock_cohere_rerank_client, cohere_rerank_capabilities):
        """Test that model_name property returns correct value."""
        from codeweaver.providers.reranking.providers.cohere import CohereRerankingProvider

        provider = CohereRerankingProvider(
            caps=cohere_rerank_capabilities, client=mock_cohere_rerank_client
        )

        assert provider.model_name == "rerank-english-v3.0"
