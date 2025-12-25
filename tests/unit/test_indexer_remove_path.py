# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for indexer _remove_path method, specifically for deleted files."""

from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from codeweaver.common.utils import uuid7
from codeweaver.common.utils.git import Missing
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.engine.indexer.indexer import Indexer
from codeweaver.engine.indexer.manifest import IndexFileManifest


pytestmark = [pytest.mark.unit]


@pytest.mark.mock_only
@pytest.mark.unit
class TestRemovePathWithDeletedFiles:
    """Test that _remove_path correctly handles deleted files."""

    @pytest.fixture
    async def mock_indexer(self, tmp_path: Path):
        """Create an indexer with mocked dependencies using DI."""
        from codeweaver.di import get_container

        container = get_container()
        container.clear_overrides()

        indexer = await container.resolve(Indexer)
        indexer._project_path = tmp_path
        indexer._file_manifest = IndexFileManifest(project_path=tmp_path)
        return indexer

    @pytest.mark.asyncio
    async def test_remove_deleted_file_from_store(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test that _remove_path can remove entries for files that no longer exist."""
        test_file = self._create_temp_file_and_index(tmp_path, "to_delete.py", mock_indexer)
        # Now delete the file
        test_file.unlink()
        assert not test_file.exists()

        self._validate_malformed_entry_removal(mock_indexer, test_file, 0)

    @pytest.mark.asyncio
    async def test_remove_existing_file_from_store(self, mock_indexer: Indexer, tmp_path: Path) -> None:
        """Test that _remove_path works for files that still exist (regression test)."""
        test_file = self._create_temp_file_and_index(tmp_path, "existing.py", mock_indexer)
        self._validate_malformed_entry_removal(mock_indexer, test_file, 0)

    @pytest.mark.asyncio
    async def test_remove_nonexistent_file_returns_zero(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test that _remove_path returns 0 for paths not in store."""
        # Create a file not in the store
        nonexistent_file = tmp_path / "not_in_store.py"

        # Try to remove it (should return 0)
        removed_count = mock_indexer._remove_path(nonexistent_file)

        # Verify no removal occurred
        assert removed_count == 0

    def _create_temp_file_and_index(self, tmp_path: Path, filename: str, mock_indexer: Indexer):
        result = tmp_path / filename
        result.write_text("def example(): pass")
        with (
            patch(
                "codeweaver.core.discovery.set_relative_path",
                side_effect=lambda p, **kwargs: Path(p).relative_to(tmp_path) if Path(p).is_absolute() else p,
            ),
            patch("codeweaver.core.discovery.get_git_branch", return_value="main"),
        ):
            discovered = DiscoveredFile.from_path(result)
            assert discovered is not None
            assert mock_indexer._store is not None
            mock_indexer._store[str(discovered.source_id)] = discovered
        assert mock_indexer._store is not None
        assert len(mock_indexer._store) == 1
        return result

    @pytest.mark.asyncio
    async def test_remove_with_multiple_files_in_store(
        self, mock_indexer: Indexer, tmp_path: Path
    ) -> None:
        """Test that _remove_path only removes the specified file from a store with multiple files."""
        file1 = tmp_path / "file1.py"
        file1.write_text("def file1(): pass")
        file2 = tmp_path / "file2.py"
        file2.write_text("def file2(): pass")
        file3 = tmp_path / "file3.py"
        file3.write_text("def file3(): pass")
        with (
            patch(
                "codeweaver.core.discovery.set_relative_path",
                side_effect=lambda p, **kwargs: Path(p).relative_to(tmp_path) if Path(p).is_absolute() else p,
            ),
            patch("codeweaver.core.discovery.get_git_branch", return_value="main"),
        ):
            assert mock_indexer._store is not None
            for f in [file1, file2, file3]:
                discovered = DiscoveredFile.from_path(f)
                assert discovered is not None
                unique_id = str(uuid7())
                git_branch = discovered.git_branch
                resolved_branch = None if isinstance(git_branch, Missing) else git_branch
                discovered = DiscoveredFile(
                    path=discovered.path,
                    ext_kind=discovered.ext_kind,
                    file_hash=discovered.file_hash,
                    git_branch=resolved_branch,
                    source_id=unique_id,
                )
                from codeweaver.core.stores import BlakeKey

                mock_indexer._store[cast(BlakeKey, unique_id)] = discovered
        self._test_malformed_entry_removal_gracefully(mock_indexer, file2)
        remaining_paths = [item.path.name for item in mock_indexer._store.values()]
        assert "file1.py" in remaining_paths
        assert "file3.py" in remaining_paths
        assert "file2.py" not in remaining_paths

    @pytest.mark.asyncio
    async def test_remove_handles_malformed_entries_gracefully(
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
        with (
            patch(
                "codeweaver.core.discovery.set_relative_path",
                side_effect=lambda p, **kwargs: Path(p).relative_to(tmp_path) if Path(p).is_absolute() else p,
            ),
            patch("codeweaver.core.discovery.get_git_branch", return_value="main"),
        ):
            self._test_removal_of_malformed_entries(valid_file, another_file, mock_indexer)
        self._test_malformed_entry_removal_gracefully(mock_indexer, another_file)
        assert "malformed_key" in mock_indexer._store  # ty:ignore[unsupported-operator]

    def _test_malformed_entry_removal_gracefully(self, mock_indexer: Indexer, file_to_remove: Path):
        assert mock_indexer._store is not None
        assert len(mock_indexer._store) == 3
        if file_to_remove.exists():
            file_to_remove.unlink()
        self._validate_malformed_entry_removal(mock_indexer, file_to_remove, 2)

    def _validate_malformed_entry_removal(
        self, mock_indexer: Indexer, file_to_remove: Path, expected_length: int
    ):
        removed_count = mock_indexer._remove_path(file_to_remove)
        assert removed_count == 1
        assert mock_indexer._store is not None
        assert len(mock_indexer._store) == expected_length

    def _test_removal_of_malformed_entries(
        self, valid_file: Path, another_file: Path, mock_indexer: Indexer
    ):
        discovered1 = DiscoveredFile.from_path(valid_file)
        discovered2 = DiscoveredFile.from_path(another_file)
        assert discovered1 is not None
        assert discovered2 is not None

        # Create with unique IDs, converting Missing to None
        id1 = str(uuid7())
        id2 = str(uuid7())
        git_branch1 = discovered1.git_branch
        git_branch1_name = None if isinstance(git_branch1, Missing) else git_branch1
        git_branch2 = discovered2.git_branch
        git_branch2_name = None if isinstance(git_branch2, Missing) else git_branch2
        discovered1 = DiscoveredFile(
            path=discovered1.path,
            ext_kind=discovered1.ext_kind,
            file_hash=discovered1.file_hash,
            git_branch=git_branch1_name,
            source_id=id1,
        )
        discovered2 = DiscoveredFile(
            path=discovered2.path,
            ext_kind=discovered2.ext_kind,
            file_hash=discovered2.file_hash,
            git_branch=git_branch2_name,
            source_id=id2,
        )
        assert mock_indexer._store is not None
        mock_indexer._store[id1] = discovered1
        mock_indexer._store[id2] = discovered2

        # Manually add a malformed entry with a path that will cause resolution issues
        bad_discovered = DiscoveredFile(
            path=Path("/nonexistent/bad/path.py"),
            ext_kind=discovered2.ext_kind,
            source_id=str(uuid7()),
        )
        mock_indexer._store["malformed_key"] = bad_discovered
