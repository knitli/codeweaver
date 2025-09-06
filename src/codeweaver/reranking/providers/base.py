# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Base class for reranking providers."""

from __future__ import annotations

import asyncio
import importlib
import logging

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Sequence
from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, cast, overload

from pydantic import BaseModel, ConfigDict, PositiveInt, TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from pydantic.main import IncEx
from pydantic_core import from_json

from codeweaver._data_structures import CodeChunk, StructuredDataInput
from codeweaver.exceptions import RerankingProviderError, ValidationError
from codeweaver.provider import Provider
from codeweaver.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.tokenizers import Tokenizer, get_tokenizer


if TYPE_CHECKING:
    from codeweaver._statistics import SessionStatistics

logger = logging.getLogger(__name__)


class RerankingResult(NamedTuple):
    """Result of a reranking operation."""

    original_index: int
    batch_rank: int
    score: float
    chunk: CodeChunk


@cache
def _get_statistics() -> SessionStatistics:
    """Get the statistics source for the reranking provider."""
    statistics_module = importlib.import_module("codeweaver._statistics")
    return statistics_module.get_session_statistics()


def default_reranking_input_transformer(documents: StructuredDataInput) -> Iterator[str]:
    """Default input transformer that converts documents to strings."""
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
    results: Sequence[float], chunks: Iterator[CodeChunk]
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


class RerankingProvider[RerankingClient](BaseModel, ABC):
    """Base class for reranking providers."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True, serialize_by_alias=True)

    _client: RerankingClient
    _provider: Provider
    _caps: RerankingModelCapabilities
    _prompt: str | None = None

    _rerank_kwargs: MappingProxyType[str, Any]
    # transforms the input documents into a format suitable for the provider
    _input_transformer: Callable[[StructuredDataInput], Any] = staticmethod(
        default_reranking_input_transformer
    )
    """The input transformer is a function that takes the input documents and returns them in a format suitable for the provider.

    The `StructuredDataInput` type is a CodeChunk or iterable of CodeChunks, but they can be in string, bytes, bytearray, python dictionary, or CodeChunk format.
    """
    _output_transformer: Callable[[Any, Iterator[CodeChunk]], Sequence[RerankingResult]] = (
        staticmethod(default_reranking_output_transformer)
    )
    """The output transformer is a function that takes the raw results from the provider and returns a Sequence of RerankingResult."""

    _chunk_store: tuple[CodeChunk, ...] | None = None
    """Stores the chunks while they are processed. We do this because we don't send the whole chunk to the provider, so we save them for later, like squirrels."""

    def __init__(
        self,
        client: RerankingClient,
        capabilities: RerankingModelCapabilities,
        prompt: str | None = None,
        top_n: PositiveInt = 40,
        **kwargs: dict[str, Any] | None,
    ) -> None:
        """Initialize the RerankingProvider."""
        self._model_dump_json = super().model_dump_json
        self._client = client
        self._prompt = prompt
        self._caps = capabilities
        self.kwargs = {**(type(self)._rerank_kwargs or {}), **(kwargs or {})}
        logger.debug("RerankingProvider kwargs", extra=self.kwargs)
        self._top_n = cast(int, self.kwargs.get("top_n", top_n))
        logger.debug("Initialized RerankingProvider with top_n=%d", self._top_n)

        self._initialize()

    def _initialize(self) -> None:
        """_initialize is an optional function in subclasses for any additional setup."""

    @property
    def top_n(self) -> PositiveInt:
        """Get the top_n value."""
        return self._top_n

    @abstractmethod
    async def _execute_rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int = 40,
        **kwargs: dict[str, Any] | None,
    ) -> Any:
        """Execute the reranking process.

        _execute_rerank must be a function in subclasses that takes a query string and document Sequence,
        and returns the unprocessed reranked results from the provider's API.
        """
        raise NotImplementedError

    async def rerank(
        self, query: str, documents: StructuredDataInput, **kwargs: dict[str, Any] | None
    ) -> Sequence[RerankingResult]:
        """Rerank the given documents based on the query."""
        processed_kwargs = self._set_kwargs(**kwargs)
        transformed_docs = self._process_documents(documents)
        self._chunk_store = tuple(transformed_docs)
        processed_docs = self._input_transformer(transformed_docs)
        reranked = await self._execute_rerank(
            query, processed_docs, top_n=self.top_n, **processed_kwargs
        )
        loop = asyncio.get_event_loop()
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
    def client(self) -> RerankingClient:
        """Get the client for the reranking provider."""
        return self._client

    @property
    def provider(self) -> Provider:
        """Get the provider for the reranking provider."""
        return self._provider

    @property
    def model_name(self) -> str:
        """Get the model name for the reranking provider."""
        return self._caps.name

    @property
    def model_capabilities(self) -> RerankingModelCapabilities:
        """Get the model capabilities for the reranking provider."""
        return self._caps

    @property
    def prompt(self) -> str | None:
        """Get the prompt for the reranking provider."""
        return self._prompt

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

    def _set_kwargs(self, **kwargs: dict[str, Any] | None) -> dict[str, Any]:
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
                self.tokenizer.estimate_batch(from_docs)  # pyright: ignore[reportArgumentType]
                if all(isinstance(doc, str) for doc in from_docs)
                else sum(self.tokenizer.estimate_batch(item) for item in from_docs)  # type: ignore
            )
            statistics.add_token_usage(reranking_generated=token_count)

    def _process_documents(self, documents: StructuredDataInput) -> Iterator[CodeChunk]:
        """Process the input documents into a uniform format."""
        yield from ()

    def _process_results(self, results: Any, raw_docs: Sequence[str]) -> Sequence[RerankingResult]:
        """Process the results from the reranking."""
        # voyage and cohere return token count, others do not
        if self.provider not in [Provider.VOYAGE, Provider.COHERE]:
            self._update_token_stats(from_docs=raw_docs)
        chunks = self._chunk_store or self._process_documents(raw_docs)
        return self._output_transformer(results, iter(chunks))

    @staticmethod
    def to_code_chunk(text: StructuredDataInput) -> Sequence[CodeChunk]:
        """Convenience wrapper around `CodeChunk.chunkify`."""
        return tuple(CodeChunk.chunkify(text))

    def _report_token_savings(
        self, results: Sequence[RerankingResult], processed_chunks: Sequence[str]
    ) -> None:
        """Report token savings from the reranking process."""
        if (context_saved := self._calculate_context_saved(results, processed_chunks)) > 0:
            statistics = _get_statistics()
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
        return tokenizer.estimate_batch(discarded_chunks)  # pyright: ignore[reportArgumentType]

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

    def model_dump_json(
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
        return self._model_dump_json(
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
