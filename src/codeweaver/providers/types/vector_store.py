# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Collection metadata models for vector stores."""

from __future__ import annotations

import logging

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypedDict, cast

from pydantic import Field, computed_field

from codeweaver.core import BasedModel, CodeChunk, ModelSwitchError
from codeweaver.core.types import BaseEnum, Provider


if TYPE_CHECKING:
    from codeweaver.core import AnonymityConversion, FilteredKeyT

logger = logging.getLogger(__name__)


class CollectionPolicy(BaseEnum):
    """Collection modification policy controlling configuration changes.

    Defines how strictly a collection's configuration is enforced when attempting
    to use different embedding models or providers with an existing collection.

    Values:
        STRICT: No model changes allowed - only the exact original model can be used.
        FAMILY_AWARE: Allow query model changes within the same model family (default).
            This is the recommended setting as it enables asymmetric embedding where
            documents are embedded with a high-quality model (e.g., voyage-4-large) and
            queries use a lighter model (e.g., voyage-4-nano) for better latency/cost.
        FLEXIBLE: Warn on breaking changes but don't block them. Use with caution as
            this can lead to degraded search quality or errors.
        UNLOCKED: Allow all configuration changes without validation. Only use for
            testing or when you fully understand the implications.

    Default: FAMILY_AWARE - balances safety with flexibility for asymmetric embedding.

    Examples:
        >>> # Strict policy - no changes allowed
        >>> metadata = CollectionMetadata(
        ...     provider="voyage", project_name="my-project", policy=CollectionPolicy.STRICT
        ... )
        >>> # Will raise ConfigurationLockError if model changes

        >>> # Family-aware policy (default) - allows query model changes in family
        >>> metadata = CollectionMetadata(
        ...     provider="voyage",
        ...     project_name="my-project",
        ...     dense_model="voyage-4-large",
        ...     dense_model_family="voyage-4",
        ...     policy=CollectionPolicy.FAMILY_AWARE,  # or omit for default
        ... )
        >>> # Can use voyage-4-nano for queries, but not voyage-3 models
    """

    STRICT = "strict"
    FAMILY_AWARE = "family_aware"
    FLEXIBLE = "flexible"
    UNLOCKED = "unlocked"


@dataclass(frozen=True)
class TransformationRecord:
    """Record of a transformation applied to collection.

    Tracks changes like quantization or dimension reduction applied to a collection,
    including timing and accuracy impact metrics.

    This dataclass is immutable to ensure transformation records cannot be
    modified after creation.
    """

    timestamp: datetime
    type: Literal["quantization", "dimension_reduction"]
    old_value: str | int
    new_value: str | int
    accuracy_impact: str
    migration_time: timedelta


class PayloadFieldDict(TypedDict):
    """A mapping of payload field names to their corresponding Qdrant data types; not all fields are indexed, but if they were, these would be the types."""

    chunk: Literal["text"]
    chunk_id: Literal["uuid"]
    file_path: Literal["text"]
    line_start: Literal["integer"]
    line_end: Literal["integer"]
    indexed_at: Literal["datetime"]
    chunked_on: Literal["datetime"]
    hash: Literal["keyword"]  # use keyword to find specific hashes
    provider: Literal["keyword"]
    embedding_complete: Literal["bool"]
    symbol: Literal["keyword"]


