# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Core embedding type definitions for CodeWeaver."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated, Literal, NamedTuple, override

from pydantic import UUID7, Field, NonNegativeInt, PositiveInt

from codeweaver.core import BasedModel
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.types.aliases import LiteralStringT, ModelName, ModelNameT
from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.provider import Provider
from codeweaver.core.types.utils import generate_field_title


if TYPE_CHECKING:
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT

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


class DataType(BaseEnum):
    """Enum representing the data type of embedding vectors."""

    FLOAT = "float"
    FLOAT16 = "float16"
    INT8 = "int8"
    UINT8 = "uint8"
    UBINARY = "ubinary"
    BINARY = "binary"

    def cross_walk(self) -> dict[Provider, str]:
        """Get the corresponding data type string for crosswalks."""
        mapping = {
            DataType.FLOAT: {Provider.VOYAGE: "float", Provider.QDRANT: "float32"},
            DataType.FLOAT16: {Provider.VOYAGE: "float16", Provider.QDRANT: "float16"},
            DataType.INT8: {Provider.VOYAGE: "int8", Provider.QDRANT: "uint8"},
            DataType.UINT8: {Provider.VOYAGE: "uint8", Provider.QDRANT: "uint8"},
            DataType.UBINARY: {Provider.VOYAGE: "ubinary", Provider.QDRANT: "uint8"},
            DataType.BINARY: {Provider.VOYAGE: "binary", Provider.QDRANT: "uint8"},
        }
        return mapping[self]


class EmbeddingKind(BaseEnum):
    """Enum representing the kind of embedding."""

    DENSE = "dense"
    SPARSE = "sparse"


class QueryResult(BasedModel):
    """Multi-vector embedding result from an embedding query.

    Stores embeddings from multiple intents (primary, backup, sparse, etc.)
    in a dictionary keyed by intent name.
    """

    vectors: Annotated[
        dict[str, RawEmbeddingVectors | SparseEmbedding],
        Field(
            description="Embeddings keyed by intent name",
            field_title_generator=generate_field_title,
        ),
    ] = Field(default_factory=dict)

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {FilteredKey("vectors"): AnonymityConversion.COUNT}

    @override
    def __getitem__(self, intent: str) -> RawEmbeddingVectors | SparseEmbedding:  # ty: ignore[invalid-method-override]
        """Get embedding for a specific intent."""
        return self.vectors[intent]

    @override
    def get(  # ty: ignore[invalid-method-override]
        self, intent: str, default: RawEmbeddingVectors | SparseEmbedding | None = None
    ) -> RawEmbeddingVectors | SparseEmbedding | None:
        """Get embedding for an intent with optional default."""
        return self.vectors.get(intent, default)

    @property
    def intents(self) -> set[str]:
        """Get all available intent names."""
        return set(self.vectors.keys())


