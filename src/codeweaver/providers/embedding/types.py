# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Types for the embedding registry."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal, NamedTuple, cast

from pydantic import UUID7, Field, NonNegativeInt, PositiveInt

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.types.aliases import LiteralStringT, ModelName, ModelNameT
from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.utils import generate_field_title
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


class EmbeddingBatchInfo(NamedTuple):
    """NamedTuple representing metadata about a CodeChunk's embedding within a batch."""

    batch_id: Annotated[
        UUID7,
        Field(
            description="Unique identifier for the batch",
            field_title_generator=generate_field_title,
        ),
    ]
    batch_index: Annotated[
        NonNegativeInt,
        Field(
            description="Index of the chunk within the batch",
            field_title_generator=generate_field_title,
        ),
    ]
    kind: Annotated[
        EmbeddingKind,
        Field(
            description="Kind of embedding (dense or sparse)",
            field_title_generator=generate_field_title,
        ),
    ]
    chunk_id: Annotated[
        UUID7,
        Field(
            description="Unique identifier for the chunk",
            field_title_generator=generate_field_title,
        ),
    ]
    model: Annotated[
        ModelNameT,
        Field(
            description="Name of the model used for embedding",
            field_title_generator=generate_field_title,
        ),
    ]
    embeddings: Annotated[
        StoredEmbeddingVectors | SparseEmbedding,
        Field(
            description="The embedding vectors (dense or sparse)",
            field_title_generator=generate_field_title,
        ),
    ]
    dimension: Annotated[
        PositiveInt | Literal[0],
        Field(
            description="Dimensionality of the embedding",
            field_title_generator=generate_field_title,
        ),
    ]
    dtype: Annotated[
        Literal["float32", "float16", "int8", "binary"],
        Field(description="Data type of the embedding", field_title_generator=generate_field_title),
    ] = "float32"
    backup: Annotated[
        bool,
        Field(
            description="Whether this embedding is for the backup vector store",
            field_title_generator=generate_field_title,
        ),
    ] = False

    @classmethod
    def create_dense(
        cls,
        batch_id: UUID7,
        batch_index: NonNegativeInt,
        chunk_id: UUID7,
        model: LiteralStringT | ModelNameT,
        embeddings: RawEmbeddingVectors,
        dimension: PositiveInt,
        *,
        dtype: Literal["float32", "float16", "int8", "binary"] = "float32",
        backup: bool = False,
    ) -> EmbeddingBatchInfo:
        """Create EmbeddingBatchInfo for dense embeddings."""
        return cls(
            batch_id=batch_id,
            batch_index=batch_index,
            kind=EmbeddingKind.DENSE,
            chunk_id=chunk_id,
            model=ModelName(model),
            embeddings=tuple(embeddings),
            dimension=dimension,
            dtype=dtype,
            backup=backup,
        )

    @classmethod
    def create_sparse(
        cls,
        batch_id: UUID7,
        batch_index: NonNegativeInt,
        chunk_id: UUID7,
        model: LiteralStringT | ModelNameT,
        embeddings: SparseEmbedding,
        *,
        dimension: Literal[0] = 0,
        backup: bool = False,
        dtype: Literal["float32", "float16", "int8", "binary"] = "float32",
    ) -> EmbeddingBatchInfo:
        """Create EmbeddingBatchInfo for sparse embeddings.

        Args:
            batch_id: Unique identifier for the batch
            batch_index: Index within the batch
            chunk_id: Unique identifier for the chunk
            model: Model name
            embeddings: SparseEmbedding with indices and values
            dimension: Dimensionality of the embedding (always 0 for sparse)
            dtype: Data type of the embedding values
            backup: Whether this embedding is for the backup vector store
        """
        return cls(
            batch_id=batch_id,
            batch_index=batch_index,
            kind=EmbeddingKind.SPARSE,
            chunk_id=chunk_id,
            model=ModelName(model),
            embeddings=embeddings.to_tuple(),
            dimension=0
            if dimension
            else dimension,  # just to be safe -- we keep it 0 but in signature for clarity
            dtype=dtype,
            backup=backup,
        )

    @property
    def is_dense(self) -> bool:
        """Check if the embedding kind is dense."""
        return self.kind == EmbeddingKind.DENSE

    @property
    def is_sparse(self) -> bool:
        """Check if the embedding kind is sparse."""
        return self.kind == EmbeddingKind.SPARSE

    @property
    def is_backup(self) -> bool:
        """Check if the embedding is marked as a backup."""
        return self.backup


class EmbeddingModelInfo(NamedTuple):
    """NamedTuple representing information about configured embedding models."""

    dense: Annotated[
        ModelNameT | None,
        Field(description="Dense embedding model name", field_title_generator=generate_field_title),
    ]
    sparse: Annotated[
        ModelNameT | None,
        Field(
            description="Sparse embedding model name", field_title_generator=generate_field_title
        ),
    ]
    backup_dense: Annotated[
        ModelNameT | None,
        Field(
            description="Backup dense embedding model name",
            field_title_generator=generate_field_title,
        ),
    ]
    backup_sparse: Annotated[
        ModelNameT | None,
        Field(
            description="Backup sparse embedding model name",
            field_title_generator=generate_field_title,
        ),
    ]


