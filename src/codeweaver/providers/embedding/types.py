# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Types for the embedding registry."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, NamedTuple, cast

from pydantic import UUID7, Field, NonNegativeInt

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.types.aliases import LiteralStringT, ModelName, ModelNameT
from codeweaver.core.types.enum import BaseEnum
from codeweaver.exceptions import ConfigurationError


class InvalidEmbeddingModelError(ConfigurationError):
    """Exception raised when an invalid embedding model is encountered."""


type RawEmbeddingVectors = Sequence[float] | Sequence[int]
type StoredEmbeddingVectors = tuple[float, ...] | tuple[int, ...]


class SparseEmbedding(NamedTuple):
    """NamedTuple representing sparse embedding with indices and values.

    Sparse embeddings are represented as two parallel arrays:
    - indices: positions in the vocabulary that have non-zero values
    - values: weights/importance scores for those positions

    This format is used by SPLADE, SparseEncoder and similar models.
    """

    indices: Annotated[Sequence[int], Field(description="Indices of non-zero embedding values")]
    values: Annotated[
        Sequence[float], Field(description="Values (weights) of non-zero embedding indices")
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

    dense: RawEmbeddingVectors | None
    sparse: SparseEmbedding | None


class EmbeddingBatchInfo(NamedTuple):
    """NamedTuple representing metadata about a CodeChunk's embedding within a batch."""

    batch_id: UUID7
    batch_index: NonNegativeInt
    kind: EmbeddingKind
    chunk_id: UUID7
    model: ModelNameT
    embeddings: StoredEmbeddingVectors | SparseEmbedding

    @classmethod
    def create_dense(
        cls,
        batch_id: UUID7,
        batch_index: NonNegativeInt,
        chunk_id: UUID7,
        model: LiteralStringT | ModelNameT,
        embeddings: RawEmbeddingVectors,
    ) -> EmbeddingBatchInfo:
        """Create EmbeddingBatchInfo for dense embeddings."""
        return cls(
            batch_id=batch_id,
            batch_index=batch_index,
            kind=EmbeddingKind.DENSE,
            chunk_id=chunk_id,
            model=ModelName(model),
            embeddings=tuple(embeddings),
        )

    @classmethod
    def create_sparse(
        cls,
        batch_id: UUID7,
        batch_index: NonNegativeInt,
        chunk_id: UUID7,
        model: LiteralStringT | ModelNameT,
        embeddings: SparseEmbedding,
    ) -> EmbeddingBatchInfo:
        """Create EmbeddingBatchInfo for sparse embeddings.

        Args:
            batch_id: Unique identifier for the batch
            batch_index: Index within the batch
            chunk_id: Unique identifier for the chunk
            model: Model name
            embeddings: SparseEmbedding with indices and values
        """
        return cls(
            batch_id=batch_id,
            batch_index=batch_index,
            kind=EmbeddingKind.SPARSE,
            chunk_id=chunk_id,
            model=ModelName(model),
            embeddings=embeddings.to_tuple(),
        )

    def is_dense(self) -> bool:
        """Check if the embedding kind is dense."""
        return self.kind == EmbeddingKind.DENSE

    def is_sparse(self) -> bool:
        """Check if the embedding kind is sparse."""
        return self.kind == EmbeddingKind.SPARSE


class ChunkEmbeddings(NamedTuple):
    """NamedTuple representing the embeddings associated with a specific CodeChunk."""

    sparse: EmbeddingBatchInfo | None
    dense: EmbeddingBatchInfo | None
    chunk: CodeChunk

    @property
    def is_complete(self) -> bool:
        """Check if both sparse and dense embeddings are present."""
        return self.has_dense and self.has_sparse

    @property
    def has_dense(self) -> bool:
        """Check if dense embeddings are present."""
        return self.dense is not None

    @property
    def has_sparse(self) -> bool:
        """Check if sparse embeddings are present."""
        return self.sparse is not None

    def add(self, embedding_info: EmbeddingBatchInfo) -> ChunkEmbeddings:
        """Add an EmbeddingBatchInfo to the ChunkEmbeddings.

        Args:
            embedding_info (EmbeddingBatchInfo): The embedding information to add.

        Returns:
            ChunkEmbeddings: A new ChunkEmbeddings instance with the added embedding.
        """
        if (embedding_info.kind == EmbeddingKind.DENSE and self.dense is not None) or (
            embedding_info.kind == EmbeddingKind.SPARSE and self.sparse is not None
        ):
            raise ValueError(
                f"Embeddings are already set for {embedding_info.kind.value} in chunk {embedding_info.chunk_id}."
            )
        if self.chunk.chunk_id != embedding_info.chunk_id:
            raise ValueError(
                f"Embedding chunk ID {embedding_info.chunk_id} does not match ChunkEmbeddings chunk ID {self.chunk.chunk_id}."
            )
        return self._replace(
            dense=embedding_info if embedding_info.kind == EmbeddingKind.DENSE else self.dense,
            sparse=embedding_info if embedding_info.kind == EmbeddingKind.SPARSE else self.sparse,
        )

    @property
    def models(self) -> tuple[ModelNameT] | tuple[ModelNameT, ModelNameT]:
        """Get the set of models used for the embeddings."""
        if not self.is_complete:
            return (
                (self.dense.model,)
                if self.dense is not None
                else (cast(EmbeddingBatchInfo, self.sparse).model,)
            )  # type: ignore
        assert self.dense is not None  # noqa: S101
        assert self.sparse is not None  # noqa: S101
        return self.dense.model, self.sparse.model

    @property
    def dense_model(self) -> ModelNameT | None:
        """Get the model name used for dense embeddings, if any."""
        return self.dense.model if self.dense is not None else None

    @property
    def sparse_model(self) -> ModelNameT | None:
        """Get the model name used for sparse embeddings, if any."""
        return self.sparse.model if self.sparse is not None else None


__all__ = (
    "ChunkEmbeddings",
    "EmbeddingBatchInfo",
    "EmbeddingKind",
    "InvalidEmbeddingModelError",
    "QueryResult",
    "RawEmbeddingVectors",
    "SparseEmbedding",
    "StoredEmbeddingVectors",
)
