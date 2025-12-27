# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Base class for embedding providers."""

from __future__ import annotations

import asyncio
import logging
import time

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Mapping, Sequence
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Literal,
    NotRequired,
    Required,
    TypedDict,
    cast,
    overload,
    override,
)
from uuid import UUID

from codeweaver_tokenizers import Tokenizer, get_tokenizer
from pydantic import UUID7, ConfigDict, Field, SkipValidation
from pydantic.main import IncEx
from pydantic.types import PositiveInt
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from codeweaver.config.providers import EmbeddingModelSettings, SparseEmbeddingModelSettings
from codeweaver.core import (
    AnonymityConversion,
    BasedModel,
    BaseEnum,
    BlakeStore,
    LazyImport,
    Provider,
    UUIDStore,
    lazy_import,
    make_blake_store,
    make_uuid_store,
    uuid7,
)
from codeweaver.exceptions import ProviderError
from codeweaver.exceptions import ValidationError as CodeWeaverValidationError
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.registry import EmbeddingRegistry
from codeweaver.providers.embedding.types import SparseEmbedding


statistics_module: LazyImport[ModuleType] = lazy_import("codeweaver.common.statistics")

if TYPE_CHECKING:
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.core.chunks import CodeChunk, SerializedStrOnlyCodeChunk, StructuredDataInput
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT


_get_statistics: LazyImport[SessionStatistics] = lazy_import(
    "codeweaver.common.statistics", "get_session_statistics"
)

logger = logging.getLogger(__name__)


