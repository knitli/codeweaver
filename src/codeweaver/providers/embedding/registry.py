# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""A UUIDStore registry for embedding providers.

This registry maps embedding batch IDs and indexes to their corresponding embedding vectors.
It only stores the last `max_size` bytes, and moves old batches to a weakref store when the limit is exceeded (all UUIDStore instances work like this).
"""

from __future__ import annotations

import logging

from typing import Literal, cast, overload

from pydantic import UUID7

from codeweaver.core import (
    ChunkEmbeddings,
    EmbeddingKind,
    InvalidEmbeddingModelError,
    ModelNameT,
    UUIDStore,
    dependency_provider,
)
from codeweaver.core import ValidationError as CodeWeaverValidationError


logger = logging.getLogger(__name__)

ONE_MB = 1024 * 1024


class EmbeddingRegistry(UUIDStore[ChunkEmbeddings]):
    """
    A UUIDStore registry for generated embeddings. It maps CodeChunk IDs to their corresponding embeddings (as `ChunkEmbeddings`).

    UUID Stores are a key value store that enforces its value types. They have a weakref 'trash_heap' that stores old values when its main store is full, freeing up memory while still allowing access to old values in most cases. In practice, it provides guaranteed storage for the most recent items, and best-effort storage for older items.

    Since vectors are large, the `size_limit` defaults to 100 MB.

    """

    is_backup_provider: bool = False
    """Indicates whether this registry is for a backup embedding provider."""

    def __init__(self, *, size_limit: int = 100 * ONE_MB, is_backup_provider: bool = False) -> None:
        """Initialize the EmbeddingRegistry with a size limit.

        Args:
            size_limit (int): The maximum size of the store in bytes. Defaults to 100 MB.
        """
        self.is_backup_provider = is_backup_provider
        super().__init__(size_limit=size_limit, _value_type=ChunkEmbeddings)

    @property
    def complete(self) -> bool:
        """Check if all chunks have both primary dense and sparse embeddings."""
        return all(embeddings.is_complete for embeddings in self.values())

    @property
    def dense_only(self) -> bool:
        """Check if all chunks have only (primary) dense embeddings."""
        return all(
            embeddings.has_dense and not embeddings.has_sparse for embeddings in self.values()
        )

    @property
    def sparse_only(self) -> bool:
        """Check if all chunks have only (primary) sparse embeddings."""
        return all(
            not embeddings.has_dense and embeddings.has_sparse for embeddings in self.values()
        )

    def _fetch_model_by_kind(self, kind: EmbeddingKind) -> ModelNameT | None:
        """Fetch the set of models used for a specific embedding kind."""
        models = {
            getattr(embeddings, f"{kind.variable}_model", None)
            for embeddings in self.values()
            if getattr(embeddings, f"has_{kind.variable}")
        }  # type: ignore
        if len(models) > 1:
            raise CodeWeaverValidationError(
                f"Multiple embedding models detected for {kind.variable} embeddings",
                details={
                    "embedding_kind": kind.variable,
                    "detected_models": list(models),
                    "model_count": len(models),
                },
                suggestions=[
                    "Use a single embedding model for all data of the same type",
                    "Clear existing embeddings before switching models",
                    "Check configuration to ensure consistent model selection",
                ],
            )
        # UUIDStores always returns a copy, so we can safely pop here
        return models.pop() if models else None

    @property
    def sparse_model(self) -> ModelNameT | None:
        """Get the model name used for primary sparse embeddings, if any."""
        return self._fetch_model_by_kind(EmbeddingKind.SPARSE)

    @property
    def dense_model(self) -> ModelNameT | None:
        """Get the model name used for primary dense embeddings, if any."""
        return self._fetch_model_by_kind(EmbeddingKind.DENSE)

    def get_item_ages(self) -> dict[UUID7, int]:
        """Get the ages of all items in the store, where age is defined as the number of insertions since the item was added."""
        from codeweaver.core import uuid7_as_timestamp

        if mapping := {key: uuid7_as_timestamp(key) for key in self}:
            return cast(dict[UUID7, int], mapping)
        logger.warning(
            "No items found in EmbeddingRegistry store when attempting to get item ages."
        )
        return {}

    def oldest_item(self) -> UUID7 | None:
        """Get the oldest item in the store based on insertion time."""
        item_ages = sorted(iter(self.get_item_ages().items()), key=lambda x: x[1])
        return min(item[0] for item in item_ages) if item_ages else None

    def validate_models(self) -> None:
        """Validate that all embeddings use the same model and return the set of models used."""
        try:
            _ = self.dense_model
            _ = self.sparse_model
        except ValueError as e:
            raise InvalidEmbeddingModelError(
                "Embeddings can't be created with multiple models for the same data. You can only have one model per embedding kind (sparse and dense). (...for now)",
                details={k.hex: v for k, v in self.items()},
            ) from e


class BackupEmbeddingRegistry(EmbeddingRegistry):
    """
    A backup embedding registry for use with backup embedding providers.

    This class is identical to `EmbeddingRegistry` but is used to differentiate between primary and backup embedding stores.
    """

    def __init__(
        self, *, size_limit: int = 100 * ONE_MB, is_backup_provider: Literal[True] = True
    ) -> None:
        super().__init__(size_limit=size_limit, is_backup_provider=is_backup_provider)


def _rebuild_store(store: type[EmbeddingRegistry | BackupEmbeddingRegistry]) -> None:
    """Rebuild the given UUIDStore to ensure proper initialization after model changes."""
    if not store.__pydantic_complete__:
        # We need CodeChunk in the namespace for the rebuild
        from codeweaver.core import CodeChunk as CodeChunk

        store.model_rebuild()


@overload
def get_embedding_registry(*, backup: bool = False) -> EmbeddingRegistry: ...


@overload
def get_embedding_registry(*, backup: Literal[True]) -> BackupEmbeddingRegistry: ...


def get_embedding_registry(*, backup: bool = False) -> EmbeddingRegistry | BackupEmbeddingRegistry:
    """Get the global EmbeddingRegistry instance, creating it if it doesn't exist."""
    _rebuild_store(BackupEmbeddingRegistry if backup else EmbeddingRegistry)
    return (
        BackupEmbeddingRegistry(is_backup_provider=True)
        if backup
        else EmbeddingRegistry(is_backup_provider=False)
    )


@dependency_provider(EmbeddingRegistry, scope="singleton", module=__name__)
def _get_main_registry() -> EmbeddingRegistry:
    """Get the main EmbeddingRegistry instance."""
    return get_embedding_registry(backup=False)


@dependency_provider(BackupEmbeddingRegistry, scope="singleton", module=__name__)
def _get_backup_registry() -> BackupEmbeddingRegistry:
    """Get the backup EmbeddingRegistry instance."""
    return get_embedding_registry(backup=True)  # ty:ignore[invalid-return-type]


__all__ = ("EmbeddingRegistry", "get_embedding_registry")
