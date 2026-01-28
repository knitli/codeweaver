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
from collections.abc import Callable, Iterator, Sequence
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

import numpy as np

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

from codeweaver.core import (
    INJECTED,
    AnonymityConversion,
    BasedModel,
    BatchKeys,
    EmbeddingBatchInfo,
    LiteralProvider,
    LiteralStringT,
    ModelName,
    Provider,
    ProviderError,
    SparseEmbedding,
    StatisticsDep,
    depends,
    get_blake_hash,
    log_to_client_or_fallback,
    make_uuid_store,
    uuid7,
)
from codeweaver.core import ValidationError as CodeWeaverValidationError
from codeweaver.core.types import ModelNameT
from codeweaver.providers.config import EmbeddingConfigT, EmbeddingProviderSettings
from codeweaver.providers.exceptions import CircuitBreakerOpenError
from codeweaver.providers.types import CircuitBreakerState


if TYPE_CHECKING:
    from codeweaver.core import (
        AnonymityConversion,
        CodeChunk,
        FilteredKeyT,
        SerializedStrOnlyCodeChunk,
        StructuredDataInput,
    )
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
    from codeweaver.providers.embedding.registry import EmbeddingRegistry


ONE_KB = 1024
ONE_MB = ONE_KB * 1024  # I guess it could be ONE_KB** but that'd be confusing

DEFAULT_MAX_TOKENS = 120_000

OPEN_CIRCUIT_DURATION = 30.0  # seconds

type EmbeddingImplementationDeps = Annotated[Any, depends(lambda: None)]
"Implementation-specific dependencies for the provider. To use this type, implement a dependency provider callable and register it with the DI system using this type as the key."

type EmbeddingCustomDeps = Annotated[Any, depends(lambda: None)]
"""Custom dependencies for the provider. To use this type, implement a dependency provider callable. You can register it simply by importing it. Here's how to declare it:

```python
from typing import Annotated
from codeweaver.core import dependency_provider

class LiterallyAnything:
    # this doesn't have to be a class, it could be anything.
    pass

type EmbeddingCustomDeps = Annotated[LiterallyAnything, depends(my_custom_deps)]

@dependency_provider(EmbeddingCustomDeps)
def my_custom_deps() -> LiterallyAnything:
    return LiterallyAnything()
```
"""

