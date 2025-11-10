# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for VoyageEmbeddingProvider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.providers.voyage import VoyageEmbeddingProvider
from codeweaver.providers.provider import Provider


@pytest.fixture
def mock_voyage_client():
    """Create a mock Voyage async client."""
    client = AsyncMock()
    client.embed = AsyncMock()
    return client


@pytest.fixture
def voyage_capabilities():
    """Create capabilities for Voyage embedding model."""
    return EmbeddingModelCapabilities(
        name="voyage-3",
        provider=Provider.VOYAGE,
        default_dimension=1024,
        default_dtype="float",
        tokenizer="tiktoken",
    )


@pytest.fixture
def voyage_context_capabilities():
    """Create capabilities for Voyage context embedding model."""
    return EmbeddingModelCapabilities(
        name="voyage-3-context",
        provider=Provider.VOYAGE,
        default_dimension=1024,
        default_dtype="float",
        tokenizer="tiktoken",
    )


class TestVoyageEmbeddingProviderInitialization:
    """Test VoyageEmbeddingProvider initialization."""

    def test_provider_initialization_with_client(self, mock_voyage_client, voyage_capabilities):
        """Test that provider initializes correctly with a client."""
        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_capabilities, kwargs=None
        )

        assert provider.client is mock_voyage_client
        assert provider.caps == voyage_capabilities
        assert provider.name == Provider.VOYAGE
        assert not provider._is_context_model

    def test_provider_initialization_with_context_model(
        self, mock_voyage_client, voyage_context_capabilities
    ):
        """Test that context models are detected during initialization."""
        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_context_capabilities, kwargs=None
        )

        assert provider._is_context_model
        assert "context" in provider.caps.name

    def test_provider_sets_doc_and_query_kwargs(self, mock_voyage_client, voyage_capabilities):
        """Test that doc_kwargs and query_kwargs are set correctly."""
        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_capabilities, kwargs=None
        )

        # Check that model name and output params are set
        assert provider.doc_kwargs["model"] == "voyage-3"
        assert provider.doc_kwargs["input_type"] == "document"
        assert provider.doc_kwargs["output_dimension"] == 1024
        assert provider.doc_kwargs["output_dtype"] == "float"

        assert provider.query_kwargs["model"] == "voyage-3"
        assert provider.query_kwargs["input_type"] == "query"
        assert provider.query_kwargs["output_dimension"] == 1024
        assert provider.query_kwargs["output_dtype"] == "float"

    def test_provider_initialization_with_custom_kwargs(
        self, mock_voyage_client, voyage_capabilities
    ):
        """Test that custom kwargs are merged correctly."""
        custom_kwargs = {"custom_param": "value"}
        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_capabilities, kwargs=custom_kwargs
        )

        assert provider.doc_kwargs["custom_param"] == "value"
        assert provider.query_kwargs["custom_param"] == "value"

    def test_provider_base_url(self, mock_voyage_client, voyage_capabilities):
        """Test that base_url property returns correct value."""
        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_capabilities, kwargs=None
        )

        assert provider.base_url == "https://api.voyageai.com/v1"


