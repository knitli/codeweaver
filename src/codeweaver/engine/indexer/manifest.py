# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""File manifest tracking for incremental indexing.

Maintains persistent state of indexed files with content hashes to enable:
- Detection of new, modified, and deleted files between sessions
- Incremental indexing (skip unchanged files)
- Vector store reconciliation
- Stale entry cleanup
"""

from __future__ import annotations

import logging

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, TypedDict

from pydantic import Field, NonNegativeInt
from pydantic_core import from_json

from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.core.stores import BlakeHashKey
from codeweaver.core.types.models import BasedModel


logger = logging.getLogger(__name__)


class FileManifestEntry(TypedDict):
    """Single file entry in the manifest.

    Tracks file path, content hash, and indexing metadata.
    """

    path: str  # Relative path from project root
    content_hash: str  # Blake3 hash of file content
    indexed_at: str  # ISO8601 timestamp when file was last indexed
    chunk_count: int  # Number of chunks created from this file
    chunk_ids: list[str]  # UUIDs of chunks in vector store


class IndexFileManifest(BasedModel):
    """Persistent manifest of indexed files for incremental indexing.

    Tracks which files have been indexed, their content hashes, and associated
    chunks to enable detection of changes between sessions and efficient cleanup.
    """

    project_path: Annotated[Path, Field(description="Path to the indexed codebase")]
    manifest_version: Annotated[int, Field(description="Manifest format version")] = 1
    last_updated: Annotated[
        datetime,
        Field(
            description="When manifest was last updated", default_factory=lambda: datetime.now(UTC)
        ),
    ]

    # Map of relative file path -> FileManifestEntry
    files: Annotated[
        dict[str, FileManifestEntry],
        Field(default_factory=dict, description="Map of file paths to their manifest entries"),
    ]

    total_files: Annotated[
        NonNegativeInt, Field(ge=0, description="Total files in manifest", default=0)
    ]
    total_chunks: Annotated[
        NonNegativeInt, Field(ge=0, description="Total chunks across all files", default=0)
    ]

    def add_file(self, path: Path, content_hash: BlakeHashKey, chunk_ids: list[str]) -> None:
        """Add or update a file in the manifest.

        Args:
            path: Relative path from project root
            content_hash: Blake3 hash of file content
            chunk_ids: List of chunk UUID strings for this file
        """
        path_str = str(path)

        # Remove old entry if exists
        if path_str in self.files:
            old_entry = self.files[path_str]
            self.total_chunks -= old_entry["chunk_count"]
            self.total_files -= 1

        # Add new entry
        self.files[path_str] = FileManifestEntry(
            path=path_str,
            content_hash=str(content_hash),
            indexed_at=datetime.now(UTC).isoformat(),
            chunk_count=len(chunk_ids),
            chunk_ids=chunk_ids,
        )
        self.total_files += 1
        self.total_chunks += len(chunk_ids)
        self.last_updated = datetime.now(UTC)

    def remove_file(self, path: Path) -> FileManifestEntry | None:
        """Remove a file from the manifest.

        Args:
            path: Relative path from project root

        Returns:
            Removed entry if it existed, None otherwise
        """
        path_str = str(path)
        if path_str in self.files:
            entry = self.files.pop(path_str)
            self.total_files -= 1
            self.total_chunks -= entry["chunk_count"]
            self.last_updated = datetime.now(UTC)
            return entry
        return None

    def get_file(self, path: Path) -> FileManifestEntry | None:
        """Get manifest entry for a file.

        Args:
            path: Relative path from project root

        Returns:
            Manifest entry if file exists in manifest, None otherwise
        """
        return self.files.get(str(path))

    def has_file(self, path: Path) -> bool:
        """Check if file exists in manifest.

        Args:
            path: Relative path from project root

        Returns:
            True if file is in manifest
        """
        return str(path) in self.files

    def file_changed(self, path: Path, current_hash: BlakeHashKey) -> bool:
        """Check if file content has changed since last indexing.

        Args:
            path: Relative path from project root
            current_hash: Current Blake3 hash of file content

        Returns:
            True if file is new or content has changed
        """
        entry = self.get_file(path)
        if entry is None:
            return True  # New file
        return entry["content_hash"] != str(current_hash)

    def get_chunk_ids_for_file(self, path: Path) -> list[str]:
        """Get list of chunk IDs associated with a file.

        Args:
            path: Relative path from project root

        Returns:
            List of chunk UUID strings, empty list if file not in manifest
        """
        entry = self.get_file(path)
        return entry["chunk_ids"] if entry else []

    def get_all_file_paths(self) -> set[Path]:
        """Get set of all file paths in the manifest.

        Returns:
            Set of Path objects for all files in manifest
        """
        return {Path(path_str) for path_str in self.files}

    def get_stats(self) -> dict[str, int]:
        """Get manifest statistics.

        Returns:
            Dictionary with file and chunk counts
        """
        return {
            "total_files": self.total_files,
            "total_chunks": self.total_chunks,
            "manifest_version": self.manifest_version,
        }

    def _telemetry_keys(self) -> None:
        """Telemetry keys for the manifest (none needed)."""
        return


class FileManifestManager:
    """Manages file manifest save/load operations."""

    def __init__(self, project_path: Path, manifest_dir: Path | None = None):
        """Initialize manifest manager.

        Args:
            project_path: Path to indexed codebase
            manifest_dir: Directory for manifest files (default: .codeweaver/)
        """
        self.project_path = project_path.resolve()
        self.manifest_dir = (manifest_dir or get_user_config_dir()).resolve()
        self.manifest_file = self.manifest_dir / f"file_manifest_{self.project_path.name}.json"

    def save(self, manifest: IndexFileManifest) -> None:
        """Save manifest to disk.

        Creates manifest directory if needed. Updates last_updated timestamp.

        Args:
            manifest: Manifest state to save
        """
        # Update timestamp
        manifest.last_updated = datetime.now(UTC)

        # Ensure directory exists
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

        # Write manifest as JSON
        try:
            _ = self.manifest_file.write_text(manifest.model_dump_json(indent=2))
            logger.info(
                "File manifest saved: %d files, %d chunks",
                manifest.total_files,
                manifest.total_chunks,
            )
        except OSError:
            logger.exception("Failed to save file manifest")

    def load(self) -> IndexFileManifest | None:
        """Load manifest from disk if available.

        Returns:
            Manifest state if file exists and is valid, None otherwise
        """
        if not self.manifest_file.exists():
            logger.debug("No manifest file found at %s", self.manifest_file)
            return None

        try:
            manifest = IndexFileManifest.model_validate(from_json(self.manifest_file.read_bytes()))
            logger.info(
                "File manifest loaded: %d files, %d chunks",
                manifest.total_files,
                manifest.total_chunks,
            )
            return manifest
        except (OSError, ValueError):
            logger.warning("Failed to load file manifest, will create new one")
            return None

    def delete(self) -> None:
        """Delete manifest file (e.g., after full reindex)."""
        if self.manifest_file.exists():
            try:
                self.manifest_file.unlink()
                logger.info("File manifest deleted")
            except OSError as e:
                logger.warning("Failed to delete manifest: %s", e)

    def create_new(self) -> IndexFileManifest:
        """Create a new empty manifest.

        Returns:
            New manifest instance for the project
        """
        return IndexFileManifest(project_path=self.project_path)


__all__ = ("FileManifestEntry", "FileManifestManager", "IndexFileManifest")