class CircuitBreakerState(BaseEnum):
    """Circuit breaker states for provider resilience."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""


def _get_registry() -> EmbeddingRegistry:
    from codeweaver.providers.embedding.registry import get_embedding_registry

    return get_embedding_registry()


class EmbeddingErrorInfo(TypedDict):
    """Information about an embedding error and the embedding batch.

    If the error occurs during a document embedding request, `EmbeddingErrorInfo` will have the `documents` and (usually) the `batch_id` fields populated. These fields aren't present for query embedding requests.
    For a query `EmbeddingErrorInfo`, only the `error` and `queries` fields are populated.
    """

    error: Required[str]
    batch_id: NotRequired[UUID7 | None]
    documents: NotRequired[Sequence[CodeChunk] | None]
    queries: NotRequired[Sequence[str] | None]


def default_input_transformer(chunks: StructuredDataInput) -> Iterator[CodeChunk]:
    """Default input transformer that serializes CodeChunks to strings."""
    from codeweaver.core.chunks import CodeChunk

    return CodeChunk.chunkify(chunks)


def default_output_transformer(output: Any) -> list[list[float]] | list[list[int]]:
    """Default output transformer that ensures the output is in the correct format."""
    if isinstance(output, list | tuple | set) and (
        all(isinstance(i, list | set | tuple) for i in output)  # type: ignore
        or (needs_wrapper := all(isinstance(i, int | float) for i in output))  # type: ignore
    ):
        return [output] if needs_wrapper else list(output)  # type: ignore
    logger.error(
        ("Received unexpected output format from embedding provider."),
        extra={"output_data": output},
    )
    raise ProviderError(
        "Embedding provider returned unexpected output format",
        details={
            "output_type": type(output).__name__,
            "output_preview": str(output)[:200] if output else None,
        },
        suggestions=[
            "Check that the provider's response format matches expectations",
            "Verify the provider's API has not changed",
            "Review provider documentation for output format",
        ],
    )


class EmbeddingProvider[EmbeddingClient](BasedModel, ABC):
    """
    Abstract class for an embedding provider. You must pass in a client and capabilities.

    This class mirrors `pydantic_ai.providers.Provider` class to make it simple to use
    existing implementations of `pydantic_ai.providers.Provider` as embedding providers.

    We chose to separate this from the `pydantic_ai.providers.Provider` class for clarity. That class is re-exported in `codeweaver.providers.agent` package as `AgentProvider`, which is used for agent operations.
    We didn't want folks accidentally conflating agent operations with embedding operations. That's kind of a 'dogs and cats living together' 🐕🐈 situation.

    We don't think many or possibly any of the pydantic-ai providers can be used directly as embedding providers -- the endpoints and request/response formats are often different.
    Each provider only supports a specific interface, but an interface can be used by multiple providers.

    The primary example of this one-to-many relationship is the OpenAI provider, which supports any OpenAI-compatible provider (Azure, Ollama, Fireworks, Heroku, Together, Github).
    """

    from codeweaver.core.chunks import StructuredDataInput

    model_config = BasedModel.model_config | ConfigDict(extra="allow", arbitrary_types_allowed=True)

    client: Annotated[
        SkipValidation[EmbeddingClient],
        Field(
            description="The client for the embedding provider.",
            exclude=True,
            validation_alias="_client",
        ),
    ]
    caps: Annotated[
        EmbeddingModelCapabilities,
        Field(description="The capabilities of the embedding model.", validation_alias="_caps"),
    ]
    _provider: ClassVar[Provider] = Provider.NOT_SET
    _input_transformer: ClassVar[Callable[[StructuredDataInput], Any]] = default_input_transformer
    _output_transformer: ClassVar[Callable[[Any], list[list[float]] | list[list[int]]]] = (
        default_output_transformer
    )
    _doc_kwargs: ClassVar[dict[str, Any]] = {}
    _query_kwargs: ClassVar[dict[str, Any]] = {}

    # Typing note: we can't type this properly because: 1) Pyright wants us to define the subtype for `list` and 2) pydantic does not support parameterized subtypes for generics.
    _store: ClassVar[UUIDStore[list]] = make_uuid_store(  # type: ignore
        value_type=list, size_limit=1024 * 1024 * 3
    )
    """The store for embedding documents, keyed by batch ID (UUID7) and stored as a batch of CodeChunks."""

    _backup_store: ClassVar[UUIDStore[list]] = make_uuid_store(
        value_type=list, size_limit=1024 * 1024
    )
    """A smaller backup store for mapping batch IDs *for codeweaver's failsafe mechanism* to the batch ID of code chunks."""

    _hash_store: ClassVar[BlakeStore[UUID7]] = make_blake_store(
        value_type=UUID, size_limit=1024 * 256
    )  # 256kb limit -- we're just storing hashes
    """A store for deduplicating CodeChunks based on their content hash. The keys are each CodeChunk's content hash, the values are their batch IDs.

    Note that we're only storing the hash keys and batch ID values, not the full CodeChunk objects. This keeps the store size small. We can lookup by batch ID in the main `_store` if needed, or if it has been ejected, in the `_store`'s `_trash_heap`. `SimpleTypedStore`, the parent class, handles that for us with a simple "get" method.
    """
    _backup_hash_store: ClassVar[BlakeStore[UUID7]] = make_blake_store(
        value_type=UUID, size_limit=1024 * 128
    )  # 128kb limit -- we're just storing hashes
    """A backup store for deduplicating CodeChunks based on their content hash. The keys are each CodeChunk's content hash, the values are their backup batch IDs.
    """
    # Circuit breaker state tracking
    _circuit_state: CircuitBreakerState = CircuitBreakerState.CLOSED
    _failure_count: int = 0
    _last_failure_time: float | None = None
    _circuit_open_duration: float = 30.0  # 30 seconds

    def __init__(
        self,
        client: EmbeddingClient,
        caps: EmbeddingModelCapabilities,
        kwargs: dict[str, Any] | None,
    ) -> None:
        """Initialize the embedding provider."""
        # Determine provider - check if subclass has it set
        getattr(type(self), "_provider", None) or caps.provider

        # Store values we'll need after super().__init__()
        _doc_kwargs = type(self)._doc_kwargs.copy() or {}
        _query_kwargs = type(self)._query_kwargs.copy() or {}
        _user_kwargs = kwargs or {}

        # Use object.__setattr__ to bypass Pydantic's validation for pre-super() initialization
        object.__setattr__(self, "_model_dump_json", super().model_dump_json)

        # Initialize circuit breaker state using object.__setattr__
        object.__setattr__(self, "_circuit_state", CircuitBreakerState.CLOSED)
        object.__setattr__(self, "_failure_count", 0)
        object.__setattr__(self, "_last_failure_time", None)

        # Initialize pydantic model BEFORE calling _initialize since _initialize may set PrivateAttr fields
        super().__init__(client=client, caps=caps)

        # Now that Pydantic is initialized, set kwargs as normal attributes (will go to __pydantic_extra__)
        self.doc_kwargs = {**_doc_kwargs, **_user_kwargs}
        self.query_kwargs = {**_query_kwargs, **_user_kwargs}

        # Call _initialize after super().__init__() so Pydantic private attributes are set up
        self._initialize(caps)

    def _add_kwargs(self, kwargs: dict[str, Any]) -> None:
        """Add keyword arguments to the embedding provider."""
        if not kwargs:
            return
        # Access attributes directly from __dict__ to avoid Pydantic validation during initialization
        doc_kwargs = self.__dict__.get("doc_kwargs", {})
        query_kwargs = self.__dict__.get("query_kwargs", {})
        object.__setattr__(self, "doc_kwargs", {**doc_kwargs, **kwargs})
        object.__setattr__(self, "query_kwargs", {**query_kwargs, **kwargs})

    @abstractmethod
    def _initialize(self, caps: EmbeddingModelCapabilities) -> None:
        """Initialize the embedding provider.

        This method is called at the end of __init__ to allow for any additional setup.
        It should minimally set up `doc_kwargs` and `query_kwargs` if they are not already set.

        Args:
            caps: The embedding model capabilities (passed since pydantic may not have set _caps yet).
        """

    @classmethod
    def clear_deduplication_stores(cls) -> None:
        """Clear class-level deduplication stores.

        This is primarily useful for testing to ensure clean state between test runs.
        """
        cls._store = make_uuid_store(value_type=list, size_limit=1024 * 1024 * 3)
        cls._backup_store = make_uuid_store(value_type=list, size_limit=1024 * 1024)
        cls._hash_store = make_blake_store(value_type=UUID, size_limit=1024 * 256)
        cls._backup_hash_store = make_blake_store(value_type=UUID, size_limit=1024 * 128)

    async def initialize_async(self) -> None:
        """Perform asynchronous initialization of the provider.

        Subclasses should override this method to perform any async setup,
        such as loading models or establishing connections, that should
        not block the event loop during provider creation.
        """
        # Default implementation does nothing
        return

    @property
    def name(self) -> Provider:
        """Get the name of the embedding provider."""
        return type(self)._provider

    @property
    @abstractmethod
    def base_url(self) -> str | None:
        """Get the base URL of the embedding provider, if any."""

    def _split_by_tokens(
        self, chunks: Sequence[CodeChunk], max_tokens: int | None = None
    ) -> list[list[CodeChunk]]:
        """Split chunks into batches that respect token limits.

        Args:
            chunks: Sequence of chunks to split
            max_tokens: Maximum tokens per batch (default: model's max_batch_tokens)

        Returns:
            List of chunk batches, each within the token limit
        """
        if not chunks:
            return []

        max_tokens = max_tokens or self.caps.max_batch_tokens
        # Apply 85% safety margin to account for tokenizer estimation variance
        # This prevents edge cases where our token estimate slightly underestimates
        # the provider's actual token count, which would cause API errors
        effective_limit = int(max_tokens * 0.85)
        tokenizer = self.tokenizer

        if effective_limit != max_tokens:
            logger.debug(
                "Using conservative token limit %d (85%% of %d) to prevent estimation errors",
                effective_limit,
                max_tokens,
            )

        batches: list[list[CodeChunk]] = []
        current_batch: list[CodeChunk] = []
        current_tokens = 0

        for chunk in chunks:
            # Estimate tokens for this chunk
            chunk_text = chunk.content
            chunk_tokens = tokenizer.estimate(chunk_text)

            # If single chunk exceeds limit, log warning and include it anyway
            # (the API will handle the error, but we shouldn't silently drop it)
            if chunk_tokens > effective_limit:
                logger.warning(
                    "Single chunk exceeds effective batch token limit (%d > %d), including anyway",
                    chunk_tokens,
                    effective_limit,
                )
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
                batches.append([chunk])
                continue

            # If adding this chunk would exceed limit, start new batch
            if current_tokens + chunk_tokens > effective_limit and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

            current_batch.append(chunk)
            current_tokens += chunk_tokens

        # Don't forget the last batch
        if current_batch:
            batches.append(current_batch)

        if len(batches) > 1:
            logger.debug(
                "Split %d chunks into %d token-aware batches (effective limit %d tokens/batch)",
                len(chunks),
                len(batches),
                effective_limit,
            )

        return batches

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

        if self._failure_count >= 3:  # 3 failures threshold
            logger.warning(
                "Circuit breaker opening for %s after %d consecutive failures",
                type(self)._provider,
                self._failure_count,
            )
            self._circuit_state = CircuitBreakerState.OPEN

    @property
    def circuit_breaker_state(self) -> str:
        """Get current circuit breaker state for health monitoring."""
        return self._circuit_state.variable

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(
            multiplier=1, min=1, max=16
        ),  # 1s, 2s, 4s, 8s, 16s as per spec FR-009c
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    async def _embed_documents_with_retry(
        self, documents: Sequence[CodeChunk], *, for_backup: bool = False, **kwargs: Any
    ) -> Sequence[Sequence[float]] | Sequence[Sequence[int]] | dict[str, list[int] | list[float]]:
        """Wrapper around _embed_documents with retry logic and circuit breaker.

        Applies exponential backoff (1s, 2s, 4s, 8s, 16s) and circuit breaker pattern.
        """
        self._check_circuit_breaker()

        try:
            result = await self._embed_documents(documents, **kwargs)
            self._record_success()
        except (ConnectionError, TimeoutError, OSError) as e:
            self._record_failure()
            logger.warning(
                "API call failed for %s: %s (attempt %d/5)",
                type(self)._provider,
                str(e),
                self._failure_count,
            )
            raise
        except Exception:
            # Non-retryable errors don't affect circuit breaker
            logger.warning("Non-retryable error in embedding", exc_info=True)
            raise
        else:
            return result  # ty: ignore[invalid-return-type]

    @abstractmethod
    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]] | list[dict[str, list[int] | list[float]]]:
        """Abstract method to implement document embedding logic."""

    def _handle_embedding_error(
        self,
        error: Exception,
        batch_id: UUID7 | None,
        documents: Sequence[CodeChunk] | None,
        queries: Sequence[str] | None,
    ) -> EmbeddingErrorInfo:
        """Handle errors that occur during embedding."""
        logger.warning(
            "Error occurred during document embedding. Batch ID: %s failed during `embed_documents`: %s (%s)",
            batch_id,
            str(error),
            type(error).__name__,
            extra={"documents": documents, "batch_id": batch_id},
        )
        if queries:
            return EmbeddingErrorInfo(error=str(error), queries=queries)
        return EmbeddingErrorInfo(error=str(error), batch_id=batch_id, documents=documents)

    async def embed_documents(  # noqa: C901
        self,
        documents: Sequence[CodeChunk],  # type: ignore # intentionally obscurred
        *,
        batch_id: UUID7 | None = None,
        for_backup: bool = False,
        skip_deduplication: bool = False,
        context: Any = None,
        **kwargs: Any,
    ) -> list[list[float]] | list[list[int]] | list[SparseEmbedding] | EmbeddingErrorInfo:
        """Embed a list of documents into vectors.

        Optionally takes a `batch_id` parameter to reprocess a specific batch of documents.
        """
        from codeweaver.common._logging import log_to_client_or_fallback

        is_old_batch = False
        if (batch_id and self._store and batch_id in self._store and not for_backup) or (
            batch_id and for_backup and self._backup_store and batch_id in self._backup_store
        ):
            documents: Sequence[CodeChunk] = (
                self._backup_store[batch_id] if for_backup else self._store[batch_id]
            )  # type: ignore
            is_old_batch = True
        chunks_iter, cache_key = self._process_input(
            documents,
            is_old_batch=is_old_batch,
            for_backup=for_backup,
            skip_deduplication=skip_deduplication,
        )  # type: ignore

        # Convert iterator to tuple once to avoid exhaustion issues
        chunks = tuple(chunks_iter)

        # Early return if no chunks to embed (all filtered as duplicates)
        if not chunks:
            await log_to_client_or_fallback(
                context,
                "debug",
                {
                    "msg": "No chunks to embed after deduplication",
                    "extra": {
                        "provider": type(self)._provider.variable,
                        "document_count": len(documents),
                        "is_reprocessing": is_old_batch,
                        "batch_id": str(batch_id or cache_key) if batch_id or cache_key else None,
                    },
                },
            )
            return []

        await log_to_client_or_fallback(
            context,
            "debug",
            {
                "msg": "Starting document embedding",
                "extra": {
                    "provider": type(self)._provider.variable,
                    "document_count": len(documents),
                    "chunk_count": len(chunks),
                    "is_reprocessing": is_old_batch,
                    "batch_id": str(batch_id or cache_key) if batch_id or cache_key else None,
                },
            },
        )

        try:
            # Split chunks into token-aware batches to avoid exceeding API limits
            token_batches = self._split_by_tokens(chunks)

            all_results: list[
                Sequence[float] | Sequence[int] | dict[str, list[int] | list[float]]
            ] = []

            # Yield after CPU-bound token batching to prevent event loop blocking
            await asyncio.sleep(0)

            for batch_idx, token_batch in enumerate(token_batches):
                if len(token_batches) > 1:
                    logger.debug(
                        "Processing token batch %d/%d (%d chunks)",
                        batch_idx + 1,
                        len(token_batches),
                        len(token_batch),
                    )

                # Use retry wrapper instead of calling _embed_documents directly
                batch_results: (
                    Sequence[Sequence[float]]
                    | Sequence[Sequence[int]]
                    | Sequence[dict[str, list[int] | list[float]]]
                ) = await self._embed_documents_with_retry(
                    token_batch, for_backup=for_backup, **kwargs
                )
                all_results.extend(batch_results)

                # Yield between token batches to keep server responsive
                await asyncio.sleep(0)

            results = all_results
        except CircuitBreakerOpenError as e:
            # Circuit breaker open - return error immediately
            await log_to_client_or_fallback(
                context,
                "error",
                {
                    "msg": "Circuit breaker open",
                    "extra": {
                        "provider": type(self)._provider.variable,
                        "document_count": len(documents),
                        "circuit_state": self._circuit_state.variable,
                    },
                },
            )
            return self._handle_embedding_error(e, batch_id or cache_key, documents or [], None)  # type: ignore
        except RetryError as e:
            # All retry attempts exhausted
            await log_to_client_or_fallback(
                context,
                "error",
                {
                    "msg": "All retry attempts exhausted",
                    "extra": {
                        "provider": type(self)._provider.variable,
                        "document_count": len(documents),
                        "failure_count": self._failure_count,
                    },
                },
            )
            return self._handle_embedding_error(e, batch_id or cache_key, documents or [], None)  # type: ignore
        except Exception as e:
            await log_to_client_or_fallback(
                context,
                "error",
                {
                    "msg": "Document embedding failed",
                    "extra": {
                        "provider": type(self)._provider.variable,
                        "document_count": len(documents),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                },
            )
            return self._handle_embedding_error(e, batch_id or cache_key, documents or [], None)  # type: ignore
        else:
            if isinstance(results, dict):
                # Sparse embedding format
                from codeweaver.providers.embedding.types import SparseEmbedding

                results = [  # ty: ignore[invalid-assignment]
                    SparseEmbedding(
                        indices=result["indices"],  # type: ignore
                        values=result["values"],  # type: ignore
                    )
                    for result in results
                ]
            if not is_old_batch:
                self._register_chunks(
                    chunks=chunks,  # Already a tuple, no need to convert again
                    batch_id=cast(UUID7, batch_id or cache_key),
                    embeddings=results,  # ty: ignore[invalid-argument-type]
                    for_backup=for_backup,
                )

            await log_to_client_or_fallback(
                context,
                "debug",
                {
                    "msg": "Document embedding complete",
                    "extra": {
                        "provider": type(self)._provider.variable,
                        "document_count": len(documents),
                        "embeddings_generated": len(results) if results else 0,
                    },
                },
            )

            return results  # ty: ignore[invalid-return-type]

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=16),  # 1s, 2s, 4s, 8s, 16s
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    async def _embed_query_with_retry(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Wrapper around _embed_query with retry logic and circuit breaker."""
        self._check_circuit_breaker()

        try:
            result = await self._embed_query(query, **kwargs)
            self._record_success()
        except (ConnectionError, TimeoutError, OSError) as e:
            self._record_failure()
            logger.warning(
                "Query embedding failed for %s(attempt %d/5)",
                type(self)._provider,
                self._failure_count,
                extra={"query": query, "error": str(e)},
            )
            raise
        except Exception:
            logger.warning("Non-retryable error in query embedding", exc_info=True)
            raise
        else:
            return result

    @abstractmethod
    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Abstract method to implement query embedding logic."""

    async def embed_query(
        self, query: str | Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]] | list[SparseEmbedding] | EmbeddingErrorInfo:
        """Embed a query into a vector."""
        processed_kwargs: Any = self._set_kwargs(self.query_kwargs, kwargs or {})
        queries: Sequence[str] = [query] if isinstance(query, str) else list(query)
        try:
            # Use retry wrapper instead of calling _embed_query directly
            results: (
                Sequence[Sequence[float]] | Sequence[Sequence[int]] | Sequence[SparseEmbedding]
            ) = await self._embed_query_with_retry(queries, **processed_kwargs)
        except CircuitBreakerOpenError as e:
            logger.warning("Circuit breaker open for query embedding")
            return self._handle_embedding_error(e, batch_id=None, documents=None, queries=queries)
        except RetryError as e:
            logger.warning("All retry attempts exhausted for query embedding", exc_info=True)
            return self._handle_embedding_error(e, batch_id=None, documents=None, queries=queries)
        except Exception as e:
            return self._handle_embedding_error(e, batch_id=None, documents=None, queries=queries)
        else:
            if isinstance(results, dict):
                # Sparse embedding format
                from codeweaver.providers.embedding.types import SparseEmbedding

                results = [
                    SparseEmbedding(
                        indices=result["indices"],  # type: ignore
                        values=result["values"],  # type: ignore
                    )
                    for result in results
                ]
            return results

    @property
    def model_name(self) -> str:
        """Get the model name for the embedding provider."""
        return self.caps.name

    @property
    def model_capabilities(self) -> EmbeddingModelCapabilities | None:
        """Get the model capabilities for the embedding provider."""
        return self.caps

    def _tokenizer(self) -> Tokenizer[Any]:
        """Get the tokenizer for the embedding provider."""
        if defined_tokenizer := self.caps.tokenizer:
            return get_tokenizer(defined_tokenizer, self.caps.tokenizer_model or self.caps.name)
        return get_tokenizer("tiktoken", "cl100k_base")

    @property
    def tokenizer(self) -> Tokenizer[Any]:
        """Get the tokenizer for the embedding provider."""
        return self._tokenizer()

    @property
    def is_instruct_model(self) -> bool:
        """Return True if the model supports custom prompts."""
        return self.model_name in (
            "intfloat/multilingual-e5-large-instruct",
            "Qwen/Qwen3-Embedding-0.6B",
            "Qwen/Qwen3-Embedding-4B",
            "Qwen/Qwen3-Embedding-8B",
        )

    @overload
    def _update_token_stats(
        self, *, token_count: int, from_docs: None = None, sparse: bool = False
    ) -> None: ...
    @overload
    def _update_token_stats(
        self,
        *,
        from_docs: Sequence[str] | Sequence[Sequence[str]],
        token_count: None = None,
        sparse: bool = False,
    ) -> None: ...
    def _update_token_stats(
        self,
        *,
        token_count: int | None = None,
        from_docs: Sequence[str] | Sequence[Sequence[str]] | None = None,
        sparse: bool = False,
    ) -> None:
        """Update token statistics for the embedding provider."""
        statistics: SessionStatistics = _get_statistics()
        if token_count is not None:
            statistics.add_token_usage(embedding_generated=token_count)
        elif from_docs and all(isinstance(doc, str) for doc in from_docs):
            token_count = self.tokenizer.estimate_batch(from_docs)  # type: ignore
            statistics.add_token_usage(embedding_generated=token_count)
        elif from_docs:
            # Handle nested sequences by flattening
            flattened: list[str] = []
            for item in from_docs:
                if isinstance(item, str):
                    flattened.append(item)
                else:
                    flattened.extend(item)  # type: ignore
            token_count = self.tokenizer.estimate_batch(flattened)
            statistics.add_token_usage(embedding_generated=token_count)
        else:
            raise CodeWeaverValidationError(
                "Token statistics update requires either token_count or from_docs",
                details={
                    "token_count_provided": token_count is not None,
                    "from_docs_provided": from_docs is not None,
                },
                suggestions=[
                    "Provide token_count directly from provider response",
                    "Provide from_docs list to estimate token count",
                ],
            )

    @overload
    def _get_model_settings(
        self, *, sparse: Literal[False] = False
    ) -> EmbeddingModelSettings | None: ...
    @overload
    def _get_model_settings(
        self, *, sparse: Literal[True] = True
    ) -> SparseEmbeddingModelSettings | None: ...
    def _get_model_settings(
        self, *, sparse: bool = False
    ) -> EmbeddingModelSettings | SparseEmbeddingModelSettings | None:
        from codeweaver.common.registry.provider import get_provider_config_for

        settings = get_provider_config_for("sparse_embedding" if sparse else "embedding")
        return settings.get("model_settings")

    def get_datatype(
        self, *, sparse: bool = False, backup: bool = False
    ) -> Literal["float32", "float16", "int8", "binary"]:
        """Get the datatype of the embedding vectors based on capabilities."""
        if backup:
            return "int8"
        default_dtype = self.caps.default_dtype
        if default_dtype and default_dtype not in ("float32", "float16", "int8", "binary"):
            default_dtype = "float16" if "float" in default_dtype else "int8"
        model_settings = self._get_model_settings(sparse=sparse)
        if model_settings and model_settings.get("data_type"):
            return model_settings["data_type"]
        return cast(Literal["float32", "float16", "int8", "binary"], default_dtype)

    def get_dimension(
        self, *, sparse: bool = False, backup: bool = False
    ) -> PositiveInt | Literal[0]:
        """Get the dimension of the embedding vectors based on capabilities."""
        if sparse:
            return 0
        if backup:
            from codeweaver.config.profiles import get_profile

            profile = get_profile("backup", "local")
            if isinstance(profile["embedding"], dict):
                # Use .get() to safely access dimension, fall back to default_dimension if not present
                backup_dim = profile["embedding"]["model_settings"].get("dimension")
            else:
                backup_dim = cast(tuple, profile["embedding"])[0]["model_settings"].get("dimension")
            if backup_dim:
                return backup_dim
                # If dimension not in backup profile, fall through to use default_dimension
        default_dim = self.caps.default_dimension
        model_settings = self._get_model_settings(sparse=sparse)
        if model_settings and model_settings.get("dimension"):
            return model_settings["dimension"]
        return default_dim

    @staticmethod
    def normalize(embedding: Sequence[float] | Sequence[int]) -> list[float]:
        """Normalize an embedding vector to unit L2 length.

        Returns the input as floats if the vector is empty or has zero norm.
        Raises ValueError if the input contains non-finite values.
        """
        import numpy as np

        arr = np.asarray(embedding, dtype=np.float32)
        if arr.size == 0:
            return arr.tolist()
        if not np.all(np.isfinite(arr)):
            raise CodeWeaverValidationError(
                "Embedding vector contains non-finite values (NaN or Inf)",
                details={
                    "embedding_size": int(arr.size),
                    "has_nan": bool(np.isnan(arr).any()),
                    "has_inf": bool(np.isinf(arr).any()),
                },
                suggestions=[
                    "Check the embedding model output for numerical stability issues",
                    "Verify input text does not contain unusual characters",
                    "Try re-generating the embedding",
                ],
            )
        denom = float(np.linalg.norm(arr))
        return arr.tolist() if denom == 0.0 else (arr / denom).tolist()

    @staticmethod
    def is_normalized(embedding: Sequence[float] | Sequence[int], *, tol: float = 1e-6) -> bool:
        """Return True if the vector's L2 norm is approximately 1 within tol."""
        import numpy as np

        arr = np.asarray(embedding, dtype=np.float32)
        if arr.size == 0 or not np.all(np.isfinite(arr)):
            return False
        norm = float(np.linalg.norm(arr))
        return bool(np.isclose(norm, 1.0, atol=tol, rtol=0.0))

    @staticmethod
    def chunks_to_strings(
        chunks: Sequence[CodeChunk],
    ) -> Sequence[SerializedStrOnlyCodeChunk[CodeChunk]]:
        """Convert a sequence of CodeChunk objects to their string representations."""
        return [
            serialized
            if (serialized := chunk.serialize_for_embedding()) and isinstance(serialized, str)
            else serialized.decode("utf-8")  # ty:ignore[unresolved-attribute]
            for chunk in chunks
            if chunk
        ]

    @staticmethod
    def _set_kwargs(instance_kwargs: Any, passed_kwargs: Any) -> Mapping[str, Any]:
        """Set keyword arguments for the embedding provider."""
        passed_kwargs = passed_kwargs or {}
        return cast(dict[str, Any], instance_kwargs) | cast(dict[str, Any], passed_kwargs)

    def _register_chunks(
        self,
        chunks: Sequence[CodeChunk],
        batch_id: UUID7,
        embeddings: Sequence[Sequence[float]] | Sequence[Sequence[int]] | Sequence[SparseEmbedding],
        *,
        for_backup: bool = False,
    ) -> None:  # sourcery skip: low-code-quality
        """Register chunks in the embedding registry."""
        from codeweaver.core.types.aliases import LiteralStringT, ModelName
        from codeweaver.providers.embedding.types import (
            ChunkEmbeddings,
            EmbeddingBatchInfo,
            SparseEmbedding,
        )

        registry = _get_registry()
        is_sparse = (
            type(self).__name__.lower().startswith("sparse")
            or "sparse" in type(self).__name__.lower()
            or isinstance(embeddings[0], SparseEmbedding)
        )
        attr = "sparse" if is_sparse else "dense"

        # Validate embedding dimensions for dense embeddings
        if not is_sparse and embeddings:
            expected_dim = self.get_dimension(sparse=False, backup=for_backup)
            first_embedding = embeddings[0]
            if not isinstance(first_embedding, SparseEmbedding):
                actual_dim = len(first_embedding)
                if actual_dim != expected_dim:
                    # Debug logging
                    logger.debug(
                        "Dimension mismatch DEBUG: model_name=%s, caps.name=%s, caps.default_dimension=%s, for_backup=%s, expected=%s, actual=%s",
                        self.model_name,
                        self.caps.name,
                        self.caps.default_dimension,
                        for_backup,
                        expected_dim,
                        actual_dim,
                    )
                    raise CodeWeaverValidationError(
                        f"Embedding dimension mismatch: expected {expected_dim}, got {actual_dim}",
                        details={
                            "expected_dimension": expected_dim,
                            "actual_dimension": actual_dim,
                            "model_name": self.model_name,
                            "provider": type(self)._provider.variable
                            if hasattr(type(self), "_provider")
                            else "unknown",
                            "for_backup": for_backup,
                        },
                        suggestions=[
                            f"Check that your embedding model '{self.model_name}' is configured with dimension={actual_dim}",
                            "If using matryoshka embeddings, ensure the dimension parameter matches your config",
                            "Verify the model in your config matches the model being used by your embedding provider",
                            "Run 'cw index --clear' to rebuild the collection with the correct dimensions",
                        ],
                    )

        chunk_infos: list[EmbeddingBatchInfo] = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            if attr == "sparse" and isinstance(embedding, dict):
                # For sparse embeddings, convert dict to SparseEmbedding
                sparse_emb = SparseEmbedding(
                    indices=embedding["indices"],  # type: ignore
                    values=embedding["values"],  # type: ignore
                )
                chunk_info = EmbeddingBatchInfo.create_sparse(
                    batch_id=batch_id,
                    batch_index=i,
                    chunk_id=chunk.chunk_id,
                    model=ModelName(cast(LiteralStringT, self.model_name)),
                    embeddings=sparse_emb,
                    dtype=self.get_datatype(sparse=True, backup=for_backup),
                    backup=for_backup,
                )
            else:
                # For dense embeddings or old format
                chunk_info = getattr(EmbeddingBatchInfo, f"create_{attr}")(
                    batch_id=batch_id,
                    batch_index=i,
                    chunk_id=chunk.chunk_id,
                    model=ModelName(cast(LiteralStringT, self.model_name)),
                    embeddings=embedding,
                    dimension=self.get_dimension(sparse=is_sparse, backup=for_backup),
                    dtype=self.get_datatype(sparse=is_sparse, backup=for_backup),
                    backup=for_backup,
                )
            chunk_infos.append(chunk_info)

        for i, info in enumerate(chunk_infos):
            if (registered := registry.get(info.chunk_id)) is not None:
                # Check if we already have this type of embedding
                has_existing = (
                    (
                        info.kind.variable == "dense"
                        and not info.backup
                        and registered.dense is not None
                    )
                    or (
                        info.kind.variable == "sparse"
                        and not info.backup
                        and registered.sparse is not None
                    )
                    or (
                        info.kind.variable == "dense"
                        and info.backup
                        and registered.backup_dense is not None
                    )
                    or (
                        info.kind.variable == "sparse"
                        and info.backup
                        and registered.backup_sparse is not None
                    )
                )

                if has_existing:
                    # Replace existing embedding (e.g., during re-embedding with skip_deduplication=True)
                    registry[info.chunk_id] = registered.update(info)
                else:
                    # Add new embedding kind to existing entry
                    registry[info.chunk_id] = registered.add(info)

                if registered.chunk != chunks[i]:
                    # because we create new CodeChunk instances during processing, we need to update the chunk reference
                    registry[info.chunk_id] = registry[info.chunk_id]._replace(chunk=chunks[i])
            else:
                registry[info.chunk_id] = ChunkEmbeddings(
                    dense=info if attr == "dense" and not for_backup else None,
                    sparse=info if attr == "sparse" and not for_backup else None,
                    chunk=chunks[i],
                    backup_dense=info if attr == "dense" and for_backup else None,
                    backup_sparse=info if attr == "sparse" and for_backup else None,
                )

    def _process_input(
        self,
        input_data: StructuredDataInput,
        *,
        is_old_batch: bool = False,
        for_backup: bool = False,
        skip_deduplication: bool = False,
    ) -> tuple[Iterator[CodeChunk], UUID7 | None]:
        """Process input data for embedding."""
        processed_chunks = default_input_transformer(input_data)
        if is_old_batch:
            return processed_chunks, None
        from codeweaver.core.chunks import BatchKeys

        key = uuid7()
        # Convert iterator to list to avoid exhaustion when used multiple times
        chunk_list = list(processed_chunks)
        final_chunks: list[CodeChunk] = []

        # FIXED: Compute hashes first WITHOUT adding to store
        from codeweaver.core.stores import get_blake_hash

        hashes = [get_blake_hash(chunk.content.encode("utf-8")) for chunk in chunk_list]

        # Check which chunks are NEW (hash not in store)
        # When skip_deduplication is True, include all chunks regardless of hash store
        if skip_deduplication:
            starter_chunks = chunk_list
        else:
            starter_chunks = (
                [
                    chunk
                    for i, chunk in enumerate(chunk_list)
                    if chunk and hashes[i] not in type(self)._backup_hash_store
                ]
                if for_backup
                else [
                    chunk
                    for i, chunk in enumerate(chunk_list)
                    if chunk and hashes[i] not in type(self)._hash_store
                ]
            )

        # Detect if this is a sparse embedding provider using type checking
        # SparseEmbeddingProvider is defined in this same module after EmbeddingProvider
        is_sparse_provider = isinstance(self, SparseEmbeddingProvider)

        # Add NEW chunks with batch keys and add their hashes to store
        for i, chunk in enumerate(starter_chunks):
            # Find the original index in chunk_list to get correct hash
            original_idx = chunk_list.index(chunk)
            batch_keys = BatchKeys(id=key, idx=i, sparse=is_sparse_provider)
            final_chunks.append(chunk.set_batch_keys(batch_keys, secondary=for_backup))
            # Now add the hash to store, mapping it to this batch key
            if for_backup:
                type(self)._backup_hash_store[hashes[original_idx]] = key
                if not type(self)._backup_store:
                    type(self)._backup_store = make_uuid_store(
                        value_type=list, size_limit=1024 * 1024
                    )  # type: ignore
                type(self)._backup_store[key] = final_chunks  # type: ignore
            else:
                type(self)._hash_store[hashes[original_idx]] = key
                if not type(self)._store:
                    type(self)._store = make_uuid_store(value_type=list, size_limit=1024 * 1024 * 3)  # type: ignore
                type(self)._store[key] = final_chunks  # type: ignore

        return iter(final_chunks), key

    def _process_output(self, output_data: Any) -> list[list[float]] | list[list[int]]:
        """Handle output data from embedding."""
        return type(self)._output_transformer(output_data)

    def _fire_and_forget(self, task: Callable[..., Any]) -> None:
        """Execute a fire-and-forget task in a thread pool executor.

        This method must be called from async context (all embedding methods are async).
        Schedules the task to run in a thread pool executor to avoid blocking the event loop.

        Used for non-time-sensitive tasks like token statistics updates that don't need
        to block the main embedding workflow.
        """
        loop = asyncio.get_running_loop()  # Will raise RuntimeError if not in async context
        _ = loop.run_in_executor(None, task)

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("_store"): AnonymityConversion.COUNT,
            FilteredKey("_hash_store"): AnonymityConversion.COUNT,
            FilteredKey("_client"): AnonymityConversion.FORBIDDEN,
            FilteredKey("_input_transformer"): AnonymityConversion.FORBIDDEN,
            FilteredKey("_output_transformer"): AnonymityConversion.FORBIDDEN,
            FilteredKey("_doc_kwargs"): AnonymityConversion.COUNT,
            FilteredKey("_query_kwargs"): AnonymityConversion.COUNT,
        }

    @override
    def model_dump_json(  # type: ignore
        self,
        *,
        indent: int | None = None,
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        fallback: Callable[[Any], Any] | None = None,
        serialize_as_any: bool = False,
    ) -> str:
        """Serialize the model to JSON, excluding certain fields."""
        return self._model_dump_json(  # ty: ignore[unresolved-attribute]
            indent=indent,
            include=include,
            exclude={"_client", "_input_transformer", "_output_transformer"},
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            fallback=fallback,
            serialize_as_any=serialize_as_any,
        )


