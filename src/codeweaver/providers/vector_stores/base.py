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
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypedDict, cast, overload

from pydantic import UUID7, ConfigDict, PrivateAttr
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from typing_extensions import TypeIs

from codeweaver.agent_api.find_code.types import StrategizedQuery
from codeweaver.config.providers import EmbeddingModelSettings, SparseEmbeddingModelSettings
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.types.models import BasedModel
from codeweaver.engine.search import Filter
from codeweaver.exceptions import ProviderError
from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    SparseEmbeddingModelCapabilities,
)
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.agent_api.find_code.results import SearchResult


logger = logging.getLogger(__name__)

type MixedQueryInput = (
    list[float] | list[int] | dict[Literal["dense", "sparse"], list[float] | list[int] | Any]
)


class EmbeddingCapsDict(TypedDict):
    dense: EmbeddingModelCapabilities | None
    sparse: SparseEmbeddingModelCapabilities | None
    backup_dense: EmbeddingModelCapabilities | None
    backup_sparse: SparseEmbeddingModelCapabilities | None


class EmbeddingSettingsDict(TypedDict):
    dense: EmbeddingModelSettings | None
    sparse: SparseEmbeddingModelSettings | None
    backup_dense: EmbeddingModelSettings | None
    backup_sparse: SparseEmbeddingModelSettings | None


# Lock for thread-safe initialization of class-level embedding capabilities
_embedding_caps_lock = threading.Lock()


