# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for indexer stale point removal and orphan detection."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from codeweaver.core.stores import get_blake_hash
from codeweaver.engine.indexer.indexer import Indexer
from codeweaver.engine.indexer.manifest import IndexFileManifest


pytestmark = [pytest.mark.unit]


@pytest.fixture
async def mock_indexer(tmp_path: Path):
    """Create an indexer with mocked dependencies using DI."""
    from codeweaver.di import get_container
    from codeweaver.engine.chunking_service import ChunkingService
    from codeweaver.providers.vector_stores.base import VectorStoreProvider

    container = get_container()
    container.clear_overrides()

    # Mock vector store
    mock_vs = AsyncMock(spec=VectorStoreProvider)
    mock_vs.delete_by_file = AsyncMock()
    mock_vs.upsert = AsyncMock()
    mock_vs.collection = "test_collection"
    mock_vs.client = MagicMock()
    mock_vs.client.retrieve = AsyncMock()
    mock_vs.client.scroll = AsyncMock(return_value=([], None))
    mock_vs.initialize = AsyncMock()
    mock_vs._initialize = AsyncMock()

    # Mock chunking service
    mock_cs = MagicMock(spec=ChunkingService)
    mock_cs.chunk_file = MagicMock(return_value=[])
    mock_cs.initialize = AsyncMock()

    # Apply overrides
    container.override(VectorStoreProvider, mock_vs)
    container.override(ChunkingService, mock_cs)

    indexer = await container.resolve(Indexer)

    # Ensure project path matches tmp_path
    indexer._project_path = tmp_path
    indexer._checkpoint_manager.project_path = tmp_path
    indexer._manifest_manager.project_path = tmp_path

    # Set up manifest
    indexer._file_manifest = IndexFileManifest(project_path=tmp_path)

    # Manually set providers to avoid initialization overhead
    indexer._vector_store = mock_vs
    indexer._chunking_service = mock_cs
    indexer._providers_initialized = True

    return indexer


