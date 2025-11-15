# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Collection metadata models for vector stores."""

from __future__ import annotations

import logging

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import Field
from qdrant_client.http.models import SparseVectorParams, VectorParams

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import DimensionMismatchError, ModelSwitchError


if TYPE_CHECKING:
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion

logger = logging.getLogger(__name__)


class HybridVectorPayload(BasedModel):
    """Metadata payload for stored vectors."""

    chunk: Annotated[CodeChunk, Field(description="Code chunk metadata")]
    chunk_id: Annotated[str, Field(description="UUID7 hex string index identifier for the chunk")]
    file_path: Annotated[str, Field(description="File path of the code chunk")]
    line_start: Annotated[int, Field(description="Start line number of the code chunk")]
    line_end: Annotated[int, Field(description="End line number of the code chunk")]
    indexed_at: Annotated[
        str, Field(description="ISO 8601 datetime string when the chunk was indexed")
    ]
    chunked_on: Annotated[
        str, Field(description="ISO 8601 datetime string when the chunk was created")
    ]
    hash: Annotated[str, Field(description="blake 3 hash of the code chunk")]
    provider: Annotated[str, Field(description="Provider name for the vector store")]
    embedding_complete: Annotated[
        bool,
        Field(
            description="Whether the chunk has been fully embedded with both sparse and dense embeddings"
        ),
    ]

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {FilteredKey("file_path"): AnonymityConversion.HASH}

    def to_payload(self) -> dict[str, Any]:
        """Convert to a dictionary payload for storage."""
        return self.model_dump(mode="json", exclude_none=True, by_alias=True, round_trip=True)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> HybridVectorPayload:
        """Create a HybridVectorPayload from a dictionary payload."""
        return cls.model_validate(payload)


class CollectionMetadata(BasedModel):
    """Metadata stored with collections for validation and compatibility checks."""

    provider: Annotated[str, Field(description="Provider name that created collection")]
    created_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(UTC))]
    project_name: Annotated[str, Field(description="Project/repository name")]
    vector_config: Annotated[
        dict[Literal["dense"], VectorParams],
        Field(description="Vector configuration snapshot", serialization_alias="vectors_config"),
    ]
    sparse_config: Annotated[
        dict[Literal["sparse"], SparseVectorParams],
        Field(
            description="Sparse embedding configuration snapshot",
            serialization_alias="sparse_vectors_config",
        ),
    ]

    dense_model: Annotated[str | None, Field(description="Embedding model name used")] = None
    sparse_model: Annotated[str | None, Field(description="Sparse embedding model name used")] = (
        None
    )
    collection_name: Annotated[str, Field(description="Name of the collection")] = ""

    version: Annotated[str, Field(description="Metadata schema version")] = "1.0.0"

    def to_collection(self) -> dict[str, Any]:
        """Convert to a dictionary that is the argument for collection creation."""
        return self.model_dump(
            exclude_none=True,
            by_alias=True,
            round_trip=True,
            exclude={
                "created_at",
                "project_name",
                "version",
                "provider",
                "dense_model",
                "sparse_model",
            },
        )

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
                        "If you encounter issues, you may need to delete the existing collection and re-index. Run `codeweaver index` to re-index.",
                    ],
                },
            )

        # Error on model switch - this corrupts search results
        # Only raise if both have models and they differ (allow None for backwards compatibility)
        if (
            self.embedding_model
            and other.embedding_model
            and self.embedding_model != other.embedding_model
        ):
            raise ModelSwitchError(
                f"Your existing embedding collection was created with model '{other.embedding_model}', but the current model is '{self.embedding_model}'. You can't use different embedding models for the same collection.",
                suggestions=[
                    "Option 1: Re-index your codebase with the new provider",
                    "Option 2: Revert provider setting to match the collection",
                    "Option 3: Delete the existing collection and re-index",
                    "Option 4: Create a new collection with a different name",
                ],
                details={
                    "collection_provider": self.provider,
                    "current_provider": other.provider,
                    "collection_model": other.embedding_model,
                    "current_model": self.embedding_model,
                    "collection": self.project_name,
                },
            )

        if (
            self.embedding_dim_dense
            and other.embedding_dim_dense
            and self.embedding_dim_dense != other.embedding_dim_dense
        ):
            raise DimensionMismatchError(
                f"Embedding dimension mismatch: collection expects {other.embedding_dim_dense}, but current embedder produces {self.embedding_dim_dense}.",
                suggestions=[
                    "Option 1: Use an embedding model with matching dimensions",
                    "Option 2: Re-index with the current embedding model",
                    "Option 3: Check your embedding provider configuration",
                ],
                details={
                    "expected_dimension": self.embedding_dim_dense,
                    "actual_dimension": other.embedding_dim_dense,
                    "collection": self.project_name,
                },
            )
        if self.embedding_dtype_dense != other.embedding_dtype_dense:
            logger.warning(
                "Embedding data type mismatch: collection was created with '%s', but current embedder produces '%s'. This can produce unexpected results.",
                other.embedding_dtype_dense,
                self.embedding_dtype_dense,
                extra={
                    "expected_dtype": other.embedding_dtype_dense,
                    "actual_dtype": self.embedding_dtype_dense,
                    "collection": self.project_name,
                },
            )

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {FilteredKey("project_name"): AnonymityConversion.HASH}


__all__ = ("CollectionMetadata", "HybridVectorPayload")
