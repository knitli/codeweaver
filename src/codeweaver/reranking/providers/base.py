# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Base class for reranking providers."""

import asyncio
import logging

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any, ClassVar, Literal, NamedTuple, cast, overload
from uuid import uuid4

from pydantic import UUID4, BaseModel, ConfigDict, PositiveInt
from pydantic.main import IncEx

from codeweaver._data_structures import CodeChunk, SimpleTypedStore, StructuredDataInput
from codeweaver._server import get_statistics
from codeweaver._settings import Provider
from codeweaver.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.tokenizers import Tokenizer, get_tokenizer


logger = logging.getLogger(__name__)


class RerankingResult(NamedTuple):
    """Result of a reranking operation."""

    original_index: int
    batch_rank: int
    score: float
    chunk: CodeChunk


def default_reranking_input_transformer(documents: StructuredDataInput) -> Sequence[str]:
    """Default input transformer that converts documents to strings."""
    if isinstance(documents, list | tuple | set):
        return [doc.serialize() if isinstance(doc, CodeChunk) else str(doc) for doc in documents]
    return [documents.serialize()] if isinstance(documents, CodeChunk) else [str(documents)]


def default_reranking_output_transformer(
    results: Sequence[float], chunks: Sequence[CodeChunk]
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

    _rerank_kwargs: dict[str, Any]
    # transforms the input documents into a format suitable for the provider
    _input_transformer: Callable[[StructuredDataInput], Any] = staticmethod(
        default_reranking_input_transformer
    )
    _output_transformer: Callable[[Any, Sequence[CodeChunk]], Sequence[RerankingResult]] = (
        staticmethod(default_reranking_output_transformer)
    )
    _store: ClassVar[SimpleTypedStore] = SimpleTypedStore()
    """The output transformer is a function that takes the raw results from the provider and returns a Sequence of RerankingResult."""

    def __init__(
        self,
        client: RerankingClient,
        capabilities: RerankingModelCapabilities,
        prompt: str | None = None,
        top_k: PositiveInt = 40,
        **kwargs: dict[str, Any] | None,
    ) -> None:
        """Initialize the RerankingProvider."""
        self._model_dump_json = super().model_dump_json
        self._client = client
        self._prompt = prompt
        self._caps = capabilities
        self.kwargs = {**(type(self)._rerank_kwargs or {}), **(kwargs or {})}
        logger.debug("RerankingProvider kwargs", extra=self.kwargs)
        self._top_k = cast(int, self.kwargs.get("top_k", top_k))
        logger.debug("Initialized RerankingProvider with top_k=%d", self._top_k)

        self._initialize()

    def _initialize(self) -> None:
        """_initialize is an optional function in subclasses for any additional setup."""

    @property
    def top_k(self) -> PositiveInt:
        """Get the top_k value."""
        return self._top_k

    @abstractmethod
    async def _execute_rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_k: int = 40,
        **kwargs: dict[str, Any] | None,
    ) -> Any:
        """Execute the reranking process.

        _execute_rerank must be a function in subclasses that takes a query string and document Sequence,
        and returns the unprocessed reranked results from the provider's API.
        """
        raise NotImplementedError

    @overload
    async def rerank(
        self, query: str, documents: None, data_id: UUID4, **kwargs: dict[str, Any] | None
    ) -> None: ...  # sourcery skip: docstrings-for-functions
    async def rerank(
        self,
        query: str,
        documents: StructuredDataInput,
        data_id: UUID4,
        **kwargs: dict[str, Any] | None,
    ) -> Sequence[RerankingResult]:
        """Rerank the given documents based on the query."""
        processed_kwargs = self._set_kwargs(**kwargs)
        transformed_docs = self._process_documents(documents)
        self._store_value(uuid4(), (query, transformed_docs))
        transformed_docs = self._input_transformer(transformed_docs)
        reranked = await self._execute_rerank(
            query, transformed_docs, top_k=self.top_k, **processed_kwargs
        )
        loop = asyncio.get_event_loop()
        processed_results = self._process_results(reranked, transformed_docs)
        if len(processed_results) > self.top_k:
            # results already sorted in descending order
            processed_results = processed_results[: self.top_k]
        await loop.run_in_executor(
            None, self._report_token_savings, processed_results, transformed_docs
        )
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
        statistics = get_statistics()
        if token_count is not None:
            statistics.add_token_usage(reranking_generated=token_count)
        elif from_docs and all(isinstance(doc, str) for doc in from_docs):
            token_count = (
                self.tokenizer.estimate_batch(from_docs)  # pyright: ignore[reportArgumentType]
                if all(isinstance(doc, str) for doc in from_docs)
                else sum(self.tokenizer.estimate_batch(item) for item in from_docs)  # type: ignore
            )
            statistics.add_token_usage(reranking_generated=token_count)

    def _process_documents(self, documents: StructuredDataInput) -> Sequence[CodeChunk]:
        """Process the input documents into a uniform format."""
        if isinstance(documents, list | tuple | set):
            return [
                item
                if isinstance(item, CodeChunk) and item
                else CodeChunk.model_validate_json(item)
                for item in documents
            ]
        return [
            documents
            if isinstance(documents, CodeChunk) and documents
            else CodeChunk.model_validate_json(documents)
        ]

    def _process_results(
        self, results: Any, transformed_docs: Sequence[str]
    ) -> Sequence[RerankingResult]:
        """Process the results from the reranking."""
        # voyage returns token count, others do not
        if self.provider != Provider.VOYAGE:
            self._update_token_stats(from_docs=transformed_docs)
        chunks: list[CodeChunk] = []
        for doc in transformed_docs:
            chunk_result = self.to_code_chunk(doc)
            if isinstance(chunk_result, CodeChunk):
                chunks.append(chunk_result)
            else:
                # chunk_result is Sequence[CodeChunk]
                chunks.extend(chunk_result)
        return self._output_transformer(results, chunks)

    @staticmethod
    def to_code_chunk(text: StructuredDataInput) -> CodeChunk | Sequence[CodeChunk]:
        """Convert text to a CodeChunk."""
        if isinstance(text, list | tuple | set):
            return tuple(
                t if isinstance(t, CodeChunk) else CodeChunk.model_validate_json(t) for t in text
            )  # type: ignore[return-value]
        return text if isinstance(text, CodeChunk) else CodeChunk.model_validate_json(text)

    def _report_token_savings(
        self, results: Sequence[RerankingResult], processed_chunks: Sequence[str]
    ) -> None:
        """Report token savings from the reranking process."""
        if (context_saved := self._calculate_context_saved(results, processed_chunks)) > 0:
            statistics = get_statistics()
            statistics.add_token_usage(saved_by_reranking=context_saved)

    def _calculate_context_saved(
        self, results: Sequence[RerankingResult], processed_chunks: Sequence[str]
    ) -> int:
        """Calculate the context saved by the reranking process."""
        if len(results) == len(processed_chunks):
            return 0
        result_indices = {res.original_index for res in results}
        discarded_chunks = (
            chunk for i, chunk in enumerate(processed_chunks) if i not in result_indices
        )
        # Because we are working in terms of context saved from the *user's agent*, we need calculate tokens for the user's tokenizer.
        # To keep things simple, we default to `cl100k_base`, as this is the tokenizer used by most LLMs.
        tokenizer = get_tokenizer("tiktoken", "cl100k_base")
        return tokenizer.estimate_batch(discarded_chunks)  # pyright: ignore[reportArgumentType]

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

    def _store_value(self, key: str, value: Any) -> None:
        """Store a value in the simple store."""
        type(self)._store.set(key, value)

    def _get_stored_value(self, key: str) -> Any | None:
        """Get a value from the simple store."""
        return type(self)._store.get(key)
