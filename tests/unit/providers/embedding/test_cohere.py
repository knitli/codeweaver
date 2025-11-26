# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for CohereEmbeddingProvider."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip this entire module if the cohere package is not installed
pytest.importorskip("cohere", reason="cohere package is required for these tests")

from codeweaver.core.chunks import CodeChunk
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.providers.base import EmbeddingErrorInfo
from codeweaver.providers.provider import Provider


@pytest.fixture(autouse=True)
def reset_embedding_registry():
    """Reset the global embedding registry and hash stores between tests to avoid state pollution."""
    import codeweaver.providers.embedding.registry as registry_module

    from codeweaver.providers.embedding.providers.base import EmbeddingProvider

    # Reset the global singleton registry
    registry_module._embedding_registry = None

    # Reset the class-level hash stores that handle deduplication
    EmbeddingProvider._hash_store.clear()
    EmbeddingProvider._backup_hash_store.clear()

    yield

    # Clean up after test
    registry_module._embedding_registry = None
    EmbeddingProvider._hash_store.clear()
    EmbeddingProvider._backup_hash_store.clear()


@pytest.fixture
def mock_cohere_client():
    """Create a mock Cohere async client."""
    client = AsyncMock()
    client.embed = AsyncMock()
    return client


@pytest.fixture
def cohere_capabilities():
    """Create capabilities for Cohere embedding model."""
    return EmbeddingModelCapabilities(
        name="embed-english-v3.0",
        provider=Provider.COHERE,
        default_dimension=1024,
        default_dtype="float",
        tokenizer=None,  # No tokenizer to avoid HuggingFace lookups in tests
    )


