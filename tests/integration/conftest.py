# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration test fixtures for provider configuration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersRerankingProvider,
        SentenceTransformersSparseProvider,
    )

# ===========================================================================
# Mock Provider Fixtures
# ===========================================================================


@pytest.fixture
def mock_embedding_provider():
    """Provide a mock embedding provider that returns test embeddings."""
    mock_provider = AsyncMock()
    # Return batch of embeddings (list of lists)
    mock_provider.embed_query = AsyncMock(
        return_value=[[0.1, 0.2, 0.3, 0.4, 0.5]]  # Single query embedding in batch format
    )
    mock_provider.embed_batch = AsyncMock(
        return_value=[
            [0.1, 0.2, 0.3, 0.4, 0.5],  # First chunk embedding
            [0.2, 0.3, 0.4, 0.5, 0.6],  # Second chunk embedding
        ]
    )
    return mock_provider


@pytest.fixture
def actual_dense_embedding_provider() -> SentenceTransformersEmbeddingProvider:
    """Provide an actual dense embedding provider using SentenceTransformers."""
    from sentence_transformers import SentenceTransformer

    from codeweaver.providers.embedding.capabilities.ibm_granite import (
        get_ibm_granite_embedding_capabilities,
    )
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
    )

    # nice lightweight model
    caps = next(
        cap
        for cap in get_ibm_granite_embedding_capabilities()
        if cap.name == "ibm-granite/granite-embedding-english-r2"
    )
    return SentenceTransformersEmbeddingProvider(
        capabilities=caps, client=SentenceTransformer(caps.name)
    )


@pytest.fixture
def mock_sparse_provider():
    """Provide a mock sparse embedding provider."""
    mock_provider = AsyncMock()
    # Sparse embeddings in new format with indices and values
    mock_provider.embed_query = AsyncMock(
        return_value=[{"indices": [0, 2, 4], "values": [0.1, 0.3, 0.5]}]  # Sparse query embedding
    )
    mock_provider.embed_batch = AsyncMock(
        return_value=[
            {"indices": [0, 2, 4], "values": [0.1, 0.3, 0.5]},  # First sparse embedding
            {"indices": [1, 3], "values": [0.2, 0.4]},  # Second sparse embedding
        ]
    )
    return mock_provider


@pytest.fixture
def actual_sparse_embedding_provider() -> SentenceTransformersSparseProvider:
    """Provide an actual sparse embedding provider using SentenceTransformers."""
    from sentence_transformers import SparseEncoder

    from codeweaver.providers.embedding.capabilities.base import get_sparse_caps
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersSparseProvider,
    )

    cap = next(
        cap
        for cap in get_sparse_caps()
        if cap.name == "opensearch-project/opensearch-neural-sparse-encoding-doc-v2-mini"
    )
    return SentenceTransformersSparseProvider(capabilities=cap, client=SparseEncoder(cap.name))


@pytest.fixture
def mock_vector_store():
    """Provide a mock vector store that returns search results."""
    from codeweaver.common.utils.utils import uuid7
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.core.language import SemanticSearchLanguage
    from codeweaver.core.metadata import ChunkKind, ExtKind
    from codeweaver.core.spans import Span
    from codeweaver.providers.vector_stores.base import SearchResult

    mock_store = AsyncMock()

    # Create test chunks for search results
    def create_test_chunk(name: str, content: str, file_path: Path) -> CodeChunk:
        chunk_id = uuid7()
        return CodeChunk(
            chunk_id=chunk_id,
            ext_kind=ExtKind.from_language(SemanticSearchLanguage.PYTHON, ChunkKind.CODE),
            chunk_name=name,
            file_path=file_path,
            language=SemanticSearchLanguage.PYTHON,
            content=content,
            line_range=Span(start=1, end=10, _source_id=chunk_id),
        )

    # Create mock search results
    test_chunks = [
        create_test_chunk(
            "test_function", "def test_function():\n    pass", Path("tests/test_file.py")
        ),
        create_test_chunk(
            "authenticate",
            "def authenticate(user, password):\n    return True",
            Path("src/auth.py"),
        ),
    ]

    search_results = [
        SearchResult(
            content=chunk,
            file_path=chunk.file_path,
            score=0.9 - i * 0.1,
            dense_score=0.9 - i * 0.1,
            sparse_score=0.8 - i * 0.1,
            relevance_score=0.9 - i * 0.1,
        )
        for i, chunk in enumerate(test_chunks)
    ]

    mock_store.search = AsyncMock(return_value=search_results)
    return mock_store


