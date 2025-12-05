# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""File change tracking for backup failover synchronization.

This module provides a FileChangeTracker that monitors which files have changed
since the last backup sync. It operates independently of both primary and backup
stores, tracking only file paths and content hashes to minimize memory usage.

The tracker supports:
- Recording file indexing events (new, modified, deleted)
- Tracking files indexed during failover for primary re-sync
- Persistence to disk for recovery across sessions
- Lazy sync coordination based on time and volume thresholds
"""

from __future__ import annotations

import logging

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field, PrivateAttr

from codeweaver.common.utils.git import set_relative_path
from codeweaver.core.stores import BlakeHashKey
from codeweaver.core.types.models import BasedModel


if TYPE_CHECKING:
    from codeweaver.core.discovery import DiscoveredFile
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT

logger = logging.getLogger(__name__)


class FileChangeTracker(BasedModel):
    """Tracks file changes between backup sync cycles.

    Uses DiscoveredFile hashes to detect changes without keeping
    full file content in memory. This allows efficient tracking of
    which files need to be re-indexed in the backup store.

    The tracker maintains three categories:
    - file_hashes: Current known state of all indexed files
    - pending_changes: Files that have changed since last backup sync
    - pending_deletions: Files deleted since last backup sync

    Additionally, during failover:
    - failover_indexed: Files indexed while primary was down (need primary re-sync)

    Attributes:
        last_sync_time: When the backup was last synchronized
        file_hashes: Map of relative file paths to their content hashes
        pending_changes: Set of files changed since last sync
        pending_deletions: Set of files deleted since last sync
        failover_indexed: Files indexed during failover (need primary re-index)
    """

    # Persisted state
    last_sync_time: Annotated[
        datetime | None, Field(default=None, description="When backup was last synchronized")
    ] = None

    file_hashes: Annotated[
        dict[str, BlakeHashKey],
        Field(default_factory=dict, description="Map of relative file paths to content hashes"),
    ]

    pending_changes: Annotated[
        set[str],
        Field(default_factory=set, description="Relative paths of files changed since last sync"),
    ]

    pending_deletions: Annotated[
        set[str],
        Field(default_factory=set, description="Relative paths of files deleted since last sync"),
    ]

    failover_indexed: Annotated[
        set[str],
        Field(
            default_factory=set,
            description="Relative paths indexed during failover (need primary re-index)",
        ),
    ]
    _version: Annotated[str, PrivateAttr()] = "1.0"

    # Runtime state (not persisted)
    _persist_path: Annotated[Path | None, PrivateAttr()] = None
    _project_path: Annotated[Path | None, PrivateAttr()] = None
    _dirty: Annotated[bool, PrivateAttr()] = False  # Track if state needs saving

    def __init__(self, project_path: Path | None = None, **data: Any) -> None:
        """Initialize the tracker.

        Args:
            project_path: Project root for resolving relative paths and persistence
            **data: Additional model data
        """
        super().__init__(**data)
        self._project_path = project_path
        from codeweaver.common.utils.utils import backup_file_path

        self._persist_path = backup_file_path(project_path=project_path)
        self._dirty = False

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        """Keys to process for telemetry privacy."""
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {
            FilteredKey("file_hashes"): AnonymityConversion.COUNT,
            FilteredKey("pending_changes"): AnonymityConversion.COUNT,
            FilteredKey("pending_deletions"): AnonymityConversion.COUNT,
            FilteredKey("failover_indexed"): AnonymityConversion.COUNT,
        }

    def record_file_indexed(self, discovered_file: DiscoveredFile) -> None:
        """Record that a file was successfully indexed by the primary.

        Compares the file's current hash with the stored hash to determine
        if this is a new file or a modification.

        Args:
            discovered_file: The discovered file that was indexed
        """
        rel_path = set_relative_path(discovered_file.path)
        if not rel_path:
            logger.debug("Could not get relative path for %s", discovered_file.path)
            return

        serialized_rel_path = str(rel_path)
        old_hash = self.file_hashes.get(serialized_rel_path)
        new_hash = discovered_file.file_hash()

        if old_hash != new_hash:
            self.pending_changes.add(serialized_rel_path)
            self.file_hashes[serialized_rel_path] = new_hash
            self._dirty = True
            logger.debug(
                "Recorded file change: %s (hash: %s -> %s)",
                serialized_rel_path,
                old_hash[:8] if old_hash else "new",
                str(new_hash)[:8],
            )

    def record_file_deleted(self, path: Path) -> None:
        """Record that a file was deleted.

        Args:
            path: Absolute path of the deleted file
        """
        rel_path = set_relative_path(path)
        if not rel_path:
            logger.debug("Could not get relative path for deleted file %s", path)
            return

        serialized_rel_path = str(rel_path)
        self.pending_deletions.add(serialized_rel_path)
        self.file_hashes.pop(serialized_rel_path, None)
        self.pending_changes.discard(serialized_rel_path)
        self._dirty = True
        logger.debug("Recorded file deletion: %s", serialized_rel_path)

    def record_file_indexed_during_failover(self, path: Path) -> None:
        """Record that a file was indexed while in failover mode.

        These files will need to be re-indexed by the primary when it recovers.

        Args:
            path: Absolute path of the file indexed during failover
        """
        rel_path = set_relative_path(path)
        if not rel_path:
            logger.debug("Could not get relative path for failover-indexed file %s", path)
            return

        serialized_rel_path = str(rel_path)
        self.failover_indexed.add(serialized_rel_path)
        self._dirty = True
        logger.debug("Recorded failover-indexed file: %s", serialized_rel_path)

    def get_files_needing_backup(self) -> tuple[set[Path], set[Path]]:
        """Get files that need to be synchronized to backup.

        Returns:
            Tuple of (files_to_index, files_to_delete) as absolute paths.
            Both sets contain absolute paths resolved from the project root.
        """
        if not self._project_path:
            logger.warning("No project path set, cannot resolve absolute paths")
            return set(), set()

        files_to_index = {self._project_path / p for p in self.pending_changes}
        files_to_delete = {self._project_path / p for p in self.pending_deletions}

        return files_to_index, files_to_delete

    def get_failover_indexed_files(self) -> set[Path]:
        """Get files that were indexed during failover and need primary re-sync.

        Returns:
            Set of absolute paths that need to be re-indexed by primary.
        """
        if not self._project_path:
            logger.warning("No project path set, cannot resolve absolute paths")
            return set()

        return {self._project_path / p for p in self.failover_indexed}

    def mark_backup_complete(self) -> None:
        """Mark that a backup sync has completed successfully.

        Clears pending changes and deletions, updates sync time.
        Does NOT clear failover_indexed - those need primary re-sync.
        """
        self.pending_changes.clear()
        self.pending_deletions.clear()
        self.last_sync_time = datetime.now(UTC)
        self._dirty = True
        logger.info(
            "Backup sync complete at %s, cleared %d pending changes",
            self.last_sync_time.isoformat(),
            len(self.pending_changes),
        )

    def mark_primary_recovery_complete(self) -> None:
        """Mark that primary has re-indexed all failover files.

        Clears the failover_indexed set.
        """
        count = len(self.failover_indexed)
        self.failover_indexed.clear()
        self._dirty = True
        logger.info("Primary recovery complete, cleared %d failover-indexed files", count)

    @property
    def pending_count(self) -> int:
        """Total number of pending changes (additions + deletions)."""
        return len(self.pending_changes) + len(self.pending_deletions)

    @property
    def has_pending_changes(self) -> bool:
        """Whether there are any pending changes to sync."""
        return bool(self.pending_changes or self.pending_deletions)

    @property
    def has_failover_files(self) -> bool:
        """Whether there are files indexed during failover needing primary re-sync."""
        return bool(self.failover_indexed)

    def time_since_last_sync(self) -> float | None:
        """Seconds since last backup sync, or None if never synced."""
        if not self.last_sync_time:
            return None
        return (datetime.now(UTC) - self.last_sync_time).total_seconds()

    def save(self) -> bool:
        """Persist tracker state to disk.

        Returns:
            True if save was successful, False otherwise.
        """
        if not self._persist_path:
            logger.debug("No persist path configured, skipping save")
            return False

        if not self._dirty:
            logger.debug("No changes to save")
            return True

        try:
            return self._save_tracker_state()
        except Exception as e:
            logger.warning("Failed to save tracker state", exc_info=e)
            return False

    def _save_tracker_state(self):
        # Ensure directory exists
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize state
        state = self.model_dump_json(round_trip=True)

        temp_path = self._persist_path.with_suffix(".tmp")
        temp_path.write_text(state)
        temp_path.replace(str(self._persist_path))

        self._dirty = False
        logger.debug("Saved tracker state to %s", self._persist_path)
        return True

    @classmethod
    def load(cls, project_path: Path) -> FileChangeTracker:
        """Load tracker state from disk, or create new if not found.

        Args:
            project_path: Project root path

        Returns:
            Loaded or new FileChangeTracker instance
        """
        from codeweaver.common.utils.utils import backup_file_path

        persist_path = backup_file_path(project_path=project_path)

        if not persist_path.exists():
            logger.debug("No existing tracker state found, creating new")
            return cls(project_path=project_path)

        try:
            data = persist_path.read_text()
            tracker = cls.model_validate_json(data)
            # Restore runtime state that isn't persisted
            tracker._project_path = project_path
            tracker._persist_path = persist_path
            tracker._dirty = False

            logger.info(
                "Loaded tracker state: %d files tracked, %d pending changes, %d deletions",
                len(tracker.file_hashes),
                len(tracker.pending_changes),
                len(tracker.pending_deletions),
            )
        except Exception as e:
            logger.warning("Failed to load tracker state, creating new", exc_info=e)
            return cls(project_path=project_path)
        else:
            return tracker

    def get_status(self) -> dict[str, Any]:
        """Get current tracker status for reporting.

        Returns:
            Dictionary with tracker status information
        """
        return {
            "total_files_tracked": len(self.file_hashes),
            "pending_changes": len(self.pending_changes),
            "pending_deletions": len(self.pending_deletions),
            "failover_indexed": len(self.failover_indexed),
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "time_since_sync_seconds": self.time_since_last_sync(),
            "needs_sync": self.has_pending_changes,
            "needs_primary_recovery": self.has_failover_files,
        }


__all__ = ["FileChangeTracker"]
