# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Global pytest configuration and fixtures for CodeWeaver tests."""

from pathlib import Path

import pytest

from qdrant_client import AsyncQdrantClient

from codeweaver.core.metadata import ChunkKind, ExtKind


# ===========================================================================
# *                    Test Configuration
# ===========================================================================
# Note: Qdrant configuration now handled by qdrant_test_manager fixture
# See tests/qdrant_test_manager.py for details


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
# *                    Qdrant Test Instance Management
# ===========================================================================


@pytest.fixture
async def qdrant_test_manager(tmp_path: Path):
    """Provide a QdrantTestManager for integration tests.

    This fixture:
    - Uses test-specific environment variables (QDRANT_TEST_*) to prevent pollution
    - Scans ports 6333-6400 for running Qdrant instances
    - Auto-starts Docker container if no instance found (can be disabled)
    - Finds first instance accessible without authentication
    - Creates unique collections per test
    - Automatically cleans up collections and containers after test

    Environment Variables (all optional):
        QDRANT_TEST_URL: Direct URL override (e.g., http://localhost:6336)
        QDRANT_TEST_HOST: Test host (default: localhost)
        QDRANT_TEST_PORT: Test port override (e.g., 6336)
        QDRANT_TEST_API_KEY: Test-specific API key
        QDRANT_TEST_SKIP_DOCKER: Set to '1' or 'true' to disable auto-start
        QDRANT_TEST_IMAGE: Custom Docker image (default: qdrant/qdrant:latest)
        QDRANT_TEST_CONTAINER_NAME: Custom container name (default: qdrant-test)

    Usage:
        async def test_something(qdrant_test_manager):
            async with qdrant_test_manager.collection_context() as (client, collection):
                # Use client and collection
                await client.upsert(collection, points=[...])
                # Cleanup automatic
    """
    from .qdrant_test_manager import QdrantTestManager

    # Create manager with unique storage path for this test
    storage_path = tmp_path / "qdrant_storage"
    storage_path.mkdir(exist_ok=True)

    # Try to find an accessible Qdrant instance by scanning ports
    # This ensures we find an unauthenticated instance (e.g., 6336) not an auth-required one (e.g., 6333)
    import socket

    manager = None
    for port in range(6333, 6401):  # Scan 6333-6400
        # Quick check: is port in use?
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.1)  # Very quick check
            if sock.connect_ex(("localhost", port)) != 0:
                # Nothing listening on this port, skip
                continue

        # Port has something running, try it as Qdrant
        try:
            test_manager = QdrantTestManager(
                port=port, storage_path=storage_path, auto_start_docker=False
            )
            # Verify this instance is accessible without auth
            if await test_manager.verify_connection():
                manager = test_manager
                break
            # Not accessible, try next port
            await test_manager.close()
        except Exception:
            # Error with this port, try next
            continue

    # If no accessible instance found, try Docker auto-start
    if manager is None:
        try:
            manager = QdrantTestManager(storage_path=storage_path, auto_start_docker=True)
            if not await manager.verify_connection():
                pytest.skip(
                    "No accessible Qdrant instance found and Docker auto-start failed. "
                    "Start unauthenticated instance with: docker run -p 6336:6333 qdrant/qdrant:latest"
                )
        except RuntimeError as e:
            pytest.skip(str(e))

    yield manager

    # Cleanup after test (including Docker container if we started it)
    await manager.close()


@pytest.fixture
async def qdrant_test_client(qdrant_test_manager):
    """Provide a connected Qdrant client for testing.

    This is a convenience fixture that just returns the client.
    Use qdrant_test_manager.collection_context() for collection management.
    """
    return await qdrant_test_manager.ensure_client()


@pytest.fixture
async def qdrant_test_collection(qdrant_test_manager):
    """Provide a test collection with automatic cleanup.

    Yields:
        Tuple of (client, collection_name)

    Usage:
        async def test_something(qdrant_test_collection):
            client, collection = qdrant_test_collection
            await client.upsert(collection, points=[...])
    """
    async with qdrant_test_manager.collection_context() as (client, collection):
        yield client, collection


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
        ext_kind=ExtKind.from_language(language, ChunkKind.CODE),
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
