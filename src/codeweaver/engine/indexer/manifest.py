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

from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.core.stores import BlakeHashKey
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.models import BasedModel


if TYPE_CHECKING:
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion


logger = logging.getLogger(__name__)


class FileManifestEntry(TypedDict):
    """Single file entry in the manifest.

    Tracks file path, content hash, and indexing metadata including embedding models used.
    
    Uses Required and NotRequired to support backward compatibility with v1.0.0 manifests
    that don't have embedding metadata fields.
    """

    # Required fields (present in all versions)
    path: Required[str]  # Relative path from project root
    content_hash: Required[str]  # Blake3 hash of file content
    indexed_at: Required[str]  # ISO8601 timestamp when file was last indexed
    chunk_count: Required[int]  # Number of chunks created from this file
    chunk_ids: Required[list[str]]  # UUIDs of chunks in vector store
    
    # Optional fields (added in v1.1.0 for embedding tracking)
    dense_embedding_provider: NotRequired[str | None]  # Provider used for dense embeddings (e.g., "openai", "voyage")
    dense_embedding_model: NotRequired[str | None]  # Model used for dense embeddings (e.g., "text-embedding-3-large")
    sparse_embedding_provider: NotRequired[str | None]  # Provider used for sparse embeddings
    sparse_embedding_model: NotRequired[str | None]  # Model used for sparse embeddings
    has_dense_embeddings: NotRequired[bool]  # Whether file chunks have dense embeddings
    has_sparse_embeddings: NotRequired[bool]  # Whether file chunks have sparse embeddings


class FileManifestStats(TypedDict):
    """Statistics about the file manifest."""

    total_files: int
    total_chunks: int
    manifest_version: str


