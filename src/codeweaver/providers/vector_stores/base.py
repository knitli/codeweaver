# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Abstract provider interfaces for embeddings and vector storage."""

from __future__ import annotations

import logging
import threading
import time

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict

from pydantic import UUID4, ConfigDict
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
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


logger = logging.getLogger(__name__)


def _get_settings() -> DictView[CodeWeaverSettingsDict]:
    """Get global CodeWeaver settings.

    Returns:
        Global settings as a dictionary view.
    """
    from codeweaver.config.settings import get_settings_map

    return get_settings_map()


class EmbeddingCapsDict(TypedDict):
    dense: tuple[EmbeddingModelCapabilities]
    sparse: tuple[SparseEmbeddingModelCapabilities]


def _assemble_caps() -> EmbeddingCapsDict | None:
    """Assemble embedding model capabilities from settings.

    Returns:
        EmbeddingModelCapabilities instance or None if not configured.
    """


# Lock for thread-safe initialization of class-level embedding capabilities
_embedding_caps_lock = threading.Lock()


class CircuitBreakerState(Enum):
    """Circuit breaker states for provider resilience."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""


class VectorStoreProvider[VectorStoreClient](BasedModel, ABC):
    """Abstract interface for vector storage providers."""

    model_config = BasedModel.model_config | ConfigDict(extra="allow")

    config: Any = None  # Provider-specific configuration object
    _client: VectorStoreClient | None
    _embedding_caps: EmbeddingCapsDict | None = None

    _provider: ClassVar[Provider] = Provider.NOT_SET

    # Circuit breaker state tracking
    _circuit_state: CircuitBreakerState = CircuitBreakerState.CLOSED
    _failure_count: int = 0
    _last_failure_time: float | None = None
    _circuit_open_duration: float = 30.0  # seconds

    def __init__(
        self,
        config: Any = None,
        client: VectorStoreClient | None = None,
        embedding_caps: EmbeddingCapsDict | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the vector store provider with embedding capabilities."""
        # Pass parameters to Pydantic's __init__
        init_data: dict[str, Any] = {**kwargs}
        if config is not None:
            init_data["config"] = config
        if client is not None:
            init_data["_client"] = client
        if embedding_caps is not None:
            init_data["_embedding_caps"] = embedding_caps
        super().__init__(**init_data)
        # Initialize embedding caps on first instance creation if not already set at class level
        # Use double-checked locking pattern for thread safety
        if not hasattr(type(self), "_embedding_caps_initialized"):
            with _embedding_caps_lock:
                # Double-check after acquiring lock to avoid race condition
                if not hasattr(type(self), "_embedding_caps_initialized"):
                    type(self)._embedding_caps = _assemble_caps()
                    type(self)._embedding_caps_initialized = True

        # Initialize circuit breaker state
        self._circuit_state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    async def _initialize(self) -> None:
        """Initialize the vector store provider.

        This method should be called after creating an instance to perform
        any async initialization. Override in subclasses for custom initialization.
        """

    @staticmethod
    @abstractmethod
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

    def _check_circuit_breaker(self) -> None:
        """Check circuit breaker state before making API calls.

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open.
        """
        current_time = time.time()

        if self._circuit_state == CircuitBreakerState.OPEN:
            if (
                self._last_failure_time
                and (current_time - self._last_failure_time) > self._circuit_open_duration
            ):
                # Transition to half-open to test recovery
                import logging

                logger = logging.getLogger(__name__)
                logger.info(
                    "Circuit breaker transitioning to half-open state for %s", self._provider
                )
                self._circuit_state = CircuitBreakerState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open for {self._provider}. Failing fast."
                )

    def _record_success(self) -> None:
        """Record successful API call and reset circuit breaker if needed."""
        if self._circuit_state in (CircuitBreakerState.HALF_OPEN, CircuitBreakerState.OPEN):
            import logging

            logger = logging.getLogger(__name__)
            logger.info("Circuit breaker closing for %s after successful operation", self._provider)
        self._circuit_state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    def _record_failure(self) -> None:
        """Record failed API call and update circuit breaker state."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= 3:  # 3 failures threshold as per spec FR-008a
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "Circuit breaker opening for %s after %d consecutive failures",
                self._provider,
                self._failure_count,
            )
            self._circuit_state = CircuitBreakerState.OPEN

    @property
    def circuit_breaker_state(self) -> str:
        """Get current circuit breaker state for health monitoring."""
        return self._circuit_state.value

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

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=16),  # 1s, 2s, 4s, 8s, 16s
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    async def _search_with_retry(
        self, vector: list[float] | dict[str, list[float] | Any], query_filter: Filter | None = None
    ) -> list[SearchResult]:
        """Wrapper around search with retry logic and circuit breaker."""
        self._check_circuit_breaker()

        try:
            result = await self.search(vector, query_filter)
            self._record_success()
        except (ConnectionError, TimeoutError, OSError) as e:
            self._record_failure()
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "Vector store search failed for %s: %s (attempt %d/5)",
                self._provider,
                str(e),
                self._failure_count,
            )
            raise
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Non-retryable error in vector store search: %s", str(e))
            raise
        else:
            return result

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

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    async def _upsert_with_retry(self, chunks: list[CodeChunk]) -> None:
        """Wrapper around upsert with retry logic and circuit breaker."""
        self._check_circuit_breaker()

        try:
            await self.upsert(chunks)
            self._record_success()
        except (ConnectionError, TimeoutError, OSError) as e:
            self._record_failure()
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "Vector store upsert failed for %s: %s (attempt %d/5)",
                self._provider,
                str(e),
                self._failure_count,
            )
            raise
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Non-retryable error in vector store upsert: %s", str(e))
            raise

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

    def _telemetry_keys(self) -> None:
        return None


__all__ = ("VectorStoreProvider",)
