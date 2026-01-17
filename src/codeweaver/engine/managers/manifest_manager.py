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
from typing import TYPE_CHECKING, Annotated, Any, NotRequired, Required, TypedDict

from pydantic import Field, NonNegativeInt, computed_field
from pydantic_core import from_json

from codeweaver.core import BasedModel, BlakeHashKey, get_blake_hash


if TYPE_CHECKING:
    from codeweaver.core import AnonymityConversion, FilteredKeyT


logger = logging.getLogger(__name__)


class FileManifestEntry(TypedDict):
    """Single file entry in the manifest."""

    # Required fields (present in all versions)
    path: Required[str]  # Relative path from project root
    content_hash: Required[str]  # Blake3 hash of file content
    indexed_at: Required[str]  # ISO8601 timestamp when file was last indexed
    chunk_count: Required[int]  # Number of chunks created from this file
    chunk_ids: Required[list[str]]  # UUIDs of chunks in vector store

    # Optional fields (added in v1.1.0 for embedding tracking)
    dense_embedding_provider: NotRequired[str | None]
    dense_embedding_model: NotRequired[str | None]
    sparse_embedding_provider: NotRequired[str | None]
    sparse_embedding_model: NotRequired[str | None]
    has_dense_embeddings: NotRequired[bool]
    has_sparse_embeddings: NotRequired[bool]


class FileManifestStats(TypedDict):
    """Statistics about the file manifest."""

    total_files: int
    total_chunks: int
    manifest_version: str