class ChunkEmbeddings(NamedTuple):
    """NamedTuple representing the embeddings associated with a specific CodeChunk."""

    sparse: Annotated[
        EmbeddingBatchInfo | None,
        Field(
            description="Sparse embedding information", field_title_generator=generate_field_title
        ),
    ]
    dense: Annotated[
        EmbeddingBatchInfo | None,
        Field(
            description="Dense embedding information", field_title_generator=generate_field_title
        ),
    ]
    chunk: Annotated[
        CodeChunk,
        Field(
            description="The code chunk associated with the embeddings",
            field_title_generator=generate_field_title,
        ),
    ]
    backup_dense: Annotated[
        EmbeddingBatchInfo | None,
        Field(
            description="Backup dense embedding information",
            field_title_generator=generate_field_title,
        ),
    ] = None
    backup_sparse: Annotated[
        EmbeddingBatchInfo | None,
        Field(
            description="Backup sparse embedding information",
            field_title_generator=generate_field_title,
        ),
    ] = None

    @property
    def is_complete(self) -> bool:
        """Check if both sparse and dense embeddings are present for primary embeddings."""
        return self.has_dense and self.has_sparse

    @property
    def is_backup_complete(self) -> bool:
        """Check if both sparse and dense embeddings are present for backup embeddings."""
        return self.backup_dense is not None and self.backup_sparse is not None

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
        if (
            (
                embedding_info.kind == EmbeddingKind.DENSE
                and embedding_info.backup
                and self.backup_dense is not None
            )
            or (
                embedding_info.kind == EmbeddingKind.DENSE
                and not embedding_info.backup
                and self.dense is not None
            )
            or (
                embedding_info.kind == EmbeddingKind.SPARSE
                and embedding_info.backup
                and self.backup_sparse is not None
            )
            or (
                embedding_info.kind == EmbeddingKind.SPARSE
                and not embedding_info.backup
                and self.sparse is not None
            )
        ):
            raise ValueError(
                f"Embeddings are already set for {embedding_info.kind.variable} in chunk {embedding_info.chunk_id}."
            )
        if self.chunk.chunk_id != embedding_info.chunk_id:
            raise ValueError(
                f"Embedding chunk ID {embedding_info.chunk_id} does not match ChunkEmbeddings chunk ID {self.chunk.chunk_id}."
            )
        return self._replace(
            dense=embedding_info
            if embedding_info.kind == EmbeddingKind.DENSE and not embedding_info.backup
            else self.dense,
            sparse=embedding_info
            if embedding_info.kind == EmbeddingKind.SPARSE and not embedding_info.backup
            else self.sparse,
            backup_dense=embedding_info
            if embedding_info.kind == EmbeddingKind.DENSE and embedding_info.backup
            else self.backup_dense,
            backup_sparse=embedding_info
            if embedding_info.kind == EmbeddingKind.SPARSE and embedding_info.backup
            else self.backup_sparse,
        )

    def update(self, embedding_info: EmbeddingBatchInfo) -> ChunkEmbeddings:
        """Update or replace an EmbeddingBatchInfo in the ChunkEmbeddings.

        Unlike `add()`, this method will replace existing embeddings of the same kind.
        This is useful for re-embedding scenarios where we want to update embeddings.

        Args:
            embedding_info (EmbeddingBatchInfo): The embedding information to update/replace.

        Returns:
            ChunkEmbeddings: A new ChunkEmbeddings instance with the updated embedding.
        """
        if self.chunk.chunk_id != embedding_info.chunk_id:
            raise ValueError(
                f"Embedding chunk ID {embedding_info.chunk_id} does not match ChunkEmbeddings chunk ID {self.chunk.chunk_id}."
            )
        return self._replace(
            dense=embedding_info
            if embedding_info.kind == EmbeddingKind.DENSE and not embedding_info.backup
            else self.dense,
            sparse=embedding_info
            if embedding_info.kind == EmbeddingKind.SPARSE and not embedding_info.backup
            else self.sparse,
            backup_dense=embedding_info
            if embedding_info.kind == EmbeddingKind.DENSE and embedding_info.backup
            else self.backup_dense,
            backup_sparse=embedding_info
            if embedding_info.kind == EmbeddingKind.SPARSE and embedding_info.backup
            else self.backup_sparse,
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

    @property
    def backup_dense_model(self) -> ModelNameT | None:
        """Get the model name used for backup dense embeddings, if any."""
        return self.backup_dense.model if self.backup_dense is not None else None

    @property
    def backup_sparse_model(self) -> ModelNameT | None:
        """Get the model name used for backup sparse embeddings, if any."""
        return self.backup_sparse.model if self.backup_sparse is not None else None


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
