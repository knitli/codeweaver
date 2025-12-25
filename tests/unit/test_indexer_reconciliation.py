# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for automatic embedding reconciliation in the indexer."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from codeweaver.core.stores import get_blake_hash
from codeweaver.engine.indexer.indexer import Indexer
from codeweaver.engine.indexer.manifest import IndexFileManifest


pytestmark = [pytest.mark.unit]


class Point:
    def __init__(self, id, vector, payload):
        self.id = id
        self.vector = vector
        self.payload = payload


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestAddMissingEmbeddings:
    """Test the add_missing_embeddings_to_existing_chunks method."""

    @pytest.fixture
    async def mock_indexer(self, tmp_path: Path):
        """Create an indexer with mocked dependencies for reconciliation testing."""
        from codeweaver.di import get_container
        from codeweaver.providers.embedding.providers.base import EmbeddingProvider
        from codeweaver.providers.vector_stores.base import VectorStoreProvider

        container = get_container()
        container.clear_overrides()

        # Mock vector store
        mock_vs = MagicMock()
        mock_vs.collection = "test_collection"
        mock_vs.client = MagicMock()
        mock_vs.client.retrieve = AsyncMock()
        mock_vs.client.update_vectors = AsyncMock()
        mock_vs.initialize = AsyncMock()
        mock_vs._initialize = AsyncMock()

        # Mock embedding providers
        mock_ep = AsyncMock(spec=EmbeddingProvider)
        mock_ep.embed_documents = AsyncMock(return_value=[[0.1] * 384])
        mock_ep.provider_name = "voyage"
        mock_ep.model_name = "voyage-3"
        mock_ep.initialize_async = AsyncMock()

        mock_sp = AsyncMock(spec=EmbeddingProvider)
        mock_sp.embed_documents = AsyncMock(return_value=[[0.2] * 128])
        mock_sp.provider_name = "fastembed"
        mock_sp.model_name = "bm25"
        mock_sp.initialize_async = AsyncMock()

        # Apply overrides
        container.override(VectorStoreProvider, mock_vs)
        container.override(EmbeddingProvider, mock_ep)

        indexer = await container.resolve(Indexer)

        # Ensure project path matches tmp_path
        indexer._project_path = tmp_path
        indexer._checkpoint_manager.project_path = tmp_path
        indexer._manifest_manager.project_path = tmp_path

        # Set up manifest
        indexer._file_manifest = IndexFileManifest(project_path=tmp_path)

        # Manually set providers
        indexer._vector_store = mock_vs
        indexer._embedding_provider = mock_ep
        indexer._sparse_provider = mock_sp
        indexer._providers_initialized = True

        # Mock manifest lock
        indexer._manifest_lock = AsyncMock()
        indexer._manifest_lock.__aenter__ = AsyncMock()
        indexer._manifest_lock.__aexit__ = AsyncMock()

        return indexer

    @pytest.mark.asyncio
    async def test_only_adds_sparse_when_dense_exists(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test that only sparse embeddings are generated when dense already exists."""
        chunk_id = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")
        content_hash = get_blake_hash(b"print('hello')")

        rel_path = Path("test.py")

        # Update manifest
        mock_indexer._file_manifest.add_file(
            rel_path,
            content_hash=content_hash,
            chunk_ids=[chunk_id],
            dense_embedding_model="voyage-3",
            dense_embedding_provider="voyage",
            sparse_embedding_model="bm25",
            sparse_embedding_provider="fastembed",
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )

        # Mock point
        mock_point = Point(
            id=chunk_id, vector={"": [0.1] * 384}, payload={"text": "print('hello')"}
        )
        mock_indexer._vector_store.client.retrieve.return_value = [mock_point]

        # Execute reconciliation
        # Use full path for files_to_process alignment if Indexer uses absolute paths internally
        # but the manifest stores relative keys.
        await mock_indexer.add_missing_embeddings_to_existing_chunks(add_sparse=True)

        # Verify
        mock_indexer._sparse_provider.embed_documents.assert_called_once()
        mock_indexer._embedding_provider.embed_documents.assert_not_called()
        mock_indexer._vector_store.client.update_vectors.assert_called_once()

        # Verify Manifest
        entry = mock_indexer._file_manifest.get_file(rel_path)
        assert entry is not None
        assert entry["has_sparse_embeddings"] is True
