# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Checkpoint and resume functionality for indexing pipeline.

Persists indexing state to enable resumption after interruption.
Checkpoints are saved:
- Every 100 files processed
- Every 5 minutes (300 seconds)
- On SIGTERM signal (graceful shutdown)
"""

from __future__ import annotations

import logging
import re

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, TypedDict

from pydantic import UUID7, DirectoryPath, Field, NonNegativeInt
from pydantic_core import from_json, to_json
from uuid_extensions import uuid7

from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.config.indexing import IndexerSettings
from codeweaver.config.providers import (
    EmbeddingProviderSettings,
    RerankingProviderSettings,
    SparseEmbeddingProviderSettings,
    VectorStoreProviderSettings,
)
from codeweaver.core.stores import BlakeHashKey, get_blake_hash
from codeweaver.core.types.models import BasedModel
from codeweaver.core.types.sentinel import Unset


if TYPE_CHECKING:
    from codeweaver.core.types import DictView
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion

logger = logging.getLogger(__name__)


EXCEPTION_PATTERN = re.compile(r"\b\w+(Exception|Error|Failure|Fault|Abort|Abortive)\b")


class CheckpointSettingsFingerprint(TypedDict):
    """Subset of settings relevant for checkpoint hashing."""

    indexer: IndexerSettings
    embedding_provider: tuple[EmbeddingProviderSettings, ...] | None
    reranking_provider: tuple[RerankingProviderSettings, ...] | None
    sparse_provider: tuple[SparseEmbeddingProviderSettings, ...] | None
    vector_store: tuple[VectorStoreProviderSettings, ...] | None
    project_path: DirectoryPath | None
    project_name: str | None


def _get_settings_map() -> DictView[CheckpointSettingsFingerprint]:
    """Get relevant settings for checkpoint hashing.

    Returns:
        Dictionary view of settings affecting indexing

    We don't want to cache this -- we want the latest settings each time. DictView always reflects changes, but we're creating a new instance here.
    """
    from codeweaver.common.utils.git import get_project_path
    from codeweaver.config.indexing import DefaultIndexerSettings, IndexerSettings
    from codeweaver.config.providers import (
        DefaultEmbeddingProviderSettings,
        DefaultRerankingProviderSettings,
        DefaultSparseEmbeddingProviderSettings,
        DefaultVectorStoreProviderSettings,
    )
    from codeweaver.config.settings import get_settings

    settings = get_settings()
    if isinstance(settings.provider, Unset):
        from codeweaver.config.providers import AllDefaultProviderSettings, ProviderSettings

        settings.provider = ProviderSettings.model_validate(AllDefaultProviderSettings)
    settings.indexing = (
        IndexerSettings.model_validate(DefaultIndexerSettings)
        if isinstance(settings.indexing, Unset)
        else settings.indexing
    )
    settings.provider.embedding = (
        DefaultEmbeddingProviderSettings
        if isinstance(settings.provider.embedding, Unset)
        else settings.provider.embedding
    )
    settings.provider.sparse_embedding = (
        DefaultSparseEmbeddingProviderSettings
        if isinstance(settings.provider.sparse_embedding, Unset)
        else settings.provider.sparse_embedding
    )
    settings.provider.vector_store = (
        DefaultVectorStoreProviderSettings
        if isinstance(settings.provider.vector_store, Unset)
        else settings.provider.vector_store
    )
    settings.provider.reranking = (
        DefaultRerankingProviderSettings
        if isinstance(settings.provider.reranking, Unset)
        else settings.provider.reranking
    )
    settings.project_path = (
        get_project_path() if isinstance(settings.project_path, Unset) else settings.project_path
    )
    settings.project_name = (
        settings.project_path.name
        if isinstance(settings.project_name, Unset)
        else settings.project_name
    )
    return DictView(
        CheckpointSettingsFingerprint(
            indexer=settings.indexing,
            embedding_provider=tuple(settings.provider.embedding)
            if settings.provider.embedding
            else None,
            reranking_provider=tuple(settings.provider.reranking)
            if settings.provider.reranking
            else None,
            sparse_provider=tuple(settings.provider.sparse_embedding)
            if settings.provider.sparse_embedding
            else None,
            vector_store=tuple(settings.provider.vector_store)
            if settings.provider.vector_store
            else None,
            project_path=settings.project_path,
            project_name=settings.project_name,
        )
    )


class IndexingCheckpoint(BasedModel):
    """Persistent checkpoint for indexing pipeline state.

    Enables resumption after interruption by tracking processed files,
    created chunks, batch completion status, and errors.
    """

    session_id: Annotated[
        UUID7, Field(description="Unique session identifier (UUIDv7) for this indexing checkpoint")
    ] = uuid7()  # type: ignore
    project_path: Annotated[Path | None, Field(description="Path to the indexed codebase")] = Field(
        default_factory=lambda: _get_settings_map().get("project_path")
    )
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When indexing started (ISO8601 UTC)"
    )
    last_checkpoint: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When checkpoint was last saved (ISO8601 UTC)",
    )

    # File progress tracking
    files_discovered: Annotated[NonNegativeInt, Field(ge=0, description="Total files found")] = 0
    files_embedding_complete: Annotated[
        NonNegativeInt, Field(ge=0, description="Files with embeddings")
    ] = 0
    files_indexed: Annotated[NonNegativeInt, Field(ge=0, description="Files in vector store")] = 0
    files_with_errors: list[str] = Field(
        default_factory=list, description="File paths that failed processing"
    )

    # Chunk progress tracking
    chunks_created: Annotated[NonNegativeInt, Field(ge=0, description="Total chunks created")] = 0
    chunks_embedded: Annotated[
        NonNegativeInt, Field(ge=0, description="Chunks with embeddings")
    ] = 0
    chunks_indexed: Annotated[NonNegativeInt, Field(ge=0, description="Chunks in vector store")] = 0

    # Batch tracking
    batch_ids_completed: list[str] = Field(
        default_factory=list, description="Completed batch IDs (hex UUIDs)"
    )
    current_batch_id: Annotated[
        UUID7 | None, Field(description="Active batch ID (UUID, if any)")
    ] = None

    # Error tracking
    errors: list[dict[str, str]] = Field(
        default_factory=list, description="Error records with file path and error message"
    )

    # Settings hash for invalidation
    settings_hash: Annotated[
        BlakeHashKey | None,
        Field(description="Blake3 hash of indexing settings (detect config changes)"),
    ] = None

    def _telemetry_handler(self, _serialized_self: dict[str, Any]) -> dict[str, Any]:
        if errors := self.errors:
            from codeweaver.core.types.enum import AnonymityConversion

            converted = AnonymityConversion.DISTRIBUTION.filtered([
                EXCEPTION_PATTERN.findall(val)
                for e in errors
                for val in e.values()
                if val and EXCEPTION_PATTERN.search(val)
            ])
            _serialized_self["errors"] = converted
        return _serialized_self

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("files_with_errors"): AnonymityConversion.COUNT,
        }

    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Check if checkpoint is too old to resume safely.

        Args:
            max_age_hours: Maximum age in hours before considering stale

        Returns:
            True if checkpoint is older than max_age_hours
        """
        age_hours = (datetime.now(UTC) - self.last_checkpoint).total_seconds() / 3600
        return age_hours > max_age_hours

    def matches_settings(self, current_settings_hash: str) -> bool:
        """Check if checkpoint settings match current configuration.

        Args:
            current_settings_hash: Blake3 hash of current settings

        Returns:
            True if settings match (safe to resume)
        """
        return self.settings_hash == current_settings_hash