@pytest.fixture
def cohere_4_capabilities():
    """Create capabilities for Cohere v4 embedding model."""
    return EmbeddingModelCapabilities(
        name="embed-english-v4.0",
        provider=Provider.COHERE,
        default_dimension=1024,
        default_dtype="float",
        tokenizer=None,  # No tokenizer to avoid HuggingFace lookups in tests
    )


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestCohereEmbeddingProviderInitialization:
    """Test CohereEmbeddingProvider initialization."""

    @patch.dict("os.environ", {"COHERE_API_KEY": "test-api-key"})
    def test_provider_initialization_with_env_api_key(self, cohere_capabilities):
        """Test that provider initializes with API key from environment."""
        from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider

        provider = CohereEmbeddingProvider(caps=cohere_capabilities)

        assert provider.caps == cohere_capabilities
        assert provider.client is not None
        assert provider.name == Provider.COHERE

    @patch.dict("os.environ", {}, clear=True)
    def test_provider_initialization_without_api_key_raises_error(self, cohere_capabilities):
        """Test that provider raises error without API key."""
        from codeweaver.exceptions import ConfigurationError
        from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider

        with pytest.raises(ConfigurationError) as exc_info:
            CohereEmbeddingProvider(caps=cohere_capabilities)

        assert "API key not found" in str(exc_info.value)

    def test_provider_initialization_with_client(self, mock_cohere_client, cohere_capabilities):
        """Test that provider initializes correctly with a provided client."""
        from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider

        provider = CohereEmbeddingProvider(caps=cohere_capabilities, _client=mock_cohere_client)

        assert provider.client is mock_cohere_client
        assert provider.caps == cohere_capabilities

    @patch.dict("os.environ", {"COHERE_API_KEY": "test-api-key"})
    def test_provider_initialization_with_custom_kwargs(self, cohere_capabilities):
        """Test that custom kwargs are stored correctly."""
        from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider

        provider = CohereEmbeddingProvider(caps=cohere_capabilities, custom_param="value")

        assert "custom_param" in provider.doc_kwargs
        assert provider.doc_kwargs["custom_param"] == "value"

    @patch.dict("os.environ", {"COHERE_API_KEY": "test-api-key"})
    def test_provider_base_url_cohere(self, cohere_capabilities):
        """Test that base_url property returns correct value for Cohere."""
        from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider

        provider = CohereEmbeddingProvider(caps=cohere_capabilities)

        assert provider.base_url == "https://api.cohere.com"

    @patch.dict("os.environ", {"AZURE_COHERE_API_KEY": "test-api-key"})
    def test_provider_initialization_azure_provider(self):
        """Test that Azure provider is supported."""
        from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider

        caps = EmbeddingModelCapabilities(
            name="embed-english-v3.0",
            provider=Provider.AZURE,
            default_dimension=1024,
            default_dtype="float",
            tokenizer="tiktoken",
        )

        provider = CohereEmbeddingProvider(
            caps=caps, endpoint="test-endpoint", region_name="eastus"
        )

        assert provider.caps.provider == Provider.AZURE


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestCohereEmbeddingProviderEmbedding:
    """Test CohereEmbeddingProvider embedding operations."""

    @pytest.mark.asyncio
    async def test_embed_documents_success(self, mock_cohere_client, cohere_capabilities):
        """Test successful document embedding."""
        from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider

        # Setup mock response with correct dimension (1024)
        mock_embeddings = MagicMock()
        mock_embeddings.float = [
            [0.1] * 1024,
            [0.2] * 1024,
        ]  # Two embeddings with 1024 dimensions each

        mock_response = MagicMock()
        mock_response.embeddings = mock_embeddings
        mock_response.meta = MagicMock()
        mock_response.meta.tokens = MagicMock()
        mock_response.meta.tokens.output_tokens = 100
        mock_response.meta.tokens.input_tokens = None

        mock_cohere_client.embed.return_value = mock_response

        provider = CohereEmbeddingProvider(caps=cohere_capabilities, _client=mock_cohere_client)
        from codeweaver.common.utils.utils import uuid7
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.core.metadata import ChunkKind, ExtKind
        from codeweaver.core.spans import Span

        # Create test chunks with explicit chunk_ids
        chunks = [
            CodeChunk(
                content="test content 1",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=1, end=1, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
                chunk_id=uuid7(),
            ),
            CodeChunk(
                content="test content 2",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=2, end=2, _source_id=uuid7()),
                file_path=Path("/test/file.py"),
                chunk_id=uuid7(),
            ),
        ]

        # Call embed_documents
        result = await provider.embed_documents(chunks)

        # Verify result
        assert len(result) == 2
        assert result is not EmbeddingErrorInfo
        assert len(result[0]) == 1024
        assert len(result[1]) == 1024
        assert result[0][0] == 0.1  # Check first element of first embedding
        assert result[1][0] == 0.2  # Check first element of second embedding

        # Verify client was called
        mock_cohere_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_query_success(self, mock_cohere_client, cohere_capabilities):
        """Test successful query embedding."""
        from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider

        # Setup mock response
        mock_embeddings = MagicMock()
        mock_embeddings.float = [[0.1, 0.2, 0.3]]

        mock_response = MagicMock()
        mock_response.embeddings = mock_embeddings
        mock_response.meta = MagicMock()
        mock_response.meta.tokens = MagicMock()
        mock_response.meta.tokens.output_tokens = 50
        mock_response.meta.tokens.input_tokens = None

        mock_cohere_client.embed.return_value = mock_response

        provider = CohereEmbeddingProvider(caps=cohere_capabilities, _client=mock_cohere_client)

        # Call embed_query
        result = await provider.embed_query("test query")

        # Verify result
        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]  # ty: ignore[invalid-key]

        # Verify client was called
        mock_cohere_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_documents_v4_model(self, mock_cohere_client, cohere_4_capabilities):
        """Test embedding with v4.0 model uses correct embedding_types."""
        from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider

        # Setup mock response - use capabilities dimension for consistency
        expected_dimension = cohere_4_capabilities.default_dimension
        mock_embeddings = MagicMock()
        mock_embeddings.float = [[0.1] * expected_dimension]

        mock_response = MagicMock()
        mock_response.embeddings = mock_embeddings
        mock_response.meta = None

        mock_cohere_client.embed.return_value = mock_response

        provider = CohereEmbeddingProvider(caps=cohere_4_capabilities, _client=mock_cohere_client)

        from pathlib import Path

        from codeweaver.common.utils.utils import uuid7
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.core.metadata import ChunkKind, ExtKind
        from codeweaver.core.spans import Span

        chunks = [
            CodeChunk(
                content="test content",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=1, end=1, _source_id=uuid7()),
                start_line=1,
                end_line=1,
                file_path=Path("/test/file.py"),
                chunk_id=uuid7(),
            )
        ]

        # Call embed_documents
        result = await provider.embed_documents(chunks)

        # Verify result
        assert len(result) == 1

        # Verify embedding_types was set for v4.0 model
        call_kwargs = mock_cohere_client.embed.call_args.kwargs
        assert "embedding_types" in call_kwargs
        assert call_kwargs["embedding_types"] == ["float"]


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestCohereEmbeddingProviderErrorHandling:
    """Test CohereEmbeddingProvider error handling."""

    @pytest.mark.asyncio
    async def test_embed_documents_handles_connection_error(
        self, mock_cohere_client, cohere_capabilities
    ):
        """Test that connection errors are handled with retry logic."""
        from codeweaver.providers.embedding.providers.cohere import CohereEmbeddingProvider

        mock_cohere_client.embed.side_effect = ConnectionError("Connection failed")

        provider = CohereEmbeddingProvider(caps=cohere_capabilities, _client=mock_cohere_client)
        from pathlib import Path

        from codeweaver.common.utils.utils import uuid7
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.core.metadata import ChunkKind, ExtKind
        from codeweaver.core.spans import Span

        chunks = [
            CodeChunk(
                content="test content",
                ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=1, end=1, _source_id=uuid7()),
                start_line=1,
                end_line=1,
                file_path=Path("/test/file.py"),
                chunk_id=uuid7(),
            )
        ]

        # Call embed_documents - should return error info
        result = await provider.embed_documents(chunks)

        # Verify we get an error info dict
        assert isinstance(result, dict)
        assert "error" in result
