# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for FileChangeTracker functionality."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codeweaver.engine.failover_tracker import FileChangeTracker


pytestmark = [pytest.mark.unit]


@pytest.mark.mock_only
@pytest.mark.unit
class TestFileChangeTrackerBasics:
    """Tests for basic FileChangeTracker operations."""

    def test_init_creates_empty_tracker(self, tmp_path: Path):
        """Test that initializing creates an empty tracker."""
        tracker = FileChangeTracker(project_path=tmp_path)

        assert tracker.file_hashes == {}
        assert tracker.pending_changes == set()
        assert tracker.pending_deletions == set()
        assert tracker.failover_indexed == set()
        assert tracker.last_sync_time is None

    def _get_tracker(self, tmp_path: Path) -> FileChangeTracker:
        return FileChangeTracker(project_path=tmp_path)

    def test_pending_count_sums_changes_and_deletions(self, tmp_path: Path):
        """Test pending_count property."""
        tracker = self._get_tracker(tmp_path)
        tracker.pending_changes = {"a.py", "b.py"}
        tracker.pending_deletions = {"c.py"}

        assert tracker.pending_count == 3

    def test_has_pending_changes_true_when_changes(self, tmp_path: Path):
        """Test has_pending_changes with pending changes."""
        tracker = self._get_tracker(tmp_path)
        tracker.pending_changes = {"a.py", "b.py"}

        assert tracker.has_pending_changes is True

    def test_has_pending_changes_true_when_deletions(self, tmp_path: Path):
        """Test has_pending_changes with pending deletions."""
        tracker = self._get_tracker(tmp_path)
        tracker.pending_deletions = {"c.py"}

        assert tracker.has_pending_changes is True

    def test_has_pending_changes_false_when_empty(self, tmp_path: Path):
        """Test has_pending_changes when empty."""
        tracker = self._get_tracker(tmp_path)

        assert tracker.has_pending_changes is False

    def test_has_failover_files(self, tmp_path: Path):
        """Test has_failover_files property."""
        tracker = self._get_tracker(tmp_path)
        assert tracker.has_failover_files is False

        tracker.failover_indexed = {"a.py"}
        assert tracker.has_failover_files is True


@pytest.mark.mock_only
@pytest.mark.unit
class TestRecordFileIndexed:
    """Tests for record_file_indexed method."""

    def _get_tracker(self, tmp_path: Path) -> FileChangeTracker:
        """Create a FileChangeTracker for testing."""
        return FileChangeTracker(project_path=tmp_path)

    def test_records_new_file(self, tmp_path: Path):
        """Test recording a new file."""
        tracker = self._get_tracker(tmp_path)

        self._validate_test_recorded_file(tmp_path, "abc123", tracker)
        assert tracker._dirty is True

    def test_records_modified_file(self, tmp_path: Path):
        """Test recording a modified file (different hash)."""
        tracker = self._get_tracker(tmp_path)
        tracker.file_hashes["src/test.py"] = "old_hash"

        self._validate_test_recorded_file(tmp_path, "new_hash", tracker)

    def _validate_test_recorded_file(
        self, tmp_path: Path, file_hash: str, tracker: FileChangeTracker
    ):
        self._mock_file_recording(tmp_path, file_hash, tracker)
        assert "src/test.py" in tracker.pending_changes
        assert tracker.file_hashes["src/test.py"] == file_hash

    def test_skips_unchanged_file(self, tmp_path: Path):
        """Test that unchanged files are skipped."""
        tracker = self._get_tracker(tmp_path)
        tracker.file_hashes["src/test.py"] = "same_hash"

        self._mock_file_recording(tmp_path, "same_hash", tracker)
        assert "src/test.py" not in tracker.pending_changes
        assert tracker._dirty is False

    def _mock_file_recording(self, tmp_path: Path, file_hash: str, tracker: FileChangeTracker):
        mock_file = MagicMock()
        mock_file.path = tmp_path / "src" / "test.py"
        mock_file.file_hash = file_hash
        with patch("codeweaver.engine.failover_tracker.set_relative_path") as mock_rel:
            mock_rel.return_value = Path("src/test.py")
            tracker.record_file_indexed(mock_file)