class CheckpointManager:
    """Manages checkpoint save/load operations for indexing pipeline."""

    def __init__(self, project_path: Path | None = None, checkpoint_dir: Path | None = None):
        """Initialize checkpoint manager.

        Args:
            project_path: Path to indexed codebase
            checkpoint_dir: Directory for checkpoint files (default: .codeweaver/)
        """
        settings = _get_settings_map()

        self.project_path = (project_path or settings.get("project_path", Path.cwd())).resolve()

        self.checkpoint_dir = (checkpoint_dir or get_user_config_dir()).resolve()
        self.checkpoint_file = (
            self.checkpoint_dir / f"index_checkpoint_{self.project_path.name}.json"
        )

    def compute_settings_hash(self, settings_dict: CheckpointSettingsFingerprint) -> BlakeHashKey:
        """Compute Blake3 hash of settings for change detection.

        Args:
            settings_dict: Dictionary of relevant settings

        Returns:
            Hex-encoded Blake3 hash of settings
        """
        serialized_settings = to_json(settings_dict)
        return get_blake_hash(serialized_settings)

    def save(self, checkpoint: IndexingCheckpoint) -> None:
        """Save checkpoint to disk.

        Creates checkpoint directory if needed. Updates last_checkpoint timestamp.

        Args:
            checkpoint: Checkpoint state to save
        """
        # Update last checkpoint time
        checkpoint.last_checkpoint = datetime.now(UTC)

        # Ensure checkpoint directory exists
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Write checkpoint as JSON
        try:
            _ = self.checkpoint_file.write_text(
                checkpoint.model_dump_json(indent=2, round_trip=True)
            )
            logger.info(
                "Checkpoint saved: %d/%d files processed, %d chunks created",
                checkpoint.files_indexed,
                checkpoint.files_discovered,
                checkpoint.chunks_created,
            )
        except OSError:
            logger.exception("Failed to save checkpoint")

    def load(self) -> IndexingCheckpoint | None:
        """Load checkpoint from disk if available.

        Returns:
            Checkpoint state if file exists and is valid, None otherwise
        """
        if not self.checkpoint_file.exists():
            logger.debug("No checkpoint file found at %s", self.checkpoint_file)
            return None

        try:
            checkpoint = IndexingCheckpoint.model_validate(
                from_json(self.checkpoint_file.read_bytes())
            )
            logger.info(
                "Checkpoint loaded: session %s, %d/%d files processed",
                checkpoint.session_id,
                checkpoint.files_indexed,
                checkpoint.files_discovered,
            )
        except (OSError, ValueError):
            logger.warning("Failed to load checkpoint")
            return None
        else:
            return checkpoint

    def delete(self) -> None:
        """Delete checkpoint file (e.g., after successful completion)."""
        if self.checkpoint_file.exists():
            try:
                self.checkpoint_file.unlink()
                logger.info("Checkpoint file deleted")
            except OSError as e:
                logger.warning("Failed to delete checkpoint: %s", e)

    def should_resume(
        self, checkpoint: IndexingCheckpoint, current_settings_hash: str, max_age_hours: int = 24
    ) -> bool:
        """Determine if checkpoint should be used for resumption.

        Args:
            checkpoint: Loaded checkpoint state
            current_settings_hash: Hash of current settings
            max_age_hours: Maximum age before considering stale

        Returns:
            True if checkpoint is valid and safe to resume from
        """
        if checkpoint.is_stale(max_age_hours):
            logger.warning(
                "Checkpoint is stale (>%d hours old), will reindex from scratch", max_age_hours
            )
            return False

        if not checkpoint.matches_settings(current_settings_hash):
            logger.warning("Settings have changed since checkpoint, will reindex from scratch")
            return False

        logger.info("Checkpoint is valid, will resume from previous session")
        return True

    def get_relevant_settings(self) -> CheckpointSettingsFingerprint:
        """Get relevant settings for checkpoint hashing.

        Returns:
            Dictionary of settings affecting indexing
        """
        return CheckpointSettingsFingerprint(**_get_settings_map())


__all__ = ("CheckpointManager", "CheckpointSettingsFingerprint", "IndexingCheckpoint")
