# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Core embedding type definitions for CodeWeaver."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, NamedTuple

from pydantic import Field

from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.utils import generate_field_title


type RawEmbeddingVectors = Sequence[float] | Sequence[int]
type StoredEmbeddingVectors = tuple[float, ...] | tuple[int, ...]


class SparseEmbedding(NamedTuple):
    """NamedTuple representing sparse embedding with indices and values.

    Sparse embeddings are represented as two parallel arrays:
    - indices: positions in the vocabulary that have non-zero values
    - values: weights/importance scores for those positions

    This format is used by SPLADE, SparseEncoder and similar models.
    """

    indices: Annotated[
        Sequence[int],
        Field(
            description="Indices of non-zero embedding values",
            field_title_generator=generate_field_title,
        ),
    ]
    values: Annotated[
        Sequence[float],
        Field(
            description="Values (weights) of non-zero embedding indices",
            field_title_generator=generate_field_title,
        ),
    ]

    def to_tuple(self) -> SparseEmbedding:
        """Convert to a SparseEmbedding with tuples for indices and values."""
        return self._replace(indices=tuple(self.indices), values=tuple(self.values))


class EmbeddingKind(BaseEnum):
    """Enum representing the kind of embedding."""

    DENSE = "dense"
    SPARSE = "sparse"


class QueryResult(NamedTuple):
    """NamedTuple representing the result of an embedding query."""

    dense: Annotated[
        RawEmbeddingVectors | None,
        Field(description="The dense embedding vector", title="Dense Embedding"),
    ]
    sparse: Annotated[
        SparseEmbedding | None,
        Field(description="The sparse embedding representation", title="Sparse Embedding"),
    ]


__all__ = (
    "EmbeddingKind",
    "QueryResult",
    "RawEmbeddingVectors",
    "SparseEmbedding",
    "StoredEmbeddingVectors",
)
