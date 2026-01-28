# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Checkpoint and resume functionality for indexing pipeline.

Persists indexing state to enable resumption after interruption.
"""

from __future__ import annotations

import logging
import re

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, TypedDict, cast
from uuid import UUID

from pydantic import UUID7, DirectoryPath, Field, NonNegativeInt
from pydantic_core import from_json, to_json

from codeweaver.core import (
    INJECTED,
    BasedModel,
    BlakeHashKey,
    CodeWeaverSettingsType,
    ResolvedProjectNameDep,
    ResolvedProjectPathDep,
    get_blake_hash,
    uuid7,
)
from codeweaver.engine.config import IndexerSettings
from codeweaver.providers import (
    EmbeddingProviderSettings,
    SparseEmbeddingProviderSettings,
    VectorStoreProviderSettings,
)


if TYPE_CHECKING:
    from codeweaver.core import AnonymityConversion, FilteredKeyT

logger = logging.getLogger(__name__)


EXCEPTION_PATTERN = re.compile(r"\b\w+(Exception|Error|Failure|Fault|Abort|Abortive)\b")


class CheckpointSettingsFingerprint(TypedDict):
    """Subset of settings relevant for checkpoint hashing."""

    indexer: dict[str, Any]
    project_path: DirectoryPath
    project_name: str
    embedding_provider: tuple[EmbeddingProviderSettings, ...] | None
    sparse_provider: tuple[SparseEmbeddingProviderSettings, ...] | None
    vector_store: tuple[VectorStoreProviderSettings, ...] | None


def get_checkpoint_settings_map(
    project_path: ResolvedProjectPathDep = INJECTED, project_name: ResolvedProjectNameDep = INJECTED
) -> CheckpointSettingsFingerprint:
    """Get relevant settings for checkpoint hashing.

    Note: This is a helper for the manager/checkpoint to use.
    It still needs access to the global settings to compute the hash.

    # We could also consider vector store changes more carefully -- we can migrate vector stores without reindexing if needed.
    """
    from codeweaver.core import get_settings

    # These values will already have been resolved by dependency injection with defaults if needed
    settings = cast(CodeWeaverSettingsType, get_settings())
    indexer: IndexerSettings = cast(IndexerSettings, settings.indexer)  # ty:ignore[unresolved-attribute]

    indexer_map = indexer.model_dump(mode="json", exclude_computed_fields=True, exclude_none=True)

    return CheckpointSettingsFingerprint(
        indexer=indexer_map,
        embedding_provider=settings.provider.embedding,  # ty:ignore[unresolved-attribute]
        sparse_provider=settings.provider.sparse_embedding,  # ty:ignore[unresolved-attribute]
        vector_store=settings.provider.vector_store,  # ty:ignore[unresolved-attribute]
        project_path=project_path,
        project_name=project_name,
    )


class IndexingCheckpoint(BasedModel):
    """Persistent checkpoint for indexing pipeline state."""

    session_id: Annotated[UUID7, Field(description="Unique session identifier (UUIDv7)")] = cast(
        UUID, uuid7()
    )  # type: ignore

    project_path: Annotated[Path | None, Field(description="Path to the indexed codebase")] = None

    start_time: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When indexing started (ISO8601 UTC)"
    )
    last_checkpoint: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When checkpoint was last saved (ISO8601 UTC)",
    )

    # File progress tracking
    files_discovered: Annotated[NonNegativeInt, Field(ge=0)] = 0
    files_embedding_complete: Annotated[NonNegativeInt, Field(ge=0)] = 0
    files_indexed: Annotated[NonNegativeInt, Field(ge=0)] = 0
    files_with_errors: list[str] = Field(default_factory=list)

    # Chunk progress tracking
    chunks_created: Annotated[NonNegativeInt, Field(ge=0)] = 0
    chunks_embedded: Annotated[NonNegativeInt, Field(ge=0)] = 0
    chunks_indexed: Annotated[NonNegativeInt, Field(ge=0)] = 0

    # Batch tracking
    batch_ids_completed: list[str] = Field(default_factory=list)
    current_batch_id: Annotated[UUID7 | None, Field()] = None

    # Error tracking
    errors: list[dict[str, str]] = Field(default_factory=list)

    # Settings hash for invalidation
    settings_hash: Annotated[
        BlakeHashKey | None, Field(description="Blake3 hash of indexing settings")
    ] = None

    def __init__(self, **data: Any):
        """Initialize checkpoint."""
        super().__init__(**data)
        if self.project_path:
            self.project_path = Path(self.project_path).resolve()
        if not self.settings_hash:
            self.settings_hash = self.current_settings_hash()

    def current_settings_hash(self) -> BlakeHashKey:
        """Compute Blake3 hash of current settings."""
        return get_blake_hash(to_json(get_checkpoint_settings_map()))

    def _telemetry_handler(self, _serialized_self: dict[str, Any]) -> dict[str, Any]:
        if errors := self.errors:
            from codeweaver.core import AnonymityConversion

            converted = AnonymityConversion.DISTRIBUTION.filtered([
                EXCEPTION_PATTERN.findall(val)
                for e in errors
                for val in e.values()
                if val and EXCEPTION_PATTERN.search(val)
            ])
            _serialized_self["errors"] = converted
        return _serialized_self

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core import AnonymityConversion, FilteredKey

        return {
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("files_with_errors"): AnonymityConversion.COUNT,
        }

    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Check if checkpoint is too old or settings mismatch."""
        age_hours = (datetime.now(UTC) - self.last_checkpoint).total_seconds() / 3600
        return (
            (age_hours > max_age_hours)
            or (age_hours < 0)
            or (self.last_checkpoint < self.start_time)
            or (not self.matches_settings())
        )

    def matches_settings(self) -> bool:
        """Check if checkpoint settings match current configuration."""
        return self.settings_hash == self.current_settings_hash()