class TestStalePointRemovalInIndexFile:
    """Test that _index_file deletes old chunks for modified files."""

    @pytest.mark.asyncio
    async def test_deletes_old_chunks_for_modified_file(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test that old chunks are deleted when reindexing a modified file."""
        # Create a test file
        test_file = tmp_path / "modified.py"
        test_file.write_text("def old_content(): pass")

        # Add file to manifest (simulating previously indexed file)
        # Relativize manually to match what set_relative_path will do
        rel_path = Path("modified.py")
        mock_indexer._file_manifest.add_file(
            path=rel_path,
            content_hash=get_blake_hash(b"old content"),
            chunk_ids=["old-chunk-1", "old-chunk-2"],
        )

        # Index the file (simulating content change)
        await mock_indexer._index_file(test_file)

        # Verify delete_by_file was called for the modified file
        mock_indexer._vector_store.delete_by_file.assert_called_once_with(test_file)

    @pytest.mark.asyncio
    async def test_no_deletion_for_new_file(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test that no deletion occurs for new files not in manifest."""
        # Create a test file (not in manifest)
        test_file = tmp_path / "new_file.py"
        test_file.write_text("def new_function(): pass")

        # Index the new file
        await mock_indexer._index_file(test_file)

        # Verify delete_by_file was NOT called
        mock_indexer._vector_store.delete_by_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletion_continues_on_error(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test that indexing continues even if deletion fails."""
        # Create a test file
        test_file = tmp_path / "modified.py"
        test_file.write_text("def content(): pass")

        # Add file to manifest
        rel_path = Path("modified.py")
        mock_indexer._file_manifest.add_file(
            path=rel_path, content_hash=get_blake_hash(b"old content"), chunk_ids=["old-chunk-1"]
        )

        # Make delete_by_file raise an exception
        mock_indexer._vector_store.delete_by_file.side_effect = Exception("Deletion failed")

        # Index should not raise, just log warning
        await mock_indexer._index_file(test_file)

        # Deletion was attempted
        mock_indexer._vector_store.delete_by_file.assert_called_once()


class TestStalePointRemovalInBatchIndexing:
    """Test that _index_files_batch deletes old chunks for modified files."""

    @pytest.mark.asyncio
    async def test_batch_deletes_old_chunks_for_modified_files(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test that batch indexing deletes old chunks for modified files."""
        # Create test files
        modified_file = tmp_path / "modified.py"
        modified_file.write_text("def modified(): pass")

        new_file = tmp_path / "new.py"
        new_file.write_text("def new(): pass")

        # Add only modified_file to manifest - ENSURE IT MATCHES LOOKUP KEY
        rel_path = Path("modified.py")
        mock_indexer._file_manifest.add_file(
            path=rel_path, content_hash=get_blake_hash(b"old content"), chunk_ids=["old-chunk-1"]
        )

        # Index batch
        await mock_indexer._index_files_batch([modified_file, new_file])

        # Verify delete_by_file was called only for modified_file
        mock_indexer._vector_store.delete_by_file.assert_called_once_with(modified_file)

    @pytest.mark.asyncio
    async def test_batch_deletes_multiple_modified_files(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test that batch indexing deletes old chunks for multiple modified files."""
        # Create test files
        file1 = tmp_path / "file1.py"
        file1.write_text("def file1(): pass")

        file2 = tmp_path / "file2.py"
        file2.write_text("def file2(): pass")

        # Add both files to manifest
        rel_path1 = Path("file1.py")
        rel_path2 = Path("file2.py")
        mock_indexer._file_manifest.add_file(
            path=rel_path1, content_hash=get_blake_hash(b"old1"), chunk_ids=["chunk-1"]
        )
        mock_indexer._file_manifest.add_file(
            path=rel_path2, content_hash=get_blake_hash(b"old2"), chunk_ids=["chunk-2"]
        )

        # Index batch
        await mock_indexer._index_files_batch([file1, file2])

        # Verify delete_by_file was called for both files
        assert mock_indexer._vector_store.delete_by_file.call_count == 2


class TestOrphanDetectionInValidation:
    """Test that validate_manifest_with_vector_store detects orphaned chunks."""

    @pytest.mark.asyncio
    async def test_detects_orphaned_chunks(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test that orphaned chunks in vector store are detected."""
        # Use valid UUIDs for chunk IDs
        chunk_id_1 = str(uuid4())
        chunk_id_2 = str(uuid4())
        orphan_id = str(uuid4())

        # Add file to manifest with specific chunks
        mock_indexer._file_manifest.add_file(
            path=Path("file.py"),
            content_hash=get_blake_hash(b"content"),
            chunk_ids=[chunk_id_1, chunk_id_2],
        )

        # Mock retrieve to return all manifest chunks (none missing)
        mock_point1 = MagicMock()
        mock_point1.id = chunk_id_1
        mock_point2 = MagicMock()
        mock_point2.id = chunk_id_2

        mock_indexer._vector_store.client.retrieve.return_value = [mock_point1, mock_point2]

        # Mock scroll to return orphaned chunks (not in manifest)
        orphan_point = MagicMock()
        orphan_point.id = orphan_id

        mock_indexer._vector_store.client.scroll.return_value = ([orphan_point], None)

        # Run validation
        result = await mock_indexer.validate_manifest_with_vector_store()

        # Verify orphans detected
        assert result["orphaned_chunks"] == 1
        assert orphan_id in result["orphaned_chunk_ids"]
        assert result["missing_chunks"] == 0

    @pytest.mark.asyncio
    async def test_detects_missing_chunks(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test that missing chunks are still detected correctly."""
        # Use valid UUIDs for chunk IDs
        chunk_id_1 = str(uuid4())
        chunk_id_2 = str(uuid4())

        # Add file to manifest with chunks
        mock_indexer._file_manifest.add_file(
            path=Path("file.py"),
            content_hash=get_blake_hash(b"content"),
            chunk_ids=[chunk_id_1, chunk_id_2],
        )

        # Mock retrieve to return only one chunk (one missing)
        mock_point = MagicMock()
        mock_point.id = chunk_id_1

        mock_indexer._vector_store.client.retrieve.return_value = [mock_point]

        # Mock scroll to return no orphans
        mock_indexer._vector_store.client.scroll.return_value = ([], None)

        # Run validation
        result = await mock_indexer.validate_manifest_with_vector_store()

        # Verify missing chunks detected
        assert result["missing_chunks"] == 1
        assert chunk_id_2 in result["missing_chunk_ids"]
        assert "file.py" in result["files_with_missing_chunks"]

    @pytest.mark.asyncio
    async def test_no_issues_when_store_matches_manifest(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test validation passes when store exactly matches manifest."""
        # Use valid UUIDs for chunk IDs
        chunk_id_1 = str(uuid4())
        chunk_id_2 = str(uuid4())

        # Add file to manifest
        mock_indexer._file_manifest.add_file(
            path=Path("file.py"),
            content_hash=get_blake_hash(b"content"),
            chunk_ids=[chunk_id_1, chunk_id_2],
        )

        # Mock retrieve to return all chunks
        mock_point1 = MagicMock()
        mock_point1.id = chunk_id_1
        mock_point2 = MagicMock()
        mock_point2.id = chunk_id_2

        mock_indexer._vector_store.client.retrieve.return_value = [mock_point1, mock_point2]

        # Mock scroll to return no orphans (empty result)
        mock_indexer._vector_store.client.scroll.return_value = ([], None)

        # Run validation
        result = await mock_indexer.validate_manifest_with_vector_store()

        # Verify no issues
        assert result["missing_chunks"] == 0
        assert result["orphaned_chunks"] == 0
        assert len(result["files_with_missing_chunks"]) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_manifest(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test validation handles empty manifest correctly."""
        # Empty manifest (no files added)
        orphan_id = str(uuid4())

        # Mock scroll to return orphaned chunks
        orphan_point = MagicMock()
        orphan_point.id = orphan_id

        mock_indexer._vector_store.client.scroll.return_value = ([orphan_point], None)

        # Run validation
        result = await mock_indexer.validate_manifest_with_vector_store()

        # Verify orphan detected with empty manifest
        assert result["total_chunks"] == 0
        assert result["orphaned_chunks"] == 1
