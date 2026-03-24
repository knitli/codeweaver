# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for VoyageEmbeddingProvider."""

from unittest.mock import AsyncMock, MagicMock

import pytest


# Guard against voyageai import failures. On Python 3.14+ the pydantic v1 incompatibility
# raises ValueError (not ImportError), so this must come before any codeweaver.providers
# import that loads the Voyage provider module. The whole module is skipped at collection
# time rather than crashing pytest with INTERNALERROR.
try:
    import voyageai  # noqa: F401
except Exception:
    pytest.skip(
        "voyageai not available or incompatible with this Python version", allow_module_level=True
    )

from codeweaver.core import CodeChunk, ExtCategory, Provider, SemanticSearchLanguage
from codeweaver.providers import (
    EmbeddingErrorInfo,
    EmbeddingModelCapabilities,
    VoyageEmbeddingProvider,
)


pytestmark = [pytest.mark.unit, pytest.mark.requires_voyageai]


@pytest.fixture(autouse=True)
def reset_embedding_registry():
    """Reset the global embedding registry between tests to avoid state pollution.

    Note: EmbeddingCacheManager is now responsible for hash stores and deduplication.
    This fixture only needs to reset the global registry singleton.
    """
    import codeweaver.providers as registry_module

    # Reset the global singleton registry
    registry_module._embedding_registry = None

    yield

    # Clean up after test
    registry_module._embedding_registry = None


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
        tokenizer=None,  # No tokenizer to avoid tiktoken lookups in tests
    )


@pytest.fixture
def voyage_context_capabilities():
    """Create capabilities for Voyage context embedding model."""
    return EmbeddingModelCapabilities(
        name="voyage-3-context",
        provider=Provider.VOYAGE,
        default_dimension=1024,
        default_dtype="float",
        tokenizer=None,  # No tokenizer to avoid HuggingFace lookups in tests
    )


@pytest.fixture
def mock_voyage_config():
    """Create a config for Voyage embedding provider."""
    from codeweaver.providers import EmbeddingProviderSettings
    from codeweaver.providers.config import VoyageEmbeddingConfig

    embedding_config = VoyageEmbeddingConfig(
        tag="voyage", provider=Provider.VOYAGE, model_name="voyage-3"
    )

    return EmbeddingProviderSettings(
        provider=Provider.VOYAGE, model_name="voyage-3", embedding_config=embedding_config
    )


@pytest.fixture
def mock_embedding_registry():
    """Create a mock embedding registry."""
    from codeweaver.providers.embedding.registry import EmbeddingRegistry

    registry = MagicMock(spec=EmbeddingRegistry)
    registry.get = MagicMock(return_value=None)
    registry.add = MagicMock()
    return registry


@pytest.fixture
def mock_cache_manager(mock_embedding_registry):
    """Create a mock cache manager."""
    from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager

    return EmbeddingCacheManager(registry=mock_embedding_registry)