@pytest.mark.mock_only
@pytest.mark.unit
class TestRecordFileDeleted:
    """Tests for record_file_deleted method."""

    def test_records_deletion(self, tmp_path: Path):
        """Test recording a file deletion."""
        tracker = FileChangeTracker(project_path=tmp_path)
        tracker.file_hashes["src/test.py"] = "hash123"
        tracker.pending_changes.add("src/test.py")

        with patch("codeweaver.engine.failover_tracker.set_relative_path") as mock_rel:
            mock_rel.return_value = Path("src/test.py")
            tracker.record_file_deleted(tmp_path / "src" / "test.py")

        assert "src/test.py" in tracker.pending_deletions
        assert "src/test.py" not in tracker.file_hashes
        assert "src/test.py" not in tracker.pending_changes
        assert tracker._dirty is True


@pytest.mark.mock_only
@pytest.mark.unit
class TestRecordFailoverIndexed:
    """Tests for record_file_indexed_during_failover method."""

    def test_records_failover_indexed(self, tmp_path: Path):
        """Test recording a file indexed during failover."""
        tracker = FileChangeTracker(project_path=tmp_path)

        with patch("codeweaver.engine.failover_tracker.set_relative_path") as mock_rel:
            mock_rel.return_value = Path("src/test.py")
            tracker.record_file_indexed_during_failover(tmp_path / "src" / "test.py")

        assert "src/test.py" in tracker.failover_indexed
        assert tracker._dirty is True


@pytest.mark.mock_only
@pytest.mark.unit
class TestGetFilesNeedingBackup:
    """Tests for get_files_needing_backup method."""

    def test_returns_absolute_paths(self, tmp_path: Path):
        """Test that absolute paths are returned."""
        tracker = FileChangeTracker(project_path=tmp_path)
        tracker.pending_changes = {"src/a.py", "src/b.py"}
        tracker.pending_deletions = {"src/c.py"}

        files_to_index, files_to_delete = tracker.get_files_needing_backup()

        assert tmp_path / "src/a.py" in files_to_index
        assert tmp_path / "src/b.py" in files_to_index
        assert tmp_path / "src/c.py" in files_to_delete

    def test_returns_empty_without_project_path(self):
        """Test returns empty sets without project path."""
        tracker = FileChangeTracker()
        tracker.pending_changes = {"src/a.py"}

        files_to_index, files_to_delete = tracker.get_files_needing_backup()

        assert files_to_index == set()
        assert files_to_delete == set()


@pytest.mark.mock_only
@pytest.mark.unit
class TestMarkComplete:
    """Tests for mark_backup_complete and mark_primary_recovery_complete."""

    def test_mark_backup_complete(self, tmp_path: Path):
        """Test marking backup sync as complete."""
        tracker = FileChangeTracker(project_path=tmp_path)
        tracker.pending_changes = {"a.py", "b.py"}
        tracker.pending_deletions = {"c.py"}

        tracker.mark_backup_complete()

        assert not tracker.pending_changes
        assert not tracker.pending_deletions
        assert tracker.last_sync_time is not None
        assert tracker._dirty is True

    def test_mark_primary_recovery_complete(self, tmp_path: Path):
        """Test marking primary recovery as complete."""
        tracker = FileChangeTracker(project_path=tmp_path)
        tracker.failover_indexed = {"a.py", "b.py"}

        tracker.mark_primary_recovery_complete()

        assert not tracker.failover_indexed
        assert tracker._dirty is True


