# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for indexer stale point removal and orphan detection."""

from pathlib import Path

import pytest

from codeweaver.core import get_blake_hash
from codeweaver.engine import IndexFileManifest, IndexingService


pytestmark = [pytest.mark.unit]


@pytest.fixture
async def mock_indexer(tmp_path: Path, mock_vector_store, monkeypatch: pytest.MonkeyPatch):
    """Create an indexer with mocked dependencies for unit testing."""
    from unittest.mock import AsyncMock, MagicMock

    from codeweaver.engine import IndexingService

    # Change to tmp_path so relative paths work correctly
    monkeypatch.chdir(tmp_path)

    # Create IndexingService directly with mocked dependencies
    indexer = IndexingService.__new__(IndexingService)
    indexer._project_path = tmp_path
    indexer._file_manifest = IndexFileManifest(project_path=tmp_path)
    indexer._vector_store = mock_vector_store
    indexer._checkpoint_manager = MagicMock()
    indexer._checkpoint_manager.project_path = tmp_path
    indexer._manifest_manager = MagicMock()
    indexer._manifest_manager.project_path = tmp_path
    indexer._embedding_provider = AsyncMock()
    indexer._sparse_provider = AsyncMock()
    indexer._chunking_service = MagicMock()

    # chunk_files is an async generator; return an async-iterable empty result
    async def _empty_chunk_files(_files):
        return
        yield  # Makes this an async generator

    indexer._chunking_service.chunk_files = _empty_chunk_files
    indexer._progress_tracker = MagicMock()
    indexer._progress_tracker.get_stats = MagicMock(return_value=MagicMock(files_processed=0))

    # Create async lock mock
    from asyncio import Lock

    indexer._manifest_lock = Lock()

    indexer._providers_initialized = True

    return indexer


@pytest.mark.async_test
@pytest.mark.unit
@pytest.mark.mock_only
class TestStalePointRemovalInBatchIndexing:
    """Test that _index_files_batch deletes old chunks for modified files."""

    @pytest.mark.asyncio
    async def test_batch_deletes_old_chunks_for_modified_files(
        self, mock_indexer: IndexingService, tmp_path: Path
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

        # Index batch - pass as list of tuples (Path, content)
        await mock_indexer._index_files_batch([(modified_file, None), (new_file, None)], None)

        # Verify delete_by_files was called with relative paths
        mock_indexer._vector_store.delete_by_files.assert_called_once_with([
            rel_path,
            Path("new.py"),
        ])

    @pytest.mark.asyncio
    async def test_batch_deletes_multiple_modified_files(
        self, mock_indexer: IndexingService, tmp_path: Path
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

        # Index batch - pass as list of tuples
        await mock_indexer._index_files_batch([(file1, None), (file2, None)], None)

        # Verify delete_by_files was called once with both relative paths
        mock_indexer._vector_store.delete_by_files.assert_called_once_with([rel_path1, rel_path2])
