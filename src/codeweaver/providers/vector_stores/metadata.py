# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Collection metadata models for vector stores."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Annotated

from pydantic import Field, PositiveInt

from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import DimensionMismatchError, ProviderSwitchError


class CollectionMetadata(BasedModel):
    """Metadata stored with collections for validation and compatibility checks."""

    provider: Annotated[str, Field(description="Provider name that created collection")]
    version: Annotated[str, Field(description="Metadata schema version")]
    created_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(UTC))]
    embedding_dim_dense: Annotated[PositiveInt, Field(description="Expected dense embedding dimension")]
    embedding_dim_sparse: Annotated[
        int | None, Field(default=None, description="Max sparse embedding dimension")
    ]
    project_name: Annotated[str, Field(description="Project/repository name")]
    vector_config: Annotated[dict[str, Any], Field(description="Vector configuration snapshot")]

    def validate_compatibility(
        self,
        current_provider: str,
        expected_dense_dim: int,
        expected_sparse_dim: int | None = None,
    ) -> None:
        """Validate collection metadata against current provider configuration.

        Args:
            current_provider: Current provider name
            expected_dense_dim: Expected dense embedding dimension
            expected_sparse_dim: Expected sparse embedding dimension (optional)

        Raises:
            ProviderSwitchError: If provider doesn't match collection metadata
            DimensionMismatchError: If embedding dimensions don't match
        """
        if self.provider != current_provider:
            raise ProviderSwitchError(
                f"Collection was created with '{self.provider}' provider, but current configuration uses '{current_provider}'",
                suggestions=[
                    "Option 1: Re-index your codebase with the current provider",
                    "Option 2: Revert provider setting to match the collection",
                    "Option 3: Delete the existing collection and re-index",
                ],
                details={
                    "collection_provider": self.provider,
                    "current_provider": current_provider,
                    "collection": self.project_name,
                },
            )

        if self.embedding_dim_dense != expected_dense_dim:
            raise DimensionMismatchError(
                f"Embedding dimension mismatch: collection expects {self.embedding_dim_dense}, but current embedder produces {expected_dense_dim}",
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

        if expected_sparse_dim and self.embedding_dim_sparse and self.embedding_dim_sparse != expected_sparse_dim:
            raise DimensionMismatchError(
                f"Sparse embedding dimension mismatch: collection expects {self.embedding_dim_sparse}, but current embedder produces {expected_sparse_dim}",
                suggestions=[
                    "Option 1: Use a sparse embedding model with matching dimensions",
                    "Option 2: Re-index with the current sparse embedding model",
                ],
                details={
                    "expected_sparse_dimension": self.embedding_dim_sparse,
                    "actual_sparse_dimension": expected_sparse_dim,
                    "collection": self.project_name,
                },
            )


__all__ = ("CollectionMetadata",)