@pytest.fixture
def mock_reranking_provider():
    """Provide a mock reranking provider."""
    from typing import NamedTuple

    # Define a simple RerankResult structure for testing
    class RerankResult(NamedTuple):
        chunk: CodeChunk
        score: float
        original_index: int

    mock_provider = AsyncMock()

    async def create_rerank_results(query: str, chunks: list[CodeChunk]) -> list[RerankResult]:
        # Create rerank results that maintain order but adjust scores
        # Note: async function to match the rerank signature
        return [
            RerankResult(chunk=chunk, score=0.95 - i * 0.05, original_index=i)
            for i, chunk in enumerate(chunks)
        ]

    mock_provider.rerank = AsyncMock(side_effect=create_rerank_results)
    return mock_provider


@pytest.fixture
def actual_reranking_provider() -> SentenceTransformersRerankingProvider:
    """Provide an actual reranking provider using SentenceTransformers."""
    from fastembed import TextEmbedding

    from codeweaver.providers.reranking.capabilities.ms_marco import (
        get_marco_reranking_capabilities,
    )

    # nice lightweight model
    caps = next(
        cap
        for cap in get_marco_reranking_capabilities()
        if cap.name == "Xenova/ms-marco-MiniLM-L6-v2"
    )
    return SentenceTransformersRerankingProvider(capabilities=caps, client=TextEmbedding(caps.name))


# ===========================================================================
# Provider Registry Configuration Fixtures
# ===========================================================================


@pytest.fixture
def mock_provider_registry(
    mock_embedding_provider, mock_sparse_provider, mock_vector_store, mock_reranking_provider
):
    """Configure mock provider registry with all providers."""
    from enum import Enum

    # Create simple mock enums for providers
    class MockProviderEnum(Enum):
        VOYAGE = "voyage"
        FASTEMBED = "fastembed"
        QDRANT = "qdrant"

    mock_registry = MagicMock()

    # Configure get_provider_enum_for to return mock provider enums
    def get_provider_enum_for(kind: str):
        if kind == "embedding":
            return MockProviderEnum.VOYAGE
        if kind == "sparse_embedding":
            return MockProviderEnum.FASTEMBED
        if kind == "vector_store":
            return MockProviderEnum.QDRANT
        if kind == "reranking":
            return MockProviderEnum.VOYAGE
        return None

    mock_registry.get_provider_enum_for = MagicMock(side_effect=get_provider_enum_for)

    # Configure get_provider_instance to return mock providers
    def get_provider_instance(enum_value, kind: str, singleton: bool = True):
        if kind == "embedding":
            return mock_embedding_provider
        if kind == "sparse_embedding":
            return mock_sparse_provider
        if kind == "vector_store":
            return mock_vector_store
        if kind == "reranking":
            return mock_reranking_provider
        return None

    mock_registry.get_provider_instance = MagicMock(side_effect=get_provider_instance)

    return mock_registry


@pytest.fixture
def configured_providers(mock_provider_registry):
    """Fixture that patches the provider registry with mock providers.

    This fixture automatically configures the provider registry for tests
    that need embedding, vector store, and reranking providers.

    Usage:
        @pytest.mark.asyncio
        async def test_something(configured_providers):
            # find_code and other functions will use mock providers
            response = await find_code("test query")
    """
    # Patch both the provider registry and time.time to ensure monotonic timing

    call_count = [0]  # Use list for mutable counter

    def mock_time():
        call_count[0] += 1
        # Return monotonically increasing time values (start from a baseline)
        return 1000000.0 + call_count[0] * 0.001

    with (
        patch(
            "codeweaver.agent_api.find_code.get_provider_registry",
            return_value=mock_provider_registry,
        ),
        patch("codeweaver.agent_api.find_code.time.time", side_effect=mock_time),
    ):
        yield mock_provider_registry


# ===========================================================================
# Settings Fixtures
# ===========================================================================


@pytest.fixture
def mock_settings_with_providers():
    """Provide mock settings with provider configuration."""
    from codeweaver.config.settings import CodeWeaverSettings as Settings

    mock_settings = MagicMock(spec=Settings)
    mock_settings.providers = {
        "embedding": {"provider": "voyage", "model": "voyage-code-2"},
        "sparse_embedding": {"provider": "fastembed", "model": "prithivida/Splade_PP_en_v1"},
        "vector_store": {"provider": "qdrant", "collection": "test_collection"},
        "reranking": {"provider": "voyage", "model": "voyage-rerank-2"},
    }
    return mock_settings