class TestVoyageEmbeddingProviderEmbedding:
    """Test VoyageEmbeddingProvider embedding operations."""

    @pytest.mark.asyncio
    async def test_embed_documents_success(self, mock_voyage_client, voyage_capabilities):
        """Test successful document embedding."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_response.total_tokens = 100
        mock_voyage_client.embed.return_value = mock_response

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_capabilities, kwargs=None
        )
        from pathlib import Path

        from codeweaver.common.utils.utils import uuid7
        from codeweaver.core.metadata import ChunkKind, ExtKind
        from codeweaver.core.spans import Span

        # Create test chunks
        chunks = [
            CodeChunk(
                content="test content 1",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=1, end=1, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
            ),
            CodeChunk(
                content="test content 2",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=2, end=2, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
            ),
        ]

        # Call embed_documents
        result = await provider.embed_documents(chunks)

        # Verify result
        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]

        # Verify client was called correctly
        mock_voyage_client.embed.assert_called_once()
        call_kwargs = mock_voyage_client.embed.call_args.kwargs
        assert "texts" in call_kwargs
        assert len(call_kwargs["texts"]) == 2
        assert call_kwargs["input_type"] == "document"
        assert call_kwargs["model"] == "voyage-3"

    @pytest.mark.asyncio
    async def test_embed_query_success(self, mock_voyage_client, voyage_capabilities):
        """Test successful query embedding."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2, 0.3]]
        mock_response.total_tokens = 50
        mock_voyage_client.embed.return_value = mock_response

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_capabilities, kwargs=None
        )

        # Call embed_query
        result = await provider.embed_query("test query")

        # Verify result
        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]

        # Verify client was called correctly
        mock_voyage_client.embed.assert_called_once()
        call_kwargs = mock_voyage_client.embed.call_args.kwargs
        assert call_kwargs["texts"] == ["test query"]
        assert call_kwargs["input_type"] == "query"
        assert call_kwargs["model"] == "voyage-3"

    @pytest.mark.asyncio
    async def test_embed_query_with_multiple_queries(self, mock_voyage_client, voyage_capabilities):
        """Test embedding multiple queries at once."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_response.total_tokens = 100
        mock_voyage_client.embed.return_value = mock_response

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_capabilities, kwargs=None
        )

        # Call embed_query with list
        result = await provider.embed_query(["query 1", "query 2"])

        # Verify result
        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]

        # Verify client was called correctly
        mock_voyage_client.embed.assert_called_once()
        call_kwargs = mock_voyage_client.embed.call_args.kwargs
        assert call_kwargs["texts"] == ["query 1", "query 2"]

    @pytest.mark.asyncio
    async def test_context_model_uses_correct_transformer(
        self, mock_voyage_client, voyage_context_capabilities
    ):
        """Test that context models use the correct output transformer."""
        # Setup mock response for context model
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(embeddings=[[0.1, 0.2, 0.3]]),
            MagicMock(embeddings=[[0.4, 0.5, 0.6]]),
        ]
        mock_response.total_tokens = 100
        mock_voyage_client.embed.return_value = mock_response

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_context_capabilities, kwargs=None
        )

        from pathlib import Path

        from codeweaver.common.utils.utils import uuid7
        from codeweaver.core.metadata import ChunkKind, ExtKind
        from codeweaver.core.spans import Span

        # Create test chunks
        chunks = [
            CodeChunk(
                content="test content 1",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=1, end=1, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
            ),
            CodeChunk(
                content="test content 2",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=2, end=2, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
            ),
        ]

        # Call embed_documents
        result = await provider.embed_documents(chunks)

        # Verify the context transformer was used
        assert isinstance(result, list)
        # Context transformer flattens nested embeddings
        assert len(result) >= 1


class TestVoyageEmbeddingProviderErrorHandling:
    """Test VoyageEmbeddingProvider error handling."""

    @pytest.mark.asyncio
    async def test_embed_documents_handles_connection_error(
        self, mock_voyage_client, voyage_capabilities
    ):
        """Test that connection errors are handled with retry logic."""
        mock_voyage_client.embed.side_effect = ConnectionError("Connection failed")

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_capabilities, kwargs=None
        )

        from pathlib import Path

        from codeweaver.common.utils.utils import uuid7
        from codeweaver.core.metadata import ChunkKind, ExtKind
        from codeweaver.core.spans import Span

        # Create test chunks
        chunks = [
            CodeChunk(
                content="test content 1",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=1, end=1, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
            ),
            CodeChunk(
                content="test content 2",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=2, end=2, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
            ),
        ]

        # Call embed_documents - should return error info
        result = await provider.embed_documents(chunks)

        # Verify we get an error info dict
        assert isinstance(result, dict)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_embed_query_handles_timeout_error(self, mock_voyage_client, voyage_capabilities):
        """Test that timeout errors are handled with retry logic."""
        mock_voyage_client.embed.side_effect = TimeoutError("Request timed out")

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_capabilities, kwargs=None
        )

        # Call embed_query - should return error info
        result = await provider.embed_query("test query")

        # Verify we get an error info dict
        assert isinstance(result, dict)
        assert "error" in result


class TestVoyageEmbeddingProviderDimension:
    """Test VoyageEmbeddingProvider dimension property."""

    def test_dimension_property_returns_correct_value(
        self, mock_voyage_client, voyage_capabilities
    ):
        """Test that dimension property returns the correct value."""
        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client, caps=voyage_capabilities, kwargs=None
        )

        assert provider.dimension == 1024

    def test_dimension_property_with_custom_dimension(self, mock_voyage_client):
        """Test dimension property with custom output_dimension."""
        caps = EmbeddingModelCapabilities(
            name="voyage-3",
            provider=Provider.VOYAGE,
            default_dimension=768,
            default_dtype="int8",
            tokenizer="tokenizers",
        )

        provider = VoyageEmbeddingProvider(client=mock_voyage_client, caps=caps, kwargs=None)

        assert provider.dimension == 768