class TestVoyageEmbeddingProviderInitialization:
    """Test VoyageEmbeddingProvider initialization."""

    def test_provider_initialization_with_client(
        self,
        mock_cache_manager,
        mock_voyage_client,
        mock_voyage_config,
        mock_embedding_registry,
        voyage_capabilities,
    ):
        """Test that provider initializes correctly with a client."""
        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client,
            config=mock_voyage_config,
            registry=mock_embedding_registry,
            caps=voyage_capabilities,
            cache_manager=mock_cache_manager,
        )

        assert provider.client is mock_voyage_client
        assert provider.caps == voyage_capabilities
        assert provider.name == Provider.VOYAGE
        assert not provider._is_context_model

    def test_provider_initialization_with_context_model(
        self,
        mock_cache_manager,
        mock_voyage_client,
        mock_voyage_config,
        mock_embedding_registry,
        voyage_context_capabilities,
    ):
        """Test that context models are detected during initialization."""
        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client,
            config=mock_voyage_config,
            registry=mock_embedding_registry,
            caps=voyage_context_capabilities,
            cache_manager=mock_cache_manager,
        )

        assert provider._is_context_model
        assert "context" in provider.caps.name

    def test_provider_sets_doc_andquery_options(
        self,
        mock_cache_manager,
        mock_voyage_client,
        mock_voyage_config,
        mock_embedding_registry,
        voyage_capabilities,
    ):
        """Test that embed_options and query_options are set correctly."""
        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client,
            config=mock_voyage_config,
            registry=mock_embedding_registry,
            caps=voyage_capabilities,
            cache_manager=mock_cache_manager,
        )

        # Check that model name and output params are set
        assert provider.embed_options["model"] == "voyage-3"
        assert provider.embed_options["input_type"] == "document"
        assert provider.embed_options["output_dimension"] == 1024
        # VoyageEmbeddingConfig._get_datatype() returns "uint8" as the default
        assert provider.embed_options["output_dtype"] == "uint8"

        assert provider.query_options["model"] == "voyage-3"
        assert provider.query_options["input_type"] == "query"
        assert provider.query_options["output_dimension"] == 1024
        # VoyageEmbeddingConfig._get_datatype() returns "uint8" as the default
        assert provider.query_options["output_dtype"] == "uint8"

    def test_provider_base_url(
        self,
        mock_cache_manager,
        mock_voyage_client,
        mock_voyage_config,
        mock_embedding_registry,
        voyage_capabilities,
    ):
        """Test that base_url property returns correct value."""
        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client,
            config=mock_voyage_config,
            registry=mock_embedding_registry,
            caps=voyage_capabilities,
            cache_manager=mock_cache_manager,
        )

        assert provider.base_url == "https://api.voyageai.com/v1"


