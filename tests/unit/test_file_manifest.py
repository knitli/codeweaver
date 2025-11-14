# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for incremental indexing with file manifest tracking."""

import tempfile

from pathlib import Path

import pytest

from codeweaver.core.stores import get_blake_hash
from codeweaver.engine.indexer.manifest import FileManifestManager, IndexFileManifest


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def manifest_manager(temp_project_dir):
    """Create a manifest manager for testing."""
    return FileManifestManager(project_path=temp_project_dir)


@pytest.fixture
def sample_manifest(temp_project_dir):
    """Create a sample manifest with some files."""
    manifest = IndexFileManifest(project_path=temp_project_dir)

    # Add some sample files
    manifest.add_file(
        path=Path("src/main.py"),
        content_hash=get_blake_hash(b"def main(): pass"),
        chunk_ids=["chunk1", "chunk2"],
    )
    manifest.add_file(
        path=Path("src/utils.py"),
        content_hash=get_blake_hash(b"def helper(): pass"),
        chunk_ids=["chunk3"],
    )

    return manifest


class TestIndexFileManifest:
    """Tests for IndexFileManifest class."""

    def test_add_file_new(self, temp_project_dir):
        """Test adding a new file to manifest."""
        manifest = IndexFileManifest(project_path=temp_project_dir)

        path = Path("test.py")
        content_hash = get_blake_hash(b"print('hello')")
        chunk_ids = ["chunk1", "chunk2"]

        manifest.add_file(path, content_hash, chunk_ids)

        assert manifest.total_files == 1
        assert manifest.total_chunks == 2
        assert manifest.has_file(path)

        entry = manifest.get_file(path)
        assert entry is not None
        assert entry["path"] == str(path)
        assert entry["content_hash"] == str(content_hash)
        assert entry["chunk_count"] == 2
        assert entry["chunk_ids"] == chunk_ids

    def test_add_file_update_existing(self, sample_manifest):
        """Test updating an existing file in manifest."""
        path = Path("src/main.py")
        new_hash = get_blake_hash(b"def main(): print('updated')")
        new_chunks = ["chunk1_v2", "chunk2_v2", "chunk3_v2"]

        initial_total = sample_manifest.total_files
        initial_chunks = sample_manifest.total_chunks

        sample_manifest.add_file(path, new_hash, new_chunks)

        assert sample_manifest.total_files == initial_total  # Same file count
        assert (
            sample_manifest.total_chunks == initial_chunks - 2 + 3
        )  # 2 old chunks removed, 3 new added

        entry = sample_manifest.get_file(path)
        assert entry["content_hash"] == str(new_hash)
        assert entry["chunk_count"] == 3
        assert entry["chunk_ids"] == new_chunks

    def test_remove_file(self, sample_manifest):
        """Test removing a file from manifest."""
        path = Path("src/main.py")

        entry = sample_manifest.remove_file(path)

        assert entry is not None
        assert entry["path"] == str(path)
        assert entry["chunk_count"] == 2
        assert sample_manifest.total_files == 1
        assert sample_manifest.total_chunks == 1
        assert not sample_manifest.has_file(path)

    def test_remove_nonexistent_file(self, sample_manifest):
        """Test removing a file that doesn't exist."""
        path = Path("nonexistent.py")

        entry = sample_manifest.remove_file(path)

        assert entry is None
        assert sample_manifest.total_files == 2  # Unchanged

    def test_file_changed_new_file(self, sample_manifest):
        # sourcery skip: class-extract-method
        """Test detecting a new file (not in manifest)."""
        path = Path("new_file.py")
        content_hash = get_blake_hash(b"new content")

        assert sample_manifest.file_changed(path, content_hash)

    def test_file_changed_modified_content(self, sample_manifest):
        """Test detecting file content change."""
        path = Path("src/main.py")
        new_hash = get_blake_hash(b"modified content")

        assert sample_manifest.file_changed(path, new_hash)

    def test_file_unchanged(self, sample_manifest):
        """Test detecting unchanged file."""
        path = Path("src/main.py")
        original_hash = get_blake_hash(b"def main(): pass")

        assert not sample_manifest.file_changed(path, original_hash)

    def test_get_chunk_ids_for_file(self, sample_manifest):
        """Test retrieving chunk IDs for a file."""
        path = Path("src/main.py")

        chunk_ids = sample_manifest.get_chunk_ids_for_file(path)

        assert chunk_ids == ["chunk1", "chunk2"]

    def test_get_chunk_ids_for_nonexistent_file(self, sample_manifest):
        """Test retrieving chunk IDs for nonexistent file."""
        path = Path("nonexistent.py")

        chunk_ids = sample_manifest.get_chunk_ids_for_file(path)

        assert chunk_ids == []

    def test_get_all_file_paths(self, sample_manifest):
        """Test getting all file paths in manifest."""
        paths = sample_manifest.get_all_file_paths()

        assert len(paths) == 2
        assert Path("src/main.py") in paths
        assert Path("src/utils.py") in paths

    def test_get_stats(self, sample_manifest):
        """Test getting manifest statistics."""
        # get_stats is a @computed_field, so access it as a property, not method
        stats = sample_manifest.get_stats

        assert stats["total_files"] == 2
        assert stats["total_chunks"] == 3
        assert stats["manifest_version"] == "1.0.0"  # It's a string


