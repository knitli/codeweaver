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
def mock_sparse_provider():
    """Provide a mock sparse embedding provider."""
    mock_provider = AsyncMock()
    # Sparse embeddings in batch format
    mock_provider.embed_query = AsyncMock(
        return_value=[[0.1, 0.0, 0.3, 0.0, 0.5]]  # Sparse query embedding
    )
    mock_provider.embed_batch = AsyncMock(
        return_value=[
            [0.1, 0.0, 0.3, 0.0, 0.5],  # First sparse embedding
            [0.0, 0.2, 0.0, 0.4, 0.0],  # Second sparse embedding
        ]
    )
    return mock_provider


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
            "test_function",
            "def test_function():\n    pass",
            Path("tests/test_file.py"),
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
            RerankResult(
                chunk=chunk,
                score=0.95 - i * 0.05,
                original_index=i,
            )
            for i, chunk in enumerate(chunks)
        ]

    mock_provider.rerank = AsyncMock(side_effect=create_rerank_results)
    return mock_provider


# ===========================================================================
# Provider Registry Configuration Fixtures
# ===========================================================================


@pytest.fixture
def mock_provider_registry(
    mock_embedding_provider,
    mock_sparse_provider,
    mock_vector_store,
    mock_reranking_provider,
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
        elif kind == "sparse_embedding":
            return MockProviderEnum.FASTEMBED
        elif kind == "vector_store":
            return MockProviderEnum.QDRANT
        elif kind == "reranking":
            return MockProviderEnum.VOYAGE
        return None

    mock_registry.get_provider_enum_for = MagicMock(side_effect=get_provider_enum_for)

    # Configure get_provider_instance to return mock providers
    def get_provider_instance(enum_value, kind: str, singleton: bool = True):
        if kind == "embedding":
            return mock_embedding_provider
        elif kind == "sparse_embedding":
            return mock_sparse_provider
        elif kind == "vector_store":
            return mock_vector_store
        elif kind == "reranking":
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
    import time

    original_time = time.time
    call_count = [0]  # Use list for mutable counter

    def mock_time():
        call_count[0] += 1
        # Return monotonically increasing time values (start from a baseline)
        return 1000000.0 + call_count[0] * 0.001

    with patch(
        "codeweaver.agent_api.find_code.get_provider_registry",
        return_value=mock_provider_registry,
    ), patch("codeweaver.agent_api.find_code.time.time", side_effect=mock_time):
        yield mock_provider_registry


# ===========================================================================
# Settings Fixtures
# ===========================================================================


@pytest.fixture
def mock_settings_with_providers():
    """Provide mock settings with provider configuration."""
    from codeweaver.config.settings import Settings

    mock_settings = MagicMock(spec=Settings)
    mock_settings.providers = {
        "embedding": {
            "provider": "voyage",
            "model": "voyage-code-2",
        },
        "sparse_embedding": {
            "provider": "fastembed",
            "model": "prithivida/Splade_PP_en_v1",
        },
        "vector_store": {
            "provider": "qdrant",
            "collection": "test_collection",
        },
        "reranking": {
            "provider": "voyage",
            "model": "rerank-2",
        },
    }
    return mock_settings
