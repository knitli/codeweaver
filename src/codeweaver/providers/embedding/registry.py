"""A UUIDStore registry for embedding providers.

This registry maps embedding batch IDs and indexes to their corresponding embedding vectors.
It only stores the last `max_size` bytes, and moves old batches to a weakref store when the limit is exceeded (all UUIDStore instances work like this).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple, cast

from pydantic import UUID7, NonNegativeInt

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.stores import UUIDStore
from codeweaver.core.types.aliases import LiteralStringT, ModelName, ModelNameT
from codeweaver.core.types.enum import BaseEnum
from codeweaver.exceptions import ConfigurationError


class InvalidEmbeddingModelError(ConfigurationError):
    """Exception raised when an invalid embedding model is encountered."""


type RawEmbeddingVectors = Sequence[float] | Sequence[int]
type StoredEmbeddingVectors = tuple[float, ...] | tuple[int, ...]


class EmbeddingKind(BaseEnum):
    """Enum representing the kind of embedding."""

    DENSE = "dense"
    SPARSE = "sparse"


class EmbeddingBatchInfo(NamedTuple):
    """NamedTuple representing metadata about a CodeChunk's embedding within a batch."""

    batch_id: UUID7
    batch_index: NonNegativeInt
    kind: EmbeddingKind
    chunk_id: UUID7
    model: ModelNameT
    embeddings: StoredEmbeddingVectors

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
        embeddings: RawEmbeddingVectors,
    ) -> EmbeddingBatchInfo:
        """Create EmbeddingBatchInfo for sparse embeddings."""
        return cls(
            batch_id=batch_id,
            batch_index=batch_index,
            kind=EmbeddingKind.SPARSE,
            chunk_id=chunk_id,
            model=ModelName(model),
            embeddings=tuple(embeddings),
        )


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


class EmbeddingRegistry(UUIDStore[ChunkEmbeddings]):
    """
    A UUIDStore registry for generated embeddings. It maps CodeChunk IDs to their corresponding embeddings (as `ChunkEmbeddings`).

    UUID Stores are a key value store that enforces its value types. They have a weakref 'trash_heap' that stores old values when its main store is full, freeing up memory while still allowing access to old values in most cases. In practice, it provides guaranteed storage for the most recent items, and best-effort storage for older items.

    Since vectors are large, the `size_limit` defaults to 100 MB.

    TODO: Make size_limit configurable by users in settings.

    TODO: Should we make `EmbeddingRegistry`'s size dynamic based on conditions? For example, if we are getting service errors from the vector store, we could increase the size_limit temporarily as a queue.

    TODO: Save the store to disk to persist across restarts. Ideally we'd use a contextmanager to load/save the store automatically. The parent class, `SimpleTypedStore` already has `load` and `save` methods we could leverage.
    """

    def __init__(self, *, size_limit: int = 100 * 1024 * 1024) -> None:
        """Initialize the EmbeddingRegistry with a size limit.

        Args:
            size_limit (int): The maximum size of the store in bytes. Defaults to 100 MB.
        """
        super().__init__(value_type=tuple, max_size=size_limit)

    @property
    def complete(self) -> bool:
        """Check if all chunks have both dense and sparse embeddings."""
        return all(embeddings.is_complete for embeddings in self.values())

    @property
    def dense_only(self) -> bool:
        """Check if all chunks have only dense embeddings."""
        return all(
            embeddings.has_dense and not embeddings.has_sparse for embeddings in self.values()
        )

    @property
    def sparse_only(self) -> bool:
        """Check if all chunks have only sparse embeddings."""
        return all(
            not embeddings.has_dense and embeddings.has_sparse for embeddings in self.values()
        )

    def _fetch_model_by_kind(self, kind: EmbeddingKind) -> ModelNameT | None:
        """Fetch the set of models used for a specific embedding kind."""
        models = {
            getattr(embeddings, f"{kind.value}_model", None)
            for embeddings in self.values()
            if getattr(embeddings, f"has_{kind.value}")
        }  # type: ignore
        if len(models) > 1:
            raise ValueError(
                f"Multiple models found for {kind.variable} embeddings. You can't use multiple models for the same data. Found: {models}"
            )
        return models.pop() if models else None

    @property
    def sparse_model(self) -> ModelNameT | None:
        """Get the model name used for sparse embeddings, if any."""
        return self._fetch_model_by_kind(EmbeddingKind.SPARSE)

    @property
    def dense_model(self) -> ModelNameT | None:
        """Get the model name used for dense embeddings, if any."""
        return self._fetch_model_by_kind(EmbeddingKind.DENSE)

    def validate_models(self) -> None:
        """Validate that all embeddings use the same model and return the set of models used."""
        try:
            _ = self.dense_model
            _ = self.sparse_model
        except ValueError as e:
            raise InvalidEmbeddingModelError(
                "Embeddings can't be created with multiple models for the same data. You can only have one model per embedding kind (sparse and dense).",
                details={k.hex: v for k, v in self.items()},
            ) from e


_embedding_registry: EmbeddingRegistry | None = None


def get_embedding_registry() -> EmbeddingRegistry:
    """Get the global EmbeddingRegistry instance, creating it if it doesn't exist."""
    global _embedding_registry
    if _embedding_registry is None:
        _embedding_registry = EmbeddingRegistry()
    return _embedding_registry


__all__ = (
    "ChunkEmbeddings",
    "EmbeddingBatchInfo",
    "EmbeddingKind",
    "EmbeddingRegistry",
    "get_embedding_registry",
)
