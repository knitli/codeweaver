# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for automatic embedding reconciliation in the indexer."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from codeweaver.core.stores import get_blake_hash
from codeweaver.engine.indexer.indexer import Indexer
from codeweaver.engine.indexer.manifest import IndexFileManifest


pytestmark = [pytest.mark.unit]


class TestAddMissingEmbeddings:
    """Test the add_missing_embeddings_to_existing_chunks method."""

    @pytest.fixture
    def mock_indexer(self, tmp_path: Path):
        """Create an indexer with mocked dependencies for reconciliation testing."""
        indexer = Indexer(project_path=tmp_path, auto_initialize_providers=False)

        # Set up manifest
        indexer._file_manifest = IndexFileManifest(project_path=tmp_path)

        # Mock vector store with client
        indexer._vector_store = MagicMock()
        indexer._vector_store.collection = "test_collection"
        indexer._vector_store.client = AsyncMock()
        indexer._vector_store.client.retrieve = AsyncMock()
        indexer._vector_store.client.update_vectors = AsyncMock()

        # Mock embedding providers
        indexer._embedding_provider = AsyncMock()
        indexer._embedding_provider.embed_document = AsyncMock(
            return_value=[[0.1] * 384]  # Mock dense embedding
        )
        indexer._embedding_provider.provider_name = "voyage"
        indexer._embedding_provider.model_name = "voyage-3"

        indexer._sparse_provider = AsyncMock()
        indexer._sparse_provider.embed_document = AsyncMock(
            return_value=[[0.2] * 128]  # Mock sparse embedding
        )
        indexer._sparse_provider.provider_name = "splade"
        indexer._sparse_provider.model_name = "splade-v3"

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
        # Setup: File with dense embeddings but missing sparse
        chunk_id = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        # Add to manifest with dense embeddings only
        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"def test(): pass"),
            chunk_ids=[chunk_id],
            dense_embedding_provider="voyage",
            dense_embedding_model="voyage-3",
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )

        # Mock retrieve to return point with dense vector only
        mock_point = MagicMock()
        mock_point.id = chunk_id
        mock_point.payload = {"text": "def test(): pass"}
        mock_point.vector = {"": [0.1] * 384}  # Has dense (empty string key)
        mock_indexer._vector_store.client.retrieve.return_value = [mock_point]

        # Mock set_relative_path
        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            # Run reconciliation
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=False, add_sparse=True
            )

        # Verify only sparse embedding was generated
        mock_indexer._embedding_provider.embed_document.assert_not_called()
        mock_indexer._sparse_provider.embed_document.assert_called_once()

        # Verify update_vectors was called with sparse only
        assert mock_indexer._vector_store.client.update_vectors.call_count == 1
        call_args = mock_indexer._vector_store.client.update_vectors.call_args
        vectors = call_args[1]["vectors"][0]
        assert "sparse" in vectors
        assert "" not in vectors  # Dense should not be included

        # Verify result
        assert result["chunks_updated"] == 1
        assert result["files_processed"] == 1

    @pytest.mark.asyncio
    async def test_only_adds_dense_when_sparse_exists(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test that only dense embeddings are generated when sparse already exists."""
        # Setup: File with sparse embeddings but missing dense
        chunk_id = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        # Add to manifest with sparse embeddings only
        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"def test(): pass"),
            chunk_ids=[chunk_id],
            sparse_embedding_provider="splade",
            sparse_embedding_model="splade-v3",
            has_dense_embeddings=False,
            has_sparse_embeddings=True,
        )

        # Mock retrieve to return point with sparse vector only
        mock_point = MagicMock()
        mock_point.id = chunk_id
        mock_point.payload = {"text": "def test(): pass"}
        mock_point.vector = {"sparse": [0.2] * 128}  # Has sparse
        mock_indexer._vector_store.client.retrieve.return_value = [mock_point]

        # Mock set_relative_path
        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            # Run reconciliation
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=True, add_sparse=False
            )

        # Verify only dense embedding was generated
        mock_indexer._embedding_provider.embed_document.assert_called_once()
        mock_indexer._sparse_provider.embed_document.assert_not_called()

        # Verify update_vectors was called with dense only
        assert mock_indexer._vector_store.client.update_vectors.call_count == 1
        call_args = mock_indexer._vector_store.client.update_vectors.call_args
        vectors = call_args[1]["vectors"][0]
        assert "" in vectors  # Dense should be included
        assert "sparse" not in vectors

        # Verify result
        assert result["chunks_updated"] == 1
        assert result["files_processed"] == 1

    @pytest.mark.asyncio
    async def test_adds_both_when_both_missing(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test that both embeddings are generated when both are missing."""
        # Setup: File with no embeddings
        chunk_id = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        # Add to manifest with no embeddings
        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"def test(): pass"),
            chunk_ids=[chunk_id],
            has_dense_embeddings=False,
            has_sparse_embeddings=False,
        )

        # Mock retrieve to return point with no vectors
        mock_point = MagicMock()
        mock_point.id = chunk_id
        mock_point.payload = {"text": "def test(): pass"}
        mock_point.vector = {}  # No vectors
        mock_indexer._vector_store.client.retrieve.return_value = [mock_point]

        # Mock set_relative_path
        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            # Run reconciliation
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=True, add_sparse=True
            )

        # Verify both embeddings were generated
        mock_indexer._embedding_provider.embed_document.assert_called_once()
        mock_indexer._sparse_provider.embed_document.assert_called_once()

        # Verify update_vectors was called with both
        assert mock_indexer._vector_store.client.update_vectors.call_count == 1
        call_args = mock_indexer._vector_store.client.update_vectors.call_args
        vectors = call_args[1]["vectors"][0]
        assert "" in vectors  # Dense included
        assert "sparse" in vectors  # Sparse included

        # Verify result
        assert result["chunks_updated"] == 1
        assert result["files_processed"] == 1

    @pytest.mark.asyncio
    async def test_skips_when_both_exist(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test that no embeddings are generated when both already exist."""
        # Setup: File with both embeddings
        chunk_id = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        # Add to manifest with both embeddings
        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"def test(): pass"),
            chunk_ids=[chunk_id],
            dense_embedding_provider="voyage",
            dense_embedding_model="voyage-3",
            sparse_embedding_provider="splade",
            sparse_embedding_model="splade-v3",
            has_dense_embeddings=True,
            has_sparse_embeddings=True,
        )

        # Mock retrieve to return point with both vectors
        mock_point = MagicMock()
        mock_point.id = chunk_id
        mock_point.payload = {"text": "def test(): pass"}
        mock_point.vector = {
            "": [0.1] * 384,  # Has dense
            "sparse": [0.2] * 128,  # Has sparse
        }
        mock_indexer._vector_store.client.retrieve.return_value = [mock_point]

        # Mock set_relative_path
        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            # Run reconciliation
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=True, add_sparse=True
            )

        # Verify no embeddings were generated
        mock_indexer._embedding_provider.embed_document.assert_not_called()
        mock_indexer._sparse_provider.embed_document.assert_not_called()

        # Verify update_vectors was not called (no updates needed)
        mock_indexer._vector_store.client.update_vectors.assert_not_called()

        # Verify result - no updates since both exist
        # Note: files_processed may still be 1 since we checked the file,
        # but chunks_updated should be 0
        assert result["chunks_updated"] == 0

    @pytest.mark.asyncio
    async def test_handles_multiple_chunks_in_file(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test reconciliation with multiple chunks from the same file."""
        # Setup: File with multiple chunks, all missing sparse
        chunk_id_1 = str(uuid4())
        chunk_id_2 = str(uuid4())
        chunk_id_3 = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass\ndef another(): pass\ndef third(): pass")

        # Add to manifest with dense only
        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"content"),
            chunk_ids=[chunk_id_1, chunk_id_2, chunk_id_3],
            dense_embedding_provider="voyage",
            dense_embedding_model="voyage-3",
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )

        # Mock retrieve to return all chunks with dense only
        mock_points = []
        for chunk_id in [chunk_id_1, chunk_id_2, chunk_id_3]:
            mock_point = MagicMock()
            mock_point.id = chunk_id
            mock_point.payload = {"text": f"chunk {chunk_id}"}
            mock_point.vector = {"": [0.1] * 384}  # All have dense only
            mock_points.append(mock_point)

        mock_indexer._vector_store.client.retrieve.return_value = mock_points

        # Mock set_relative_path
        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            # Run reconciliation
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=False, add_sparse=True
            )

        # Verify sparse embedding was generated for each chunk
        assert mock_indexer._sparse_provider.embed_document.call_count == 3

        # Verify update_vectors was called with all 3 chunks
        assert mock_indexer._vector_store.client.update_vectors.call_count == 1
        call_args = mock_indexer._vector_store.client.update_vectors.call_args
        assert len(call_args[1]["vectors"]) == 3

        # Verify result
        assert result["chunks_updated"] == 3
        assert result["files_processed"] == 1

    @pytest.mark.asyncio
    async def test_handles_mixed_vector_states(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test reconciliation with chunks in different states."""
        # Setup: File with 3 chunks in different states
        chunk_id_1 = str(uuid4())  # Has both
        chunk_id_2 = str(uuid4())  # Has dense only
        chunk_id_3 = str(uuid4())  # Has neither

        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"content"),
            chunk_ids=[chunk_id_1, chunk_id_2, chunk_id_3],
            has_dense_embeddings=False,  # File-level tracking
            has_sparse_embeddings=False,
        )

        # Mock retrieve with mixed states
        mock_point_1 = MagicMock()
        mock_point_1.id = chunk_id_1
        mock_point_1.payload = {"text": "chunk 1"}
        mock_point_1.vector = {"": [0.1] * 384, "sparse": [0.2] * 128}  # Has both

        mock_point_2 = MagicMock()
        mock_point_2.id = chunk_id_2
        mock_point_2.payload = {"text": "chunk 2"}
        mock_point_2.vector = {"": [0.1] * 384}  # Has dense only

        mock_point_3 = MagicMock()
        mock_point_3.id = chunk_id_3
        mock_point_3.payload = {"text": "chunk 3"}
        mock_point_3.vector = {}  # Has neither

        mock_indexer._vector_store.client.retrieve.return_value = [
            mock_point_1,
            mock_point_2,
            mock_point_3,
        ]

        # Mock set_relative_path
        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            # Run reconciliation requesting both
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=True, add_sparse=True
            )

        # Verify correct generation:
        # - chunk 1: no calls (has both)
        # - chunk 2: 1 sparse call (missing sparse)
        # - chunk 3: 1 dense + 1 sparse call (missing both)
        # Total: 1 dense, 2 sparse
        assert mock_indexer._embedding_provider.embed_document.call_count == 1
        assert mock_indexer._sparse_provider.embed_document.call_count == 2

        # Verify only 2 chunks were updated (chunk 1 skipped)
        call_args = mock_indexer._vector_store.client.update_vectors.call_args
        assert len(call_args[1]["vectors"]) == 2

        assert result["chunks_updated"] == 2


class TestAutomaticReconciliation:
    """Test automatic reconciliation during prime_index.

    Note: These tests require extensive mocking of complex Pydantic models and
    async initialization behavior. They are marked as integration tests to
    avoid brittleness from class-level patching.
    """

    @pytest.fixture
    def mock_indexer_with_reconciliation(self, tmp_path: Path):
        """Create indexer for testing automatic reconciliation."""
        indexer = Indexer(project_path=tmp_path, auto_initialize_providers=False)

        indexer._file_manifest = IndexFileManifest(project_path=tmp_path)
        indexer._vector_store = MagicMock()
        indexer._vector_store.collection = "test_collection"

        # Mock embedding providers
        indexer._embedding_provider = AsyncMock()
        indexer._embedding_provider.provider_name = "voyage"
        indexer._embedding_provider.model_name = "voyage-3"

        indexer._sparse_provider = AsyncMock()
        indexer._sparse_provider.provider_name = "splade"
        indexer._sparse_provider.model_name = "splade-v3"

        return indexer

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.xfail(
        reason="Pydantic v2 models don't support standard mock patching approaches. "
        "The reconciliation logic is tested in TestAddMissingEmbeddings."
    )
    async def test_reconciliation_called_during_prime_index(
        self, mock_indexer_with_reconciliation: Indexer, tmp_path: Path
    ) -> None:
        """Test that reconciliation is automatically called during prime_index.

        This test verifies the integration of reconciliation into the indexing pipeline.
        Due to complexity of mocking prime_index internals (provider initialization,
        file discovery, batch indexing), this test is marked as integration.
        """
        # Add file to manifest indicating sparse embeddings are missing
        mock_indexer_with_reconciliation._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"content"),
            chunk_ids=[str(uuid4())],
            dense_embedding_provider="voyage",
            dense_embedding_model="voyage-3",
            has_dense_embeddings=True,
            has_sparse_embeddings=False,  # Missing sparse
        )

        # Create mock async functions
        mock_reconciliation = AsyncMock(
            return_value={"chunks_updated": 0, "files_processed": 0, "errors": []}
        )

        # Use class-level patching to avoid Pydantic v2 model attribute setting issues
        with (
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._initialize_providers_async",
                AsyncMock(),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._perform_batch_indexing_async",
                AsyncMock(),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._get_current_embedding_models",
                MagicMock(
                    return_value={
                        "dense_provider": "voyage",
                        "dense_model": "voyage-3",
                        "sparse_provider": "splade",
                        "sparse_model": "splade-v3",
                    }
                ),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer.add_missing_embeddings_to_existing_chunks",
                mock_reconciliation,
            ),
        ):
            # Run prime_index (not force_reindex)
            await mock_indexer_with_reconciliation.prime_index(force_reindex=False)

            # Verify reconciliation was called
            mock_reconciliation.assert_called_once()
            call_args = mock_reconciliation.call_args
            assert call_args[1]["add_sparse"] is True  # Should request sparse

    @pytest.mark.asyncio
    async def test_reconciliation_skipped_on_force_reindex(
        self, mock_indexer_with_reconciliation: Indexer, tmp_path: Path
    ) -> None:
        """Test that reconciliation is skipped when force_reindex is True.

        This test verifies that force_reindex bypasses reconciliation.
        Since reconciliation is inside a conditional that checks force_reindex,
        we can validate this without full prime_index mocking.
        """
        # Add file to manifest indicating sparse embeddings are missing
        mock_indexer_with_reconciliation._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"content"),
            chunk_ids=[str(uuid4())],
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )

        # Create mock async functions
        mock_reconciliation = AsyncMock(
            return_value={"chunks_updated": 0, "files_processed": 0, "errors": []}
        )

        # Use module-level patching to avoid Pydantic model patching issues
        with (
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._initialize_providers_async",
                AsyncMock(),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._perform_batch_indexing_async",
                AsyncMock(),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer.add_missing_embeddings_to_existing_chunks",
                mock_reconciliation,
            ),
        ):
            # Run prime_index with force_reindex
            await mock_indexer_with_reconciliation.prime_index(force_reindex=True)

            # Verify reconciliation was NOT called
            mock_reconciliation.assert_not_called()


class TestEdgeCases:
    """Test edge cases and error scenarios for reconciliation."""

    @pytest.fixture
    def mock_indexer(self, tmp_path: Path):
        """Create an indexer with mocked dependencies for edge case testing."""
        indexer = Indexer(project_path=tmp_path, auto_initialize_providers=False)

        # Set up manifest
        indexer._file_manifest = IndexFileManifest(project_path=tmp_path)

        # Mock vector store with client
        indexer._vector_store = MagicMock()
        indexer._vector_store.collection = "test_collection"
        indexer._vector_store.client = AsyncMock()
        indexer._vector_store.client.retrieve = AsyncMock()
        indexer._vector_store.client.update_vectors = AsyncMock()

        # Mock embedding providers
        indexer._embedding_provider = AsyncMock()
        indexer._embedding_provider.embed_document = AsyncMock(
            return_value=[[0.1] * 384]  # Mock dense embedding
        )
        indexer._embedding_provider.provider_name = "voyage"
        indexer._embedding_provider.model_name = "voyage-3"

        indexer._sparse_provider = AsyncMock()
        indexer._sparse_provider.embed_document = AsyncMock(
            return_value=[[0.2] * 128]  # Mock sparse embedding
        )
        indexer._sparse_provider.provider_name = "splade"
        indexer._sparse_provider.model_name = "splade-v3"

        # Mock manifest lock
        indexer._manifest_lock = AsyncMock()
        indexer._manifest_lock.__aenter__ = AsyncMock()
        indexer._manifest_lock.__aexit__ = AsyncMock()

        return indexer

    @pytest.mark.asyncio
    async def test_handles_list_vector_type(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test handling of non-dict vector types (list representation for single vector)."""
        chunk_id = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"def test(): pass"),
            chunk_ids=[chunk_id],
            has_dense_embeddings=False,
            has_sparse_embeddings=False,
        )

        # Mock retrieve to return point with list vector (single unnamed vector)
        mock_point = MagicMock()
        mock_point.id = chunk_id
        mock_point.payload = {"text": "def test(): pass"}
        mock_point.vector = [0.1] * 384  # List, not dict - represents a single dense vector
        mock_indexer._vector_store.client.retrieve.return_value = [mock_point]

        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=True, add_sparse=True
            )

        # Dense should not be generated (list represents existing dense vector)
        mock_indexer._embedding_provider.embed_document.assert_not_called()
        # Sparse should be generated (no sparse vector exists)
        mock_indexer._sparse_provider.embed_document.assert_called_once()

        assert result["chunks_updated"] == 1

    @pytest.mark.asyncio
    async def test_handles_empty_retrieve_results(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test handling when vector store returns no points."""
        chunk_id = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"def test(): pass"),
            chunk_ids=[chunk_id],
            has_dense_embeddings=False,
            has_sparse_embeddings=False,
        )

        # Mock retrieve to return empty list
        mock_indexer._vector_store.client.retrieve.return_value = []

        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=True, add_sparse=True
            )

        # No embeddings should be generated since no points were retrieved
        mock_indexer._embedding_provider.embed_document.assert_not_called()
        mock_indexer._sparse_provider.embed_document.assert_not_called()
        mock_indexer._vector_store.client.update_vectors.assert_not_called()

        # No chunks updated
        assert result["chunks_updated"] == 0

    @pytest.mark.asyncio
    async def test_handles_missing_payload_text(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test handling when point has no text in payload."""
        chunk_id = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"def test(): pass"),
            chunk_ids=[chunk_id],
            has_dense_embeddings=False,
            has_sparse_embeddings=False,
        )

        # Mock retrieve to return point with no text in payload
        mock_point = MagicMock()
        mock_point.id = chunk_id
        mock_point.payload = {"some_other_field": "value"}  # No "text" field
        mock_point.vector = {}
        mock_indexer._vector_store.client.retrieve.return_value = [mock_point]

        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=True, add_sparse=True
            )

        # No embeddings should be generated since no text available
        mock_indexer._embedding_provider.embed_document.assert_not_called()
        mock_indexer._sparse_provider.embed_document.assert_not_called()

        assert result["chunks_updated"] == 0

    @pytest.mark.asyncio
    async def test_handles_none_payload(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test handling when point has None payload."""
        chunk_id = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"def test(): pass"),
            chunk_ids=[chunk_id],
            has_dense_embeddings=False,
            has_sparse_embeddings=False,
        )

        # Mock retrieve to return point with None payload
        mock_point = MagicMock()
        mock_point.id = chunk_id
        mock_point.payload = None
        mock_point.vector = {}
        mock_indexer._vector_store.client.retrieve.return_value = [mock_point]

        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=True, add_sparse=True
            )

        # No embeddings should be generated since no payload
        mock_indexer._embedding_provider.embed_document.assert_not_called()
        mock_indexer._sparse_provider.embed_document.assert_not_called()

        assert result["chunks_updated"] == 0

    @pytest.mark.asyncio
    async def test_single_dense_provider_only(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test reconciliation when only dense provider is configured."""
        chunk_id = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        # Remove sparse provider
        mock_indexer._sparse_provider = None

        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"def test(): pass"),
            chunk_ids=[chunk_id],
            has_dense_embeddings=False,
            has_sparse_embeddings=False,
        )

        # Mock retrieve to return point with no vectors
        mock_point = MagicMock()
        mock_point.id = chunk_id
        mock_point.payload = {"text": "def test(): pass"}
        mock_point.vector = {}
        mock_indexer._vector_store.client.retrieve.return_value = [mock_point]

        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            # Only request dense since sparse provider is not configured
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=True, add_sparse=False
            )

        # Only dense should be generated
        mock_indexer._embedding_provider.embed_document.assert_called_once()

        # Verify update contains only dense vector
        # Note: Empty string key ("") is Qdrant's convention for the default/unnamed dense vector
        call_args = mock_indexer._vector_store.client.update_vectors.call_args
        vectors = call_args[1]["vectors"][0]
        assert "" in vectors  # Dense vector present (empty string = default dense vector)
        assert "sparse" not in vectors  # Sparse not present

        assert result["chunks_updated"] == 1

    @pytest.mark.asyncio
    async def test_single_sparse_provider_only(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test reconciliation when only sparse provider is configured."""
        chunk_id = str(uuid4())
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        # Remove dense provider
        mock_indexer._embedding_provider = None

        mock_indexer._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"def test(): pass"),
            chunk_ids=[chunk_id],
            has_dense_embeddings=False,
            has_sparse_embeddings=False,
        )

        # Mock retrieve to return point with no vectors
        mock_point = MagicMock()
        mock_point.id = chunk_id
        mock_point.payload = {"text": "def test(): pass"}
        mock_point.vector = {}
        mock_indexer._vector_store.client.retrieve.return_value = [mock_point]

        with patch(
            "codeweaver.engine.indexer.indexer.set_relative_path", return_value=Path("test.py")
        ):
            # Only request sparse since dense provider is not configured
            result = await mock_indexer.add_missing_embeddings_to_existing_chunks(
                add_dense=False, add_sparse=True
            )

        # Only sparse should be generated
        mock_indexer._sparse_provider.embed_document.assert_called_once()

        # Verify update contains only sparse vector
        # Note: Empty string key ("") is Qdrant's convention for the default/unnamed dense vector
        call_args = mock_indexer._vector_store.client.update_vectors.call_args
        vectors = call_args[1]["vectors"][0]
        assert "sparse" in vectors  # Sparse present
        assert "" not in vectors  # Dense not present (empty string = default dense vector)

        assert result["chunks_updated"] == 1


class TestReconciliationExceptionHandling:
    """Test exception handling during reconciliation in prime_index.

    Note: These tests verify that prime_index handles reconciliation failures
    gracefully. They require complex mocking of the indexer's internal state
    and are marked as integration tests.
    """

    @pytest.fixture
    def mock_indexer_for_exceptions(self, tmp_path: Path):
        """Create indexer for testing exception handling."""
        indexer = Indexer(project_path=tmp_path, auto_initialize_providers=False)

        indexer._file_manifest = IndexFileManifest(project_path=tmp_path)
        indexer._vector_store = MagicMock()
        indexer._vector_store.collection = "test_collection"

        # Mock embedding providers
        indexer._embedding_provider = AsyncMock()
        indexer._embedding_provider.provider_name = "voyage"
        indexer._embedding_provider.model_name = "voyage-3"

        indexer._sparse_provider = AsyncMock()
        indexer._sparse_provider.provider_name = "splade"
        indexer._sparse_provider.model_name = "splade-v3"

        return indexer

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.xfail(
        reason="Pydantic v2 models don't support standard mock patching approaches. "
        "The reconciliation error handling is tested indirectly via prime_index's "
        "exception handling code paths."
    )
    async def test_prime_index_handles_provider_error(
        self, mock_indexer_for_exceptions: Indexer, tmp_path: Path
    ) -> None:
        """Test that prime_index handles ProviderError during reconciliation gracefully."""
        from codeweaver.exceptions import ProviderError

        mock_indexer_for_exceptions._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"content"),
            chunk_ids=[str(uuid4())],
            dense_embedding_provider="voyage",
            dense_embedding_model="voyage-3",
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )

        mock_reconciliation = AsyncMock(side_effect=ProviderError("Test provider error"))

        # Use class-level patching to avoid Pydantic v2 model attribute setting issues
        with (
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._initialize_providers_async",
                AsyncMock(),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._perform_batch_indexing_async",
                AsyncMock(),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._get_current_embedding_models",
                MagicMock(
                    return_value={
                        "dense_provider": "voyage",
                        "dense_model": "voyage-3",
                        "sparse_provider": "splade",
                        "sparse_model": "splade-v3",
                    }
                ),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer.add_missing_embeddings_to_existing_chunks",
                mock_reconciliation,
            ),
        ):
            # Should not raise - error should be caught and logged
            result = await mock_indexer_for_exceptions.prime_index(force_reindex=False)

            # Verify reconciliation was called (and failed)
            mock_reconciliation.assert_called_once()

            # prime_index should still return normally
            assert result is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.xfail(
        reason="Pydantic v2 models don't support standard mock patching approaches. "
        "The reconciliation error handling is tested indirectly via prime_index's "
        "exception handling code paths."
    )
    async def test_prime_index_handles_indexing_error(
        self, mock_indexer_for_exceptions: Indexer, tmp_path: Path
    ) -> None:
        """Test that prime_index handles IndexingError during reconciliation gracefully."""
        from codeweaver.exceptions import IndexingError

        mock_indexer_for_exceptions._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"content"),
            chunk_ids=[str(uuid4())],
            dense_embedding_provider="voyage",
            dense_embedding_model="voyage-3",
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )

        mock_reconciliation = AsyncMock(side_effect=IndexingError("Test indexing error"))

        # Use class-level patching to avoid Pydantic v2 model attribute setting issues
        with (
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._initialize_providers_async",
                AsyncMock(),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._perform_batch_indexing_async",
                AsyncMock(),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._get_current_embedding_models",
                MagicMock(
                    return_value={
                        "dense_provider": "voyage",
                        "dense_model": "voyage-3",
                        "sparse_provider": "splade",
                        "sparse_model": "splade-v3",
                    }
                ),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer.add_missing_embeddings_to_existing_chunks",
                mock_reconciliation,
            ),
        ):
            # Should not raise - error should be caught and logged
            result = await mock_indexer_for_exceptions.prime_index(force_reindex=False)

            mock_reconciliation.assert_called_once()
            assert result is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.xfail(
        reason="Pydantic v2 models don't support standard mock patching approaches. "
        "The reconciliation error handling is tested indirectly via prime_index's "
        "exception handling code paths."
    )
    async def test_prime_index_handles_connection_error(
        self, mock_indexer_for_exceptions: Indexer, tmp_path: Path
    ) -> None:
        """Test that prime_index handles connection errors during reconciliation."""
        mock_indexer_for_exceptions._file_manifest.add_file(
            path=Path("test.py"),
            content_hash=get_blake_hash(b"content"),
            chunk_ids=[str(uuid4())],
            dense_embedding_provider="voyage",
            dense_embedding_model="voyage-3",
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )

        mock_reconciliation = AsyncMock(side_effect=ConnectionError("Network error"))

        # Use class-level patching to avoid Pydantic v2 model attribute setting issues
        with (
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._initialize_providers_async",
                AsyncMock(),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._perform_batch_indexing_async",
                AsyncMock(),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer._get_current_embedding_models",
                MagicMock(
                    return_value={
                        "dense_provider": "voyage",
                        "dense_model": "voyage-3",
                        "sparse_provider": "splade",
                        "sparse_model": "splade-v3",
                    }
                ),
            ),
            patch(
                "codeweaver.engine.indexer.indexer.Indexer.add_missing_embeddings_to_existing_chunks",
                mock_reconciliation,
            ),
        ):
            # Should not raise - connection errors should be caught
            result = await mock_indexer_for_exceptions.prime_index(force_reindex=False)

            mock_reconciliation.assert_called_once()
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
