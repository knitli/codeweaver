# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Base class for reranking providers."""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import logging
import time

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Mapping, Sequence
from functools import cache
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Literal,
    NamedTuple,
    cast,
    overload,
    override,
)

from pydantic import ConfigDict, Field, PositiveInt, PrivateAttr, SkipValidation, TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from pydantic.main import IncEx
from pydantic_core import from_json
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import RerankingProviderError, ValidationError
from codeweaver.providers.provider import Provider
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.tokenizers import Tokenizer, get_tokenizer


if TYPE_CHECKING:
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.core.chunks import CodeChunk, StructuredDataInput
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion

logger = logging.getLogger(__name__)


class CircuitBreakerState(BaseEnum):
    """Circuit breaker states for provider resilience."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""


class RerankingResult(NamedTuple):
    """Result of a reranking operation."""

    original_index: int
    batch_rank: int
    score: float
    chunk: CodeChunk


@cache
def _get_statistics() -> SessionStatistics:
    """Get the statistics source for the reranking provider."""
    statistics_module = importlib.import_module("codeweaver.common.statistics")
    # we need SessionStatistics in this namespace at runtime for pydantic to find it
    SessionStatistics = statistics_module.SessionStatistics  # type: ignore # noqa: F841, N806
    return statistics_module.get_session_statistics()


def default_reranking_input_transformer(documents: StructuredDataInput) -> Iterator[str]:
    """Default input transformer that converts documents to strings."""
    from codeweaver.core.chunks import CodeChunk

    try:
        yield from CodeChunk.dechunkify(documents, for_embedding=True)
    except (PydanticValidationError, ValueError) as e:
        logger.exception("Error in default_reranking_input_transformer: ")
        raise RerankingProviderError(
            "Error in default_reranking_input_transformer",
            details={"input": documents},
            suggestions=["Check input format", "Validate document structure"],
        ) from e


def default_reranking_output_transformer(
    results: Sequence[float], chunks: Iterator[CodeChunk] | tuple[CodeChunk, ...]
) -> Sequence[RerankingResult]:
    """Default output transformer that converts results and chunks to RerankingResult.

    This transformer handles the most common case where the results are a sequence of floats with
    the same length as the input chunks, and each float represents the score for the corresponding chunk
    """
    processed_results: list[RerankingResult] = []
    mapped_scores = sorted(
        ((i, score) for i, score in enumerate(results)), key=lambda x: x[1], reverse=True
    )
    processed_results.extend(
        RerankingResult(
            original_index=i,
            batch_rank=next((j + 1 for j, (idx, _) in enumerate(mapped_scores) if idx == i), -1),
            score=score,
            chunk=chunk,
        )
        for i, (score, chunk) in enumerate(zip(results, chunks, strict=True))
    )
    return processed_results


class QueryType(NamedTuple):
    """Represents a query and its associated metadata."""

    query: str
    docs: Sequence[CodeChunk]


class RerankingProvider[RerankingClient](BasedModel, ABC):
    """Base class for reranking providers."""

    model_config = BasedModel.model_config | ConfigDict(
        extra="allow", arbitrary_types_allowed=True, defer_build=True
    )

    client: Annotated[
        SkipValidation[RerankingClient],
        Field(
            exclude=True,
            description="The client for the reranking provider.",
            validation_alias="_client",
        ),
    ]
    _provider: Provider
    caps: Annotated[
        RerankingModelCapabilities,
        Field(description="The capabilities of the reranking model.", validation_alias="_caps"),
    ]
    prompt: Annotated[
        str | None,
        Field(description="The prompt for the reranking provider.", validation_alias="_prompt"),
    ]

    _rerank_kwargs: ClassVar[MappingProxyType[str, Any]]
    # transforms the input documents into a format suitable for the provider
    _input_transformer: ClassVar[Callable[[StructuredDataInput], Any]] = PrivateAttr(
        default=staticmethod(default_reranking_input_transformer)
    )
    """The input transformer is a function that takes the input documents and returns them in a format suitable for the provider.

    The `StructuredDataInput` type is a CodeChunk or iterable of CodeChunks, but they can be in string, bytes, bytearray, python dictionary, or CodeChunk format.
    """
    _output_transformer: ClassVar[
        Callable[[Any, Iterator[CodeChunk]], Sequence[RerankingResult]]
    ] = PrivateAttr(default=staticmethod(default_reranking_output_transformer))
    """The output transformer is a function that takes the raw results from the provider and returns a Sequence of RerankingResult."""

    _chunk_store: tuple[CodeChunk, ...] | None = PrivateAttr(default=None)
    """Stores the chunks while they are processed. We do this because we don't send the whole chunk to the provider, so we save them for later, like squirrels."""

    # Circuit breaker state tracking
    _circuit_state: CircuitBreakerState = CircuitBreakerState.CLOSED
    _failure_count: int = 0
    _last_failure_time: float | None = None
    _circuit_open_duration: float = 30.0  # 30 seconds as per spec FR-008a

    def __init__(
        self,
        client: RerankingClient,
        caps: RerankingModelCapabilities,
        prompt: str | None = None,
        top_n: PositiveInt = 40,
        **kwargs: Any,
    ) -> None:
        """Initialize the RerankingProvider."""
        # Store values we'll need after super().__init__()
        # Get _rerank_kwargs safely - it might not be defined in the subclass
        _rerank_kwargs = kwargs or {}
        with contextlib.suppress(AttributeError, TypeError):
            class_rerank_kwargs = type(self)._rerank_kwargs
            if class_rerank_kwargs and isinstance(class_rerank_kwargs, dict):
                _rerank_kwargs = {**class_rerank_kwargs, **_rerank_kwargs}

        _top_n = cast(int, _rerank_kwargs.get("top_n", top_n))

        # Use object.__setattr__ to bypass Pydantic's validation for pre-super() initialization
        object.__setattr__(self, "_model_dump_json", super().model_dump_json)

        logger.debug("RerankingProvider kwargs", extra=_rerank_kwargs)
        logger.debug("Initialized RerankingProvider with top_n=%d", _top_n)

        # Initialize circuit breaker state using object.__setattr__
        object.__setattr__(self, "_circuit_state", CircuitBreakerState.CLOSED)
        object.__setattr__(self, "_failure_count", 0)
        object.__setattr__(self, "_last_failure_time", None)

        # Initialize pydantic model with the proper fields BEFORE _initialize
        super().__init__(client=client, caps=caps, prompt=prompt)

        # Now that Pydantic is initialized, set kwargs as normal attributes
        self.kwargs = _rerank_kwargs
        self._top_n = _top_n

        # Call _initialize after super().__init__() so Pydantic private attributes are set up
        self._initialize()

    def _initialize(self) -> None:
        """_initialize is an optional function in subclasses for any additional setup."""

    @property
    def top_n(self) -> PositiveInt:
        """Get the top_n value."""
        return self._top_n

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

        if self._failure_count >= 3:  # 3 failures threshold as per spec FR-008a
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

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(
            multiplier=1, min=1, max=16
        ),  # 1s, 2s, 4s, 8s, 16s as per spec FR-009c
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    async def _execute_rerank_with_retry(
        self, query: str, documents: Sequence[str], *, top_n: int = 40, **kwargs: Any
    ) -> Any:
        """Wrapper around _execute_rerank with retry logic and circuit breaker.

        Applies exponential backoff (1s, 2s, 4s, 8s, 16s) and circuit breaker pattern.
        """
        self._check_circuit_breaker()

        try:
            result = await self._execute_rerank(query, documents, top_n=top_n, **kwargs)
            self._record_success()
        except (ConnectionError, TimeoutError, OSError) as e:
            self._record_failure()
            logger.warning(
                "Reranking API call failed for %s: %s (attempt %d/5)",
                type(self)._provider,
                str(e),
                self._failure_count,
            )
            raise
        except Exception:
            # Non-retryable errors don't affect circuit breaker
            logger.exception("Non-retryable error in reranking")
            raise
        else:
            return result

    @abstractmethod
    async def _execute_rerank(
        self, query: str, documents: Sequence[str], *, top_n: int = 40, **kwargs: Any
    ) -> Any:
        """Execute the reranking process.

        _execute_rerank must be a function in subclasses that takes a query string and document Sequence,
        and returns the unprocessed reranked results from the provider's API.
        """
        raise NotImplementedError

    async def rerank(
        self, query: str, documents: StructuredDataInput, **kwargs: Any
    ) -> Sequence[RerankingResult]:
        """Rerank the given documents based on the query."""
        from codeweaver.core.chunks import CodeChunk

        processed_kwargs = self._set_kwargs(**kwargs)
        transformed_docs = CodeChunk.chunkify(documents)
        self._chunk_store = tuple(transformed_docs)
        processed_docs = self._input_transformer(transformed_docs)

        try:
            # Use retry wrapper instead of calling _execute_rerank directly
            reranked = await self._execute_rerank_with_retry(
                query, processed_docs, top_n=self.top_n, **processed_kwargs
            )
        except CircuitBreakerOpenError:
            logger.warning("Circuit breaker open for reranking")
            # Return empty results when circuit breaker is open
            return []
        except RetryError:
            logger.exception("All retry attempts exhausted for reranking")
            # Return empty results when all retries exhausted
            return []
        except Exception:
            logger.exception("Reranking failed with error")
            # Return empty results on other errors
            return []

        loop = asyncio.get_running_loop()
        processed_results = self._process_results(reranked, processed_docs)
        if len(processed_results) > self.top_n:
            # results already sorted in descending order
            processed_results = processed_results[: self.top_n]

        # Reorder processed_docs so included (reranked) docs appear first in reranked order,
        # followed by all excluded docs. This allows token-savings to treat the tail as discarded.
        included_indices = [
            r.original_index
            for r in sorted(
                processed_results,
                key=lambda r: (r.batch_rank if r.batch_rank != -1 else float("inf")),
            )
        ]
        included_set = set(included_indices)
        included_docs = [
            processed_docs[i] for i in included_indices if 0 <= i < len(processed_docs)
        ]
        excluded_docs = [doc for i, doc in enumerate(processed_docs) if i not in included_set]
        savings_ordered_docs = included_docs + excluded_docs

        await loop.run_in_executor(
            None, self._report_token_savings, processed_results, savings_ordered_docs
        )
        self._chunk_store = None
        return processed_results

    @property
    def provider(self) -> Provider:
        """Get the provider for the reranking provider."""
        return type(self)._provider

    @property
    def model_name(self) -> str:
        """Get the model name for the reranking provider."""
        return self.caps.name

    @property
    def model_capabilities(self) -> RerankingModelCapabilities:
        """Get the model capabilities for the reranking provider."""
        return self.caps

    def _tokenizer(self) -> Tokenizer[Any]:
        """Retrieves the tokenizer associated with the reranking model."""
        if tokenizer := self.model_capabilities.tokenizer:
            return get_tokenizer(
                tokenizer, self.model_capabilities.tokenizer_model or self.model_capabilities.name
            )
        return get_tokenizer("tiktoken", "cl100k_base")

    @property
    def tokenizer(self) -> Tokenizer[Any]:
        """Get the tokenizer for the reranking provider."""
        return self._tokenizer()

    def _set_kwargs(self, **kwargs: Any) -> Mapping[str, Any]:
        """Set the keyword arguments for the reranking provider."""
        return self.kwargs | (kwargs or {})

    @overload
    def _update_token_stats(self, *, token_count: int) -> None: ...
    @overload
    def _update_token_stats(
        self, *, from_docs: Sequence[str] | Sequence[Sequence[str]]
    ) -> None: ...
    def _update_token_stats(
        self,
        *,
        token_count: int | None = None,
        from_docs: Sequence[str] | Sequence[Sequence[str]] | None = None,
    ) -> None:
        """Update token statistics for the embedding provider."""
        statistics = _get_statistics()
        if token_count is not None:
            statistics.add_token_usage(reranking_generated=token_count)
        elif from_docs and all(isinstance(doc, str) for doc in from_docs):
            token_count = (
                self.tokenizer.estimate_batch(from_docs)  # ty: ignore[invalid-argument-type]
                if all(isinstance(doc, str) for doc in from_docs)
                else sum(self.tokenizer.estimate_batch(item) for item in from_docs)  # type: ignore
            )
            statistics.add_token_usage(reranking_generated=token_count)

    def _process_results(self, results: Any, raw_docs: Sequence[str]) -> Sequence[RerankingResult]:
        """Process the results from the reranking.

        Note: This sync method is only called from async contexts (from the rerank method).
        """
        # voyage and cohere return token count, others do not
        if self.provider not in [Provider.VOYAGE, Provider.COHERE]:
            # We're always called from async context (rerank method), so we can safely get the loop
            loop = asyncio.get_running_loop()
            _ = loop.run_in_executor(None, lambda: self._update_token_stats(from_docs=raw_docs))

        from codeweaver.core.chunks import CodeChunk

        chunks = self._chunk_store or CodeChunk.chunkify(raw_docs)
        return type(self)._output_transformer(results, iter(chunks))

    @staticmethod
    def to_code_chunk(text: StructuredDataInput) -> Sequence[CodeChunk]:
        """Convenience wrapper around `CodeChunk.chunkify`."""
        from codeweaver.core.chunks import CodeChunk

        return tuple(CodeChunk.chunkify(text))

    def _report_token_savings(
        self, results: Sequence[RerankingResult], processed_chunks: Sequence[str]
    ) -> None:
        """Report token savings from the reranking process."""
        if (context_saved := self._calculate_context_saved(results, processed_chunks)) > 0:
            statistics = _get_statistics()
            # * Note: We aren't double counting tokens between here and `self.rerank`.
            # * This is for `saved_by_reranking`, while the other count in the pipeline is for `reranking_generated`.
            # * Put differently, `self.rerank` counts *spending* while this counts *savings*.
            statistics.add_token_usage(saved_by_reranking=context_saved)

    def _calculate_context_saved(
        self, results: Sequence[RerankingResult], processed_chunks: Sequence[str]
    ) -> int:
        """Calculate the context saved by the reranking process.

        Assumes processed_chunks are ordered with all included (kept) chunks first in reranked order,
        followed by all excluded (discarded) chunks. Token savings equals the token count of the tail
        after the number of kept results.

        We use `tiktoken` with `cl100k_base` as a reasonable default tokenizer for estimating the user LLM's token usage (we're not estimating based on the reranking model's tokenizer).
        """
        if not processed_chunks or not results or len(results) >= len(processed_chunks):
            return 0
        # All discarded chunks are in the tail after the kept results
        discarded_chunks = processed_chunks[len(results) :]
        tokenizer = get_tokenizer("tiktoken", "cl100k_base")
        return tokenizer.estimate_batch(discarded_chunks)

    @classmethod
    def from_json(
        cls, input_data: str | bytes | bytearray, client: RerankingClient, kwargs: dict[str, Any]
    ) -> RerankingProvider[RerankingClient]:
        """Create a RerankingProvider from JSON."""
        adapter = TypeAdapter(cls)
        python_obj = from_json(input_data)
        try:
            return adapter.validate_python({**python_obj, "_client": client, **kwargs})
        except PydanticValidationError as e:
            logger.exception("Error in RerankingProvider.from_json: ")
            raise ValidationError(
                "RerankingProvider received invalid JSON input that it couldn't deserialize.",
                details={"json_input": input_data, "client": client, "kwargs": kwargs},
                suggestions=[
                    "Make sure the JSON validates as JSON, and matches the expected schema for the RerankingProvider."
                ],
            ) from e

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        """Return telemetry keys for privacy filtering.

        Defines which fields should be filtered/anonymized when sending telemetry data.
        """
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("_client"): AnonymityConversion.FORBIDDEN,
            FilteredKey("_input_transformer"): AnonymityConversion.FORBIDDEN,
            FilteredKey("_output_transformer"): AnonymityConversion.FORBIDDEN,
            FilteredKey("_rerank_kwargs"): AnonymityConversion.COUNT,
            FilteredKey("_chunk_store"): AnonymityConversion.COUNT,
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


__all__ = ("RerankingProvider", "RerankingResult")
