#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for file_writer module."""

from __future__ import annotations

import tempfile

from pathlib import Path

import pytest

from tools.lazy_imports.export_manager.file_writer import BackupPolicy, FileWriter, WriteResult


class TestFileWriter:
    """Test FileWriter class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def writer(self):
        """Create a FileWriter instance."""
        return FileWriter(backup_policy=BackupPolicy.ALWAYS)

    def test_write_new_file(self, writer, temp_dir):
        """Test writing to a new file."""
        target = temp_dir / "test.py"
        content = "# Test file\n__all__ = ['test']\n"

        result = writer.write_file(target, content)

        assert result.success
        assert result.file_path == target
        assert result.backup_path is None
        assert result.error is None
        assert target.exists()
        assert target.read_text() == content

    def test_write_existing_file_creates_backup(self, writer, temp_dir):
        """Test that writing to existing file creates backup."""
        target = temp_dir / "test.py"
        original_content = "# Original\n__all__ = ['old']\n"
        new_content = "# Updated\n__all__ = ['new']\n"

        # Write original
        target.write_text(original_content)

        # Update
        result = writer.write_file(target, new_content)

        assert result.success
        assert target.read_text() == new_content
        # Backup should be cleaned up after successful write
        assert not (temp_dir / "test.py.bak").exists()

    def test_write_invalid_syntax_fails(self, writer, temp_dir):
        """Test that invalid Python syntax is rejected."""
        target = temp_dir / "test.py"
        invalid_content = "def broken(\n"  # Missing closing paren

        result = writer.write_file(target, invalid_content)

        assert not result.success
        assert "syntax error" in result.error.lower()
        assert not target.exists()

    def test_backup_policy_never(self, temp_dir):
        """Test NEVER backup policy."""
        writer = FileWriter(backup_policy=BackupPolicy.NEVER)
        target = temp_dir / "test.py"
        original = "# Original\n__all__ = []\n"
        updated = "# Updated\n__all__ = []\n"

        target.write_text(original)
        result = writer.write_file(target, updated)

        assert result.success
        assert result.backup_path is None
        assert not (temp_dir / "test.py.bak").exists()

    def test_backup_policy_on_change_no_change(self, temp_dir):
        """Test ON_CHANGE policy when content doesn't change."""
        writer = FileWriter(backup_policy=BackupPolicy.ON_CHANGE)
        target = temp_dir / "test.py"
        content = "# Same content\n__all__ = []\n"

        target.write_text(content)
        result = writer.write_file(target, content)

        assert result.success
        assert result.backup_path is None

    def test_backup_policy_on_change_with_change(self, temp_dir):
        """Test ON_CHANGE policy when content changes."""
        writer = FileWriter(backup_policy=BackupPolicy.ON_CHANGE)
        target = temp_dir / "test.py"
        original = "# Original\n__all__ = []\n"
        updated = "# Updated\n__all__ = []\n"

        target.write_text(original)
        result = writer.write_file(target, updated)

        assert result.success
        # Backup cleaned up after successful write
        assert not (temp_dir / "test.py.bak").exists()

    def test_restore_backup(self, writer, temp_dir):
        """Test backup restoration."""
        target = temp_dir / "test.py"
        backup_path = target.with_suffix(".py.bak")

        backup_content = "# Backup content\n__all__ = []\n"
        backup_path.write_text(backup_content)

        result = writer.restore_backup(target)

        assert result.success
        assert target.exists()
        assert target.read_text() == backup_content

    def test_restore_backup_no_backup(self, writer, temp_dir):
        """Test restore_backup when no backup exists."""
        target = temp_dir / "test.py"

        result = writer.restore_backup(target)

        assert not result.success
        assert "no backup file" in result.error.lower()

    def test_cleanup_backups(self, writer, temp_dir):
        """Test backup cleanup."""
        import time

        # Create some backup files
        old_backup = temp_dir / "old.py.bak"
        new_backup = temp_dir / "new.py.bak"

        old_backup.write_text("old")
        new_backup.write_text("new")

        # Make old backup appear old
        old_time = time.time() - (10 * 86400)  # 10 days ago
        import os

        os.utime(old_backup, (old_time, old_time))

        # Clean up backups older than 7 days
        removed = writer.cleanup_backups(temp_dir, max_age_days=7)

        assert removed == 1
        assert not old_backup.exists()
        assert new_backup.exists()

    def test_custom_validator(self, temp_dir):
        """Test custom validation function."""

        def strict_validator(content: str) -> list[str]:
            if "forbidden" in content:
                return ["Content contains forbidden keyword"]
            return []

        writer = FileWriter(validator=strict_validator)
        target = temp_dir / "test.py"

        # Should fail
        result = writer.write_file(target, "forbidden content")
        assert not result.success
        assert "forbidden" in result.error.lower()

        # Should succeed
        result = writer.write_file(target, "allowed content")
        assert result.success

    def test_atomic_write_on_error(self, writer, temp_dir):
        """Test that atomic write preserves original on error."""
        target = temp_dir / "test.py"
        original = "# Original\n__all__ = []\n"
        invalid = "def broken(\n"  # Syntax error

        target.write_text(original)

        result = writer.write_file(target, invalid)

        assert not result.success
        # Original should be preserved
        assert target.read_text() == original

    def test_create_parent_directories(self, writer, temp_dir):
        """Test that parent directories are created."""
        target = temp_dir / "deep" / "nested" / "path" / "test.py"
        content = "# Test\n__all__ = []\n"

        result = writer.write_file(target, content)

        assert result.success
        assert target.exists()
        assert target.parent.exists()

    def test_write_result_success_helper(self):
        """Test WriteResult.success_result helper."""
        target = Path("/tmp/test.py")
        backup = Path("/tmp/test.py.bak")

        result = WriteResult.success_result(target, backup)

        assert result.success
        assert result.file_path == target
        assert result.backup_path == backup
        assert result.error is None

    def test_write_result_failure_helper(self):
        """Test WriteResult.failure_result helper."""
        target = Path("/tmp/test.py")
        error_msg = "Something went wrong"

        result = WriteResult.failure_result(target, error_msg)

        assert not result.success
        assert result.file_path == target
        assert result.backup_path is None
        assert result.error == error_msg


class TestBackupPolicy:
    """Test BackupPolicy enum."""

    def test_policy_values(self):
        """Test that all policy values are defined."""
        assert BackupPolicy.ALWAYS.value == "always"
        assert BackupPolicy.NEVER.value == "never"
        assert BackupPolicy.ON_CHANGE.value == "on_change"

    def test_policy_membership(self):
        """Test policy enum membership."""
        assert BackupPolicy.ALWAYS in BackupPolicy
        assert BackupPolicy.NEVER in BackupPolicy
        assert BackupPolicy.ON_CHANGE in BackupPolicy
