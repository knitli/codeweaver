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

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, NoReturn, TypedDict, cast
from uuid import UUID

from anyio import Path as AsyncPath
from pydantic import UUID7, DirectoryPath, Field, NonNegativeInt
from pydantic_core import from_json, to_json

from codeweaver.core import (
    INJECTED,
    BasedModel,
    BlakeHashKey,
    CodeWeaverDeveloperError,
    ResolvedProjectNameDep,
    ResolvedProjectPathDep,
    TypeIs,
    get_blake_hash,
    get_settings,
    uuid7,
)
from codeweaver.core.constants import ONE_HOUR
from codeweaver.engine.config import CodeWeaverEngineSettings, IndexerSettings
from codeweaver.providers import EmbeddingModelCapabilities, ProviderSettings
from codeweaver.providers.config.categories import (
    AsymmetricEmbeddingProviderSettings,
    EmbeddingProviderSettingsType,
    SparseEmbeddingProviderSettingsType,
    VectorStoreProviderSettingsType,
)


if TYPE_CHECKING:
    from codeweaver.core import AnonymityConversion, FilteredKeyT

logger = logging.getLogger(__name__)


EXCEPTION_PATTERN = re.compile(r"\b\w+(Exception|Error|Failure|Fault|Abort|Abortive)\b")


def _raise_if_unset_provider() -> NoReturn:
    raise CodeWeaverDeveloperError(
        "Encountered unset provider configuration when analyzing configuration changes in `CheckpointManager`. This shouldn't be possible; please file an issue if you see this error."
    )


def _is_provider_settings(value: Any) -> TypeIs[ProviderSettings]:
    assert isinstance(value, ProviderSettings)  # noqa: S101
    return True


class ChangeImpact(Enum):
    """Classification of configuration change impact on index validity.

    Defines how configuration changes affect the need for reindexing operations.
    Each level represents increasingly severe impacts requiring different handling strategies.
    """

    NONE = "none"
    """No configuration changes detected. Index remains fully valid."""

    COMPATIBLE = "compatible"
    """Changes within same model family that don't require reindexing.

    Example: Query model change in asymmetric config within same family.
    The indexed embeddings remain valid because they use the same embed model.
    """

    QUANTIZABLE = "quantizable"
    """Datatype reduction only, no dimension changes.

    Example: float32 → float16 or float16 → uint8.
    Can be handled via quantization without full reindexing.
    """

    TRANSFORMABLE = "transformable"
    """Dimension reduction within same model family.

    Example: 1024 → 768 dimensions using same model.
    Requires transformation but not full reindexing from source.
    """

    BREAKING = "breaking"
    """Requires full reindexing from source documents.

    Examples:
    - Different embed model or model family
    - Different sparse embedding model
    - Incompatible dimension changes
    - Different vector store requiring migration
    """


