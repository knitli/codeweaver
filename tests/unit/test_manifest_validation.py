# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Additional tests for manifest validation and edge cases."""

import tempfile

from pathlib import Path

import pytest

from codeweaver.core.stores import get_blake_hash
from codeweaver.engine.indexer.manifest import IndexFileManifest

pytestmark = [pytest.mark.unit]



@pytest.fixture
def manifest():
    """Create a manifest for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield IndexFileManifest(project_path=Path(tmpdir))


class TestManifestValidation:
    """Tests for manifest input validation."""

    def test_add_file_none_path(self, manifest):
        """Test that None path is rejected."""
        with pytest.raises(ValueError, match="Path cannot be None"):
            manifest.add_file(None, get_blake_hash(b"test"), ["chunk1"])

    def test_add_file_empty_path(self, manifest):
        """Test that empty path is rejected."""
        with pytest.raises(ValueError, match="Path cannot be empty"):
            manifest.add_file(Path(""), get_blake_hash(b"test"), ["chunk1"])

    def test_add_file_dot_path(self, manifest):
        """Test that '.' path is rejected."""
        with pytest.raises(ValueError, match="Path cannot be empty"):
            manifest.add_file(Path("."), get_blake_hash(b"test"), ["chunk1"])

    def test_add_file_absolute_path(self, manifest):
        """Test that absolute paths are rejected."""
        with pytest.raises(ValueError, match="Path must be relative"):
            manifest.add_file(Path("/tmp/test.py"), get_blake_hash(b"test"), ["chunk1"])

    def test_add_file_path_traversal(self, manifest):
        """Test that path traversal is rejected."""
        with pytest.raises(ValueError, match="cannot contain path traversal"):
            manifest.add_file(Path("../../../etc/passwd"), get_blake_hash(b"test"), ["chunk1"])

    def test_add_file_empty_chunk_ids(self, manifest):
        """Test that empty chunk_ids is allowed (file with no chunks)."""
        # This should work - a file can have no chunks
        manifest.add_file(Path("test.py"), get_blake_hash(b"test"), [])
        assert manifest.total_files == 1
        assert manifest.total_chunks == 0

    def test_add_file_valid_relative_path(self, manifest):
        """Test that valid relative paths are accepted."""
        manifest.add_file(Path("src/test.py"), get_blake_hash(b"test"), ["chunk1"])
        assert manifest.total_files == 1
        assert manifest.has_file(Path("src/test.py"))

    def test_remove_file_none_path(self, manifest):
        """Test that None path is rejected in remove_file."""
        with pytest.raises(ValueError, match="Path cannot be None"):
            manifest.remove_file(None)

    def test_get_file_none_path(self, manifest):
        """Test that None path is rejected in get_file."""
        with pytest.raises(ValueError, match="Path cannot be None"):
            manifest.get_file(None)

    def test_has_file_none_path(self, manifest):
        """Test that None path is rejected in has_file."""
        with pytest.raises(ValueError, match="Path cannot be None"):
            manifest.has_file(None)

    def test_file_changed_none_path(self, manifest):
        """Test that None path is rejected in file_changed."""
        with pytest.raises(ValueError, match="Path cannot be None"):
            manifest.file_changed(None, get_blake_hash(b"test"))

    def test_get_chunk_ids_none_path(self, manifest):
        """Test that None path is rejected in get_chunk_ids_for_file."""
        with pytest.raises(ValueError, match="Path cannot be None"):
            manifest.get_chunk_ids_for_file(None)


class TestManifestEdgeCases:
    """Tests for manifest edge cases."""

    def test_duplicate_chunk_ids(self, manifest):
        """Test that duplicate chunk IDs are counted correctly."""
        # Duplicate chunk IDs should be stored as-is (caller's responsibility)
        manifest.add_file(Path("test.py"), get_blake_hash(b"test"), ["chunk1", "chunk1"])
        assert manifest.total_chunks == 2  # Count includes duplicates
        entry = manifest.get_file(Path("test.py"))
        assert entry["chunk_count"] == 2
        assert len(entry["chunk_ids"]) == 2

    def test_update_with_different_chunk_count(self, manifest):
        """Test updating a file with different number of chunks."""
        # Add file with 2 chunks
        manifest.add_file(Path("test.py"), get_blake_hash(b"v1"), ["c1", "c2"])
        assert manifest.total_chunks == 2

        # Update with 3 chunks
        manifest.add_file(Path("test.py"), get_blake_hash(b"v2"), ["c1", "c2", "c3"])
        assert manifest.total_chunks == 3
        assert manifest.total_files == 1

    def test_nested_relative_paths(self, manifest):
        """Test that deeply nested relative paths work."""
        deep_path = Path("a/b/c/d/e/f/test.py")
        manifest.add_file(deep_path, get_blake_hash(b"test"), ["chunk1"])
        assert manifest.has_file(deep_path)

    def test_path_with_special_chars(self, manifest):
        """Test paths with special characters."""
        special_path = Path("test-file_v2.0.py")
        manifest.add_file(special_path, get_blake_hash(b"test"), ["chunk1"])
        assert manifest.has_file(special_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
