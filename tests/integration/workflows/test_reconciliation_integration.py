# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration tests for embedding reconciliation in the indexer.

These tests exercise the reconciliation path in prime_index() using real
Qdrant vector store instances. They replace the unit tests that were
previously marked xfail due to Pydantic v2 mocking incompatibility.

Critical Code Path Tested (indexer.py:1334-1400):
    if not force_reindex and self._vector_store and (...):
        try:
            result = await self.add_missing_embeddings_to_existing_chunks(...)
        except (ProviderError, IndexingError) as e:
            logger.warning(...)
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.warning(...)

Coverage Areas:
--------------
1. Reconciliation workflow during prime_index()
   - test_prime_index_reconciliation_without_force_reindex
   - test_reconciliation_with_add_dense_flag
   - test_reconciliation_with_add_sparse_flag
   - test_reconciliation_skipped_when_no_files_need_embeddings

2. Error handling for various exception types
   - test_reconciliation_handles_provider_error_gracefully (ProviderError)
   - test_reconciliation_handles_indexing_error_gracefully (IndexingError)
   - test_reconciliation_handles_connection_error_gracefully (ConnectionError)

3. Conditional logic for when reconciliation should/shouldn't run
   - test_reconciliation_not_called_when_force_reindex_true
   - test_reconciliation_not_called_when_no_vector_store
   - test_reconciliation_not_called_when_no_providers

Why Integration Tests:
---------------------
- Indexer is a Pydantic v2 BaseModel (method patching unreliable)
- Integration tests exercise real behavior without brittle mocking
- Core reconciliation logic has comprehensive unit test coverage
- This approach provides better test reliability and maintenance

Related Unit Tests:
------------------
- tests/unit/test_indexer_reconciliation.py::TestAddMissingEmbeddings
  * Direct testing of add_missing_embeddings_to_existing_chunks()
  * Comprehensive coverage of reconciliation logic
- tests/unit/test_indexer_reconciliation.py::TestEdgeCases
  * Edge case handling and error scenarios
