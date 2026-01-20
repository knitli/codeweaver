# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Collection metadata models for vector stores."""

from __future__ import annotations

import logging

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypedDict

from pydantic import Field, computed_field

from codeweaver.core import BasedModel, CodeChunk, ModelSwitchError
from codeweaver.core.types import Provider


if TYPE_CHECKING:
    from codeweaver.core import AnonymityConversion, FilteredKeyT

logger = logging.getLogger(__name__)


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
    """Metadata stored with collections for validation and compatibility checks."""

    provider: Annotated[str, Field(description="Provider name that created collection")]
    created_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(UTC))]
    project_name: Annotated[str, Field(description="Project/repository name")]

    dense_model: Annotated[
        str | None, Field(description="Name of the dense embedding model used.")
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
    version: Annotated[str, Field(description="Metadata schema version")] = "1.2.0"

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

        Args:
            other: Other collection metadata to compare against

        Raises:
            ModelSwitchError: If embedding models don't match
            DimensionMismatchError: If embedding dimensions don't match

        Warnings:
            Logs warning if provider has changed (suggests reindexing)
        """
        # Warn on provider switch - suggests reindexing but doesn't block
        if self.provider != other.provider:
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

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core import AnonymityConversion, FilteredKey

        return {FilteredKey("project_name"): AnonymityConversion.HASH}


__all__ = ("CollectionMetadata", "HybridVectorPayload")
