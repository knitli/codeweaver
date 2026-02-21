#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""File writing operations with atomic writes and backup management.

This module implements safe file writing operations for generated __init__.py files:
- Atomic writes via temp file + rename
- Automatic backup creation
- Validation before commit
- Rollback on failure
- Backup restoration and cleanup
"""

from __future__ import annotations

import ast
import contextlib
import shutil
import tempfile

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable


class BackupPolicy(Enum):
    """Backup file creation policy."""

    ALWAYS = "always"
    NEVER = "never"
    ON_CHANGE = "on_change"


@dataclass(frozen=True)
class WriteResult:
    """Result of a file write operation."""

    success: bool
    file_path: Path
    backup_path: Path | None
    error: str | None

    @classmethod
    def success_result(cls, file_path: Path, backup_path: Path | None) -> WriteResult:
        """Create a success result."""
        return cls(success=True, file_path=file_path, backup_path=backup_path, error=None)

    @classmethod
    def failure_result(cls, file_path: Path, error: str) -> WriteResult:
        """Create a failure result."""
        return cls(success=False, file_path=file_path, backup_path=None, error=error)


class FileWriter:
    """Handles atomic file writes with backup and validation."""

    def __init__(
        self,
        backup_policy: BackupPolicy = BackupPolicy.ALWAYS,
        validator: Callable[[str], list[str]] | None = None,
        max_backups: int = 5,
    ):
        """Initialize file writer.

        Args:
            backup_policy: When to create backup files
            validator: Optional validation function that returns list of errors
            max_backups: Maximum number of timestamped backups to keep (default: 5)
        """
        self.backup_policy = backup_policy
        self.validator = validator or self._default_validator
        self.max_backups = max_backups

    def write_file(self, target: Path, content: str, *, create_backup: bool = True) -> WriteResult:
        """Write file atomically with optional backup.

        Algorithm from requirements Section 8.2.1:
        1. Validate content (AST parse)
        2. Create backup if file exists
        3. Write to temp file
        4. Validate temp file
        5. Atomic rename
        6. Return result

        Args:
            target: Target file path
            content: File content to write
            create_backup: Whether to create backup (respects backup_policy)

        Returns:
            WriteResult with success status and paths
        """
        # 1. Validate content first
        if validation_errors := self.validator(content):
            error_msg = "Generated code has syntax errors:\n" + "\n".join(
                f"  - {err}" for err in validation_errors
            )
            return WriteResult.failure_result(target, error_msg)

        # Ensure parent directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        # 2. Create backup if file exists and policy allows
        backup_path = None
        if target.exists() and create_backup and self._should_backup(target, content):
            backup_path = self._create_timestamped_backup(target)
            if backup_path is None:
                return WriteResult.failure_result(target, f"Cannot create backup of {target}")
            # Clean up old backups after creating new one
            self._cleanup_old_backups(target)

        # 3. Write to temp file
        try:
            _temp_fd, temp_filepath = tempfile.mkstemp(
                suffix=".py", prefix="__init__", dir=target.parent, text=True
            )
            temp_path = Path(temp_filepath)
        except OSError as e:
            return WriteResult.failure_result(target, f"Cannot create temp file: {e}")
        try:
            # Write content
            with temp_path.open("w", encoding="utf-8") as f:
                f.write(content)

            # 4. Validate temp file (redundant but safe)
            temp_content = temp_path.read_text(encoding="utf-8")
            if validation_errors := self.validator(temp_content):
                error_msg = "Temp file validation failed:\n" + "\n".join(
                    f"  - {err}" for err in validation_errors
                )
                return WriteResult.failure_result(target, error_msg)

            # 5. Atomic rename
            temp_path.replace(target)

            # 6. Backup is kept (timestamped backups are not deleted on success)
            return WriteResult.success_result(target, backup_path)

        except OSError as e:
            # Cleanup and rollback on error
            if temp_path.exists():
                temp_path.unlink()

            # Restore from backup if available
            if backup_path and backup_path.exists():
                with contextlib.suppress(OSError):
                    shutil.copy2(backup_path, target)
                    backup_path.unlink()

            error_type = "Permission denied" if isinstance(e, PermissionError) else "Write failed"
            return WriteResult.failure_result(target, f"{error_type}: {e}")

    def restore_backup(self, target: Path, backup_path: Path | None = None) -> WriteResult:
        """Restore file from timestamped backup.

        Args:
            target: Target file path
            backup_path: Specific backup to restore. If None, restores most recent backup.

        Returns:
            WriteResult indicating success or failure
        """
        if backup_path is None:
            # Find most recent timestamped backup
            backup_path = self._find_latest_backup(target)
        if backup_path is None:
            return WriteResult.failure_result(target, f"No backup files found for {target.name}")

        if not backup_path.exists():
            return WriteResult.failure_result(target, f"Backup file not found: {backup_path}")

        try:
            shutil.copy2(backup_path, target)
            return WriteResult.success_result(target, backup_path)
        except OSError as e:
            return WriteResult.failure_result(target, f"Failed to restore backup: {e}")

    def _create_timestamped_backup(self, target: Path) -> Path | None:
        """Create timestamped backup of target file.

        Args:
            target: File to backup

        Returns:
            Path to backup file, or None if backup failed
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup_path = target.with_suffix(f".py.backup.{timestamp}")

        try:
            shutil.copy2(target, backup_path)
        except OSError:
            return None
        else:
            return backup_path

    def _cleanup_old_backups(self, target: Path) -> int:
        """Remove old backup files, keeping only the most recent N.

        Args:
            target: Target file whose backups should be cleaned up

        Returns:
            Number of backup files removed
        """
        # Find all timestamped backups for this file
        backup_pattern = f"{target.stem}.py.backup.*"
        backups = sorted(
            target.parent.glob(backup_pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,  # Most recent first
        )

        # Keep only max_backups most recent
        removed_count = 0
        for backup in backups[self.max_backups :]:
            try:
                backup.unlink()
                removed_count += 1
            except OSError:
                # Skip files we can't remove
                continue

        return removed_count

    def _find_latest_backup(self, target: Path) -> Path | None:
        """Find most recent backup file for target.

        Args:
            target: Target file to find backup for

        Returns:
            Path to most recent backup, or None if no backups exist
        """
        backup_pattern = f"{target.stem}.py.backup.*"
        backups = sorted(
            target.parent.glob(backup_pattern), key=lambda p: p.stat().st_mtime, reverse=True
        )

        return backups[0] if backups else None

    def cleanup_backups(self, directory: Path, *, max_age_days: int = 7) -> int:
        """Remove old backup files.

        Args:
            directory: Directory to scan for backup files
            max_age_days: Maximum age in days for backup files

        Returns:
            Number of backup files removed
        """
        import time

        if not directory.exists():
            return 0

        cutoff_time = time.time() - (max_age_days * 86400)  # days to seconds
        removed_count = 0

        for backup_file in directory.rglob("*.py.bak"):
            try:
                if backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
                    removed_count += 1
            except OSError:
                # Skip files we can't access
                continue

        return removed_count

    def _should_backup(self, target: Path, new_content: str) -> bool:
        """Determine if backup should be created based on policy.

        Args:
            target: Target file path
            new_content: New content to be written

        Returns:
            True if backup should be created
        """
        if self.backup_policy == BackupPolicy.ALWAYS:
            return True
        if self.backup_policy == BackupPolicy.NEVER:
            return False

        # ON_CHANGE: only backup if content differs
        if not target.exists():
            return False

        try:
            existing_content = target.read_text(encoding="utf-8")
        except OSError:
            # If we can't read, play it safe and backup
            return True
        else:
            return existing_content != new_content

    @staticmethod
    def _default_validator(content: str) -> list[str]:
        """Default validation: check Python syntax.

        Args:
            content: Python source code

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        try:
            ast.parse(content)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        return errors


__all__ = ["BackupPolicy", "FileWriter", "WriteResult"]
