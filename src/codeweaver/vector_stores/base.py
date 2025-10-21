# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Abstract provider interfaces for embeddings and vector storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import UUID4, ConfigDict

from codeweaver._data_structures import CodeChunk, SearchResult
from codeweaver._types import BasedModel
from codeweaver.provider import Provider
from codeweaver.services._filter import Filter


class VectorStoreProvider[VectorStoreClient](BasedModel, ABC):
    """Abstract interface for vector storage providers."""

    model_config = BasedModel.model_config | ConfigDict(extra="allow")

    _client: VectorStoreClient
    _provider: Provider

    def __init__(self, client: Any = None, **kwargs: Any) -> None:
        """Initialize the vector store provider."""
        self._client = client
        self.kwargs = kwargs
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the vector store provider."""

    @property
    def client(self) -> VectorStoreClient:
        """Returns the vector store client instance."""
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
        """
        The base URL for the provider's API, if applicable.
        """
        return None

    @property
    def collection(self) -> str | None:
        """Get the name of the currently configured collection."""
        return None

    @abstractmethod
    def list_collections(self) -> list[str] | None:
        """List all collections in the vector store.

        Returns:
            List of collection names
        """

    @abstractmethod
    async def search(
        self, vector: list[float], query_filter: Filter | None = None
    ) -> list[SearchResult]:
        """Search for similar vectors.

        Args:
            vector: Query vector
            query_filter: Filter to apply to the search

        Returns:
            List of search results
        """

    @abstractmethod
    async def upsert(self, chunks: list[CodeChunk]) -> None:
        """Insert or update code chunks in the vector store.

        Args:
            chunks: List of code chunks to store
        """

    @abstractmethod
    async def delete_by_file(self, file_path: Path) -> None:
        """Delete all chunks for a specific file.

        Args:
            file_path: Path of file to remove from index
        """

    @abstractmethod
    async def delete_by_id(self, ids: list[UUID4]) -> None:
        """
        Delete a specific code chunk by its unique identifier (the `chunk_id` field).
        """

    @abstractmethod
    async def delete_by_name(self, names: list[str]) -> None:
        """
        Delete specific code chunks by their unique names.
        """


__all__ = ("VectorStoreProvider",)