class TestVoyageEmbeddingProviderEmbedding:
    """Test VoyageEmbeddingProvider embedding operations."""

    @pytest.mark.asyncio
    async def test_embed_documents_success(
        self,
        mock_cache_manager,
        mock_voyage_client,
        mock_voyage_config,
        mock_embedding_registry,
        voyage_capabilities,
    ):
        """Test successful document embedding."""
        # Setup mock response with correct dimension (1024)
        mock_response = MagicMock()
        mock_response.embeddings = [
            [0.1] * 1024,
            [0.2] * 1024,
        ]  # Two embeddings with 1024 dimensions each
        mock_response.total_tokens = 100
        mock_voyage_client.embed.return_value = mock_response

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client,
            config=mock_voyage_config,
            registry=mock_embedding_registry,
            caps=voyage_capabilities,
            cache_manager=mock_cache_manager,
        )
        from pathlib import Path

        from codeweaver.core import ChunkKind, ExtCategory, Span, uuid7

        # Create test chunks
        chunks = [
            CodeChunk(
                content="test content 1",
                ext_category=ExtCategory(
                    language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE
                ),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=1, end=1, source_id=uuid7()),
                file_path=Path("/test/file.py"),
                chunk_id=uuid7(),
            ),
            CodeChunk(
                content="test content 2",
                ext_category=ExtCategory(
                    language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE
                ),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=2, end=2, source_id=uuid7()),
                file_path=Path("/test/file.py"),
                chunk_id=uuid7(),
            ),
        ]

        # Call embed_documents
        result = await provider.embed_documents(chunks)

        # Verify result
        assert result is not EmbeddingErrorInfo
        assert len(result) == 2
        assert len(result[0]) == 1024  # ty: ignore[invalid-key]
        assert len(result[1]) == 1024  # ty: ignore[invalid-key]
        assert result[0][0] == 0.1  # ty:ignore[invalid-key]
        assert result[1][0] == 0.2  # ty:ignore[invalid-key]

        # Verify client was called correctly
        mock_voyage_client.embed.assert_called_once()
        call_kwargs = mock_voyage_client.embed.call_args.kwargs
        assert "texts" in call_kwargs
        assert len(call_kwargs["texts"]) == 2
        assert call_kwargs["input_type"] == "document"
        assert call_kwargs["model"] == "voyage-3"

    @pytest.mark.asyncio
    async def test_embed_query_success(
        self,
        mock_cache_manager,
        mock_voyage_client,
        mock_voyage_config,
        mock_embedding_registry,
        voyage_capabilities,
    ):
        """Test successful query embedding."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2, 0.3]]
        mock_response.total_tokens = 50
        mock_voyage_client.embed.return_value = mock_response

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client,
            config=mock_voyage_config,
            registry=mock_embedding_registry,
            caps=voyage_capabilities,
            cache_manager=mock_cache_manager,
        )

        # Call embed_query
        result = await provider.embed_query("test query")

        # Verify result
        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]  # ty: ignore[invalid-key]

        # Verify client was called correctly
        mock_voyage_client.embed.assert_called_once()
        call_kwargs = mock_voyage_client.embed.call_args.kwargs
        assert call_kwargs["texts"] == ["test query"]
        assert call_kwargs["input_type"] == "query"
        assert call_kwargs["model"] == "voyage-3"

    @pytest.mark.asyncio
    async def test_embed_query_with_multiple_queries(
        self,
        mock_cache_manager,
        mock_voyage_client,
        mock_voyage_config,
        mock_embedding_registry,
        voyage_capabilities,
    ):
        """Test embedding multiple queries at once."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_response.total_tokens = 100
        mock_voyage_client.embed.return_value = mock_response

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client,
            config=mock_voyage_config,
            registry=mock_embedding_registry,
            caps=voyage_capabilities,
            cache_manager=mock_cache_manager,
        )

        # Call embed_query with list
        result = await provider.embed_query(["query 1", "query 2"])

        # Verify result
        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]  # ty: ignore[invalid-key]
        assert result[1] == [0.4, 0.5, 0.6]  # ty: ignore[invalid-key]

        # Verify client was called correctly
        mock_voyage_client.embed.assert_called_once()
        call_kwargs = mock_voyage_client.embed.call_args.kwargs
        assert call_kwargs["texts"] == ["query 1", "query 2"]

    @pytest.mark.asyncio
    async def test_context_model_uses_correct_transformer(
        self,
        mock_cache_manager,
        mock_voyage_client,
        mock_voyage_config,
        mock_embedding_registry,
        voyage_context_capabilities,
    ):
        """Test that context models use the correct output transformer."""
        # Setup mock response for context model
        # For simplicity, mock results to directly return 2D embeddings like non-context models
        # The key test is that _is_context_model is True and the context transformer is used
        mock_response = MagicMock()
        # Make results attribute return a simple 2D embedding list when accessed by transformer
        # This works around the complex flattening logic for testing purposes
        mock_response.results = []

        # Mock the transformer to return correct format directly
        def mock_transformer(result):
            return [[0.1] * 1024, [0.2] * 1024]

        # Monkey-patch the transformer for this test
        from codeweaver.providers.embedding.providers import voyage as voyage_module

        original_transformer = voyage_module.voyage_context_output_transformer
        voyage_module.voyage_context_output_transformer = mock_transformer

        try:
            provider = VoyageEmbeddingProvider(
                client=mock_voyage_client,
                config=mock_voyage_config,
                registry=mock_embedding_registry,
                caps=voyage_context_capabilities,
                cache_manager=mock_cache_manager,
            )

            from pathlib import Path

            from codeweaver.core import ChunkKind, Span, uuid7

            # Create test chunks
            chunks = [
                CodeChunk(
                    content="test content 1",
                    ext_category=ExtCategory(
                        language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE
                    ),
                    language=SemanticSearchLanguage.PYTHON,
                    line_range=Span(start=1, end=1, source_id=uuid7()),
                    file_path=Path("/test/file.py"),
                    chunk_id=uuid7(),
                ),
                CodeChunk(
                    content="test content 2",
                    ext_category=ExtCategory(
                        language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE
                    ),
                    language=SemanticSearchLanguage.PYTHON,
                    line_range=Span(start=2, end=2, source_id=uuid7()),
                    file_path=Path("/test/file.py"),
                    chunk_id=uuid7(),
                ),
            ]

            # Call embed_documents
            result = await provider.embed_documents(chunks)

            # Verify the context transformer was used (via _is_context_model flag)
            assert provider._is_context_model is True

            # Verify correct structure and dimensions
            assert isinstance(result, list)
            assert len(result) == 2
            assert len(result[0]) == 1024
            assert len(result[1]) == 1024
            assert result[0][0] == 0.1
            assert result[1][0] == 0.2
        finally:
            # Restore original transformer
            voyage_module.voyage_context_output_transformer = original_transformer