class CircuitBreakerState(Enum):
    """Circuit breaker states for provider resilience."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""


@overload
def _get_caps(
    *, sparse: Literal[False] = False, backup: bool = False
) -> EmbeddingModelCapabilities | None: ...
@overload
def _get_caps(
    *, sparse: Literal[True], backup: bool = False
) -> SparseEmbeddingModelCapabilities | None: ...
def _get_caps(
    *, sparse: bool = False, backup: bool = False
) -> EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities | None:
    """Get embedding capabilities for in-memory provider.

    Args:
        sparse: Whether to get sparse embedding capabilities.

    Returns:
        Embedding capabilities or None.
    """
    from codeweaver.common.registry import get_model_registry
    from codeweaver.core.types import Unset

    registry = get_model_registry()
    if backup:
        from codeweaver.config.profiles import get_profile

        profile = get_profile("backup", "local")
        if not profile:
            return None
        if (
            sparse
            and (sparse_profile := profile["sparse_embedding"])
            and (
                sparse_settings := sparse_profile[0]
                if isinstance(sparse_profile, tuple) and len(sparse_profile) > 0
                else None
                if isinstance(sparse_profile, Unset)
                else sparse_profile
            )
            and (
                sparse_model := registry.get_embedding_capabilities(
                    provider=sparse_settings["provider"],
                    name=sparse_settings["model_settings"]["model"],
                )
            )
        ):  # type: ignore
            return sparse_model  # type: ignore
        if (
            (dense_profile := profile["embedding"])
            and (
                dense_settings := dense_profile[0]
                if isinstance(dense_profile, tuple) and len(dense_profile) > 0
                else None
                if isinstance(dense_profile, Unset)
                else dense_profile
            )
            and (
                dense_model := registry.get_embedding_capabilities(
                    provider=dense_settings["provider"],
                    name=dense_settings["model_settings"]["model"],
                )
            )
        ):  # type: ignore
            return dense_model  # type: ignore
    if sparse and (sparse_settings := registry.configured_models_for_kind(kind="sparse_embedding")):
        return sparse_settings[0] if isinstance(sparse_settings, tuple) else sparse_settings  # type: ignore
    if not sparse and (dense_settings := registry.configured_models_for_kind(kind="embedding")):
        return dense_settings[0] if isinstance(dense_settings, tuple) else dense_settings  # type: ignore
    return None


def _get_embedding_settings() -> EmbeddingSettingsDict:
    """Get embedding model settings for in-memory provider.

    Returns:
        Embedding model settings dictionary.
    """
    from codeweaver.common.registry.provider import get_provider_registry
    from codeweaver.config.profiles import get_profile

    profile = get_profile("backup", "local")
    registry = get_provider_registry()
    dense = registry.get_configured_provider_settings("embedding")
    sparse = registry.get_configured_provider_settings("sparse_embedding")
    return EmbeddingSettingsDict(
        dense=dense.get("model_settings") if dense else None,
        sparse=sparse.get("model_settings") if sparse else None,
        backup_dense=profile["embedding"][0]["model_settings"]
        if profile
        and profile["embedding"]
        and isinstance(profile["embedding"], tuple)
        and len(profile["embedding"]) > 0
        else None,
        backup_sparse=profile["sparse_embedding"][0]["model_settings"]
        if profile
        and profile["sparse_embedding"]
        and isinstance(profile["sparse_embedding"], tuple)
        and len(profile["sparse_embedding"]) > 0
        else None,
    )


def _default_embedding_caps() -> EmbeddingCapsDict:
    """Default factory for embedding capabilities. Evaluated lazily at instance creation."""
    return EmbeddingCapsDict(
        dense=_get_caps(),
        sparse=_get_caps(sparse=True),
        backup_dense=_get_caps(backup=True),
        backup_sparse=_get_caps(sparse=True, backup=True),
    )


class VectorStoreProvider[VectorStoreClient](BasedModel, ABC):
    """Abstract interface for vector storage providers."""

    model_config = BasedModel.model_config | ConfigDict(extra="allow")

    config: Any = None  # Provider-specific configuration object
    _client: VectorStoreClient | None
    _embedding_caps: EmbeddingCapsDict = PrivateAttr(default_factory=_default_embedding_caps)
    _settings: EmbeddingSettingsDict = PrivateAttr(default_factory=_get_embedding_settings)

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
        # Note: Don't pass _embedding_caps here - PrivateAttr with default_factory
        # will always call the factory. Set it after super().__init__() instead.

        super().__init__(**init_data)

        # Override _embedding_caps if explicitly provided (after super().__init__)
        # This is required because PrivateAttr with default_factory always calls the factory
        if embedding_caps is not None:
            object.__setattr__(self, "_embedding_caps", embedding_caps)

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
            raise ProviderError(
                "Vector store client not initialized",
                details={
                    "provider": type(self)._provider.value
                    if hasattr(self, "_provider")
                    else "unknown",
                    "client_type": type(self).__name__,
                },
                suggestions=[
                    "Ensure initialize() method was called before use",
                    "Check vector store configuration is valid",
                    "Verify required dependencies are installed",
                ],
            )
        return self._client

    @property
    def name(self) -> Provider:
        """
        The enum member representing the provider.
        """
        return type(self)._provider

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

    @property
    def embedding_capabilities(self) -> EmbeddingCapsDict:
        """Get the embedding capabilities for this vector store provider.

        Returns:
            Embedding capabilities dictionary with 'dense' and 'sparse' keys.
        """
        return self._embedding_caps

    @property
    def embedding_settings(self) -> EmbeddingSettingsDict:
        """Get the embedding model settings for this vector store provider.

        Returns:
            Embedding model settings dictionary with 'dense' and 'sparse' keys.
        """
        return self._settings

    @property
    def dense_dimension(self) -> int | None:
        """Get the dimension of dense embeddings for this vector store provider.

        Returns:
            Dimension of dense embeddings, or None if dense embeddings not supported.
        """
        dense_caps = self.embedding_capabilities.get("dense")
        default_dim = dense_caps.default_dimension if dense_caps else None

        dense_settings = self.embedding_settings.get("dense")
        set_dim = dense_settings.get("dimension") if dense_settings else None

        return set_dim or default_dim

    @property
    def dense_dtype(self) -> Literal["float32", "float16", "int8", "binary"]:
        """Get the data type of dense embeddings for this vector store provider.

        Returns:
            Data type of dense embeddings.
        """
        dense_caps = self.embedding_capabilities.get("dense")
        default_dtype = dense_caps.default_dtype if dense_caps else "float16"

        dense_settings = self.embedding_settings.get("dense")
        set_dtype = dense_settings.get("data_type") if dense_settings else None

        return cast(Literal["float32", "float16", "int8", "binary"], set_dtype or default_dtype)

    @property
    def distance_metric(self) -> Literal["cosine", "dot", "euclidean"]:
        """Get the distance metric used for similarity search.

        Returns:
            Distance metric as a string.
        """
        dense_caps = self.embedding_capabilities.get("dense")
        if dense_caps and dense_caps.preferred_metrics:
            return dense_caps.preferred_metrics[0]
        return "cosine"

    @property
    def dense_model(self) -> str | None:
        """Get the name of the dense embedding model.

        Returns:
            Dense model name, or None if not configured.
        """
        dense_caps = self.embedding_capabilities.get("dense")
        return dense_caps.name if dense_caps else None

    @property
    def sparse_model(self) -> str | None:
        """Get the name of the sparse embedding model.

        Returns:
            Sparse model name, or None if not configured.
        """
        sparse_caps = self.embedding_capabilities.get("sparse")
        return sparse_caps.name if sparse_caps else None

    @property
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
                    "Circuit breaker transitioning to half-open state for %s", type(self)._provider
                )
                self._circuit_state = CircuitBreakerState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open for {type(self)._provider}. Failing fast."
                )

    def _record_success(self) -> None:
        """Record successful API call and reset circuit breaker if needed."""
        if self._circuit_state in (CircuitBreakerState.HALF_OPEN, CircuitBreakerState.OPEN):
            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                "Circuit breaker closing for %s after successful operation", type(self)._provider
            )
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
                type(self)._provider,
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
        self,
        vector: StrategizedQuery | MixedQueryInput,
        query_filter: Filter | None = None,
        context: Any = None,
    ) -> list[SearchResult]:
        """Wrapper around search with retry logic and circuit breaker."""
        from codeweaver.common.logging import log_to_client_or_fallback

        _ = self._check_circuit_breaker

        try:
            result = await self.search(vector, query_filter)
            self._record_success()

            await log_to_client_or_fallback(
                context,
                "debug",
                {
                    "msg": "Vector store search successful",
                    "extra": {"provider": type(self)._provider.value, "results_count": len(result)},
                },
            )
        except (ConnectionError, TimeoutError, OSError) as e:
            self._record_failure()

            await log_to_client_or_fallback(
                context,
                "warning",
                {
                    "msg": "Vector store search failed",
                    "extra": {
                        "provider": type(self)._provider.value,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "attempt": self._failure_count,
                        "max_attempts": 5,
                    },
                },
            )
            raise
        except Exception as e:
            await log_to_client_or_fallback(
                context,
                "error",
                {
                    "msg": "Non-retryable error in vector store search",
                    "extra": {
                        "provider": type(self)._provider.value,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                },
            )
            raise
        else:
            return result

    @abstractmethod
    async def search(
        self, vector: StrategizedQuery | MixedQueryInput, query_filter: Filter | None = None
    ) -> list[SearchResult]:
        """Search for similar vectors using query vector(s).

        Supports both dense-only and hybrid search.

        Args:
            vector: Preferred input is a StrategizedQuery object containing:
                - query: Original query string (for logging/metadata/tracking)
                - dense: Dense embedding vector (list of floats or ints) or None
                - sparse: Sparse embedding vector (list of floats/ints) or None
                - strategy: Search strategy to use (DENSE_ONLY, SPARSE_ONLY, HYBRID_SEARCH)

                Alternatively, a MixedQueryInput can be provided (will be deprecated), which is any of:
                - For dense-only: list of floats or ints
                - For sparse-only: list of floats or ints
                - For hybrid: dict with keys "dense" and "sparse" mapping to respective vectors

            query_filter: Optional filter to apply to search results.

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
    async def _upsert_with_retry(
        self, chunks: list[CodeChunk], context: Any = None, *, for_backup: bool = False
    ) -> None:
        """Wrapper around upsert with retry logic and circuit breaker."""
        from codeweaver.common.logging import log_to_client_or_fallback

        _ = self._check_circuit_breaker

        await log_to_client_or_fallback(
            context,
            "debug",
            {
                "msg": "Starting vector store upsert",
                "extra": {"provider": type(self)._provider.value, "chunks_count": len(chunks)},
            },
        )

        try:
            await self.upsert(chunks, for_backup=for_backup)
            self._record_success()

            await log_to_client_or_fallback(
                context,
                "debug",
                {
                    "msg": "Vector store upsert successful",
                    "extra": {"provider": type(self)._provider.value, "chunks_count": len(chunks)},
                },
            )
        except (ConnectionError, TimeoutError, OSError) as e:
            self._record_failure()

            await log_to_client_or_fallback(
                context,
                "warning",
                {
                    "msg": "Vector store upsert failed",
                    "extra": {
                        "provider": type(self)._provider.value,
                        "chunks_count": len(chunks),
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "attempt": self._failure_count,
                        "max_attempts": 5,
                    },
                },
            )
            raise
        except Exception as e:
            await log_to_client_or_fallback(
                context,
                "error",
                {
                    "msg": "Non-retryable error in vector store upsert",
                    "extra": {
                        "provider": type(self)._provider.value,
                        "chunks_count": len(chunks),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                },
            )
            raise

    @abstractmethod
    async def upsert(self, chunks: list[CodeChunk], *, for_backup: bool = False) -> None:
        """Insert or update code chunks with their embeddings.

        Args:
            chunks: List of code chunks to insert/update.
                - Each chunk must have unique chunk_id.
                - Each chunk must have at least one embedding (sparse or dense).
                - Embedding dimensions must match collection configuration.
                - Maximum 1000 chunks per batch.
            for_backup: Whether these chunks are being upserted as part of a backup process.

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
    async def delete_by_id(self, ids: list[UUID7]) -> None:
        """Delete specific code chunks by their unique identifiers.

        Args:
            ids: List of chunk IDs to delete.
                - Each ID must be valid UUID7.
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
