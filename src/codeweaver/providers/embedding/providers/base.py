# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Base class for embedding providers."""

import asyncio
import logging

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Mapping, Sequence
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    NotRequired,
    Required,
    TypedDict,
    cast,
    overload,
)
from uuid import UUID

from pydantic import UUID7, ConfigDict
from pydantic.main import IncEx

from codeweaver.common import LazyImport, lazy_import, uuid7
from codeweaver.core import (
    BasedModel,
    BlakeStore,
    CodeChunk,
    SerializedCodeChunk,
    StructuredDataInput,
    UUIDStore,
    make_blake_store,
    make_uuid_store,
)
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.provider import Provider
from codeweaver.tokenizers import Tokenizer, get_tokenizer


statistics_module: LazyImport[ModuleType] = lazy_import("codeweaver.common.statistics")

if TYPE_CHECKING:
    from codeweaver.common import SessionStatistics
else:
    SessionStatistics = statistics_module.SessionStatistics

_get_statistics: LazyImport[SessionStatistics] = lazy_import(
    "codeweaver.common.statistics", "get_statistics"
)

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
        extra={"output_data": output},  # pyright: ignore[reportUnknownArgumentType]
    )
    raise ValueError("Unexpected output format from embedding provider.")


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

    model_config = BasedModel.model_config | ConfigDict(extra="allow", arbitrary_types_allowed=True)

    _client: EmbeddingClient
    _provider: Provider
    _caps: EmbeddingModelCapabilities

    _input_transformer: ClassVar[Callable[[StructuredDataInput], Any]] = default_input_transformer
    _output_transformer: ClassVar[Callable[[Any], list[list[float]] | list[list[int]]]] = (
        default_output_transformer
    )
    _doc_kwargs: ClassVar[dict[str, Any]] = {}
    _query_kwargs: ClassVar[dict[str, Any]] = {}

    # Typing note: we can't type this properly because: 1) Pyright wants us to define the subtype for `list` and 2) pydantic does not support parameterized subtypes for generics.
    _store: UUIDStore[list] = make_uuid_store(  # type: ignore
        value_type=list, size_limit=1024 * 1024 * 3
    )

    """The store for embedding documents, keyed by batch ID (UUID7) and stored as a batch of CodeChunks."""
    _hash_store: ClassVar[BlakeStore[UUID7]] = make_blake_store(
        value_type=UUID, size_limit=1024 * 256
    )  # 256kb limit -- we're just storing hashes
    """A store for deduplicating CodeChunks based on their content hash. The keys are each CodeChunk's content hash, the values are their batch IDs.

    Note that we're only storing the hash keys and batch ID values, not the full CodeChunk objects. This keeps the store size small. We can lookup by batch ID in the main `_store` if needed, or if it has been ejected, in the `_store`'s `_trash_heap`. `SimpleTypedStore`, the parent class, handles that for us with a simple "get" method.
    """

    def __init__(
        self,
        client: EmbeddingClient,
        caps: EmbeddingModelCapabilities,
        kwargs: dict[str, Any] | None,
    ) -> None:
        """Initialize the embedding provider."""
        self._model_dump_json = super().model_dump_json
        self._client = client
        self._caps = caps
        if not self._provider:
            self._provider = caps.provider
        self.doc_kwargs = type(self)._doc_kwargs.copy() or {}
        self.query_kwargs = type(self)._query_kwargs.copy() or {}
        self._add_kwargs(kwargs or {})
        """Add any user-provided kwargs to the embedding provider, after we merge the defaults together."""
        self._store: UUIDStore[list] = make_uuid_store(value_type=list, size_limit=1024 * 1024 * 3)  # type: ignore # 3mb limit
        self._initialize()

    def _add_kwargs(self, kwargs: dict[str, Any]) -> None:
        """Add keyword arguments to the embedding provider."""
        if not kwargs:
            return
        self.doc_kwargs = {**self.doc_kwargs, **kwargs}
        self.query_kwargs = {**self.query_kwargs, **kwargs}

    @abstractmethod
    def _initialize(self) -> None:
        """Initialize the embedding provider.

        This method is called at the end of __init__ to allow for any additional setup.
        It should minimally set up `_doc_kwargs` and `_query_kwargs` if they are not already set.
        """

    @property
    def name(self) -> Provider:
        """Get the name of the embedding provider."""
        return self._provider

    @property
    @abstractmethod
    def base_url(self) -> str | None:
        """Get the base URL of the embedding provider, if any."""

    @abstractmethod
    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Mapping[str, Any] | None
    ) -> list[list[float]] | list[list[int]]:
        """Abstract method to implement document embedding logic."""

    def _handle_embedding_error(
        self,
        error: Exception,
        batch_id: UUID7 | None,
        documents: Sequence[CodeChunk] | None,
        queries: Sequence[str] | None,
    ) -> EmbeddingErrorInfo:
        """Handle errors that occur during embedding."""
        logger.exception(
            "Error occurred during document embedding. Batch ID: %s failed during `embed_documents`",
            batch_id,
            extra={"documents": documents, "batch_id": batch_id},
        )
        if queries:
            return EmbeddingErrorInfo(error=str(error), queries=queries)
        return EmbeddingErrorInfo(error=str(error), batch_id=batch_id, documents=documents)

    async def embed_documents(
        self,
        documents: Sequence[CodeChunk],  # type: ignore # intentionally obscurred
        *,
        batch_id: UUID7 | None = None,
        **kwargs: Mapping[str, Any] | None,
    ) -> list[list[float]] | list[list[int]] | EmbeddingErrorInfo:
        """Embed a list of documents into vectors.

        Optionally takes a `batch_id` parameter to reprocess a specific batch of documents.
        """
        is_old_batch = False
        if batch_id and self._store and batch_id in self._store:  # pyright: ignore[reportUnknownMemberType]
            documents: Sequence[CodeChunk] = self._store[batch_id]  # type: ignore
            is_old_batch = True
        chunks, cache_key = self._process_input(documents, is_old_batch=is_old_batch)  # type: ignore
        try:
            results: (
                Sequence[Sequence[float]] | Sequence[Sequence[int]]
            ) = await self._embed_documents(tuple(chunks), **kwargs)
        except Exception as e:
            return self._handle_embedding_error(e, batch_id or cache_key, documents or [], None)  # type: ignore
        else:
            return results

    @abstractmethod
    async def _embed_query(
        self, query: Sequence[str], **kwargs: Mapping[str, Any] | None
    ) -> list[list[float]] | list[list[int]]:
        """Abstract method to implement query embedding logic."""

    async def embed_query(
        self, query: str | Sequence[str], **kwargs: Mapping[str, Any] | None
    ) -> list[list[float]] | list[list[int]] | EmbeddingErrorInfo:
        """Embed a query into a vector."""
        processed_kwargs: Mapping[str, Any] = self._set_kwargs(self.query_kwargs, kwargs or {})
        queries: Sequence[str] = query if isinstance(query, list | tuple | set) else [query]  # pyright: ignore[reportAssignmentType]
        try:
            results: Sequence[Sequence[float]] | Sequence[Sequence[int]] = await self._embed_query(
                queries, **processed_kwargs
            )  # pyright: ignore[reportUnknownVariableType, reportGeneralTypeIssues]
        except Exception as e:
            return self._handle_embedding_error(e, batch_id=None, documents=None, queries=queries)
        else:
            return results

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Get the size of the vector for the collection."""

    @property
    def client(self) -> EmbeddingClient:
        """Get the client for the embedding provider."""
        return self._client

    @property
    def model_name(self) -> str:
        """Get the model name for the embedding provider."""
        return self._caps.name

    @property
    def model_capabilities(self) -> EmbeddingModelCapabilities | None:
        """Get the model capabilities for the embedding provider."""
        return self._caps

    def _tokenizer(self) -> Tokenizer[Any]:
        """Get the tokenizer for the embedding provider."""
        if defined_tokenizer := self._caps.tokenizer:
            return get_tokenizer(defined_tokenizer, self._caps.tokenizer_model or self._caps.name)
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
    def _update_token_stats(self, *, token_count: int, from_docs: None = None) -> None: ...
    @overload
    def _update_token_stats(
        self, *, from_docs: Sequence[str] | Sequence[Sequence[str]], token_count: None = None
    ) -> None: ...
    def _update_token_stats(
        self,
        *,
        token_count: int | None = None,
        from_docs: Sequence[str] | Sequence[Sequence[str]] | None = None,
    ) -> None:
        """Update token statistics for the embedding provider."""
        statistics: SessionStatistics = _get_statistics()
        if token_count is not None:
            statistics.add_token_usage(embedding_generated=token_count)
        elif from_docs and all(isinstance(doc, str) for doc in from_docs):
            token_count = (
                self.tokenizer.estimate_batch(from_docs)  # pyright: ignore[reportArgumentType]
                if all(isinstance(doc, str) for doc in from_docs)
                else sum(self.tokenizer.estimate_batch(item) for item in from_docs)  # type: ignore
            )
            statistics.add_token_usage(embedding_generated=token_count)
        raise ValueError(
            "Either `token_count` or `from_docs` must be provided to update token statistics."
        )

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
            raise ValueError("Embedding contains non-finite values.")
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
    def chunks_to_strings(chunks: Sequence[CodeChunk]) -> Sequence[SerializedCodeChunk[CodeChunk]]:
        """Convert a sequence of CodeChunk objects to their string representations."""
        return [chunk.serialize_for_embedding() for chunk in chunks if chunk]

    @staticmethod
    def _set_kwargs(
        instance_kwargs: Mapping[str, Any], passed_kwargs: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Set keyword arguments for the embedding provider."""
        passed_kwargs = passed_kwargs or {}
        return cast(dict[str, Any], instance_kwargs) | cast(dict[str, Any], passed_kwargs)

    def _process_input(
        self, input_data: StructuredDataInput, *, is_old_batch: bool = False
    ) -> tuple[Iterator[CodeChunk], UUID7 | None]:
        """Process input data for embedding."""
        processed_chunks = default_input_transformer(input_data)
        if is_old_batch:
            return processed_chunks, None
        key = uuid7()
        hashes = [self._hash_store.keygen.__call__(chunk.content) for chunk in processed_chunks]
        for i, chunk in enumerate(processed_chunks):
            chunk.set_batch_id(key)
            if hashes[i] not in self._hash_store:
                self._hash_store[hashes[i]] = key
            else:
                chunk = None
        final_chunks = [chunk for chunk in processed_chunks if chunk]
        if self._store:  # type: ignore
            self._store[key] = final_chunks  # type: ignore
        return iter(final_chunks), key

    def _process_output(self, output_data: Any) -> list[list[float]] | list[list[int]]:
        """Handle output data from embedding."""
        return self._output_transformer(output_data)

    def _fire_and_forget(self, task: Callable[..., Any]) -> None:
        """Execute a fire-and-forget task."""
        try:
            loop = asyncio.get_event_loop()
            _ = loop.run_in_executor(None, task)
        except Exception:
            logger.exception("Error occurred while executing fire-and-forget task.")

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


__all__ = ("EmbeddingErrorInfo", "EmbeddingProvider")