class SparseEmbeddingProvider[SparseClient](EmbeddingProvider[SparseClient], ABC):
    """Abstract class for sparse embedding providers.

    Overrides hash stores to prevent collision with dense embedding deduplication.
    Dense and sparse embeddings should deduplicate independently.
    """

    # Override parent class hash stores with separate stores for sparse embeddings
    _hash_store: ClassVar[BlakeStore[UUID7]] = make_blake_store(
        value_type=UUID, size_limit=1024 * 256
    )  # 256kb limit -- separate from dense embeddings
    _backup_hash_store: ClassVar[BlakeStore[UUID7]] = make_blake_store(
        value_type=UUID, size_limit=1024 * 128
    )  # 128kb limit -- separate from dense embeddings

    @classmethod
    def clear_deduplication_stores(cls) -> None:
        """Clear class-level deduplication stores for sparse embeddings."""
        cls._hash_store = make_blake_store(value_type=UUID, size_limit=1024 * 256)
        cls._backup_hash_store = make_blake_store(value_type=UUID, size_limit=1024 * 128)

    def _batch_and_key(
        self, chunk_list: Sequence[CodeChunk], *, for_backup: bool, skip_deduplication: bool
    ) -> tuple[Iterator[CodeChunk], UUID7]:
        """Override to create batch keys with sparse=True.

        This ensures chunks get their sparse_batch_key set correctly, which is
        required for sparse embeddings to be stored in the vector store.
        """
        from codeweaver.core.chunks import BatchKeys
        from codeweaver.core.stores import get_blake_hash

        key = uuid7()
        final_chunks: list[CodeChunk] = []

        hashes = [get_blake_hash(chunk.content.encode("utf-8")) for chunk in chunk_list]

        # Check which chunks are NEW (hash not in store)
        # When skip_deduplication is True, include all chunks regardless of hash store
        if skip_deduplication:
            starter_chunks = chunk_list
        else:
            starter_chunks = (
                [
                    chunk
                    for i, chunk in enumerate(chunk_list)
                    if chunk and hashes[i] not in type(self)._backup_hash_store
                ]
                if for_backup
                else [
                    chunk
                    for i, chunk in enumerate(chunk_list)
                    if chunk and hashes[i] not in type(self)._hash_store
                ]
            )

        # Add NEW chunks with batch keys (sparse=True for sparse providers) and add their hashes to store
        for i, chunk in enumerate(starter_chunks):
            # Find the original index in chunk_list to get correct hash
            original_idx = chunk_list.index(chunk)
            # *** FIX: Create batch keys with sparse=True for sparse embedding providers ***
            batch_keys = BatchKeys(id=key, idx=i, sparse=True)
            final_chunks.append(chunk.set_batch_keys(batch_keys, secondary=for_backup))
            # Now add the hash to store, mapping it to this batch key
            if for_backup:
                type(self)._backup_hash_store[hashes[original_idx]] = key
                if not type(self)._backup_store:
                    type(self)._backup_store = make_uuid_store(
                        value_type=list, size_limit=1024 * 1024
                    )  # type: ignore
                type(self)._backup_store[key] = final_chunks  # type: ignore
            else:
                type(self)._hash_store[hashes[original_idx]] = key
                if not type(self)._store:
                    type(self)._store = make_uuid_store(value_type=list, size_limit=1024 * 1024 * 3)  # type: ignore
                type(self)._store[key] = final_chunks  # type: ignore

        return iter(final_chunks), key

    @abstractmethod
    @override
    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[SparseEmbedding]:  # ty:ignore[invalid-method-override]
        """Abstract method to implement document embedding logic for sparse embeddings."""

    @abstractmethod
    @override
    async def _embed_query(self, query: Sequence[str], **kwargs: Any) -> list[SparseEmbedding]:  # ty:ignore[invalid-method-override]
        """Abstract method to implement query embedding logic for sparse embeddings."""


__all__ = ("EmbeddingErrorInfo", "EmbeddingProvider", "SparseEmbeddingProvider")