class TestVoyageEmbeddingProviderErrorHandling:
    """Test VoyageEmbeddingProvider error handling."""

    @pytest.mark.asyncio
    async def test_embed_documents_handles_connection_error(
        self,
        mock_cache_manager,
        mock_voyage_client,
        mock_voyage_config,
        mock_embedding_registry,
        voyage_capabilities,
    ):
        """Test that connection errors are handled with retry logic."""
        mock_voyage_client.embed.side_effect = ConnectionError("Connection failed")

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client,
            config=mock_voyage_config,
            registry=mock_embedding_registry,
            caps=voyage_capabilities,
            cache_manager=mock_cache_manager,
        )

        from pathlib import Path

        from codeweaver.core import ChunkKind, ExtCategory, Span, uuid7

        # Create test chunks
        chunks = [
            CodeChunk(
                content="test content 1",
                ext_category=ExtCategory(
                    language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE
                ),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=1, end=1, source_id=uuid7()),
                file_path=Path("/test/file.py"),
                chunk_id=uuid7(),
            ),
            CodeChunk(
                content="test content 2",
                ext_category=ExtCategory(
                    language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE
                ),
                language=SemanticSearchLanguage.PYTHON,
                line_range=Span(start=2, end=2, source_id=uuid7()),
                file_path=Path("/test/file.py"),
                chunk_id=uuid7(),
            ),
        ]

        # Call embed_documents - should return error info
        result = await provider.embed_documents(chunks)

        # Verify we get an error info dict
        assert isinstance(result, dict)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_embed_query_handles_timeout_error(
        self,
        mock_cache_manager,
        mock_voyage_client,
        mock_voyage_config,
        mock_embedding_registry,
        voyage_capabilities,
    ):
        """Test that timeout errors are handled with retry logic."""
        mock_voyage_client.embed.side_effect = TimeoutError("Request timed out")

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client,
            config=mock_voyage_config,
            registry=mock_embedding_registry,
            caps=voyage_capabilities,
            cache_manager=mock_cache_manager,
        )

        # Call embed_query - should return error info
        result = await provider.embed_query("test query")

        # Verify we get an error info dict
        assert isinstance(result, dict)
        assert "error" in result


class TestVoyageEmbeddingProviderDimension:
    """Test VoyageEmbeddingProvider dimension property."""

    def test_dimension_property_returns_correct_value(
        self,
        mock_cache_manager,
        mock_voyage_client,
        mock_voyage_config,
        mock_embedding_registry,
        voyage_capabilities,
    ):
        """Test that dimension property returns the correct value."""
        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client,
            config=mock_voyage_config,
            registry=mock_embedding_registry,
            caps=voyage_capabilities,
            cache_manager=mock_cache_manager,
        )

        assert provider.dimension == 1024

    def test_dimension_property_with_custom_dimension(
        self, mock_voyage_client, mock_embedding_registry, mock_cache_manager
    ):
        """Test dimension property with custom output_dimension."""
        from codeweaver.providers import EmbeddingProviderSettings
        from codeweaver.providers.config import VoyageEmbeddingConfig

        caps = EmbeddingModelCapabilities(
            name="voyage-3",
            provider=Provider.VOYAGE,
            default_dimension=768,
            default_dtype="int8",
            tokenizer="tokenizers",
        )

        # Create config with explicit dimension in embedding dict to override the 1024 default
        embedding_config = VoyageEmbeddingConfig(
            tag="voyage",
            provider=Provider.VOYAGE,
            model_name="voyage-3",
            embedding={"output_dimension": 768},
            query={"output_dimension": 768},
        )

        config = EmbeddingProviderSettings(
            provider=Provider.VOYAGE, model_name="voyage-3", embedding_config=embedding_config
        )

        provider = VoyageEmbeddingProvider(
            client=mock_voyage_client,
            config=config,
            registry=mock_embedding_registry,
            caps=caps,
            cache_manager=mock_cache_manager,
        )

        assert provider.dimension == 768
