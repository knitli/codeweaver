# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Abstract provider interfaces for embeddings and vector storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import UUID4, ConfigDict
from typing_extensions import TypeIs

from codeweaver.core.chunks import CodeChunk, SearchResult
from codeweaver.core.types.models import BasedModel
from codeweaver.engine.filter import Filter
from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    SparseEmbeddingModelCapabilities,
)
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types.dictview import DictView


def _get_settings() -> DictView[CodeWeaverSettingsDict]:
    """Get global CodeWeaver settings.

    Returns:
        Global settings as a dictionary view.
    """
    from codeweaver.config.settings import get_settings_map

    return get_settings_map()


def _assemble_caps() -> dict[
    Literal["dense", "sparse"],
    list[EmbeddingModelCapabilities] | list[SparseEmbeddingModelCapabilities],
]:
    """Assemble embedding model capabilities from settings.

    Returns:
        EmbeddingModelCapabilities instance or None if not configured.
    """
    settings_map: dict[Literal["dense", "sparse"], list[dict[str, Any]]] = {
        "dense": [],
        "sparse": [],
    }
    settings_map["dense"].extend(
        model.get("model_settings") for model in _get_settings()["provider"]["embedding"]
    )

    settings_map["sparse"].extend(
        model.get("sparse_model_settings") for model in _get_settings()["provider"]["embedding"]
    )

    embedding_caps: list[EmbeddingModelCapabilities] = (
        [
            cap
            for cap in get_model_registry().list_embedding_models()
            if cap.name in {config.name for config in settings_map["dense"]}
        ]
        if settings_map["dense"]
        else []
    )
    sparse_caps: list[SparseEmbeddingModelCapabilities] = (
        [
            cap
            for cap in get_model_registry().list_sparse_embedding_models()
            if cap.name in {config.name for config in settings_map["sparse"]}
        ]
        if settings_map["sparse"]
        else []
    )
    if embedding_caps or sparse_caps:
        return {"dense": embedding_caps, "sparse": sparse_caps}
    raise RuntimeError(
        "No embedding model capabilities found in settings. We can't store vectors without embeddings."
    )


class VectorStoreProvider[VectorStoreClient](BasedModel, ABC):
    """Abstract interface for vector storage providers."""

    model_config = BasedModel.model_config | ConfigDict(extra="allow")

    _embedding_caps: dict[
        Literal["dense", "sparse"],
        list[EmbeddingModelCapabilities] | list[SparseEmbeddingModelCapabilities],
    ] = _assemble_caps()
    _client: VectorStoreClient | None
    _provider: Provider

    async def _initialize(self) -> None:
        """Initialize the vector store provider.

        This method should be called after creating an instance to perform
        any async initialization. Override in subclasses for custom initialization.
        """

    @abstractmethod
    @staticmethod
    def _ensure_client(client: Any) -> TypeIs[VectorStoreClient]:
        """Ensure the vector store client is initialized.

        Returns:
            bool: True if the client is initialized and ready.
        """

    @property
    def client(self) -> VectorStoreClient:
        """Returns the vector store client instance."""
        if not self._ensure_client(self._client):
            raise RuntimeError("Vector store client is not initialized.")
        return self._client

    @property
    def name(self) -> Provider:
        """
        The enum member representing the provider.
        """
        return self._provider

    @property
    @abstractmethod
    def base_url(self) -> str | None:
        """The base URL for the provider's API, if applicable.

        Returns:
            Valid HTTP/HTTPS URL or None.
        """
        return None

    @property
    def collection(self) -> str | None:
        """Name of the currently configured collection.

        Returns:
            Collection name (alphanumeric, underscores, hyphens; max 255 chars)
            or None if no collection configured.
        """
        return None

    @abstractmethod
    async def list_collections(self) -> list[str] | None:
        """List all collections in the vector store.

        Returns:
            List of collection names, or None if operation not supported.
            Returns empty list when no collections exist.

        Raises:
            ConnectionError: Failed to connect to vector store.
            ProviderError: Provider-specific operation failure.
        """

    @abstractmethod
    async def search(
        self, vector: list[float] | dict[str, list[float] | Any], query_filter: Filter | None = None
    ) -> list[SearchResult]:
        """Search for similar vectors using query vector(s).

        Supports both dense-only and hybrid search:
        - Dense only: Pass a list[float] for the query vector
        - Hybrid: Pass a dict with named vectors like {"dense": [...], "sparse": {...}}

        Args:
            vector: Query vector (single dense vector or dict of named vectors for hybrid search).
                For hybrid search, the dict can contain:
                - "dense": list[float] - Dense embedding vector
                - "sparse": dict with "indices" and "values" keys - Sparse embedding
            query_filter: Optional filter to apply to search results.
                Filter fields must exist in payload schema.

        Returns:
            List of search results sorted by relevance score (descending).
            Maximum 100 results returned per query.
            Each result includes score between 0.0 and 1.0.
            Returns empty list when no results match query/filter.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DimensionMismatchError: Query vector dimension doesn't match collection.
            InvalidFilterError: Filter contains invalid fields or values.
            SearchError: Search operation failed.
        """

    @abstractmethod
    async def upsert(self, chunks: list[CodeChunk]) -> None:
        """Insert or update code chunks with their embeddings.

        Args:
            chunks: List of code chunks to insert/update.
                - Each chunk must have unique chunk_id.
                - Each chunk must have at least one embedding (sparse or dense).
                - Embedding dimensions must match collection configuration.
                - Maximum 1000 chunks per batch.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DimensionMismatchError: Embedding dimension doesn't match collection.
            ValidationError: Chunk data validation failed.
            UpsertError: Upsert operation failed.

        Notes:
            - Existing chunks with same ID are replaced.
            - Payload indexes updated for new/modified chunks.
            - Operation is atomic (all-or-nothing for batch).
        """

    @abstractmethod
    async def delete_by_file(self, file_path: Path) -> None:
        """Delete all chunks for a specific file.

        Args:
            file_path: Path of file to remove from index.
                Must be relative path from project root.
                Use forward slashes for cross-platform compatibility.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DeleteError: Delete operation failed.

        Notes:
            - Idempotent: No error if file has no chunks.
            - Payload indexes updated to remove deleted chunks.
        """

    @abstractmethod
    async def delete_by_id(self, ids: list[UUID4]) -> None:
        """Delete specific code chunks by their unique identifiers.

        Args:
            ids: List of chunk IDs to delete.
                - Each ID must be valid UUID4.
                - Maximum 1000 IDs per batch.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DeleteError: Delete operation failed.

        Notes:
            - Idempotent: No error if some IDs don't exist.
            - Operation is atomic (all-or-nothing for batch).
        """

    @abstractmethod
    async def delete_by_name(self, names: list[str]) -> None:
        """Delete specific code chunks by their unique names.

        Args:
            names: List of chunk names to delete.
                - Each name must be non-empty string.
                - Maximum 1000 names per batch.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DeleteError: Delete operation failed.

        Notes:
            - Idempotent: No error if some names don't exist.
            - Operation is atomic (all-or-nothing for batch).
        """


__all__ = ("VectorStoreProvider",)