class IndexFileManifest(BasedModel):
    """Persistent manifest of indexed files for incremental indexing."""

    project_path: Annotated[Path, Field(description="Path to the indexed codebase")]
    last_updated: datetime = Field(
        description="When manifest was last updated", default_factory=lambda: datetime.now(UTC)
    )

    # Map of relative file path -> FileManifestEntry
    files: dict[str, FileManifestEntry] = Field(
        default_factory=dict, description="Map of file paths to their manifest entries"
    )

    total_files: Annotated[NonNegativeInt, Field(ge=0)] = 0
    total_chunks: Annotated[NonNegativeInt, Field(ge=0)] = 0
    manifest_version: Annotated[str, Field()] = "1.1.0"

    def add_file(
        self,
        path: Path,
        content_hash: BlakeHashKey,
        chunk_ids: list[str],
        *,
        dense_embedding_provider: str | None = None,
        dense_embedding_model: str | None = None,
        sparse_embedding_provider: str | None = None,
        sparse_embedding_model: str | None = None,
        has_dense_embeddings: bool = False,
        has_sparse_embeddings: bool = False,
    ) -> None:
        """Add or update a file in the manifest."""
        # Validate path
        if path is None:
            raise ValueError("Path cannot be None")
        if not path or not str(path) or str(path) == ".":
            raise ValueError(f"Path cannot be empty: {path!r}")
        if path.is_absolute():
            raise ValueError(f"Path must be relative, got absolute path: {path}")
        if ".." in path.parts:
            raise ValueError(f"Path cannot contain path traversal (..), got: {path}")

        raw_path = str(path)

        # Remove old entry if exists
        if raw_path in self.files:
            old_entry = self.files[raw_path]
            self.total_chunks -= old_entry["chunk_count"]
            self.total_files -= 1

        # Add new entry with embedding metadata
        self.files[raw_path] = FileManifestEntry(
            path=raw_path,
            content_hash=str(content_hash),
            indexed_at=datetime.now(UTC).isoformat(),
            chunk_count=len(chunk_ids),
            chunk_ids=chunk_ids,
            dense_embedding_provider=dense_embedding_provider,
            dense_embedding_model=dense_embedding_model,
            sparse_embedding_provider=sparse_embedding_provider,
            sparse_embedding_model=sparse_embedding_model,
            has_dense_embeddings=has_dense_embeddings,
            has_sparse_embeddings=has_sparse_embeddings,
        )
        self.total_files += 1
        self.total_chunks += len(chunk_ids)
        self.last_updated = datetime.now(UTC)

    def remove_file(self, path: Path) -> FileManifestEntry | None:
        """Remove a file from the manifest."""
        if path is None:
            raise ValueError("Path cannot be None")

        raw_path = str(path)
        if raw_path in self.files:
            entry = self.files.pop(raw_path)
            self.total_files -= 1
            self.total_chunks -= entry["chunk_count"]
            self.last_updated = datetime.now(UTC)
            return entry
        return None

    def get_file(self, path: Path) -> FileManifestEntry | None:
        """Get manifest entry for a file."""
        if path is None:
            raise ValueError("Path cannot be None")
        return self.files.get(str(path))

    def has_file(self, path: Path) -> bool:
        """Check if file exists in manifest."""
        if path is None:
            raise ValueError("Path cannot be None")
        return str(path) in self.files

    def file_changed(self, path: Path, current_hash: BlakeHashKey) -> bool:
        """Check if file content has changed."""
        if path is None:
            raise ValueError("Path cannot be None")

        entry = self.get_file(path)
        return True if entry is None else entry["content_hash"] != str(current_hash)

    def get_all_file_paths(self) -> set[Path]:
        """Get set of all file paths in the manifest."""
        return {Path(raw_path) for raw_path in self.files}

    def file_needs_reindexing(
        self,
        path: Path,
        current_hash: BlakeHashKey,
        *,
        current_dense_provider: str | None = None,
        current_dense_model: str | None = None,
        current_sparse_provider: str | None = None,
        current_sparse_model: str | None = None,
    ) -> tuple[bool, str]:
        """Check if file needs reindexing."""
        if path is None:
            raise ValueError("Path cannot be None")

        entry = self.get_file(path)

        # New file - needs indexing
        if entry is None:
            return True, "new_file"

        # Content changed - needs reindexing
        if entry["content_hash"] != str(current_hash):
            return True, "content_changed"

        # Check for embedding model changes
        manifest_dense_provider = entry.get("dense_embedding_provider")
        manifest_dense_model = entry.get("dense_embedding_model")
        if (
            current_dense_provider
            or manifest_dense_provider
            or current_dense_model
            or manifest_dense_model
        ) and (
            manifest_dense_provider != current_dense_provider
            or manifest_dense_model != current_dense_model
        ):
            return True, "dense_embedding_model_changed"

        manifest_sparse_provider = entry.get("sparse_embedding_provider")
        manifest_sparse_model = entry.get("sparse_embedding_model")
        if (
            current_sparse_provider
            or manifest_sparse_provider
            or current_sparse_model
            or manifest_sparse_model
        ) and (
            manifest_sparse_provider != current_sparse_provider
            or manifest_sparse_model != current_sparse_model
        ):
            return True, "sparse_embedding_model_changed"

        return False, "unchanged"

    @computed_field
    def get_stats(self) -> FileManifestStats:
        """Get manifest statistics."""
        return FileManifestStats(
            total_files=self.total_files,
            total_chunks=self.total_chunks,
            manifest_version=self.manifest_version,
        )

    def _telemetry_handler(self, _serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """Telemetry handler for the manifest."""
        return {
            "files": {
                get_blake_hash(path): {
                    key: value for key, value in entry.items() if key not in {"path", "chunk_ids"}
                }
                for path, entry in _serialized_self.get("files", {}).items()
            }
        }

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        """Telemetry keys for the manifest."""
        from codeweaver.core import AnonymityConversion, FilteredKey

        return {FilteredKey("project_path"): AnonymityConversion.HASH}


class FileManifestManager:
    """Manages file manifest save/load operations.

    PURE state management.
    """

    def __init__(self, project_path: Path, project_name: str, manifest_dir: Path):
        """Initialize manifest manager with required paths.

        Args:
            project_path: Path to indexed codebase
            project_name: Name of the project (for filename)
            manifest_dir: Directory for manifest files
        """
        self.project_path = project_path.resolve()
        self.project_name = project_name
        self.manifest_dir = manifest_dir.resolve()

        # Add path hash to filename to avoid collisions between projects with same name
        path_hash = get_blake_hash(str(self.project_path).encode("utf-8"))[:16]
        self.manifest_file = (
            self.manifest_dir / f"file_manifest_{self.project_name}_{path_hash}.json"
        )

    def save(self, manifest: IndexFileManifest) -> bool:
        """Save manifest to disk."""
        manifest.last_updated = datetime.now(UTC)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

        try:
            _ = self.manifest_file.write_text(manifest.model_dump_json(indent=2))
            logger.info("Saved file manifest to %s", self.manifest_file)
        except OSError:
            logger.warning("Failed to save file manifest", exc_info=True)
            return False
        else:
            return True

    def load(self) -> IndexFileManifest | None:
        """Load manifest from disk if available."""
        if not self.manifest_file.exists():
            return None

        try:
            return IndexFileManifest.model_validate(from_json(self.manifest_file.read_bytes()))
        except (OSError, ValueError):
            logger.warning("Failed to load file manifest from %s", self.manifest_file)
            return None

    def delete(self) -> None:
        """Delete manifest file."""
        if self.manifest_file.exists():
            try:
                self.manifest_file.unlink()
                logger.info("Deleted file manifest %s", self.manifest_file)
            except OSError as e:
                logger.warning("Failed to delete manifest: %s", e)

    def create_new(self) -> IndexFileManifest:
        """Create a new empty manifest."""
        return IndexFileManifest(project_path=self.project_path)


__all__ = ("FileManifestEntry", "FileManifestManager", "FileManifestStats", "IndexFileManifest")
