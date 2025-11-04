# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Collection metadata models for vector stores."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field, PositiveInt

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import DimensionMismatchError, ModelSwitchError


if TYPE_CHECKING:
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion


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


class CollectionMetadata(BasedModel):
    """Metadata stored with collections for validation and compatibility checks."""

    provider: Annotated[str, Field(description="Provider name that created collection")]
    created_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(UTC))]
    project_name: Annotated[str, Field(description="Project/repository name")]
    vector_config: Annotated[dict[str, Any], Field(description="Vector configuration snapshot")]
    embedding_dtype_dense: Annotated[
        str, Field(description="Data type of dense embeddings, e.g., 'float32'")
    ] = "float32"
    embedding_dim_dense: Annotated[
        PositiveInt | None, Field(description="Expected dense embedding dimension")
    ] = None

    embedding_model: Annotated[str | None, Field(description="Embedding model name used")] = None
    sparse_embedding_model: Annotated[
        str | None, Field(description="Sparse embedding model name used")
    ] = None
    collection_name: Annotated[str, Field(description="Name of the collection")] = ""

    version: Annotated[str, Field(description="Metadata schema version")] = "1.0.0"

    def validate_compatibility(self, other: CollectionMetadata) -> None:
        """Validate collection metadata against current provider configuration.

        Args:
            other: Other collection metadata to compare against

        Raises:
            ProviderSwitchError: If provider doesn't match collection metadata
            DimensionMismatchError: If embedding dimensions don't match
        """
        if self.embedding_model and self.embedding_model != other.embedding_model:
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
                    "actual_dimension": expected_dense_dim,
                    "collection": self.project_name,
                },
            )

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {FilteredKey("project_name"): AnonymityConversion.HASH}


__all__ = ("CollectionMetadata", "HybridVectorPayload")