class TestFileManifestManager:
    """Tests for FileManifestManager class."""

    def test_save_and_load(self, manifest_manager, sample_manifest):
        """Test saving and loading manifest."""
        # Save
        manifest_manager.save(sample_manifest)
        assert manifest_manager.manifest_file.exists()

        # Load
        loaded = manifest_manager.load()
        assert loaded is not None
        assert loaded.total_files == sample_manifest.total_files
        assert loaded.total_chunks == sample_manifest.total_chunks
        assert len(loaded.files) == len(sample_manifest.files)

    def test_load_nonexistent(self, manifest_manager):
        """Test loading when no manifest file exists."""
        loaded = manifest_manager.load()
        assert loaded is None

    def test_delete(self, manifest_manager, sample_manifest):
        """Test deleting manifest file."""
        # Save first
        manifest_manager.save(sample_manifest)
        assert manifest_manager.manifest_file.exists()

        # Delete
        manifest_manager.delete()
        assert not manifest_manager.manifest_file.exists()

    def test_create_new(self, manifest_manager, temp_project_dir):
        """Test creating a new manifest."""
        manifest = manifest_manager.create_new()

        assert manifest.project_path == temp_project_dir
        assert manifest.total_files == 0
        assert manifest.total_chunks == 0
        assert len(manifest.files) == 0


class TestIncrementalIndexing:
    """Integration tests for incremental indexing workflow."""

    def test_skip_unchanged_files(self, temp_project_dir):
        """Test that unchanged files are skipped during incremental indexing."""
        manifest = IndexFileManifest(project_path=temp_project_dir)
        unchanged_files = _add_unchanged_files(manifest)
        unchanged_files = _add_unchanged_files(manifest)
        _add_unchanged_files_to_manifest(manifest, unchanged_files)
        files_to_index = [
            path
            for path, original_hash in unchanged_files
            if manifest.file_changed(path, original_hash)
        ]

        assert not files_to_index

    def test_detect_new_files(self, temp_project_dir):
        """Test detecting new files that need indexing."""
        # Create manifest with one file
        manifest = IndexFileManifest(project_path=temp_project_dir)
        manifest.add_file(
            path=Path("existing.py"),
            content_hash=get_blake_hash(b"existing content"),
            chunk_ids=["chunk1"],
        )

        # Simulate file discovery
        discovered_files = [
            Path("existing.py"),  # Already in manifest
            Path("new_file.py"),  # New file
        ]

        # Filter to only new/modified files
        files_to_index = _get_files_to_index(manifest, discovered_files)

        assert len(files_to_index) == 1
        assert Path("new_file.py") in files_to_index

    def test_detect_modified_files(self, temp_project_dir):
        """Test detecting modified files that need reindexing."""
        # Create manifest with original content
        manifest = IndexFileManifest(project_path=temp_project_dir)
        original_hash = get_blake_hash(b"original content")
        manifest.add_file(path=Path("file.py"), content_hash=original_hash, chunk_ids=["chunk1"])

        # Simulate file with modified content
        modified_hash = get_blake_hash(b"modified content")

        assert manifest.file_changed(Path("file.py"), modified_hash)

    def test_detect_deleted_files(self, temp_project_dir):
        """Test detecting files deleted from repository."""
        # Create manifest with three files - explicit test data for clarity
        manifest = IndexFileManifest(project_path=temp_project_dir)
        test_files = [
            (Path("file0.py"), "content0", "chunk0"),
            (Path("file1.py"), "content1", "chunk1"),
            (Path("file2.py"), "content2", "chunk2"),
        ]
        _add_test_files(manifest, test_files)
        # Simulate discovery finding only 2 files
        discovered_files = {Path("file0.py"), Path("file1.py")}
        manifest_files = manifest.get_all_file_paths()

        deleted_files = manifest_files - discovered_files

        assert len(deleted_files) == 1
        assert Path("file2.py") in deleted_files

    def test_update_manifest_after_indexing(self, temp_project_dir):
        """Test updating manifest after successfully indexing a file."""
        manifest = IndexFileManifest(project_path=temp_project_dir)

        # Simulate successful indexing
        path = Path("indexed_file.py")
        content_hash = get_blake_hash(b"file content")
        chunk_ids = ["chunk1", "chunk2", "chunk3"]

        manifest.add_file(path, content_hash, chunk_ids)

        # Verify manifest updated
        assert manifest.has_file(path)
        assert manifest.total_files == 1
        assert manifest.total_chunks == 3

        if entry := manifest.get_file(path):
            assert entry["content_hash"] == str(content_hash)
            assert entry["chunk_count"] == 3
            assert entry["chunk_ids"] == chunk_ids


def _get_files_to_index(manifest, discovered_files):
    """Helper to get new/modified files for indexing."""
    files_to_index = []
    for path in discovered_files:
        # In real code, would compute hash from file content
        if path == Path("new_file.py"):
            current_hash = get_blake_hash(b"new content")
        else:
            current_hash = get_blake_hash(b"existing content")

        if manifest.file_changed(path, current_hash):
            files_to_index.append(path)
    return files_to_index


def _add_unchanged_files(manifest, count=5):
    """Helper to add unchanged files to manifest and return their info."""
    return [
        (Path(f"unchanged{i}.py"), get_blake_hash(f"content{i}".encode())) for i in range(count)
    ]


def _add_unchanged_files_to_manifest(manifest, unchanged_files):
    """Helper to add unchanged files to manifest."""
    for path, content_hash in unchanged_files:
        manifest.add_file(path, content_hash, chunk_ids=[f"chunk{path.stem[-1]}"])


def _add_test_files(manifest, test_files):
    """Helper to add test files to manifest."""
    for path, content, chunk_id in test_files:
        manifest.add_file(
            path=path, content_hash=get_blake_hash(content.encode()), chunk_ids=[chunk_id]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