logger = logging.getLogger(__name__)


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

    Each provider only supports a specific interface, but an interface can be used by multiple providers.

    The primary example of this one-to-many relationship is the OpenAI provider, which supports any OpenAI-compatible provider (Azure, Ollama, Fireworks, Heroku, Together, Github, and more).
    """

    model_config = BasedModel.model_config | ConfigDict(extra="allow", arbitrary_types_allowed=True)

    client: Annotated[
        SkipValidation[EmbeddingClient],
        Field(
            description="The client for the embedding provider.",
            exclude=True,
            validation_alias="_client",
        ),
    ]

    config: Annotated[
        EmbeddingConfigT,
        Field(description="Configuration for the embedding model, including all request options."),
    ]

    registry: Annotated[
        EmbeddingRegistry,
        Field(
            description="The embedding registry. Stores completed embedding batches for deduplication and caching."
        ),
    ]

    caps: Annotated[
        EmbeddingModelCapabilities | None,
        Field(
            description="The capabilities of the embedding model. Can be None if capabilities are not available. If you are adding a custom model, you'll get best results if you define an `EmbeddingModelCapabilities` object for it and register it with the DI system (using `@dependency_provider` decorator)."
        ),
    ] = None

    cache_manager: Annotated[
        Any,  # EmbeddingCacheManager - avoiding circular import
        Field(
            description="Centralized cache manager for deduplication and batch storage with namespace isolation",
            exclude=True,
        ),
    ]

    _namespace: Annotated[
        str,
        Field(
            description="Namespace for cache isolation (computed from provider_id.embedding_kind)",
            exclude=True,
            default="",
        ),
    ] = ""

    _provider: ClassVar[LiteralProvider] = cast(LiteralProvider, Provider.NOT_SET)
    _max_tokens: ClassVar[PositiveInt] = DEFAULT_MAX_TOKENS
    _input_transformer: Callable[[StructuredDataInput], Any] = default_input_transformer
    _output_transformer: Callable[[Any], list[list[float]] | list[list[int]]] = (
        default_output_transformer
    )
    # Circuit breaker state tracking
    _circuit_state: CircuitBreakerState = CircuitBreakerState.CLOSED
    _failure_count: int = 0
    _last_failure_time: float | None = None
    _circuit_open_duration: float = OPEN_CIRCUIT_DURATION  # 30 seconds

    def __init__(
        self,
        client: EmbeddingClient,
        config: EmbeddingProviderSettings,
        registry: EmbeddingRegistry,
        cache_manager: Any,  # EmbeddingCacheManager - avoiding circular import
        caps: EmbeddingModelCapabilities | None = None,
        impl_deps: EmbeddingImplementationDeps = None,
        custom_deps: EmbeddingCustomDeps = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the embedding provider with centralized cache manager.

        Args:
            client: SDK client for the embedding provider
            config: Provider configuration settings
            registry: Global embedding registry
            cache_manager: Centralized cache manager for deduplication (singleton)
            caps: Model capabilities metadata
            impl_deps: Implementation-specific dependencies
            custom_deps: Custom dependencies
            **kwargs: Additional keyword arguments
        """
        defaults = getattr(self, "_defaults", {})
        object.__setattr__(self, "_model_dump_json", super().model_dump_json)
        object.__setattr__(self, "_circuit_state", CircuitBreakerState.CLOSED)
        object.__setattr__(self, "_failure_count", kwargs.get("failure_count", 0))
        object.__setattr__(self, "_last_failure_time", kwargs.get("last_failure_time"))
        object.__setattr__(
            self,
            "_circuit_open_duration",
            kwargs.get("circuit_open_duration", OPEN_CIRCUIT_DURATION),
        )
        object.__setattr__(self, "client", client)
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "query_options", config.query if config and config.query else {})
        object.__setattr__(
            self, "embed_options", config.embedding if config and config.embedding else {}
        )
        object.__setattr__(self, "model_options", config.model if config and config.model else {})

        # Phase 4: Use centralized cache manager instead of per-instance stores
        object.__setattr__(self, "cache_manager", cache_manager)

        # Compute namespace from provider ID + embedding kind
        # Note: We need to check the type after initialization to determine if sparse
        # For now, we'll set a placeholder and update it after _initialize
        provider_id = config.provider.variable if config.provider else "unknown"
        object.__setattr__(self, "_namespace", f"{provider_id}.dense")  # Default to dense, may be updated

        self._initialize(impl_deps, custom_deps)
        object.__setattr__(self, "caps", caps)
        object.__setattr__(self, "registry", registry)
        super().__init__(
            client=client,
            config=config,
            caps=caps,
            registry=registry,
            cache_manager=cache_manager,
            **defaults
        )

    def _update_namespace_for_sparse(self) -> None:
        """Update namespace if this is a sparse embedding provider.

        Called by SparseEmbeddingProvider to set the correct namespace after initialization.
        """
        provider_id = self.config.provider.variable if self.config.provider else "unknown"
        object.__setattr__(self, "_namespace", f"{provider_id}.sparse")

    @abstractmethod
    def _initialize(
        self, impl_deps: EmbeddingImplementationDeps = None, custom_deps: EmbeddingCustomDeps = None
    ) -> None:
        """Initialize the embedding provider.

        This method is called at the end of __init__ and before pydantic validation to allow for any additional setup.
        It offers a flexible opportunity to insert implementation-specific or custom dependencies needed for the provider,
        which can be either directly passed or dependency injected.

        Args:
            impl_deps: Any implementation-specific dependencies or parameters for initialization.
            custom_deps: Any custom dependencies or parameters for initialization.
        """

    def clear_deduplication_stores(self) -> None:
        """Clear namespace-isolated deduplication stores.

        This is primarily useful for testing to ensure clean state between test runs.
        Uses the centralized cache manager to clear only this provider's namespace.
        """
        self.cache_manager.clear_namespace(self._namespace)

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

        max_tokens = max_tokens or DEFAULT_MAX_TOKENS
        # Apply 85% safety margin to account for tokenizer estimation variance
        # This prevents edge cases where our token estimate slightly underestimates
        # the provider's actual token count, which would cause API errors
        effective_limit = int(max_tokens * 0.85)
        tokenizer = self.tokenizer

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
        self, documents: Sequence[CodeChunk], **kwargs: Any
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
        documents: Sequence[CodeChunk],
        *,
        batch_id: UUID7 | None = None,
        skip_deduplication: bool = False,
        context: Any = None,
        **kwargs: Any,
    ) -> list[list[float]] | list[list[int]] | list[SparseEmbedding] | EmbeddingErrorInfo:
        # sourcery skip: low-code-quality
        """Embed a list of documents into vectors.

        Optionally takes a `batch_id` parameter to reprocess a specific batch of documents.
        """
        is_old_batch = False
        if batch_id:
            # Try to get batch from cache manager
            cached_batch = self.cache_manager.get_batch(batch_id, self._namespace)
            if cached_batch:
                documents = cached_batch
                is_old_batch = True
        chunks_iter, cache_key = await self._process_input(
            documents, is_old_batch=is_old_batch, skip_deduplication=skip_deduplication
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
                ) = await self._embed_documents_with_retry(token_batch, **kwargs)
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
                results = [  # ty: ignore[invalid-assignment]
                    SparseEmbedding(
                        indices=result["indices"],  # type: ignore
                        values=result["values"],  # type: ignore
                    )
                    for result in results
                ]
            if not is_old_batch:
                await self._register_chunks(
                    chunks=chunks,  # Already a tuple, no need to convert again
                    batch_id=cast(UUID7, batch_id or cache_key),
                    embeddings=results,  # ty: ignore[invalid-argument-type]
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
        # Config structure delivers query options directly, no need to merge kwargs
        queries: Sequence[str] = [query] if isinstance(query, str) else list(query)
        try:
            # Use retry wrapper instead of calling _embed_query directly
            kwargs = (self.query_options or {}) | kwargs
            results: (
                Sequence[Sequence[float]] | Sequence[Sequence[int]] | Sequence[SparseEmbedding]
            ) = await self._embed_query_with_retry(queries, **kwargs)
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
                results = [
                    SparseEmbedding(
                        indices=result["indices"],  # type: ignore
                        values=result["values"],  # type: ignore
                    )
                    for result in results
                ]
            return results

    @property
    def model_name(self) -> ModelNameT:
        """Get the model name for the embedding provider."""
        if self.caps:
            return ModelName(self.caps.name)
        return ModelName(
            self.config.model_name or self.config.embedding_config.model_name or "unknown-model"
        )

    @property
    def model_capabilities(self) -> EmbeddingModelCapabilities | None:
        """Get the model capabilities for the embedding provider."""
        return self.caps

    @property
    def is_provider_backup(self) -> bool:
        """Return True if this is a backup embedding provider."""
        return False

    def _tokenizer(self) -> Tokenizer[Any]:
        """Get the tokenizer for the embedding provider."""
        if self.caps and (defined_tokenizer := self.caps.tokenizer):
            return get_tokenizer(defined_tokenizer, self.caps.tokenizer_model or self.caps.name)
        return get_tokenizer("tiktoken", "o200k_base")

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
        statistics: StatisticsDep = INJECTED,
    ) -> None:
        """Update token statistics for the embedding provider."""
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

    def get_datatype(
        self, *, sparse: bool = False
    ) -> Literal["float32", "float16", "int8", "binary"]:
        """Get the datatype of the embedding vectors based on capabilities and config."""
        # First try to get from capabilities
        if self.caps:
            default_dtype = self.caps.default_dtype
            if default_dtype and default_dtype not in ("float32", "float16", "int8", "binary"):
                default_dtype = "float16" if "float" in default_dtype else "int8"
            return cast(Literal["float32", "float16", "int8", "binary"], default_dtype)
        # Fallback to float32 if no capabilities
        return "float32"

    def get_dimension(self, *, sparse: bool = False) -> PositiveInt | Literal[0]:
        """Get the dimension of the embedding vectors based on capabilities."""
        if sparse:
            return 0
        if self.caps:
            return self.caps.default_dimension
        return self.caps.default_dimension if self.caps else 0

    @staticmethod
    def normalize(embedding: Sequence[float] | Sequence[int] | np.ndarray) -> list[float]:
        """Normalize an embedding vector to unit L2 length.

        Returns the input as floats if the vector is empty or has zero norm.
        Raises ValueError if the input contains non-finite values.
        """
        arr = (
            embedding
            if isinstance(embedding, np.ndarray)
            else np.asarray(embedding, dtype=np.float32)
        )
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
        return arr.tolist() if denom == 0.0 else (arr / np.asarray(denom, dtype=arr.dtype)).tolist()

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

    async def _register_chunks(
        self,
        chunks: Sequence[CodeChunk],
        batch_id: UUID7,
        embeddings: Sequence[Sequence[float]] | Sequence[Sequence[int]] | Sequence[SparseEmbedding],
    ) -> None:  # sourcery skip: low-code-quality
        """Register chunks in the embedding registry.

        Now uses centralized EmbeddingCacheManager for registry operations.
        """
        is_sparse = self._is_sparse
        attr = "sparse" if is_sparse else "dense"

        # Validate embedding dimensions for dense embeddings
        if not is_sparse and embeddings:
            expected_dim = self.get_dimension(sparse=False)
            first_embedding = embeddings[0]
            if not isinstance(first_embedding, SparseEmbedding):
                actual_dim = len(first_embedding)
                if actual_dim != expected_dim:
                    # Debug logging
                    logger.debug(
                        "Dimension mismatch DEBUG: model_name=%s, caps.name=%s, caps.default_dimension=%s, expected=%s, actual=%s",
                        self.model_name,
                        self.caps.name,
                        self.caps.default_dimension,
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
                        },
                        suggestions=[
                            f"Check that your embedding model '{self.model_name}' is configured with dimension={actual_dim}",
                            "If using matryoshka embeddings, ensure the dimension parameter matches your config",
                            "Verify the model in your config matches the model being used by your embedding provider",
                            "Run 'cw index --clear' to rebuild the collection with the correct dimensions",
                        ],
                    )

        # Create embedding batch infos for all chunks
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
                    dtype=self.get_datatype(sparse=True),
                )
            else:
                # For dense embeddings or old format
                chunk_info = getattr(EmbeddingBatchInfo, f"create_{attr}")(
                    batch_id=batch_id,
                    batch_index=i,
                    chunk_id=chunk.chunk_id,
                    model=ModelName(cast(LiteralStringT, self.model_name)),
                    embeddings=embedding,
                    dimension=self.get_dimension(sparse=is_sparse),
                    dtype=self.get_datatype(sparse=is_sparse),
                )
            chunk_infos.append(chunk_info)

        # Register each chunk using cache manager
        for i, info in enumerate(chunk_infos):
            await self.cache_manager.register_embeddings(
                chunk_id=info.chunk_id,
                embedding_info=info,
                chunk=chunks[i],
            )

    async def _process_input(
        self,
        input_data: StructuredDataInput,
        *,
        is_old_batch: bool = False,
        skip_deduplication: bool = False,
    ) -> tuple[Iterator[CodeChunk], UUID7 | None]:
        """Process input data for embedding.

        Now uses centralized EmbeddingCacheManager for deduplication and storage.
        """
        processed_chunks = default_input_transformer(input_data)
        if is_old_batch:
            return processed_chunks, None

        batch_id = uuid7()
        # Convert iterator to list to avoid exhaustion when used multiple times
        chunk_list = list(processed_chunks)

        # Use cache manager for deduplication if not skipping
        if skip_deduplication:
            unique_chunks = chunk_list
        else:
            unique_chunks, _hash_mapping = await self.cache_manager.deduplicate(
                chunk_list, self._namespace, batch_id
            )

        # Detect if this is a sparse embedding provider using type checking
        # SparseEmbeddingProvider is defined in this same module after EmbeddingProvider
        is_sparse_provider = isinstance(self, SparseEmbeddingProvider)

        # Add batch keys to unique chunks
        final_chunks: list[CodeChunk] = []
        for i, chunk in enumerate(unique_chunks):
            batch_keys = BatchKeys(id=batch_id, idx=i, sparse=is_sparse_provider)
            final_chunks.append(chunk.set_batch_keys(batch_keys))

        # Store final chunks using cache manager
        if final_chunks:
            await self.cache_manager.store_batch(final_chunks, batch_id, self._namespace)

        return iter(final_chunks), batch_id

    def _process_output(self, output_data: Any) -> list[list[float]] | list[list[int]]:
        """Handle output data from embedding."""
        return self._output_transformer(output_data)

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
        from codeweaver.core import AnonymityConversion, FilteredKey

        return {
            FilteredKey("cache_manager"): AnonymityConversion.FORBIDDEN,
            FilteredKey("client"): AnonymityConversion.FORBIDDEN,
            FilteredKey("_input_transformer"): AnonymityConversion.FORBIDDEN,
            FilteredKey("_output_transformer"): AnonymityConversion.FORBIDDEN,
            FilteredKey("config"): AnonymityConversion.AGGREGATE,
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
            exclude={"client", "_input_transformer", "_output_transformer"},
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

    Uses namespace isolation (provider_id.sparse) to prevent collision with dense embeddings.
    Dense and sparse embeddings deduplicate independently via separate namespaces.
    """

    def __init__(
        self,
        client: SparseClient,
        config: EmbeddingProviderSettings,
        registry: Any,  # EmbeddingRegistry
        cache_manager: Any,  # EmbeddingCacheManager
        caps: Any = None,  # EmbeddingModelCapabilities
        impl_deps: EmbeddingImplementationDeps = None,
        custom_deps: EmbeddingCustomDeps = None,
        **kwargs: Any,
    ) -> None:
        """Initialize sparse embedding provider with correct namespace."""
        super().__init__(
            client=client,
            config=config,
            registry=registry,
            cache_manager=cache_manager,
            caps=caps,
            impl_deps=impl_deps,
            custom_deps=custom_deps,
            **kwargs,
        )
        # Update namespace to use .sparse instead of .dense
        self._update_namespace_for_sparse()

    def _batch_and_key(
        self, chunk_list: Sequence[CodeChunk], *, skip_deduplication: bool
    ) -> tuple[Iterator[CodeChunk], UUID7]:
        """Override to create batch keys with sparse=True."""
        key = uuid7()
        final_chunks: list[CodeChunk] = []

        hashes = [get_blake_hash(chunk.content.encode("utf-8")) for chunk in chunk_list]

        # Check which chunks are NEW (hash not in store)
        # When skip_deduplication is True, include all chunks regardless of hash store
        if skip_deduplication:
            starter_chunks = chunk_list
        else:
            starter_chunks = [
                chunk
                for i, chunk in enumerate(chunk_list)
                if chunk and hashes[i] not in self._hash_store
            ]

        # Add NEW chunks with batch keys (sparse=True for sparse providers) and add their hashes to store
        for i, chunk in enumerate(starter_chunks):
            # Find the original index in chunk_list to get correct hash
            original_idx = chunk_list.index(chunk)
            batch_keys = BatchKeys(id=key, idx=i, sparse=True)
            final_chunks.append(chunk.set_batch_keys(batch_keys))
            # Now add the hash to store, mapping it to this batch key
            self._hash_store[hashes[original_idx]] = key
            if not self._store:
                self._store = make_uuid_store(value_type=list, size_limit=ONE_MB * 3)  # type: ignore
            self._store[key] = final_chunks  # type: ignore

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


__all__ = (
    "EmbeddingCustomDeps",
    "EmbeddingErrorInfo",
    "EmbeddingImplementationDeps",
    "EmbeddingProvider",
    "SparseEmbeddingProvider",
)