@pytest.mark.mock_only
@pytest.mark.unit
class TestTimeSinceLastSync:
    """Tests for time_since_last_sync method."""

    def test_returns_none_when_never_synced(self, tmp_path: Path):
        """Test returns None when never synced."""
        tracker = FileChangeTracker(project_path=tmp_path)

        assert tracker.time_since_last_sync() is None

    def test_returns_seconds_since_sync(self, tmp_path: Path):
        """Test returns seconds since last sync."""
        tracker = FileChangeTracker(project_path=tmp_path)
        tracker.last_sync_time = datetime.now(UTC)

        time_since = tracker.time_since_last_sync()
        assert time_since is not None
        assert time_since >= 0
        assert time_since < 1  # Should be less than 1 second


@pytest.mark.mock_only
@pytest.mark.unit
class TestPersistence:
    """Tests for save and load functionality."""

    def test_save_creates_file(self, tmp_path: Path):
        """Test that save creates the tracker file."""
        tracker = FileChangeTracker(project_path=tmp_path)
        tracker.pending_changes = {"test.py"}
        tracker._dirty = True

        result = tracker.save()

        assert result is True
        assert tracker._persist_path.exists()

    def test_save_skips_when_not_dirty(self, tmp_path: Path):
        """Test that save skips when not dirty."""
        tracker = FileChangeTracker(project_path=tmp_path)
        tracker._dirty = False

        result = tracker.save()

        assert result is True
        # File should not exist since we skipped
        assert not tracker._persist_path.exists()

    def test_load_creates_new_when_not_found(self, tmp_path: Path):
        """Test that load creates new tracker when file not found."""
        tracker = FileChangeTracker.load(tmp_path)

        assert tracker.file_hashes == {}
        assert tracker.pending_changes == set()

    def test_load_restores_state(self, tmp_path: Path):
        """Test that load restores saved state."""
        # Create and save a tracker
        # Use a valid 64-character blake3 hash
        valid_hash = "a" * 64
        tracker1 = FileChangeTracker(project_path=tmp_path)
        tracker1.file_hashes["test.py"] = valid_hash  # ty:ignore[invalid-assignment]
        tracker1.pending_changes = {"test.py"}
        tracker1._dirty = True
        tracker1.save()

        # Load it back
        tracker2 = FileChangeTracker.load(tmp_path)

        assert tracker2.file_hashes == {"test.py": valid_hash}
        assert tracker2.pending_changes == {"test.py"}
        assert tracker2._project_path == tmp_path
        assert tracker2._dirty is False

    def test_load_handles_corrupt_file(self, tmp_path: Path):
        """Test that load handles corrupt file gracefully."""
        from codeweaver.common.utils.utils import backup_file_path

        # Create corrupt file
        persist_path = backup_file_path(project_path=tmp_path)
        persist_path.parent.mkdir(parents=True, exist_ok=True)
        persist_path.write_text("not valid json {{{")

        tracker = FileChangeTracker.load(tmp_path)

        # Should create new tracker
        assert tracker.file_hashes == {}


@pytest.mark.mock_only
@pytest.mark.unit
class TestGetStatus:
    """Tests for get_status method."""

    def test_returns_complete_status(self, tmp_path: Path):
        """Test that get_status returns complete information."""
        tracker = FileChangeTracker(project_path=tmp_path)
        tracker.file_hashes = {"a.py": "h1", "b.py": "h2"}
        tracker.pending_changes = {"a.py"}
        tracker.pending_deletions = {"c.py"}
        tracker.failover_indexed = {"d.py"}
        tracker.last_sync_time = datetime.now(UTC)

        status = tracker.get_status()

        assert status["total_files_tracked"] == 2
        assert status["pending_changes"] == 1
        assert status["pending_deletions"] == 1
        assert status["failover_indexed"] == 1
        assert status["last_sync_time"] is not None
        assert status["time_since_sync_seconds"] is not None
        assert status["needs_sync"] is True
        assert status["needs_primary_recovery"] is True