class CheckpointManager:
    """Manages checkpoint save/load operations for indexing pipeline.

    PURE state management. No default configuration fetching.
    """

    def __init__(self, project_path: Path, project_name: str, checkpoint_dir: Path):
        """Initialize checkpoint manager with required paths.

        Args:
            project_path: Path to indexed codebase
            project_name: Name of the project (for filename)
            checkpoint_dir: Directory for checkpoint files
        """
        self.project_path = project_path.resolve()
        self.project_name = project_name
        self.checkpoint_dir = checkpoint_dir.resolve()

        # Consistent filename pattern
        project_hash = get_blake_hash(str(self.project_path).encode("utf-8"))[:8]
        self.checkpoint_file = (
            self.checkpoint_dir / f"checkpoint_{self.project_name}-{project_hash}.json"
        )

    @property
    def checkpoint_path(self) -> Path:
        """Get full path to checkpoint file."""
        return self.checkpoint_file.resolve()

    def save(self, checkpoint: IndexingCheckpoint) -> None:
        """Save checkpoint to disk."""
        checkpoint.last_checkpoint = datetime.now(UTC)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        try:
            _ = self.checkpoint_file.write_text(
                checkpoint.model_dump_json(indent=2, round_trip=True)
            )
            logger.info("Saved indexing checkpoint to %s", self.checkpoint_file)
        except OSError:
            logger.warning("Failed to save checkpoint", exc_info=True)

    def load(self) -> IndexingCheckpoint | None:
        """Load checkpoint from disk if available."""
        if not self.checkpoint_file.exists():
            return None

        try:
            return IndexingCheckpoint.model_validate(from_json(self.checkpoint_file.read_bytes()))
        except (OSError, ValueError):
            logger.warning("Failed to load checkpoint from %s", self.checkpoint_file)
            return None

    def delete(self) -> None:
        """Delete checkpoint file."""
        if self.checkpoint_file.exists():
            try:
                self.checkpoint_file.unlink()
                logger.info("Deleted checkpoint file %s", self.checkpoint_file)
            except OSError as e:
                logger.warning("Failed to delete checkpoint: %s", e)


__all__ = (
    "CheckpointManager",
    "CheckpointSettingsFingerprint",
    "IndexingCheckpoint",
    "get_checkpoint_settings_map",
)
