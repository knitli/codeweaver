# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Global pytest configuration and fixtures for CodeWeaver tests."""

from pathlib import Path
from uuid import uuid4

import pytest

from qdrant_client import AsyncQdrantClient


# ===========================================================================
# *                    Test Configuration
# ===========================================================================


def get_test_qdrant_config(collection_suffix: str = "") -> dict:
    """Get test-specific Qdrant configuration.

    Uses local Qdrant container at localhost:6336 without authentication.

    Args:
        collection_suffix: Optional suffix for collection name to ensure uniqueness

    Returns:
        Configuration dict for QdrantVectorStoreProvider
    """
    # Use local Qdrant container without auth at port 6336
    config = {
        "url": "http://localhost:6336",
        "prefer_grpc": False,  # Use REST API
    }

    # Set test-specific collection name
    base_name = "codeweaver-test"
    if collection_suffix:
        config["collection_name"] = f"{base_name}-{collection_suffix}"
    else:
        config["collection_name"] = f"{base_name}-{uuid4().hex[:8]}"

    return config


# ===========================================================================
# *                    Fixtures
# ===========================================================================


@pytest.fixture
def initialize_test_settings():
    """Initialize settings for test environment.

    This fixture ensures that the global settings are properly initialized
    with minimal required configuration for tests. It resets settings after
    the test to avoid cross-test contamination.
    """
    from codeweaver.config.settings import get_settings, reset_settings

    # Reset any existing settings
    reset_settings()

    # Initialize settings by calling get_settings() which will create
    # the global instance with defaults, including the "providers" key
    # This prevents KeyError when tests access provider settings
    get_settings()

    yield

    # Cleanup: reset settings after test
    reset_settings()


@pytest.fixture
async def qdrant_test_config():
    """Provide test-specific Qdrant configuration."""
    return get_test_qdrant_config()


@pytest.fixture
async def qdrant_client_cleanup():
    """Fixture that provides a cleanup function for Qdrant collections.

    Yields a cleanup function that can be called with (client, collection_name).
    Automatically cleans up at test end if not called explicitly.
    """
    collections_to_cleanup = []

    async def cleanup(client: AsyncQdrantClient, collection_name: str):
        """Clean up a Qdrant collection."""
        if collection_name:
            collections_to_cleanup.append((client, collection_name))

    yield cleanup

    # Cleanup all collections at test end
    for client, collection_name in collections_to_cleanup:
        try:
            await client.delete_collection(collection_name=collection_name)
        except Exception:
            # Ignore cleanup errors - collection might not exist
            pass


@pytest.fixture
def temp_test_file(tmp_path: Path):
    """Create a temporary test file."""
    test_file = tmp_path / "test_code.py"
    test_file.write_text("def test_function():\n    pass\n")
    return test_file


# ===========================================================================
# *                    Embedding Test Utilities
# ===========================================================================


def create_test_chunk_with_embeddings(
    chunk_id,
    chunk_name: str,
    file_path: Path,
    language,
    content: str,
    dense_embedding: list[float] | None = None,
    sparse_embedding: dict | None = None,
    line_start: int = 1,
    line_end: int = 1,
):
    """Create a CodeChunk with embeddings registered in the EmbeddingRegistry.

    Args:
        chunk_id: UUID for the chunk
        chunk_name: Name identifier for the chunk
        file_path: Path to the source file
        language: Programming language
        content: Code content
        dense_embedding: Dense embedding vector (list of floats)
        sparse_embedding: Sparse embedding dict with 'indices' and 'values'
        line_start: Starting line number
        line_end: Ending line number

    Returns:
        CodeChunk with embeddings registered in the global registry
    """

    from codeweaver.common.utils.utils import uuid7
    from codeweaver.core.chunks import BatchKeys, CodeChunk
    from codeweaver.core.spans import Span
    from codeweaver.providers.embedding.registry import get_embedding_registry
    from codeweaver.providers.embedding.types import ChunkEmbeddings, EmbeddingBatchInfo

    # Create the base chunk
    chunk = CodeChunk(
        chunk_id=chunk_id,
        chunk_name=chunk_name,
        file_path=file_path,
        language=language,
        content=content,
        line_range=Span(start=line_start, end=line_end, _source_id=chunk_id),
    )

    registry = get_embedding_registry()

    # Create batch IDs
    dense_batch_id = uuid7() if dense_embedding else None
    sparse_batch_id = uuid7() if sparse_embedding else None

    # Register embeddings in the registry
    dense_info = None
    sparse_info = None

    if dense_embedding:
        dense_info = EmbeddingBatchInfo.create_dense(
            batch_id=dense_batch_id,
            batch_index=0,
            chunk_id=chunk_id,
            model="test-dense-model",
            embeddings=dense_embedding,
        )
        # Set batch key on chunk
        dense_batch_key = BatchKeys(id=dense_batch_id, idx=0, sparse=False)
        chunk = chunk.set_batch_keys(dense_batch_key)

    if sparse_embedding:
        # Convert sparse dict format to flat list for storage
        # Qdrant sparse format uses indices and values separately
        # For simplicity in tests, store the values list
        sparse_values = sparse_embedding.get("values", [])
        sparse_info = EmbeddingBatchInfo.create_sparse(
            batch_id=sparse_batch_id,
            batch_index=0,
            chunk_id=chunk_id,
            model="test-sparse-model",
            embeddings=sparse_values,
        )
        # Set batch key on chunk
        sparse_batch_key = BatchKeys(id=sparse_batch_id, idx=0, sparse=True)
        chunk = chunk.set_batch_keys(sparse_batch_key)

    # Register in the embedding registry
    if dense_info or sparse_info:
        registry[chunk_id] = ChunkEmbeddings(sparse=sparse_info, dense=dense_info, chunk=chunk)

    return chunk