@dataclass(frozen=True)
class CheckpointSettingsFingerprint:
    """Family-aware configuration fingerprint for checkpoint compatibility checking.

    This dataclass captures the critical configuration elements that determine whether
    an existing index can be reused. It supports asymmetric embedding configurations
    where query models can change without invalidating the index if they stay within
    the same model family.

    Attributes:
        embedding_config_type: Whether config is "symmetric" or "asymmetric"
        embed_model: Document embedding model name
        embed_model_family: Model family ID for compatibility checks (optional)
        query_model: Query embedding model name (required for asymmetric configs)
        sparse_model: Sparse embedding model name (optional)
        vector_store: Vector store provider name
        config_hash: Hash of full configuration for validation
    """

    embedding_config_type: Literal["symmetric", "asymmetric"]
    embed_model: str
    embed_model_family: str | None
    query_model: str | None
    sparse_model: str | None
    vector_store: str
    config_hash: str
    dimension: int | None = None
    datatype: str | None = None

    def is_compatible_with(self, other: CheckpointSettingsFingerprint) -> tuple[bool, ChangeImpact]:
        """Check compatibility and classify change impact with family-aware logic.

        Implements comprehensive compatibility checking that handles:
        - Asymmetric embedding configs with model families
        - Symmetric embedding model changes
        - Sparse model changes
        - Vector store changes

        For asymmetric configs:
        - Same family + same embed model + different query model = COMPATIBLE
        - Different families or embed models = BREAKING

        For symmetric configs:
        - Different model = BREAKING

        Args:
            other: The other fingerprint to compare against (typically from checkpoint)

        Returns:
            Tuple of (is_compatible: bool, impact: ChangeImpact)
        """
        # Check vector store changes (always breaking if different)
        if self.vector_store != other.vector_store:
            logger.info(
                "Vector store changed: %s → %s (BREAKING)", other.vector_store, self.vector_store
            )
            return False, ChangeImpact.BREAKING

        # Check sparse model changes (always breaking if different)
        if self.sparse_model != other.sparse_model:
            logger.info(
                "Sparse model changed: %s → %s (BREAKING)", other.sparse_model, self.sparse_model
            )
            return False, ChangeImpact.BREAKING

        # Handle asymmetric embedding configuration
        if self.embedding_config_type == "asymmetric":
            # Family-aware comparison for asymmetric configs
            if (
                self.embed_model_family
                and other.embed_model_family
                and self.embed_model_family == other.embed_model_family
            ):
                # Same family - check if only query model changed
                if self.embed_model == other.embed_model:
                    if self.query_model != other.query_model:
                        logger.info(
                            "Query model changed within family %s: %s → %s (COMPATIBLE)",
                            self.embed_model_family,
                            other.query_model,
                            self.query_model,
                        )
                        return True, ChangeImpact.COMPATIBLE
                    # No changes at all
                    return True, ChangeImpact.NONE
                # Embed model changed even within same family
                logger.info(
                    "Embed model changed within family %s: %s → %s (BREAKING)",
                    self.embed_model_family,
                    other.embed_model,
                    self.embed_model,
                )
                return False, ChangeImpact.BREAKING
            # Different families or no family info
            logger.info(
                "Model family changed or unavailable: %s → %s (BREAKING)",
                other.embed_model_family,
                self.embed_model_family,
            )
            return False, ChangeImpact.BREAKING

        # Symmetric mode: exact match required for embed_model
        if self.embed_model != other.embed_model:
            logger.info(
                "Embed model changed (symmetric): %s → %s (BREAKING)",
                other.embed_model,
                self.embed_model,
            )
            return False, ChangeImpact.BREAKING

        # No relevant changes detected
        return True, ChangeImpact.NONE


class CheckpointSettingsMap(TypedDict):
    """Subset of settings relevant for checkpoint hashing.

    This is the complete settings map used for hash generation, distinct from
    the CheckpointSettingsFingerprint which is used for compatibility checking.
    """

    indexer: dict[str, Any]
    project_path: DirectoryPath
    project_name: str
    embedding_provider: tuple[EmbeddingProviderSettingsType, ...] | None
    sparse_provider: tuple[SparseEmbeddingProviderSettingsType, ...] | None
    vector_store: tuple[VectorStoreProviderSettingsType, ...] | None


def get_checkpoint_settings_map(
    project_path: ResolvedProjectPathDep = INJECTED, project_name: ResolvedProjectNameDep = INJECTED
) -> CheckpointSettingsMap:
    """Get relevant settings for checkpoint hashing.

    Note: This is a helper for the manager/checkpoint to use.
    It still needs access to the global settings to compute the hash.

    We could also consider vector store changes more carefully -- we can migrate
    vector stores without reindexing if needed.
    """
    # These values will already have been resolved by dependency injection with defaults if needed
    settings = cast(CodeWeaverEngineSettings, get_settings())
    indexer: IndexerSettings = cast(IndexerSettings, settings.indexer)

    indexer_map = indexer.model_dump(mode="json", exclude_computed_fields=True, exclude_none=True)
    if not _is_provider_settings(settings.provider):
        _raise_if_unset_provider()
    return CheckpointSettingsMap(
        indexer=indexer_map,
        embedding_provider=cast(ProviderSettings, settings.provider).embedding,
        sparse_provider=cast(ProviderSettings, settings.provider).sparse_embedding,
        vector_store=cast(ProviderSettings, settings.provider).vector_store,
        project_path=project_path,
        project_name=project_name,
    )