class EmbeddingBatchInfo(BasedModel):
    """BasedModel representing metadata about a CodeChunk's embedding within a batch."""

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
    intent: Annotated[
        str,
        Field(
            description="Intent/purpose of this embedding (e.g., 'primary', 'backup', 'sparse')",
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

    def _telemetry_keys(self) -> None:
        return None

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
        intent: str = "primary",
        dtype: Literal["float32", "float16", "int8", "binary"] = "float32",
    ) -> EmbeddingBatchInfo:
        """Create EmbeddingBatchInfo for dense embeddings."""
        return cls(
            batch_id=batch_id,
            batch_index=batch_index,
            intent=intent,
            kind=EmbeddingKind.DENSE,
            chunk_id=chunk_id,
            model=ModelName(model),
            embeddings=tuple(embeddings),
            dimension=dimension,
            dtype=dtype,
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
        intent: str = "sparse",
        dimension: Literal[0] = 0,
        dtype: Literal["float32", "float16", "int8", "binary"] = "float32",
    ) -> EmbeddingBatchInfo:
        """Create EmbeddingBatchInfo for sparse embeddings.

        Args:
            batch_id: Unique identifier for the batch
            batch_index: Index within the batch
            chunk_id: Unique identifier for the chunk
            model: Model name
            embeddings: SparseEmbedding with indices and values
            intent: Intent/purpose of this embedding (default: "sparse")
            dimension: Dimensionality of the embedding (always 0 for sparse)
            dtype: Data type of the embedding values
        """
        return cls(
            batch_id=batch_id,
            batch_index=batch_index,
            intent=intent,
            kind=EmbeddingKind.SPARSE,
            chunk_id=chunk_id,
            model=ModelName(model),
            embeddings=embeddings.to_tuple(),
            dimension=0
            if dimension
            else dimension,  # just to be safe -- we keep it 0 but in signature for clarity
            dtype=dtype,
        )

    @property
    def is_dense(self) -> bool:
        """Check if the embedding kind is dense."""
        return self.kind == EmbeddingKind.DENSE

    @property
    def is_sparse(self) -> bool:
        """Check if the embedding kind is sparse."""
        return self.kind == EmbeddingKind.SPARSE


class ChunkEmbeddings(BasedModel):
    """Model representing the embeddings associated with a specific CodeChunk.

    Uses a dynamic dictionary to support arbitrary named embeddings (intents).
    Common keys include: "primary", "sparse", "backup", "summary", "ast".
    """

    embeddings: dict[str, EmbeddingBatchInfo] = Field(
        default_factory=dict, description="Dictionary mapping intent names to embedding information"
    )
    chunk: CodeChunk

    def _telemetry_keys(self) -> None:
        return None

    def add(self, embedding_info: EmbeddingBatchInfo) -> ChunkEmbeddings:
        """Add an EmbeddingBatchInfo to the ChunkEmbeddings.

        Args:
            embedding_info: The embedding information to add (intent is extracted from this object).

        Returns:
            ChunkEmbeddings: A new ChunkEmbeddings instance with the added embedding.

        Raises:
            ValueError: If embedding already exists for this intent or chunk IDs don't match.
        """
        if self.chunk.chunk_id != embedding_info.chunk_id:
            raise ValueError(
                f"Embedding chunk ID {embedding_info.chunk_id} does not match ChunkEmbeddings chunk ID {self.chunk.chunk_id}."
            )

        intent = embedding_info.intent

        if intent in self.embeddings:
            raise ValueError(
                f"Embeddings are already set for intent '{intent}' in chunk {embedding_info.chunk_id}."
            )

        return self._set_intent_embedding(embedding_info, intent)

    def update(self, embedding_info: EmbeddingBatchInfo) -> ChunkEmbeddings:
        """Update or replace an EmbeddingBatchInfo in the ChunkEmbeddings.

        Unlike `add()`, this method will replace existing embeddings of the same intent.
        This is useful for re-embedding scenarios where we want to update embeddings.

        Args:
            embedding_info: The embedding information to update/replace (intent is extracted from this object).

        Returns:
            ChunkEmbeddings: A new ChunkEmbeddings instance with the updated embedding.

        Raises:
            ValueError: If chunk IDs don't match.
        """
        if self.chunk.chunk_id != embedding_info.chunk_id:
            raise ValueError(
                f"Embedding chunk ID {embedding_info.chunk_id} does not match ChunkEmbeddings chunk ID {self.chunk.chunk_id}."
            )

        intent = embedding_info.intent

        return self._set_intent_embedding(embedding_info, intent)

    def _set_intent_embedding(self, embedding_info, intent):
        new_embeddings = dict(self.embeddings)
        new_embeddings[intent] = embedding_info
        return self.model_copy(update={"embeddings": new_embeddings})

    def get_model_by_vector_intent(self, intent: str) -> ModelNameT | None:
        """Get the model name used for a specific embedding intent, if it exists."""
        return self.embeddings.get(intent).model if intent in self.embeddings else None

    @property
    def models(self) -> tuple[ModelNameT, ...]:
        """Get all unique models used for the embeddings."""
        return tuple({emb.model for emb in self.embeddings.values()})

    @property
    def dense_model(self) -> ModelNameT | None:
        """Get the model name used for primary dense embeddings, if any."""
        return self.embeddings.get("primary").model if "primary" in self.embeddings else None

    @property
    def sparse_model(self) -> ModelNameT | None:
        """Get the model name used for sparse embeddings, if any."""
        return self.embeddings.get("sparse").model if "sparse" in self.embeddings else None

    @property
    def backup_dense_model(self) -> ModelNameT | None:
        """Get the model name used for backup dense embeddings, if any."""
        return self.embeddings.get("backup").model if "backup" in self.embeddings else None

    @property
    def has_dense(self) -> bool:
        """Check if this chunk has any dense embedding (primary or backup)."""
        return any(emb.is_dense for emb in self.embeddings.values())

    @property
    def has_sparse(self) -> bool:
        """Check if this chunk has any sparse embedding."""
        return any(emb.is_sparse for emb in self.embeddings.values())

    @property
    def is_complete(self) -> bool:
        """Check if this chunk has both dense and sparse embeddings."""
        return self.has_dense and self.has_sparse


__all__ = (
    "ChunkEmbeddings",
    "DataType",
    "EmbeddingBatchInfo",
    "EmbeddingKind",
    "QueryResult",
    "RawEmbeddingVectors",
    "SparseEmbedding",
    "StoredEmbeddingVectors",
)