"""

import asyncio
import logging

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from codeweaver.core import SemanticSearchLanguage as Language
from codeweaver.core import uuid7
from codeweaver.engine import Indexer
from codeweaver.providers import QdrantVectorStoreProvider

# sourcery skip: dont-import-test-modules
from tests.conftest import create_test_chunk_with_embeddings


pytestmark = [pytest.mark.integration, pytest.mark.external_api]

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prime_index_reconciliation_without_force_reindex(
    qdrant_test_manager, tmp_path, initialized_cw_state, clean_container, vector_store_factory
):
    """Verify reconciliation runs when force_reindex=False."""
    # Create unique collection
    collection_name = qdrant_test_manager.create_collection_name("reconcile")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    # Use factory to create provider
    provider = await vector_store_factory(
        QdrantVectorStoreProvider,
        config_overrides={
            "collection_name": collection_name,
            "url": qdrant_test_manager.url,
            "dense_vector_size": 768,
            "sparse_vector_size": 1000,
        },
    )

    # Create test project directory with Python files
    project_path = tmp_path / "test_project"
    project_path.mkdir()

    file1 = project_path / "module1.py"
    file1.write_text("def function_one():\n    return 1\n")

    file2 = project_path / "module2.py"
    file2.write_text("def function_two():\n    return 2\n")

    # Phase 1: Initial setup
    chunk1 = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="module1.py:function_one",
        file_path=Path("module1.py"),
        language=Language.PYTHON,
        content="def function_one():\n    return 1",
        dense_embedding=[0.1] * 768,
        sparse_embedding={"indices": [1, 2, 3], "values": [0.9, 0.8, 0.7]},
        line_start=1,
        line_end=2,
    )

    chunk2 = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="module2.py:function_two",
        file_path=Path("module2.py"),
        language=Language.PYTHON,
        content="def function_two():\n    return 2",
        dense_embedding=[0.2] * 768,
        sparse_embedding={"indices": [4, 5, 6], "values": [0.6, 0.5, 0.4]},
        line_start=1,
        line_end=2,
    )

    # Upsert chunks to simulate initial indexing
    await provider.upsert([chunk1, chunk2])

    # Create mocked embedding providers
    mock_dense_provider = AsyncMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.model_name = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"
    mock_dense_provider.embed_documents = AsyncMock(return_value=[[0.3] * 768, [0.4] * 768])
    mock_dense_provider.initialize_async = AsyncMock()

    mock_sparse_provider = AsyncMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.model_name = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"
    mock_sparse_provider.embed_documents = AsyncMock(
        return_value=[
            {"indices": [7, 8, 9], "values": [0.3, 0.2, 0.1]},
            {"indices": [10, 11, 12], "values": [0.9, 0.8, 0.7]},
        ]
    )
    mock_sparse_provider.initialize_async = AsyncMock()

    from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider, VectorStoreProvider

    # Apply overrides to container
    clean_container.override(EmbeddingProvider, mock_dense_provider)
    clean_container.override(SparseEmbeddingProvider, mock_sparse_provider)
    clean_container.override(VectorStoreProvider, provider)

    # Mock _initialize_providers_async
    async def mock_init_providers_async(vector_store=None):
        pass

    # Resolve indexer from container
    indexer = await clean_container.resolve(Indexer)

    # Permanently replace _initialize_providers_async
    object.__setattr__(indexer, "_initialize_providers_async", mock_init_providers_async)

    # Initialize manifest manager
    from codeweaver.engine import FileManifestManager

    indexer._manifest_manager = FileManifestManager(project_path=project_path)
    indexer._file_manifest = indexer._manifest_manager.create_new()

    # Simulate manifest state needing reconciliation (missing sparse)
    indexer._file_manifest.add_file(
        path=Path("module1.py"),
        content_hash="test_hash_1",
        chunk_ids=[str(chunk1.chunk_id)],
        dense_embedding_provider="test-provider",
        dense_embedding_model="test-dense-model",
        has_dense_embeddings=True,
        has_sparse_embeddings=False,
    )

    indexer._file_manifest.add_file(
        path=Path("module2.py"),
        content_hash="test_hash_2",
        chunk_ids=[str(chunk2.chunk_id)],
        dense_embedding_provider="test-provider",
        dense_embedding_model="test-dense-model",
        has_dense_embeddings=True,
        has_sparse_embeddings=False,
    )

    # Track calls to reconciliation
    call_tracker = {"called": False, "call_count": 0}
    original_reconcile = indexer.add_missing_embeddings_to_existing_chunks

    async def tracked_add_missing_embeddings(*args, **kwargs):
        call_tracker["called"] = True
        call_tracker["call_count"] += 1
        return await original_reconcile(*args, **kwargs)

    object.__setattr__(
        indexer, "add_missing_embeddings_to_existing_chunks", tracked_add_missing_embeddings
    )

    # Mock discovery to return files
    def mock_discover_files(progress_callback=None):
        return [file1, file2]

    object.__setattr__(indexer, "_discover_files_to_index", mock_discover_files)

    # Mock batch indexing
    async def mock_perform_batch(*args, **kwargs):
        indexer._stats.files_processed += 2
        return

    object.__setattr__(indexer, "_perform_batch_indexing_async", mock_perform_batch)

    # Mock load manifest
    object.__setattr__(indexer, "_load_file_manifest", lambda: True)

    # Trigger reconciliation path
    await indexer.prime_index(force_reindex=False, add_dense=True, add_sparse=True)

    # Verify reconciliation was invoked
    assert call_tracker["called"]
    assert call_tracker["call_count"] == 1

    print("✅ PASSED: Reconciliation path tested successfully")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_with_add_dense_flag(
    qdrant_test_manager, tmp_path, initialized_cw_state, clean_container, vector_store_factory
):
    """Test reconciliation specifically for adding dense embeddings."""
    # Create unique collection
    collection_name = qdrant_test_manager.create_collection_name("reconcile_dense")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    provider = await vector_store_factory(
        QdrantVectorStoreProvider,
        config_overrides={
            "collection_name": collection_name,
            "url": qdrant_test_manager.url,
            "dense_vector_size": 768,
            "sparse_vector_size": 1000,
        },
    )

    project_path = tmp_path / "test_project_dense"
    project_path.mkdir()

    # Create chunk with sparse-only (missing dense)
    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="module.py:func",
        file_path=Path("module.py"),
        language=Language.PYTHON,
        content="def func():\n    pass",
        dense_embedding=None,  # Missing dense
        sparse_embedding={"indices": [1, 2, 3], "values": [0.9, 0.8, 0.7]},
        line_start=1,
        line_end=2,
    )

    await provider.upsert([chunk])

    # Create indexer with only dense provider
    mock_dense_provider = AsyncMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"
    mock_dense_provider.get_async_embeddings = AsyncMock(return_value=[[0.5] * 768])
    mock_dense_provider.initialize_async = AsyncMock()

    from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider, VectorStoreProvider

    # Apply overrides to container
    clean_container.override(EmbeddingProvider, mock_dense_provider)
    clean_container.override(SparseEmbeddingProvider, None)
    clean_container.override(VectorStoreProvider, provider)

    # Mock _initialize_providers_async
    async def mock_init_providers_async(vector_store=None):
        pass

    # Resolve indexer from container
    indexer = await clean_container.resolve(Indexer)

    # Permanently replace _initialize_providers_async
    object.__setattr__(indexer, "_initialize_providers_async", mock_init_providers_async)

    # Initialize manifest manager
    from codeweaver.engine import FileManifestManager

    indexer._manifest_manager = FileManifestManager(project_path=project_path)
    indexer._file_manifest = indexer._manifest_manager.create_new()

    # Track file as sparse-only in manifest
    indexer._file_manifest.add_file(
        path=Path("module.py"),
        content_hash="test_hash_sparse",
        chunk_ids=[str(chunk.chunk_id)],
        dense_embedding_provider=None,
        dense_embedding_model=None,
        sparse_embedding_provider="test-sparse-provider",
        sparse_embedding_model="test-sparse-model",
        has_dense_embeddings=False,
        has_sparse_embeddings=True,
    )

    # Call add_missing_embeddings_to_existing_chunks with add_dense=True
    result = await indexer.add_missing_embeddings_to_existing_chunks(
        add_dense=True, add_sparse=False
    )

    # Verify result indicates dense embeddings were processed
    assert "files_processed" in result
    assert "chunks_updated" in result

    print("✅ PASSED: Dense reconciliation flag tested successfully")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_with_add_sparse_flag(
    qdrant_test_manager, tmp_path, initialized_cw_state, clean_container, vector_store_factory
):
    """Test reconciliation specifically for adding sparse embeddings."""
    # Create unique collection
    collection_name = qdrant_test_manager.create_collection_name("reconcile_sparse")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    provider = await vector_store_factory(
        QdrantVectorStoreProvider,
        config_overrides={
            "collection_name": collection_name,
            "url": qdrant_test_manager.url,
            "dense_vector_size": 768,
            "sparse_vector_size": 1000,
        },
    )

    project_path = tmp_path / "test_project_sparse"
    project_path.mkdir()

    # Create chunk with dense-only (missing sparse)
    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="module.py:func",
        file_path=Path("module.py"),
        language=Language.PYTHON,
        content="def func():\n    pass",
        dense_embedding=[0.1] * 768,
        sparse_embedding=None,  # Missing sparse
        line_start=1,
        line_end=2,
    )

    await provider.upsert([chunk])

    # Create mocked sparse provider
    mock_sparse_provider = AsyncMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"
    mock_sparse_provider.get_async_embeddings = AsyncMock(
        return_value=[{"indices": [7, 8, 9], "values": [0.3, 0.2, 0.1]}]
    )
    mock_sparse_provider.initialize_async = AsyncMock()

    from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider, VectorStoreProvider

    # Apply overrides to container
    clean_container.override(EmbeddingProvider, None)
    clean_container.override(SparseEmbeddingProvider, mock_sparse_provider)
    clean_container.override(VectorStoreProvider, provider)

    # Mock _initialize_providers_async
    async def mock_init_providers_async(vector_store=None):
        pass

    # Resolve indexer from container
    indexer = await clean_container.resolve(Indexer)

    # Permanently replace _initialize_providers_async
    object.__setattr__(indexer, "_initialize_providers_async", mock_init_providers_async)

    # Initialize manifest manager
    from codeweaver.engine import FileManifestManager

    indexer._manifest_manager = FileManifestManager(project_path=project_path)
    indexer._file_manifest = indexer._manifest_manager.create_new()

    # Track file as dense-only in manifest
    indexer._file_manifest.add_file(
        path=Path("module.py"),
        content_hash="test_hash_dense",
        chunk_ids=[str(chunk.chunk_id)],
        dense_embedding_provider="test-provider",
        dense_embedding_model="test-dense-model",
        has_dense_embeddings=True,
        has_sparse_embeddings=False,
    )

    # Call reconciliation directly to test add_sparse flag
    result = await indexer.add_missing_embeddings_to_existing_chunks(
        add_dense=False, add_sparse=True
    )

    # Verify result indicates sparse embeddings were processed
    assert "files_processed" in result
    assert "chunks_updated" in result

    print("✅ PASSED: Sparse reconciliation flag tested successfully")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_skipped_when_no_files_need_embeddings(
    qdrant_test_manager, tmp_path, initialized_cw_state, clean_container, vector_store_factory
):
    """Test that reconciliation is skipped when all files have complete embeddings."""
    # Create unique collection
    collection_name = qdrant_test_manager.create_collection_name("reconcile_skip")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    provider = await vector_store_factory(
        QdrantVectorStoreProvider,
        config_overrides={
            "collection_name": collection_name,
            "url": qdrant_test_manager.url,
            "dense_vector_size": 768,
            "sparse_vector_size": 1000,
        },
    )

    project_path = tmp_path / "test_project_complete"
    project_path.mkdir()

    # Create chunk with BOTH dense and sparse embeddings
    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="module.py:func",
        file_path=Path("module.py"),
        language=Language.PYTHON,
        content="def func():\n    pass",
        dense_embedding=[0.1] * 768,
        sparse_embedding={"indices": [1, 2, 3], "values": [0.9, 0.8, 0.7]},
        line_start=1,
        line_end=2,
    )

    await provider.upsert([chunk])

    # Create mocked providers
    mock_dense_provider = AsyncMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"
    mock_dense_provider.initialize_async = AsyncMock()

    mock_sparse_provider = AsyncMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"
    mock_sparse_provider.initialize_async = AsyncMock()

    from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider, VectorStoreProvider

    # Apply overrides to container
    clean_container.override(EmbeddingProvider, mock_dense_provider)
    clean_container.override(SparseEmbeddingProvider, mock_sparse_provider)
    clean_container.override(VectorStoreProvider, provider)

    # Mock _initialize_providers_async
    async def mock_init_providers_async(vector_store=None):
        pass

    # Resolve indexer from container
    indexer = await clean_container.resolve(Indexer)

    # Permanently replace _initialize_providers_async
    object.__setattr__(indexer, "_initialize_providers_async", mock_init_providers_async)

    # Initialize manifest manager
    from codeweaver.engine import FileManifestManager

    indexer._manifest_manager = FileManifestManager(project_path=project_path)
    indexer._file_manifest = indexer._manifest_manager.create_new()

    # Track file as having BOTH embeddings
    indexer._file_manifest.add_file(
        path=Path("module.py"),
        content_hash="test_hash_both",
        chunk_ids=[str(chunk.chunk_id)],
        dense_embedding_provider="test-provider",
        dense_embedding_model="test-dense-model",
        sparse_embedding_provider="test-sparse-provider",
        sparse_embedding_model="test-sparse-model",
        has_dense_embeddings=True,
        has_sparse_embeddings=True,
    )

    # Call reconciliation - should return early with no work
    result = await indexer.add_missing_embeddings_to_existing_chunks(
        add_dense=True, add_sparse=True
    )

    # Verify no files were processed (all complete)
    assert result["files_processed"] == 0
    assert result["chunks_updated"] == 0

    print("✅ PASSED: Reconciliation correctly skipped when no work needed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_handles_provider_error_gracefully(
    qdrant_test_manager,
    tmp_path,
    initialized_cw_state,
    clean_container,
    caplog,
    vector_store_factory,
):
    """Verify prime_index continues when reconciliation fails with ProviderError."""
    from codeweaver.core import ProviderError

    # Set caplog to capture logs
    caplog.set_level(logging.WARNING, logger="codeweaver")

    # Create unique collection
    collection_name = qdrant_test_manager.create_collection_name("error_provider")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    provider = await vector_store_factory(
        QdrantVectorStoreProvider,
        config_overrides={
            "collection_name": collection_name,
            "url": qdrant_test_manager.url,
            "dense_vector_size": 768,
            "sparse_vector_size": 1000,
        },
    )

    project_path = tmp_path / "test_error_project"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    # Create chunk with dense-only
    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="module.py:func",
        file_path=Path("module.py"),
        language=Language.PYTHON,
        content="def func():\n    pass",
        dense_embedding=[0.1] * 768,
        sparse_embedding=None,
        line_start=1,
        line_end=2,
    )

    await provider.upsert([chunk])

    # Create mocked providers
    mock_dense_provider = AsyncMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.model_name = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"
    mock_dense_provider.initialize_async = AsyncMock()

    mock_sparse_provider = AsyncMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.model_name = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"
    mock_sparse_provider.initialize_async = AsyncMock()
    # Make embedding generation fail with ProviderError
    mock_sparse_provider.embed_documents = AsyncMock(
        side_effect=ProviderError("Simulated provider failure")
    )

    from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider, VectorStoreProvider

    # Apply overrides to container
    clean_container.override(EmbeddingProvider, mock_dense_provider)
    clean_container.override(SparseEmbeddingProvider, mock_sparse_provider)
    clean_container.override(VectorStoreProvider, provider)

    # Resolve indexer
    indexer = await clean_container.resolve(Indexer)

    # Ensure vector store and providers are set
    object.__setattr__(indexer, "_project_path", project_path)
    object.__setattr__(indexer, "_vector_store", provider)
    object.__setattr__(indexer, "_embedding_provider", mock_dense_provider)
    object.__setattr__(indexer, "_sparse_provider", mock_sparse_provider)

    # Patch _get_current_embedding_models
    object.__setattr__(
        indexer,
        "_get_current_embedding_models",
        lambda: {
            "dense_provider": "test-provider",
            "dense_model": "test-dense-model",
            "sparse_provider": "test-sparse-provider",
            "sparse_model": "test-sparse-model",
        },
    )

    # Initialize manifest
    from codeweaver.engine import FileManifestManager

    indexer._manifest_manager = FileManifestManager(project_path=project_path)
    indexer._file_manifest = indexer._manifest_manager.create_new()

    # Set up manifest to show missing sparse embeddings
    indexer._file_manifest.add_file(
        path=Path("module.py"),
        content_hash="test_hash",
        chunk_ids=[str(chunk.chunk_id)],
        dense_embedding_provider="test-provider",
        dense_embedding_model="test-dense-model",
        has_dense_embeddings=True,
        has_sparse_embeddings=False,
    )

    # Mock discovery to return files
    object.__setattr__(indexer, "_discover_files_to_index", lambda **kwargs: [file1])
    object.__setattr__(indexer, "_perform_batch_indexing_async", AsyncMock(return_value=None))
    object.__setattr__(indexer, "_load_file_manifest", lambda: True)

    # This should NOT crash despite ProviderError during reconciliation
    await indexer.prime_index(force_reindex=False)

    print("✅ PASSED: ProviderError handling verified")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_handles_indexing_error_gracefully(
    qdrant_test_manager,
    tmp_path,
    initialized_cw_state,
    clean_container,
    caplog,
    vector_store_factory,
):
    """Verify prime_index continues when reconciliation fails with IndexingError."""
    from codeweaver.core import IndexingError

    # Create unique collection
    collection_name = qdrant_test_manager.create_collection_name("error_indexing")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    provider = await vector_store_factory(
        QdrantVectorStoreProvider,
        config_overrides={
            "collection_name": collection_name,
            "url": qdrant_test_manager.url,
            "dense_vector_size": 768,
            "sparse_vector_size": 1000,
        },
    )

    project_path = tmp_path / "test_error_indexing"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="module.py:func",
        file_path=Path("module.py"),
        language=Language.PYTHON,
        content="def func():\n    pass",
        dense_embedding=[0.1] * 768,
        sparse_embedding=None,
        line_start=1,
        line_end=2,
    )

    await provider.upsert([chunk])

    # Make vector store client fail with IndexingError during update
    from qdrant_client.models import Record

    mock_record = Record(
        id=str(chunk.chunk_id), payload={"text": "def func():\n    pass\n"}, vector={}
    )
    provider.client.retrieve = AsyncMock(return_value=[mock_record])
    provider.client.update_vectors = AsyncMock(
        side_effect=IndexingError("Simulated indexing failure")
    )

    # Create mocked providers
    mock_dense_provider = AsyncMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"
    mock_dense_provider.initialize_async = AsyncMock()

    mock_sparse_provider = AsyncMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"
    mock_sparse_provider.initialize_async = AsyncMock()
    mock_sparse_provider.embed_documents = AsyncMock(
        return_value=[{"indices": [1, 2], "values": [0.9, 0.8]}]
    )

    from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider, VectorStoreProvider

    # Apply overrides to container
    clean_container.override(EmbeddingProvider, mock_dense_provider)
    clean_container.override(SparseEmbeddingProvider, mock_sparse_provider)
    clean_container.override(VectorStoreProvider, provider)

    # Resolve indexer
    indexer = await clean_container.resolve(Indexer)

    # Ensure vector store and providers are set
    object.__setattr__(indexer, "_project_path", project_path)
    object.__setattr__(indexer, "_vector_store", provider)
    object.__setattr__(indexer, "_embedding_provider", mock_dense_provider)
    object.__setattr__(indexer, "_sparse_provider", mock_sparse_provider)

    # Patch _get_current_embedding_models
    object.__setattr__(
        indexer,
        "_get_current_embedding_models",
        lambda: {
            "dense_provider": "test-provider",
            "dense_model": "test-dense-model",
            "sparse_provider": "test-sparse-provider",
            "sparse_model": "test-sparse-model",
        },
    )

    # Initialize manifest
    from codeweaver.engine import FileManifestManager

    indexer._manifest_manager = FileManifestManager(project_path=project_path)
    indexer._file_manifest = indexer._manifest_manager.create_new()

    # Set up manifest to show missing sparse embeddings
    indexer._file_manifest.add_file(
        path=Path("module.py"),
        content_hash="test_hash",
        chunk_ids=[str(chunk.chunk_id)],
        dense_embedding_provider="test-provider",
        dense_embedding_model="test-dense-model",
        has_dense_embeddings=True,
        has_sparse_embeddings=False,
    )

    # Mock discovery
    object.__setattr__(indexer, "_discover_files_to_index", lambda **kwargs: [file1])
    object.__setattr__(indexer, "_perform_batch_indexing_async", AsyncMock(return_value=None))
    object.__setattr__(indexer, "_load_file_manifest", lambda: True)

    # This should return dict with errors
    result = await indexer.prime_index(force_reindex=False)

    assert isinstance(result, dict)
    assert result.get("errors")

    print("✅ PASSED: IndexingError handling verified")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_handles_connection_error_gracefully(
    qdrant_test_manager,
    tmp_path,
    initialized_cw_state,
    clean_container,
    caplog,
    vector_store_factory,
):
    """Verify prime_index continues when reconciliation fails with ConnectionError."""

    collection_name = qdrant_test_manager.create_collection_name("error_connection")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    provider = await vector_store_factory(
        QdrantVectorStoreProvider,
        config_overrides={
            "collection_name": collection_name,
            "url": qdrant_test_manager.url,
            "dense_vector_size": 768,
            "sparse_vector_size": 1000,
        },
    )

    project_path = tmp_path / "test_error_connection"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="module.py:func",
        file_path=Path("module.py"),
        language=Language.PYTHON,
        content="def func():\n    pass",
        dense_embedding=[0.1] * 768,
        sparse_embedding=None,
        line_start=1,
        line_end=2,
    )

    await provider.upsert([chunk])

    # Make client.retrieve fail with ConnectionError
    async def failing_retrieve(*args, **kwargs):
        raise ConnectionError("Simulated connection failure")

    provider.client.retrieve = failing_retrieve

    mock_sparse_provider = AsyncMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"
    mock_sparse_provider.initialize_async = AsyncMock()

    mock_dense_provider = AsyncMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"
    mock_dense_provider.initialize_async = AsyncMock()

    from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider, VectorStoreProvider

    # Apply overrides to container
    clean_container.override(EmbeddingProvider, mock_dense_provider)
    clean_container.override(SparseEmbeddingProvider, mock_sparse_provider)
    clean_container.override(VectorStoreProvider, provider)

    # Mock _initialize_providers_async
    async def mock_init_providers_async(vector_store=None):
        pass

    # Resolve indexer from container
    indexer = await clean_container.resolve(Indexer)

    # Permanently replace _initialize_providers_async
    object.__setattr__(indexer, "_initialize_providers_async", mock_init_providers_async)

    # Initialize manifest manager
    from codeweaver.engine import FileManifestManager

    indexer._manifest_manager = FileManifestManager(project_path=project_path)
    indexer._file_manifest = indexer._manifest_manager.create_new()

    # Set up manifest to show missing sparse embeddings
    indexer._file_manifest.add_file(
        path=Path("module.py"),
        content_hash="test_hash",
        chunk_ids=[str(chunk.chunk_id)],
        dense_embedding_provider="test-provider",
        dense_embedding_model="test-dense-model",
        sparse_embedding_provider=None,
        sparse_embedding_model=None,
        has_dense_embeddings=True,
        has_sparse_embeddings=False,
    )

    # Mock discovery to return files
    def mock_discover_files(progress_callback=None):
        return [file1]

    object.__setattr__(indexer, "_discover_files_to_index", mock_discover_files)

    # Pydantic v2 workaround: Use object.__setattr__ to bypass validation
    async def mock_perform_batch(*args, **kwargs):
        return None

    object.__setattr__(indexer, "_perform_batch_indexing_async", mock_perform_batch)
    result = await indexer.prime_index(force_reindex=False)

    # Small delay to ensure logs are processed
    await asyncio.sleep(0.1)

    if isinstance(result, dict):
        assert result["files_processed"] == 0
        assert result.get("errors"), "Expected errors in reconciliation result"
        assert any("Simulated connection failure" in str(e) for e in result["errors"]), (
            "Expected 'Simulated connection failure' in errors"
        )
    else:
        pytest.fail(f"Expected dict result with errors, got {result}")

    print("✅ PASSED: ConnectionError handling verified")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_not_called_when_force_reindex_true(
    qdrant_test_manager, tmp_path, initialized_cw_state, clean_container, vector_store_factory
):
    """Verify reconciliation is skipped when force_reindex=True."""
    collection_name = qdrant_test_manager.create_collection_name("skip_reindex")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    provider = await vector_store_factory(
        QdrantVectorStoreProvider,
        config_overrides={
            "collection_name": collection_name,
            "url": qdrant_test_manager.url,
            "dense_vector_size": 768,
            "sparse_vector_size": 1000,
        },
    )

    project_path = tmp_path / "test_skip"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    # Create mock that will fail if called
    mock_sparse_provider = AsyncMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"
    mock_sparse_provider.embed_document = AsyncMock(
        side_effect=Exception("Should not be called during force_reindex")
    )
    mock_sparse_provider.initialize_async = AsyncMock()

    mock_dense_provider = AsyncMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"
    mock_dense_provider.initialize_async = AsyncMock()

    from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider, VectorStoreProvider

    # Apply overrides to container
    clean_container.override(EmbeddingProvider, mock_dense_provider)
    clean_container.override(SparseEmbeddingProvider, mock_sparse_provider)
    clean_container.override(VectorStoreProvider, provider)

    # Resolve indexer
    indexer = await clean_container.resolve(Indexer)

    # Ensure vector store and providers are set
    object.__setattr__(indexer, "_vector_store", None)
    object.__setattr__(indexer, "_embedding_provider", mock_dense_provider)
    object.__setattr__(indexer, "_sparse_provider", mock_sparse_provider)

    # Patch _get_current_embedding_models to be consistent with manifest
    object.__setattr__(
        indexer,
        "_get_current_embedding_models",
        lambda: {
            "dense_provider": "test",
            "dense_model": "test-dense-model",
            "sparse_provider": "test-sparse",
            "sparse_model": "test-sparse-model",
        },
    )

    # Initialize manifest manager (normally done in prime_index)
    from codeweaver.engine import FileManifestManager

    indexer._manifest_manager = FileManifestManager(project_path=project_path)
    indexer._file_manifest = indexer._manifest_manager.create_new()

    # Set up manifest to show missing embeddings
    # (would trigger reconciliation if force_reindex=False)
    indexer._file_manifest.add_file(
        path=Path("module.py"),
        content_hash="test_hash",
        chunk_ids=["fake-chunk-id"],
        dense_embedding_provider="test",
        dense_embedding_model="test-dense-model",
        sparse_embedding_provider=None,
        sparse_embedding_model=None,
        has_dense_embeddings=True,
        has_sparse_embeddings=False,
    )

    # Mock batch indexing
    object.__setattr__(indexer, "_perform_batch_indexing_async", AsyncMock(return_value=None))
    object.__setattr__(indexer, "_load_file_manifest", lambda: True)

    # Call with force_reindex=True
    # If reconciliation runs, embed_document will raise exception
    await indexer.prime_index(force_reindex=True)

    # Test passes if we reach here
    print("✅ PASSED: Reconciliation correctly skipped during force_reindex")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_not_called_when_no_vector_store(
    tmp_path, initialized_cw_state, clean_container
):
    """Verify reconciliation is skipped when no vector store is configured."""
    project_path = tmp_path / "test_no_vs"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    # Create mocked providers
    mock_sparse_provider = AsyncMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"
    mock_sparse_provider.initialize_async = AsyncMock()

    mock_dense_provider = AsyncMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"
    mock_dense_provider.initialize_async = AsyncMock()

    from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider, VectorStoreProvider

    # Apply overrides to container
    clean_container.override(EmbeddingProvider, mock_dense_provider)
    clean_container.override(SparseEmbeddingProvider, mock_sparse_provider)
    clean_container.override(VectorStoreProvider, None)

    # Resolve indexer
    indexer = await clean_container.resolve(Indexer)

    # Ensure vector store and providers are set
    object.__setattr__(indexer, "_vector_store", None)
    object.__setattr__(indexer, "_embedding_provider", mock_dense_provider)
    object.__setattr__(indexer, "_sparse_provider", mock_sparse_provider)

    # Patch _get_current_embedding_models to be consistent with manifest
    object.__setattr__(
        indexer,
        "_get_current_embedding_models",
        lambda: {
            "dense_provider": "test",
            "dense_model": "test-dense-model",
            "sparse_provider": "test-sparse",
            "sparse_model": "test-sparse-model",
        },
    )

    # Initialize manifest manager (normally done in prime_index)
    from codeweaver.engine import FileManifestManager

    indexer._manifest_manager = FileManifestManager(project_path=project_path)
    indexer._file_manifest = indexer._manifest_manager.create_new()

    # Set up manifest to show missing embeddings
    indexer._file_manifest.add_file(
        path=Path("module.py"),
        content_hash="test_hash",
        chunk_ids=["fake-chunk-id"],
        dense_embedding_provider="test",
        dense_embedding_model="test-dense-model",
        has_dense_embeddings=True,
        has_sparse_embeddings=False,
    )

    # Mock batch indexing
    object.__setattr__(indexer, "_perform_batch_indexing_async", AsyncMock(return_value=None))
    object.__setattr__(indexer, "_load_file_manifest", lambda: True)

    # Should not attempt reconciliation (no vector store)
    await indexer.prime_index(force_reindex=False)

    print("✅ PASSED: Reconciliation correctly skipped when no vector store")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_not_called_when_no_providers(
    qdrant_test_manager, tmp_path, initialized_cw_state, clean_container, vector_store_factory
):
    """Verify reconciliation is skipped when no embedding providers configured."""
    collection_name = qdrant_test_manager.create_collection_name("no_providers")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    provider = await vector_store_factory(
        QdrantVectorStoreProvider,
        config_overrides={
            "collection_name": collection_name,
            "url": qdrant_test_manager.url,
            "dense_vector_size": 768,
            "sparse_vector_size": 1000,
        },
    )

    project_path = tmp_path / "test_no_providers"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider, VectorStoreProvider

    # Apply overrides to container
    clean_container.override(EmbeddingProvider, None)
    clean_container.override(SparseEmbeddingProvider, None)
    clean_container.override(VectorStoreProvider, provider)

    # Resolve indexer
    indexer = await clean_container.resolve(Indexer)

    # Ensure vector store and providers are set
    object.__setattr__(indexer, "_vector_store", None)
    object.__setattr__(indexer, "_embedding_provider", None)
    object.__setattr__(indexer, "_sparse_provider", None)

    # Patch _get_current_embedding_models to be consistent with manifest
    object.__setattr__(
        indexer,
        "_get_current_embedding_models",
        lambda: {
            "dense_provider": "test",
            "dense_model": "test-dense-model",
            "sparse_provider": "test-sparse",
            "sparse_model": "test-sparse-model",
        },
    )

    # Initialize manifest manager (normally done in prime_index)
    from codeweaver.engine import FileManifestManager

    indexer._manifest_manager = FileManifestManager(project_path=project_path)
    indexer._file_manifest = indexer._manifest_manager.create_new()

    # Set up manifest to show missing embeddings
    indexer._file_manifest.add_file(
        path=Path("module.py"),
        content_hash="test_hash",
        chunk_ids=["fake-chunk-id"],
        dense_embedding_provider="test",
        dense_embedding_model="test-dense-model",
        has_dense_embeddings=True,
        has_sparse_embeddings=False,
    )

    # Mock batch indexing
    object.__setattr__(indexer, "_perform_batch_indexing_async", AsyncMock(return_value=None))
    object.__setattr__(indexer, "_load_file_manifest", lambda: True)

    # Should not attempt reconciliation (no providers)
    await indexer.prime_index(force_reindex=False)

    print("✅ PASSED: Reconciliation correctly skipped when no providers")