class IndexingCheckpoint(BasedModel):
    """Persistent checkpoint for indexing pipeline state."""

    session_id: Annotated[UUID7, Field(description="Unique session identifier (UUIDv7)")] = cast(
        UUID, uuid7()
    )

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
        age_hours = (datetime.now(UTC) - self.last_checkpoint).total_seconds() / ONE_HOUR
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

    This manager now includes unified compatibility checking that bridges:
    - CheckpointSettingsFingerprint (new family-aware comparison)
    - IndexingCheckpoint.matches_settings() (existing validation)
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

    async def save(self, checkpoint: IndexingCheckpoint) -> None:
        """Save checkpoint to disk."""
        checkpoint.last_checkpoint = datetime.now(UTC)
        await AsyncPath(self.checkpoint_dir).mkdir(parents=True, exist_ok=True)

        try:
            await AsyncPath(self.checkpoint_file).write_text(
                checkpoint.model_dump_json(indent=2, round_trip=True)
            )
            logger.info("Saved indexing checkpoint to %s", self.checkpoint_file)
        except OSError:
            logger.warning("Failed to save checkpoint", exc_info=True)

    async def load(self) -> IndexingCheckpoint | None:
        """Load checkpoint from disk if available."""
        async_file = AsyncPath(self.checkpoint_file)
        if not await async_file.exists():
            return None

        try:
            return IndexingCheckpoint.model_validate(from_json(await async_file.read_bytes()))
        except (OSError, ValueError):
            logger.warning("Failed to load checkpoint from %s", self.checkpoint_file)
            return None

    async def delete(self) -> None:
        """Delete checkpoint file."""
        async_file = AsyncPath(self.checkpoint_file)
        if await async_file.exists():
            try:
                await async_file.unlink()
                logger.info("Deleted checkpoint file %s", self.checkpoint_file)
            except OSError as e:
                logger.warning("Failed to delete checkpoint: %s", e)

    def is_index_valid_for_config(
        self, checkpoint: IndexingCheckpoint, new_config: EmbeddingProviderSettingsType
    ) -> tuple[bool, ChangeImpact]:
        """Unified compatibility check connecting fingerprint and checkpoint logic.

        This method bridges the gap between:
        - CheckpointSettingsFingerprint (new family-aware comparison)
        - IndexingCheckpoint.matches_settings() (existing validation)

        It implements family-aware compatibility checking for asymmetric embedding
        configurations while maintaining backward compatibility with existing
        checkpoint validation logic.

        Args:
            checkpoint: Existing indexing checkpoint
            new_config: New embedding configuration to check against

        Returns:
            Tuple of (is_valid: bool, impact: ChangeImpact)
            - is_valid: True if checkpoint can be reused with new config
            - impact: Classification of the configuration change impact
        """
        # Get fingerprints from checkpoint and new config
        old_fingerprint = self._extract_fingerprint(checkpoint)
        new_fingerprint = self._create_fingerprint(new_config)

        # Delegate to fingerprint comparison (family-aware)
        is_compatible, impact = new_fingerprint.is_compatible_with(old_fingerprint)

        # Only invalidate if BREAKING change
        if is_compatible:
            return (False, impact) if impact == ChangeImpact.BREAKING else (True, impact)
        return False, ChangeImpact.BREAKING

    def _extract_fingerprint(self, checkpoint: IndexingCheckpoint) -> CheckpointSettingsFingerprint:
        """Extract fingerprint from existing checkpoint.

        Constructs a CheckpointSettingsFingerprint from the checkpoint's stored
        configuration hash and settings. This allows comparison with new configurations.

        Args:
            checkpoint: The checkpoint to extract fingerprint from

        Returns:
            CheckpointSettingsFingerprint instance

        Note:
            This currently extracts from the settings hash. In the future,
            checkpoints will store fingerprint data directly for better
            forward compatibility.
        """
        settings = cast(CodeWeaverEngineSettings, get_settings())
        if not _is_provider_settings(settings.provider):
            _raise_if_unset_provider()
        # Get provider configurations
        embedding_config = settings.provider.embedding[0] if settings.provider.embedding else None
        sparse_config = (
            settings.provider.sparse_embedding[0] if settings.provider.sparse_embedding else None
        )
        vector_store_config = (
            settings.provider.vector_store[0] if settings.provider.vector_store else None
        )

        # Extract embedding model information
        embed_model = ""
        embed_model_family = None
        query_model = None
        config_type: Literal["symmetric", "asymmetric"] = "symmetric"

        if embedding_config:
            if isinstance(embedding_config, AsymmetricEmbeddingProviderSettings):
                config_type = "asymmetric"
                embed_model = str(embedding_config.embed_provider.model_name)
                query_model = str(embedding_config.query_provider.model_name)

                # Try to get model family from capabilities
                if (
                    (embed_caps := embedding_config.embed_provider.embedding_config.capabilities)
                    and isinstance(embed_caps, EmbeddingModelCapabilities)
                    and embed_caps.model_family
                ):
                    embed_model_family = embed_caps.model_family.family_id
            else:
                embed_model = str(embedding_config.model_name)
                # Try to get model family for symmetric config too
                if (
                    (embed_caps := embedding_config.embedding_config.capabilities)
                    and isinstance(embed_caps, EmbeddingModelCapabilities)
                    and embed_caps.model_family
                ):
                    embed_model_family = embed_caps.model_family.family_id

        sparse_model = str(sparse_config.model_name) if sparse_config else None
        vector_store = str(vector_store_config.provider) if vector_store_config else "inmemory"

        # Get dimension and datatype from metadata if available
        dimension = None
        datatype = None
        collection_metadata = getattr(checkpoint, "collection_metadata", None)
        if collection_metadata:
            dimension = collection_metadata.dimension
            datatype = collection_metadata.datatype

        return CheckpointSettingsFingerprint(
            embedding_config_type=config_type,
            embed_model=embed_model,
            embed_model_family=embed_model_family,
            query_model=query_model,
            sparse_model=sparse_model,
            vector_store=vector_store,
            config_hash=str(checkpoint.settings_hash or ""),
            dimension=dimension,
            datatype=datatype,
        )

    def _create_fingerprint(
        self, config: EmbeddingProviderSettingsType
    ) -> CheckpointSettingsFingerprint:
        """Create fingerprint from new embedding configuration.

        Extracts the critical configuration elements needed for compatibility
        checking from a new embedding configuration.

        Args:
            config: New embedding configuration

        Returns:
            CheckpointSettingsFingerprint instance
        """
        settings = cast(CodeWeaverEngineSettings, get_settings())
        if not _is_provider_settings(settings.provider):
            _raise_if_unset_provider()
        # Extract sparse and vector store info
        sparse_config = (
            settings.provider.sparse_embedding[0] if settings.provider.sparse_embedding else None
        )
        vector_store_config = (
            settings.provider.vector_store[0] if settings.provider.vector_store else None
        )

        # Extract embedding model information
        embed_model = ""
        embed_model_family = None
        query_model = None
        config_type: Literal["symmetric", "asymmetric"] = "symmetric"
        dimension = None
        datatype = None

        if isinstance(config, AsymmetricEmbeddingProviderSettings):
            config_type = "asymmetric"
            embed_model = str(config.embed_provider.model_name)
            query_model = str(config.query_provider.model_name)
            dimension = config.dimension
            datatype = config.datatype

            # Try to get model family from capabilities
            if (
                (embed_caps := config.embed_provider.embedding_config.capabilities)
                and isinstance(embed_caps, EmbeddingModelCapabilities)
                and embed_caps.model_family
            ):
                embed_model_family = embed_caps.model_family.family_id
        else:
            embed_model = str(config.model_name)
            dimension = getattr(config, "dimension", None)
            datatype = getattr(config, "datatype", None)

            # Try to get model family for symmetric config too
            if (
                (embed_caps := config.embedding_config.capabilities)
                and isinstance(embed_caps, EmbeddingModelCapabilities)
                and embed_caps.model_family
            ):
                embed_model_family = embed_caps.model_family.family_id

        sparse_model = str(sparse_config.model_name) if sparse_config else None
        vector_store = str(vector_store_config.provider) if vector_store_config else "inmemory"

        # Compute hash of current settings
        config_hash = get_blake_hash(to_json(get_checkpoint_settings_map()))

        return CheckpointSettingsFingerprint(
            embedding_config_type=config_type,
            embed_model=embed_model,
            embed_model_family=embed_model_family,
            query_model=query_model,
            sparse_model=sparse_model,
            vector_store=vector_store,
            config_hash=str(config_hash),
            dimension=dimension,
            datatype=datatype,
        )


__all__ = (
    "EXCEPTION_PATTERN",
    "ChangeImpact",
    "CheckpointManager",
    "CheckpointSettingsFingerprint",
    "CheckpointSettingsMap",
    "IndexingCheckpoint",
    "get_checkpoint_settings_map",
)