class IndexFileManifest(BasedModel):
    """Persistent manifest of indexed files for incremental indexing.

    Tracks which files have been indexed, their content hashes, and associated
    chunks to enable detection of changes between sessions and efficient cleanup.
    """

    project_path: Annotated[Path, Field(description="Path to the indexed codebase")]
    last_updated: datetime = Field(
        description="When manifest was last updated", default_factory=lambda: datetime.now(UTC)
    )

    # Map of relative file path -> FileManifestEntry
    files: dict[str, FileManifestEntry] = Field(
        default_factory=dict, description="Map of file paths to their manifest entries"
    )

    total_files: Annotated[NonNegativeInt, Field(ge=0, description="Total files in manifest")] = 0
    total_chunks: Annotated[
        NonNegativeInt, Field(ge=0, description="Total chunks across all files")
    ] = 0
    manifest_version: Annotated[str, Field(description="Manifest format version")] = "1.1.0"

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
        """Add or update a file in the manifest.

        Args:
            path: Relative path from project root
            content_hash: Blake3 hash of file content
            chunk_ids: List of chunk UUID7 strings for this file
            dense_embedding_provider: Provider name for dense embeddings (e.g., "openai")
            dense_embedding_model: Model name for dense embeddings (e.g., "text-embedding-3-large")
            sparse_embedding_provider: Provider name for sparse embeddings
            sparse_embedding_model: Model name for sparse embeddings
            has_dense_embeddings: Whether chunks have dense embeddings
            has_sparse_embeddings: Whether chunks have sparse embeddings

        Raises:
            ValueError: If path is None, empty, absolute, or contains path traversal
        """
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
        """Remove a file from the manifest.

        Args:
            path: Relative path from project root

        Returns:
            Removed entry if it existed, None otherwise

        Raises:
            ValueError: If path is None or invalid
        """
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
        """Get manifest entry for a file.

        Args:
            path: Relative path from project root

        Returns:
            Manifest entry if file exists in manifest, None otherwise

        Raises:
            ValueError: If path is None
        """
        if path is None:
            raise ValueError("Path cannot be None")
        return self.files.get(str(path))

    def has_file(self, path: Path) -> bool:
        """Check if file exists in manifest.

        Args:
            path: Relative path from project root

        Returns:
            True if file is in manifest

        Raises:
            ValueError: If path is None
        """
        if path is None:
            raise ValueError("Path cannot be None")
        return str(path) in self.files

    def file_changed(self, path: Path, current_hash: BlakeHashKey) -> bool:
        """Check if file content has changed since last indexing.

        Args:
            path: Relative path from project root
            current_hash: Current Blake3 hash of file content

        Returns:
            True if file is new or content has changed

        Raises:
            ValueError: If path is None
        """
        if path is None:
            raise ValueError("Path cannot be None")

        entry = self.get_file(path)
        return True if entry is None else entry["content_hash"] != str(current_hash)

    def get_chunk_ids_for_file(self, path: Path) -> list[str]:
        """Get list of chunk IDs associated with a file.

        Args:
            path: Relative path from project root

        Returns:
            List of chunk UUID strings, empty list if file not in manifest

        Raises:
            ValueError: If path is None
        """
        if path is None:
            raise ValueError("Path cannot be None")

        entry = self.get_file(path)
        return entry["chunk_ids"] if entry else []

    def get_all_file_paths(self) -> set[Path]:
        """Get set of all file paths in the manifest.

        Returns:
            Set of Path objects for all files in manifest
        """
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
        """Check if file needs reindexing due to content or embedding model changes.

        Args:
            path: Relative path from project root
            current_hash: Current Blake3 hash of file content
            current_dense_provider: Current dense embedding provider name
            current_dense_model: Current dense embedding model name
            current_sparse_provider: Current sparse embedding provider name
            current_sparse_model: Current sparse embedding model name

        Returns:
            Tuple of (needs_reindexing, reason) where reason explains why

        Raises:
            ValueError: If path is None
        """
        if path is None:
            raise ValueError("Path cannot be None")

        entry = self.get_file(path)
        
        # New file - needs indexing
        if entry is None:
            return True, "new_file"
        
        # Content changed - needs reindexing
        if entry["content_hash"] != str(current_hash):
            return True, "content_changed"
        
        # Check for embedding model changes (v1.1.0+ manifests)
        # Dense model changed
        # Dense model changed, added, or removed
        manifest_dense_provider = entry.get("dense_embedding_provider")
        manifest_dense_model = entry.get("dense_embedding_model")
        if current_dense_provider or manifest_dense_provider or current_dense_model or manifest_dense_model:
            if manifest_dense_provider != current_dense_provider or manifest_dense_model != current_dense_model:
                return True, "dense_embedding_model_changed"
        
        # Sparse model changed, added, or removed
        manifest_sparse_provider = entry.get("sparse_embedding_provider")
        manifest_sparse_model = entry.get("sparse_embedding_model")
        if current_sparse_provider or manifest_sparse_provider or current_sparse_model or manifest_sparse_model:
            if manifest_sparse_provider != current_sparse_provider or manifest_sparse_model != current_sparse_model:
                return True, "sparse_embedding_model_changed"
        
        # File up-to-date
        return False, "unchanged"

    def get_embedding_model_info(self, path: Path) -> dict[str, str | bool | None]:
        """Get embedding model information for a file.

        Args:
            path: Relative path from project root

        Returns:
            Dictionary with embedding model info, empty dict if file not in manifest

        Raises:
            ValueError: If path is None
        """
        if path is None:
            raise ValueError("Path cannot be None")

        entry = self.get_file(path)
        if not entry:
            return {}
        
        return {
            "dense_provider": entry.get("dense_embedding_provider"),
            "dense_model": entry.get("dense_embedding_model"),
            "sparse_provider": entry.get("sparse_embedding_provider"),
            "sparse_model": entry.get("sparse_embedding_model"),
            "has_dense": entry.get("has_dense_embeddings", False),
            "has_sparse": entry.get("has_sparse_embeddings", False),
        }

    def get_files_needing_embeddings(
        self,
        *,
        current_dense_provider: str | None = None,
        current_dense_model: str | None = None,
        current_sparse_provider: str | None = None,
        current_sparse_model: str | None = None,
    ) -> dict[str, list[Path]]:
        """Get files that need specific embedding types added.

        This is for selective reindexing where we add missing embeddings
        without reprocessing the entire file.
        
        Note: If a file needs both dense and sparse embeddings, it will be
        categorized under 'dense_only' (processed first). This prioritization
        ensures dense embeddings are added before sparse embeddings.

        Args:
            current_dense_provider: Current dense embedding provider name
            current_dense_model: Current dense embedding model name
            current_sparse_provider: Current sparse embedding provider name
            current_sparse_model: Current sparse embedding model name

        Returns:
            Dictionary with keys 'dense_only' and 'sparse_only' containing
            lists of paths that need those embeddings added
        """
        result: dict[str, list[Path]] = {
            "dense_only": [],
            "sparse_only": [],
        }

        for path_str, entry in self.files.items():
            path = Path(path_str)
            
            # Check if file needs dense embeddings added
            # Criteria: dense provider configured BUT file doesn't have dense embeddings
            if current_dense_provider and current_dense_model:
                has_dense = entry.get("has_dense_embeddings", False)
                if not has_dense:
                    result["dense_only"].append(path)
                    continue  # Skip sparse check if already needs dense
            
            # Check if file needs sparse embeddings added
            # Criteria: sparse provider configured BUT file doesn't have sparse embeddings
            if current_sparse_provider and current_sparse_model:
                has_sparse = entry.get("has_sparse_embeddings", False)
                if not has_sparse:
                    result["sparse_only"].append(path)

        return result

    def get_all_chunk_ids(self) -> set[str]:
        """Get all chunk IDs from all files in the manifest.

        Returns:
            Set of all chunk UUID strings across all files
        """
        chunk_ids: set[str] = set()
        for entry in self.files.values():
            chunk_ids.update(entry["chunk_ids"])
        return chunk_ids

    def get_files_by_embedding_config(
        self,
        *,
        has_dense: bool | None = None,
        has_sparse: bool | None = None,
    ) -> list[Path]:
        """Get files matching specific embedding configuration.

        Args:
            has_dense: Filter by dense embedding presence (None = don't filter)
            has_sparse: Filter by sparse embedding presence (None = don't filter)

        Returns:
            List of paths matching the criteria
        """
        matching_files: list[Path] = []
        
        for path_str, entry in self.files.items():
            # Check dense criteria
            if has_dense is not None:
                entry_has_dense = entry.get("has_dense_embeddings", False)
                if entry_has_dense != has_dense:
                    continue
            
            # Check sparse criteria
            if has_sparse is not None:
                entry_has_sparse = entry.get("has_sparse_embeddings", False)
                if entry_has_sparse != has_sparse:
                    continue
            
            matching_files.append(Path(path_str))
        
        return matching_files

    @computed_field
    def get_stats(self) -> FileManifestStats:
        """Get manifest statistics.

        Returns:
            Dictionary with file and chunk counts
        """
        return FileManifestStats(
            total_files=self.total_files,
            total_chunks=self.total_chunks,
            manifest_version=self.manifest_version,
        )

    def _telemetry_handler(self, _serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """Telemetry handler for the manifest."""
        return {
            "files": {
                hash(path): {
                    key: value for key, value in entry.items() if key not in {"path", "chunk_ids"}
                }
                for path, entry in _serialized_self.get("files", {}).items()
            }
        }

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        """Telemetry keys for the manifest (none needed)."""
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {FilteredKey("project_path"): AnonymityConversion.HASH}


class FileManifestManager:
    """Manages file manifest save/load operations."""

    def __init__(self, project_path: Path, manifest_dir: Path | None = None):
        """Initialize manifest manager.

        Args:
            project_path: Path to indexed codebase
            manifest_dir: Directory for manifest files (default: .codeweaver/)
        """
        from codeweaver.core.stores import get_blake_hash

        # Ensure consistent path normalization: absolute -> resolve -> real path
        # This prevents different representations of the same path from generating different hashes
        self.project_path = project_path.absolute().resolve(strict=False)

        manifest_dir = manifest_dir or get_user_config_dir() / ".indexes/manifests"
        if not manifest_dir.exists():
            manifest_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_dir = manifest_dir.resolve()

        # Add path hash to filename to avoid collisions between projects with same name
        path_hash = get_blake_hash(str(self.project_path))[:16]
        self.manifest_file = (
            self.manifest_dir / f"file_manifest_{self.project_path.name}_{path_hash}.json"
        )

        # Debug logging to help diagnose path mismatches
        logger.debug(
            "FileManifestManager initialized: project_path=%s, hash=%s, manifest=%s",
            self.project_path,
            path_hash,
            self.manifest_file.name,
        )

    def save(self, manifest: IndexFileManifest) -> bool:
        """Save manifest to disk.

        Creates manifest directory if needed. Updates last_updated timestamp.

        Args:
            manifest: Manifest state to save

        Returns:
            True if save was successful, False otherwise
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
            logger.warning("Failed to save file manifest", exc_info=True)
            return False
        else:
            return True

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
        except (OSError, ValueError):
            logger.warning("Failed to load file manifest, will create new one")
            return None
        else:
            return manifest

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