class HybridVectorPayload(BasedModel):
    """Metadata payload for stored vectors."""

    chunk: Annotated[CodeChunk, Field(description="Code chunk metadata")]
    chunk_id: Annotated[str, Field(description="UUID7 hex string index identifier for the chunk")]
    file_path: Annotated[str, Field(description="File path of the code chunk")]
    line_start: Annotated[int, Field(description="Start line number of the code chunk")]
    line_end: Annotated[int, Field(description="End line number of the code chunk")]
    indexed_at: Annotated[
        datetime,
        Field(
            description="Datetime object when the chunk was indexed. We use datetime here because qdrant can filter by datetime."
        ),
    ]
    chunked_on: Annotated[
        datetime,
        Field(
            description="Datetime object when the chunk was created. We use datetime here because qdrant can filter by datetime."
        ),
    ]
    hash: Annotated[str, Field(description="blake 3 hash of the code chunk")]
    provider: Annotated[Provider, Field(description="Provider name for the vector store")]
    embedding_complete: Annotated[
        bool,
        Field(
            description="Whether the chunk has been fully embedded with both sparse and dense embeddings"
        ),
    ]

    @computed_field
    @property
    def symbol(self) -> str | None:
        """Return the symbol associated with the semantic metadata, if available."""
        if hasattr(self, "_symbol"):
            return self._symbol  # ty:ignore[invalid-return-type]
        if not self.chunk.metadata or not (metadata := self.chunk.metadata.get("semantic_meta")):
            return None
        return metadata.symbol

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core import AnonymityConversion, FilteredKey

        return {FilteredKey("file_path"): AnonymityConversion.HASH}

    def to_payload(self) -> dict[str, Any]:
        """Convert to a dictionary payload for storage."""
        return self.model_dump(
            mode="json",
            exclude_none=True,
            by_alias=True,
            round_trip=True,
            exclude_computed_fields=False,
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> HybridVectorPayload:
        """Create a HybridVectorPayload from a dictionary payload."""
        context = payload.pop("symbol", None)
        new = cls.model_validate(payload)
        new._symbol = context  # ty:ignore[unresolved-attribute]
        return new

    @staticmethod
    def indexed_fields() -> tuple[str, ...]:
        """Return the payload fields that are indexed by default in the Qdrant collection."""
        return ("chunk_id", "symbol", "indexed_at")

    @staticmethod
    def index_field_types() -> PayloadFieldDict:
        """Return the payload fields mapped to their datatype for Qdrant indexing."""
        return PayloadFieldDict({
            "chunk": "text",
            "chunk_id": "uuid",
            "file_path": "text",
            "line_start": "integer",
            "line_end": "integer",
            "indexed_at": "datetime",
            "chunked_on": "datetime",
            "hash": "keyword",
            "provider": "keyword",
            "embedding_complete": "bool",
            "symbol": "keyword",
        })


class CollectionMetadata(BasedModel):
    """Metadata stored with collections for validation and compatibility checks.

    Version History:
        - v1.2.0: Initial schema with dense_model, sparse_model
        - v1.3.0: Added dense_model_family and query_model for asymmetric embedding support
        - v1.4.0: Added configuration tracking and transformation tracking fields
        - v1.5.0: Added collection policy system for controlling configuration changes

    Migration from v1.2.x to v1.3.0:
        Collections created with v1.2.x are fully compatible with v1.3.0. The new fields
        (dense_model_family, query_model) default to None, indicating single-model mode:

        - dense_model_family=None: No model family tracking (backward compatible)
        - query_model=None: Symmetric mode (query uses same model as dense_model)

        Existing collections can be loaded, modified, and saved without requiring migration.
        The pydantic validators handle missing fields gracefully via Field defaults.

    Migration from v1.3.0 to v1.4.0:
        Collections created with v1.3.0 are fully compatible with v1.4.0. The new fields
        default to None or empty lists, maintaining backward compatibility:

        - profile_name, profile_version, config_hash, config_timestamp: Optional tracking
        - quantization_type, quantization_rescore, original_dimension: Optional transformations
        - transformations: Empty list by default

    Migration from v1.4.0 to v1.5.0:
        Collections created with v1.4.0 are fully compatible with v1.5.0. The new policy
        field defaults to FAMILY_AWARE, maintaining existing behavior:

        - policy: Defaults to CollectionPolicy.FAMILY_AWARE for backward compatibility
        - Existing collections will use FAMILY_AWARE policy unless explicitly changed
        - No breaking changes to existing validation logic

    Asymmetric Embedding Support (v1.3.0+):
        When dense_model_family is set, the collection supports cross-model querying within
        the same family (e.g., Voyage-4 family allows voyage-4-large for embedding and
        voyage-4-nano for queries). This enables:

        - Local query models (zero cost, instant latency)
        - API embedding models (higher quality)
        - 3-point retrieval improvement (per Voyage AI)

    Transformation Tracking (v1.4.0+):
        Tracks quantization and dimension reduction transformations applied to collections,
        enabling migration auditing and accuracy impact analysis.
    """

    provider: Annotated[str, Field(description="Provider name that created collection")]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    project_name: Annotated[str, Field(description="Project/repository name")]

    dense_model: Annotated[
        str | None, Field(description="Name of the dense embedding model used.")
    ] = None
    dense_model_family: Annotated[
        str | None,
        Field(
            description="Model family identifier for the dense embedding model. "
            "Identifies compatible models that share the same vector space, enabling "
            "asymmetric embedding configurations (e.g., using voyage-4-large for documents "
            "and voyage-4-nano for queries)."
        ),
    ] = None
    query_model: Annotated[
        str | None,
        Field(
            description="Name of the query model used for asymmetric search. "
            "When set, indicates this collection supports asymmetric embedding where "
            "documents are embedded with dense_model and queries use this model. "
            "Must be compatible with dense_model_family."
        ),
    ] = None
    sparse_model: Annotated[
        str | None, Field(description="Name of the sparse embedding model used.")
    ] = None
    backup_enabled: Annotated[
        bool, Field(description="Whether backup is enabled for the collection")
    ] = False
    backup_model: Annotated[
        str | None,
        Field(description="Name of the backup dense embedding model used for the collection"),
    ] = None
    collection_name: Annotated[str, Field(description="Name of the collection")] = ""

    # Configuration tracking (v1.4.0)
    profile_name: Annotated[
        str | None,
        Field(description="Name of the configuration profile used to create this collection"),
    ] = None
    profile_version: Annotated[
        str | None, Field(description="CodeWeaver version when profile was applied")
    ] = None
    config_hash: Annotated[
        str | None,
        Field(description="Hash of custom configuration for tracking non-profile configs"),
    ] = None
    config_timestamp: Annotated[
        datetime | None, Field(description="Timestamp when configuration was applied")
    ] = None

    # Transformation tracking (v1.4.0)
    quantization_type: Annotated[
        Literal["int8", "binary"] | None,
        Field(description="Type of quantization applied to vectors"),
    ] = None
    quantization_rescore: Annotated[
        bool, Field(description="Whether rescoring is enabled for quantized searches")
    ] = False
    original_dimension: Annotated[
        int | None, Field(description="Original embedding dimension before reduction")
    ] = None
    transformations: Annotated[
        list[TransformationRecord],
        Field(
            description="History of transformations applied to this collection",
            default_factory=list,
        ),
    ] = Field(default_factory=list)

    # Collection policy (v1.4.0)
    policy: Annotated[
        CollectionPolicy,
        Field(
            description="Policy controlling configuration changes to the collection. "
            "STRICT: no model changes; FAMILY_AWARE: allow query model changes within "
            "same family (default); FLEXIBLE: warn on breaking changes; UNLOCKED: allow all."
        ),
    ] = CollectionPolicy.FAMILY_AWARE

    version: Annotated[str, Field(description="Metadata schema version")] = "1.5.0"

    # Vector configuration (optional, used for dimension validation)
    vector_config: Annotated[
        dict[str, Any] | None,
        Field(
            description="Vector configuration mapping name to VectorParams. "
            "Used to validate dimension compatibility when switching configurations.",
            default=None,
        ),
    ] = None

    sparse_config: Annotated[
        dict[str, Any] | None,
        Field(
            description="Sparse vector configuration mapping name to SparseVectorParams.",
            default=None,
        ),
    ] = None

    def to_collection(self) -> dict[str, Any]:
        """Convert to a dictionary that is the argument for collection creation."""
        # Return collection creation params without metadata (metadata is stored separately)
        return self.model_dump(exclude_none=True, by_alias=True, round_trip=True)

    @classmethod
    def from_collection(cls, data: dict[str, Any]) -> CollectionMetadata:
        """Create CollectionMetadata from a collection dictionary."""
        metadata = data.get("metadata", {})
        return cls.model_validate(metadata)

    def validate_compatibility(self, other: CollectionMetadata) -> None:
        """Validate collection metadata against current provider configuration.

        Performs family-aware validation when dense_model_family is present,
        allowing asymmetric embedding configurations where query models can differ
        from embed models as long as they belong to the same model family.

        Args:
            other: Other collection metadata to compare against (typically from existing collection)

        Raises:
            ModelSwitchError: If embedding models don't match and family validation fails
            ConfigurationError: If models are incompatible within their family

        Warnings:
            Logs warning if provider has changed (suggests reindexing)
        """
        # Warn on provider switch - suggests reindexing but doesn't block
        if self.provider != other.provider and not (
            self.dense_model_family and other.dense_model_family
        ):
            logger.warning(
                "Provider switch detected: collection created with '%s', but current provider is '%s'.",
                other.provider,
                self.provider,
                extra={
                    "collection_provider": other.provider,
                    "current_provider": self.provider,
                    "collection": other.collection_name,
                    "current_collection": self.collection_name,
                    "project_name": self.project_name,
                    "suggestions": [
                        "Changing vector storage providers without changing models *may* be OK.",
                        "To ensure compatibility, consider re-indexing your codebase with the new provider.",
                        "If you encounter issues, you may need to delete the existing collection and re-index. Run `cw index` to re-index.",
                    ],
                },
            )

        # Family-aware validation: Check if collection has family metadata
        if other.dense_model_family:
            self._validate_family_compatibility(other)
            return

        # Dimension validation: check if vector_config dimensions match
        self._validate_dimensions_from_config(other)

        # Legacy validation (no family metadata) - strict model matching
        # Error on model switch - this corrupts search results
        # Only raise if both have models and they differ (allow None for backwards compatibility)
        if self.dense_model and other.dense_model and self.dense_model != other.dense_model:
            raise ModelSwitchError(
                f"Your existing embedding collection was created with model '{other.dense_model}', but the current model is '{self.dense_model}'. You can't use different embedding models for the same collection.",
                suggestions=[
                    "Option 1: Re-index your codebase with the new provider",
                    "Option 2: Revert provider setting to match the collection",
                    "Option 3: Delete the existing collection and re-index",
                    "Option 4: Create a new collection with a different name",
                ],
                details={
                    "collection_provider": self.provider,
                    "current_provider": other.provider,
                    "collection_model": other.dense_model,
                    "current_model": self.dense_model,
                    "collection": self.project_name,
                },
            )

    def _get_dense_dimension(self) -> int | None:
        """Extract the dense vector dimension from vector_config."""
        if not self.vector_config:
            return None
        for params in self.vector_config.values():
            size = getattr(params, "size", None)
            if isinstance(size, int):
                return size
        return None

    def _validate_dimensions_from_config(self, other: CollectionMetadata) -> None:
        """Validate that vector dimensions match between two CollectionMetadata instances.

        Raises:
            DimensionMismatchError: If the dense vector dimensions differ.
        """
        from codeweaver.core import DimensionMismatchError

        self_dim = self._get_dense_dimension()
        other_dim = other._get_dense_dimension()

        if self_dim is not None and other_dim is not None and self_dim != other_dim:
            raise DimensionMismatchError(
                f"Vector dimension mismatch: existing collection uses {other_dim}-dimensional "
                f"embeddings, but current configuration produces {self_dim}-dimensional embeddings. "
                f"You cannot mix different embedding dimensions in the same collection.",
                suggestions=[
                    "Option 1: Revert to the original embedding configuration",
                    "Option 2: Delete the existing collection and re-index with new dimensions",
                    "Option 3: Create a new collection with a different name",
                ],
                details={
                    "existing_dimension": other_dim,
                    "current_dimension": self_dim,
                    "collection": self.project_name,
                },
            )

    def _validate_family_compatibility(self, other: CollectionMetadata) -> None:
        """Helper to validate family-aware compatibility."""
        from codeweaver.core.exceptions import ConfigurationError
        from codeweaver.providers.embedding.capabilities.resolver import EmbeddingCapabilityResolver

        indexed_model = other.dense_model
        # Priority: query_model if set (for asymmetric), otherwise dense_model
        current_model = self.query_model or self.dense_model

        if not current_model or current_model == indexed_model:
            return

        resolver = EmbeddingCapabilityResolver()
        current_caps = resolver.resolve(current_model)

        if not current_caps:
            raise ConfigurationError(
                f"No capabilities found for current model: {current_model}",
                details={
                    "current_model": current_model,
                    "indexed_model": indexed_model,
                    "indexed_family": other.dense_model_family,
                },
                suggestions=[
                    f"Ensure model '{current_model}' is registered in the capabilities system",
                    "Check that the model name is spelled correctly",
                    "List available models with: codeweaver list models",
                    f"Or use the indexed model '{indexed_model}' for queries",
                ],
            )

        # Check if current model belongs to a family
        if not current_caps.model_family:
            self._handle_missing_family(current_model, indexed_model, other.dense_model_family)  # ty:ignore[invalid-argument-type]

        current_family = current_caps.model_family

        # Verify same family ID
        if not current_family:
            raise ConfigurationError(
                f"Current model '{current_model}' does not belong to any family, but collection was indexed with family '{other.dense_model_family}'",
                details={
                    "current_model": current_model,
                    "indexed_model": indexed_model,
                    "indexed_family": other.dense_model_family,
                },
                suggestions=[
                    f"Use a model from the '{other.dense_model_family}' family",
                    f"Or use the indexed model '{indexed_model}' for queries",
                    "Asymmetric embedding requires both models to belong to the same family",
                ],
            )
        if current_family.family_id != other.dense_model_family:
            self._handle_family_mismatch(
                current_model,
                indexed_model,
                cast(str, other.dense_model_family),
                current_family,
                resolver,
            )

        # Verify models are compatible within the family
        if indexed_model and not current_family.is_compatible(indexed_model, current_model):
            raise ConfigurationError(
                f"Models '{indexed_model}' and '{current_model}' are not compatible within family '{current_family.family_id}'",
                details={
                    "current_model": current_model,
                    "indexed_model": indexed_model,
                    "family_id": current_family.family_id,
                    "family_members": sorted(current_family.member_models),
                },
                suggestions=[
                    "Ensure both models are listed as family members",
                    f"Valid family members: {', '.join(sorted(current_family.member_models))}",
                    "This may indicate a configuration error",
                ],
            )

        # Verify dimensions match
        self._validate_dimensions_compatibility(
            current_model, indexed_model, current_caps, current_family, resolver
        )

        logger.debug(
            "Family-aware validation passed: query model '%s' is compatible with indexed model '%s' (family: %s)",
            current_model,
            indexed_model,
            current_family.family_id,
        )

    def _handle_missing_family(
        self, current_model: str, indexed_model: str | None, indexed_family: str
    ) -> None:
        """Handle case where current model lacks family support."""
        from codeweaver.core.exceptions import ConfigurationError

        if self.query_model and current_model == self.query_model:
            raise ConfigurationError(
                f"Query model '{current_model}' does not belong to a model family, "
                f"but collection was indexed with family '{indexed_family}'",
                details={
                    "query_model": current_model,
                    "indexed_model": indexed_model,
                    "indexed_family": indexed_family,
                },
                suggestions=[
                    f"Use a query model from the '{indexed_family}' family",
                    f"Or use the indexed model '{indexed_model}' for queries",
                    "Asymmetric embedding requires both models to belong to the same family",
                ],
            )
        raise ModelSwitchError(
            f"Your existing embedding collection was created with model '{indexed_model}' "
            f"(family: '{indexed_family}'), but the current model '{current_model}' "
            f"does not belong to a model family. You can't switch to a non-family model.",
            suggestions=[
                f"Use a model from the '{indexed_family}' family",
                "Or re-index your codebase with the new model",
                "Asymmetric embedding requires both models to belong to the same family",
            ],
            details={
                "current_model": current_model,
                "indexed_model": indexed_model,
                "indexed_family": indexed_family,
                "collection": self.project_name,
            },
        )

    def _handle_family_mismatch(
        self,
        current_model: str,
        indexed_model: str | None,
        indexed_family: str,
        current_family: Any,
        resolver: Any,
    ) -> None:
        """Handle case where model families don't match."""
        from codeweaver.core.exceptions import ConfigurationError

        indexed_caps = resolver.resolve(indexed_model) if indexed_model else None
        compatible_models = []
        if indexed_caps and indexed_caps.model_family:
            compatible_models = sorted(indexed_caps.model_family.member_models)

        raise ConfigurationError(
            f"Model family mismatch: collection indexed with '{indexed_family}' family "
            f"but current model '{current_model}' belongs to '{current_family.family_id}' family",
            details={
                "current_model": current_model,
                "current_family": current_family.family_id,
                "indexed_model": indexed_model,
                "indexed_family": indexed_family,
            },
            suggestions=[
                f"Use a model from the '{indexed_family}' family",
                f"Compatible models: {', '.join(compatible_models)}"
                if compatible_models
                else f"Use the indexed model '{indexed_model}'",
                "Or re-index the collection with the new model family",
            ],
        )

    def _validate_dimensions_compatibility(
        self,
        current_model: str,
        indexed_model: str | None,
        current_caps: Any,
        current_family: Any,
        resolver: Any,
    ) -> None:
        """Verify embedding dimensions are compatible."""
        from codeweaver.core.exceptions import ConfigurationError

        indexed_caps = resolver.resolve(indexed_model) if indexed_model else None
        indexed_dim = indexed_caps.default_dimension if indexed_caps else None

        if indexed_dim:
            is_valid, error_msg = current_family.validate_dimensions(
                indexed_dim, current_caps.default_dimension
            )
            if not is_valid:
                raise ConfigurationError(
                    f"Dimension mismatch: {error_msg}",
                    details={
                        "current_model": current_model,
                        "current_dimension": current_caps.default_dimension,
                        "indexed_model": indexed_model,
                        "indexed_dimension": indexed_dim,
                        "expected_dimension": current_family.default_dimension,
                        "family_id": current_family.family_id,
                    },
                    suggestions=[
                        "Ensure both models use the same embedding dimension",
                        f"Expected dimension for '{current_family.family_id}': {current_family.default_dimension}",
                        "Check model configurations and verify dimension settings",
                    ],
                )

    def validate_config_change(
        self,
        new_dense_model: str | None = None,
        new_query_model: str | None = None,
        new_sparse_model: str | None = None,
        new_provider: str | None = None,
    ) -> None:
        """Validate configuration change against collection policy.

        Validates whether proposed configuration changes are allowed based on the
        collection's policy setting. This method is called before applying any
        configuration changes to ensure they won't break the collection.

        Args:
            new_dense_model: Proposed new dense embedding model
            new_query_model: Proposed new query model (for asymmetric embedding)
            new_sparse_model: Proposed new sparse embedding model
            new_provider: Proposed new provider

        Raises:
            ConfigurationLockError: If the proposed change violates the collection policy
                - STRICT: Any model or provider change
                - FAMILY_AWARE: Model change outside the same family
                - FLEXIBLE: Only warns, doesn't raise
                - UNLOCKED: Never raises

        Examples:
            >>> metadata = CollectionMetadata(
            ...     provider="voyage",
            ...     project_name="my-project",
            ...     dense_model="voyage-4-large",
            ...     dense_model_family="voyage-4",
            ...     policy=CollectionPolicy.FAMILY_AWARE,
            ... )
            >>> # This succeeds - same family
            >>> metadata.validate_config_change(new_query_model="voyage-4-nano")
            >>> # This raises - different family
            >>> metadata.validate_config_change(new_dense_model="voyage-3-large")
            Traceback (most recent call last):
            ...
            ConfigurationLockError: Model change breaks family compatibility
        """
        from codeweaver.core.exceptions import ConfigurationLockError

        match self.policy:
            case CollectionPolicy.STRICT:
                if not self._exact_match(
                    new_dense_model, new_query_model, new_sparse_model, new_provider
                ):
                    raise ConfigurationLockError(
                        "Collection policy is STRICT - no configuration changes allowed",
                        details={
                            "policy": self.policy.value,
                            "collection": self.collection_name,
                            "project": self.project_name,
                            "current_dense_model": self.dense_model,
                            "current_query_model": self.query_model,
                            "current_sparse_model": self.sparse_model,
                            "current_provider": self.provider,
                            "proposed_dense_model": new_dense_model,
                            "proposed_query_model": new_query_model,
                            "proposed_sparse_model": new_sparse_model,
                            "proposed_provider": new_provider,
                        },
                        suggestions=[
                            "Use the original configuration that created this collection",
                            f"Original dense model: {self.dense_model}",
                            f"Original query model: {self.query_model or 'same as dense model'}",
                            f"Original sparse model: {self.sparse_model or 'none'}",
                            f"Original provider: {self.provider}",
                            "Or change the collection policy to FAMILY_AWARE or FLEXIBLE",
                            "Or create a new collection with a different name",
                        ],
                    )

            case CollectionPolicy.FAMILY_AWARE:
                if not self._family_compatible(
                    new_dense_model, new_query_model, new_sparse_model, new_provider
                ):
                    raise ConfigurationLockError(
                        "Model change breaks family compatibility",
                        details={
                            "policy": self.policy.value,
                            "collection": self.collection_name,
                            "project": self.project_name,
                            "dense_model_family": self.dense_model_family,
                            "current_dense_model": self.dense_model,
                            "current_query_model": self.query_model,
                            "proposed_dense_model": new_dense_model,
                            "proposed_query_model": new_query_model,
                        },
                        suggestions=[
                            "Use a model from the same family as the indexed model",
                            f"Indexed model family: {self.dense_model_family}"
                            if self.dense_model_family
                            else "No family specified - use exact model match",
                            f"Indexed dense model: {self.dense_model}",
                            "Query models can differ if they belong to the same family",
                            "Or change the collection policy to FLEXIBLE or UNLOCKED",
                            "Or re-index the collection with the new model",
                        ],
                    )

            case CollectionPolicy.FLEXIBLE:
                if not self._any_compatible(
                    new_dense_model, new_query_model, new_sparse_model, new_provider
                ):
                    logger.warning(
                        "Configuration change may break compatibility: "
                        "proposed models differ significantly from indexed models",
                        extra={
                            "policy": self.policy.value,
                            "collection": self.collection_name,
                            "current_dense_model": self.dense_model,
                            "current_query_model": self.query_model,
                            "current_sparse_model": self.sparse_model,
                            "proposed_dense_model": new_dense_model,
                            "proposed_query_model": new_query_model,
                            "proposed_sparse_model": new_sparse_model,
                            "warning": "Search quality may be degraded or errors may occur",
                        },
                    )

            case CollectionPolicy.UNLOCKED:
                ...  # Allow everything without validation.

    def _exact_match(
        self,
        new_dense_model: str | None,
        new_query_model: str | None,
        new_sparse_model: str | None,
        new_provider: str | None,
    ) -> bool:
        """Check if proposed configuration exactly matches current configuration.

        For STRICT policy - no changes allowed at all.
        """
        # None means "keep current", so treat as match
        dense_matches = new_dense_model is None or new_dense_model == self.dense_model
        query_matches = new_query_model is None or new_query_model == self.query_model
        sparse_matches = new_sparse_model is None or new_sparse_model == self.sparse_model
        provider_matches = new_provider is None or new_provider == self.provider

        return dense_matches and query_matches and sparse_matches and provider_matches

    def _family_compatible(
        self,
        new_dense_model: str | None,
        new_query_model: str | None,
        new_sparse_model: str | None,
        new_provider: str | None,
    ) -> bool:
        """Check if proposed configuration is family-compatible.

        For FAMILY_AWARE policy - allow query model changes within same family,
        but dense model and sparse model must match exactly (or be None to keep current).
        """
        from codeweaver.providers.embedding.capabilities.resolver import EmbeddingCapabilityResolver

        # Provider changes allowed only if no family tracking (backward compat)
        if new_provider and new_provider != self.provider and self.dense_model_family:
            return False

        # Dense model must match exactly (None means keep current)
        if new_dense_model and new_dense_model != self.dense_model:
            return False

        # Sparse model must match exactly
        if new_sparse_model and new_sparse_model != self.sparse_model:
            return False

        # Query model can change if within same family
        if new_query_model:
            # If no family tracking, query model must match dense model
            if not self.dense_model_family:
                return new_query_model == self.dense_model

            # Check if new query model belongs to same family
            resolver = EmbeddingCapabilityResolver()
            query_caps = resolver.resolve(new_query_model)

            if not query_caps or not query_caps.model_family:
                return False

            # Verify same family ID
            if query_caps.model_family.family_id != self.dense_model_family:
                return False

            # Verify models are compatible within family
            if self.dense_model and not query_caps.model_family.is_compatible(
                self.dense_model, new_query_model
            ):
                return False

        return True

    def _any_compatible(
        self,
        new_dense_model: str | None,
        new_query_model: str | None,
        new_sparse_model: str | None,
        new_provider: str | None,
    ) -> bool:
        """Check if proposed configuration has any compatibility indicators.

        For FLEXIBLE policy - warn if models are completely different,
        but allow the change. This method returns False only if we detect
        obvious incompatibilities (e.g., dramatically different dimensions).
        """
        from codeweaver.providers.embedding.capabilities.resolver import EmbeddingCapabilityResolver

        # If nothing is changing, it's compatible
        if (
            not new_dense_model
            and not new_query_model
            and not new_sparse_model
            and not new_provider
        ):
            return True

        resolver = EmbeddingCapabilityResolver()

        # Check dense model dimensions if changing
        if new_dense_model and self.dense_model:
            current_caps = resolver.resolve(self.dense_model)
            new_caps = resolver.resolve(new_dense_model)

            if current_caps and new_caps:
                current_dim = current_caps.default_dimension
                new_dim = new_caps.default_dimension
                # Warn if dimensions differ significantly (>10% difference)
                if abs(current_dim - new_dim) / current_dim > 0.1:
                    return False

        return True

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core import AnonymityConversion, FilteredKey

        return {FilteredKey("project_name"): AnonymityConversion.HASH}


__all__ = (
    "CollectionMetadata",
    "CollectionPolicy",
    "HybridVectorPayload",
    "PayloadFieldDict",
    "TransformationRecord",
)
