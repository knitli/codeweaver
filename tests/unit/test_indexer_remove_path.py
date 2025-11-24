# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for indexer _remove_path method, specifically for deleted files."""

from pathlib import Path
from unittest.mock import patch

import pytest

from codeweaver.common.utils import uuid7
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.engine.indexer.indexer import Indexer
from codeweaver.engine.indexer.manifest import IndexFileManifest


pytestmark = [pytest.mark.unit]


class TestRemovePathWithDeletedFiles:
    """Test that _remove_path correctly handles deleted files."""

    @pytest.fixture
    def mock_indexer(self, tmp_path: Path):
        """Create an indexer with mocked dependencies."""
        indexer = Indexer(project_path=tmp_path, auto_initialize_providers=False)
        indexer._file_manifest = IndexFileManifest(project_path=tmp_path)
        # Ensure project root is set
        indexer._project_root = tmp_path
        return indexer

    def test_remove_deleted_file_from_store(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test that _remove_path can remove entries for files that no longer exist."""
        # Create a test file and add it to the store
        test_file = tmp_path / "to_delete.py"
        test_file.write_text("def example(): pass")

        # Mock set_relative_path to return relative path
        with patch(
            "codeweaver.core.discovery.set_relative_path",
            side_effect=lambda p: Path(p).relative_to(tmp_path) if Path(p).is_absolute() else p,
        ), patch(
            "codeweaver.core.discovery.get_git_branch",
            return_value="main",
        ):
            discovered = DiscoveredFile.from_path(test_file)
            assert discovered is not None
            # Add to store
            mock_indexer._store[str(discovered.source_id)] = discovered

        # Verify file is in store
        assert len(mock_indexer._store) == 1

        # Now delete the file
        test_file.unlink()
        assert not test_file.exists()

        # Try to remove the path from store (this should not raise FileNotFoundError)
        removed_count = mock_indexer._remove_path(test_file)

        # Verify removal succeeded
        assert removed_count == 1
        assert len(mock_indexer._store) == 0

    def test_remove_existing_file_from_store(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test that _remove_path works for files that still exist (regression test)."""
        # Create a test file and add it to the store
        test_file = tmp_path / "existing.py"
        test_file.write_text("def example(): pass")

        # Mock set_relative_path to return relative path
        with patch(
            "codeweaver.core.discovery.set_relative_path",
            side_effect=lambda p: Path(p).relative_to(tmp_path) if Path(p).is_absolute() else p,
        ), patch(
            "codeweaver.core.discovery.get_git_branch",
            return_value="main",
        ):
            discovered = DiscoveredFile.from_path(test_file)
            assert discovered is not None
            # Add to store
            mock_indexer._store[str(discovered.source_id)] = discovered

        # Verify file is in store
        assert len(mock_indexer._store) == 1

        # Remove the path while file still exists
        removed_count = mock_indexer._remove_path(test_file)

        # Verify removal succeeded
        assert removed_count == 1
        assert len(mock_indexer._store) == 0

    def test_remove_nonexistent_file_returns_zero(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test that _remove_path returns 0 for paths not in store."""
        # Create a file not in the store
        nonexistent_file = tmp_path / "not_in_store.py"

        # Try to remove it (should return 0)
        removed_count = mock_indexer._remove_path(nonexistent_file)

        # Verify no removal occurred
        assert removed_count == 0

    def test_remove_with_multiple_files_in_store(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test that _remove_path only removes the specified file from a store with multiple files."""
        # Create multiple test files
        file1 = tmp_path / "file1.py"
        file1.write_text("def file1(): pass")
        file2 = tmp_path / "file2.py"
        file2.write_text("def file2(): pass")
        file3 = tmp_path / "file3.py"
        file3.write_text("def file3(): pass")

        # Add all files to store with unique source IDs to work around existing bug
        with patch(
            "codeweaver.core.discovery.set_relative_path",
            side_effect=lambda p: Path(p).relative_to(tmp_path) if Path(p).is_absolute() else p,
        ), patch(
            "codeweaver.core.discovery.get_git_branch",
            return_value="main",
        ):
            for f in [file1, file2, file3]:
                discovered = DiscoveredFile.from_path(f)
                assert discovered is not None
                # Use a unique source_id for each file to work around UUID reuse bug
                unique_id = str(uuid7())
                # Re-create with unique ID
                discovered = DiscoveredFile(
                    path=discovered.path,
                    ext_kind=discovered.ext_kind,
                    file_hash=discovered._file_hash,
                    git_branch=discovered._git_branch,
                    source_id=unique_id,
                )
                mock_indexer._store[unique_id] = discovered

        # Verify all files are in store
        assert len(mock_indexer._store) == 3

        # Delete file2 and remove it from store
        file2.unlink()
        removed_count = mock_indexer._remove_path(file2)

        # Verify only file2 was removed
        assert removed_count == 1
        assert len(mock_indexer._store) == 2

        # Verify file1 and file3 are still in store
        remaining_paths = [item.path.name for item in mock_indexer._store.values()]
        assert "file1.py" in remaining_paths
        assert "file3.py" in remaining_paths
        assert "file2.py" not in remaining_paths

    def test_remove_handles_malformed_entries_gracefully(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test that _remove_path handles malformed entries without breaking cleanup."""
        # Create a valid file
        valid_file = tmp_path / "valid.py"
        valid_file.write_text("def valid(): pass")

        # Create another file to delete
        another_file = tmp_path / "another.py"
        another_file.write_text("def another(): pass")

        # Add valid entry and another file to store with unique IDs
        with patch(
            "codeweaver.core.discovery.set_relative_path",
            side_effect=lambda p: Path(p).relative_to(tmp_path) if Path(p).is_absolute() else p,
        ), patch(
            "codeweaver.core.discovery.get_git_branch",
            return_value="main",
        ):
            discovered1 = DiscoveredFile.from_path(valid_file)
            discovered2 = DiscoveredFile.from_path(another_file)
            assert discovered1 is not None
            assert discovered2 is not None

            # Create with unique IDs
            id1 = str(uuid7())
            id2 = str(uuid7())
            discovered1 = DiscoveredFile(
                path=discovered1.path,
                ext_kind=discovered1.ext_kind,
                file_hash=discovered1._file_hash,
                git_branch=discovered1._git_branch,
                source_id=id1,
            )
            discovered2 = DiscoveredFile(
                path=discovered2.path,
                ext_kind=discovered2.ext_kind,
                file_hash=discovered2._file_hash,
                git_branch=discovered2._git_branch,
                source_id=id2,
            )

            mock_indexer._store[id1] = discovered1
            mock_indexer._store[id2] = discovered2

            # Manually add a malformed entry with a path that will cause resolution issues
            bad_discovered = DiscoveredFile(
                path=Path("/nonexistent/bad/path.py"),
                ext_kind=discovered2.ext_kind,
                source_id=str(uuid7()),
            )
            mock_indexer._store["malformed_key"] = bad_discovered

        # Verify store has 3 entries
        assert len(mock_indexer._store) == 3

        # Delete another_file and remove it
        another_file.unlink()
        removed_count = mock_indexer._remove_path(another_file)

        # Should have removed only another_file, other entries should remain
        # (even the malformed one, because it doesn't match)
        assert removed_count == 1
        assert len(mock_indexer._store) == 2
        assert "malformed_key" in mock_indexer._store


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
