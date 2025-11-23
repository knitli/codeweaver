# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: avoid-single-character-names-variables
"""Provider for Sentence Transformers models."""

from __future__ import annotations

import asyncio

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, ClassVar, cast

import numpy as np

from codeweaver.common.utils.utils import rpartial
from codeweaver.exceptions import ConfigurationError
from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    SparseEmbeddingModelCapabilities,
)
from codeweaver.providers.embedding.providers.base import EmbeddingProvider, SparseEmbeddingProvider
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.providers.embedding.types import SparseEmbedding


try:
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    raise ConfigurationError(
        'Please install the `sentence-transformers` package to use the Sentence Transformers provider, \nyou can use the `sentence-transformers` optional group — `pip install "codeweaver[sentence-transformers]"` or `codeweaver[sentence-transformers-gpu]`'
    ) from e

# SparseEncoder is not available in all versions of sentence-transformers
# Import it conditionally for sparse embedding support
try:
    from sentence_transformers.sparse_encoder import SparseEncoder  # ty: ignore[unresolved-import]

    HAS_SPARSE_ENCODER = True
except ImportError:
    HAS_SPARSE_ENCODER = False
    # Create a placeholder for type hints
    if TYPE_CHECKING:
        SparseEncoder = Any  # type: ignore


def default_client_args(model: str, *, query: bool = False) -> dict[str, Any]:
    """Get default client arguments for a specific model."""
    extra: dict[str, Any] = {}
    float16 = {"model_kwargs": {"torch_dtype": "torch.float16"}}
    if "qwen3" in model.lower():
        extra = {
            "instruction": "Given search results containing code snippets, tree-sitter parse trees, documentation and code comments from a codebase, retrieve relevant Documents that answer the Query.",
            "tokenizer_kwargs": {"padding_side": "left"},
            **float16,
        }
    if "bge" in model.lower() and "m3" not in model.lower() and query:
        extra = {
            "prompt_name": "query",
            "prompts": {
                "query": {"text": "Represent this sentence for searching relevant passages:"}
            },
            **float16,
        }
    if "snowflake" in model.lower() and "v2.0" in model.lower():
        extra = {"prompt_name": "query"}  # only for query embeddings
    if "intfloat" in model.lower() and "instruct" not in model.lower():
        extra = {"prompt_name": "query"} if query else {"prompt_name": "document"}
    if "jina" in model.lower() and "v2" not in model.lower():
        if "v4" in model.lower():
            extra = (
                {"prompt_name": "query", "task": "code"}
                if query
                else {"task": "code", "prompt_name": "passage"}
            )
        else:
            extra = (
                {"task": "retrieval.query", "prompt_name": "query"}
                if query
                else {"task": "retrieval.passage"}
            )
    if "nomic" in model.lower():
        extra = {"tokenizer_kwargs": {"padding": True}}
    return {
        "model_name_or_path": model,
        "normalize_embeddings": True,
        "trust_remote_code": True,
        **extra,
    }


def process_for_instruction_model(queries: Sequence[str], instruction: str) -> list[str]:
    """Process documents for instruction models."""

    def format_doc(query: str) -> str:
        """Format a document for the instruction model."""
        return f"Instruct: {instruction}\nQuery: {query}"

    return [format_doc(query) for query in queries]


class SentenceTransformersEmbeddingProvider(EmbeddingProvider[SentenceTransformer]):
    """Sentence Transformers embedding provider for dense embeddings."""

    client: SentenceTransformer
    _provider: Provider = Provider.SENTENCE_TRANSFORMERS
    caps: EmbeddingModelCapabilities

    _doc_kwargs: ClassVar[dict[str, Any]] = {"client_options": {"trust_remote_code": True}}
    _query_kwargs: ClassVar[dict[str, Any]] = {"client_options": {"trust_remote_code": True}}

    def __init__(
        self,
        capabilities: EmbeddingModelCapabilities,
        client: SentenceTransformer | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Sentence Transformers embedding provider."""
        # Initialize client if not provided
        if client is None:
            doc_kwargs = {**type(self)._doc_kwargs, **(kwargs or {})}
            client = SentenceTransformer(
                model_name_or_path=capabilities.name, **doc_kwargs.get("client_options", {})
            )

        # Call super().__init__() FIRST which handles all Pydantic initialization
        # The base class will set doc_kwargs, query_kwargs, and call _initialize()
        super().__init__(client=client, caps=capabilities, kwargs=kwargs)

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the provider, if applicable."""
        return None

    def _initialize(self, caps: EmbeddingModelCapabilities) -> None:
        """Initialize the Sentence Transformers embedding provider."""
        # Set _caps for later use
        self.caps = caps

        for keyword_args in (self.doc_kwargs, self.query_kwargs):
            keyword_args.setdefault("client_options", {})
            if "normalize_embeddings" not in keyword_args["client_options"]:
                keyword_args["client_options"]["normalize_embeddings"] = True
            if "trust_remote_code" not in keyword_args["client_options"]:
                keyword_args["client_options"]["trust_remote_code"] = True
            if (
                "model_name" not in keyword_args["client_options"]
                and "model_name_or_path" not in keyword_args["client_options"]
            ):
                keyword_args["client_options"]["model_name_or_path"] = caps.name

        # Extract model name for potential use
        name = (
            self.doc_kwargs.pop("model_name", None)
            or self.doc_kwargs.pop("model_name_or_path", None)
            or caps.name
        )
        self.query_kwargs.pop("model_name", None)
        self.query_kwargs.pop("model_name_or_path", None)

        # Note: _client is already set by __init__ when client is provided
        # The old code here (self.client = self.client(name, ...)) was incorrect
        # as it tried to call an instance as if it were a class

        if (
            (other := caps.other)
            and (model := other.get("model_kwargs", {}))
            and (instruction := model.get("instruction"))
        ):
            self.preprocess = rpartial(process_for_instruction_model, instruction=instruction)

        if "Qwen3" in name:
            self._setup_qwen3()

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a sequence of documents."""
        preprocessed = cast(list[str], self.chunks_to_strings(documents))
        if "nomic" in self.model_name:
            preprocessed = [f"search_document: {doc}" for doc in preprocessed]
        embed_partial = rpartial(  # type: ignore
            self.client.encode,  # type: ignore
            **(
                self.doc_kwargs.get("client_options", {})
                | {"model_kwargs": self.doc_kwargs.get("model_kwargs", {})}
                | {**kwargs, "convert_to_numpy": True}
            ),
        )
        loop = asyncio.get_running_loop()
        results: np.ndarray = await loop.run_in_executor(None, embed_partial, preprocessed)  # type: ignore
        _ = self._fire_and_forget(lambda: self._update_token_stats(from_docs=preprocessed))
        return results.tolist()

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a sequence of queries."""
        preprocessed = cast(list[str], query)
        if "qwen3" in self.model_name.lower() or "instruct" in self.model_name.lower():
            preprocessed = self.preprocess(preprocessed)  # type: ignore
        elif "nomic" in self.model_name:
            preprocessed = [f"search_query: {query}" for query in preprocessed]
        embed_partial = rpartial(  # type: ignore
            self.client.encode,  # type: ignore
            **(
                self.query_kwargs.get("client_options", {})
                | {"model_kwargs": self.query_kwargs.get("model_kwargs", {})}
                | {**kwargs, "convert_to_numpy": True}
            ),
        )
        loop = asyncio.get_running_loop()
        results: np.ndarray = await loop.run_in_executor(None, embed_partial, preprocessed)  # type: ignore
        _ = self._fire_and_forget(
            lambda: self._update_token_stats(from_docs=cast(list[str], preprocessed))
        )
        return results.tolist()

    @property
    def st_pooling_config(self) -> dict[str, Any]:
        """The pooling configuration for the SentenceTransformer."""
        # ty doesn't like these because the model doesn't exist statically
        if isinstance(self.client, SentenceTransformer) and callable(self.client[1]):  # type: ignore
            return self.client[1].get_config_dict()  # type: ignore
        return {}

    @property
    def transformer_config(self) -> dict[str, Any]:
        """Returns the transformer configuration for the SentenceTransformer."""
        if isinstance(self.client, SentenceTransformer) and callable(self.client[0]):  # type: ignore
            return self.client[0].get_config_dict()  # type: ignore
        return {}

    def _setup_qwen3(self) -> None:
        """Sets up Qwen3 specific parameters."""
        if "Qwen3" not in (
            self.doc_kwargs.get("model_name", ""),
            self.doc_kwargs.get("model_name_or_path", ""),
        ):
            return
        from importlib import metadata

        try:
            has_flash_attention = metadata.version("flash_attn")
        except Exception:
            has_flash_attention = None
        if has_flash_attention:
            self.doc_kwargs["client_options"]["model_kwargs"]["attention_implementation"] = (
                "flash_attention_2"
            )


# Use SparseEncoder if available, otherwise use Any as a placeholder
_SparseEncoderType = SparseEncoder if HAS_SPARSE_ENCODER else Any  # type: ignore


class SentenceTransformersSparseProvider(SparseEmbeddingProvider[_SparseEncoderType]):  # type: ignore
    """Sentence Transformers sparse embedding provider.

    This provider handles sparse embeddings from SparseEncoder models,
    returning properly formatted sparse embeddings with indices and values.

    Note: This provider requires SparseEncoder which may not be available in all
    versions of sentence-transformers. The __init__ method will raise ConfigurationError
    if SparseEncoder is not available.
    """

    client: _SparseEncoderType  # type: ignore
    _provider: Provider = Provider.SENTENCE_TRANSFORMERS
    caps: SparseEmbeddingModelCapabilities

    _doc_kwargs: ClassVar[dict[str, Any]] = {"client_options": {"trust_remote_code": True}}
    _query_kwargs: ClassVar[dict[str, Any]] = {"client_options": {"trust_remote_code": True}}

    def __init__(
        self,
        capabilities: SparseEmbeddingModelCapabilities,
        client: _SparseEncoderType | None = None,  # type: ignore
        **kwargs: Any,
    ) -> None:
        """Initialize the Sentence Transformers sparse embedding provider."""
        if not HAS_SPARSE_ENCODER:
            raise ConfigurationError(
                "SparseEncoder is not available in the installed version of sentence-transformers. "
                "Sparse embedding support may require a different version or additional dependencies."
            )

        # Initialize client if not provided
        if client is None:
            doc_kwargs = {**type(self)._doc_kwargs, **(kwargs or {})}
            client = _SparseEncoderType(  # type: ignore
                model_name_or_path=capabilities.name, **doc_kwargs.get("client_options", {})
            )

        # Call super().__init__() FIRST which handles all Pydantic initialization
        # The base class will set doc_kwargs, query_kwargs, and call _initialize()
        super().__init__(client=client, caps=capabilities, kwargs=kwargs)  # type: ignore

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the provider, if applicable."""
        return None

    def _initialize(self, caps: EmbeddingModelCapabilities) -> None:
        """Initialize the Sentence Transformers sparse embedding provider."""
        # Set _caps for later use
        self.caps = caps  # type: ignore

        for keyword_args in (self.doc_kwargs, self.query_kwargs):
            keyword_args.setdefault("client_options", {})
            if "trust_remote_code" not in keyword_args["client_options"]:
                keyword_args["client_options"]["trust_remote_code"] = True
            if (
                "model_name" not in keyword_args["client_options"]
                and "model_name_or_path" not in keyword_args["client_options"]
            ):
                keyword_args["client_options"]["model_name_or_path"] = caps.name
        self.doc_kwargs.pop("model_name", None) or self.doc_kwargs.pop("model_name_or_path", None)
        self.query_kwargs.pop("model_name", None)
        self.query_kwargs.pop("model_name_or_path", None)

        # Note: _client is already set by __init__ when client is provided
        # The old code here (self.client = SparseEncoder(name, ...)) was incorrect
        # as it tried to re-initialize an already-initialized client

    def _to_sparse_format(self, embedding: Any) -> SparseEmbedding:
        """Convert embedding to sparse format with indices and values."""
        from codeweaver.providers.embedding.types import SparseEmbedding

        if hasattr(embedding, "indices") and hasattr(embedding, "values"):
            return SparseEmbedding(indices=list(embedding.indices), values=list(embedding.values))
        return SparseEmbedding(
            indices=list(embedding.get("indices", [])), values=list(embedding.get("values", []))
        )

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[SparseEmbedding]:
        """Embed a sequence of documents into sparse vectors."""
        preprocessed = cast(list[str], self.chunks_to_strings(documents))
        embed_partial = rpartial(  # type: ignore
            self.client.encode,  # type: ignore
            **(
                self.doc_kwargs.get("client_options", {})
                | {"model_kwargs": self.doc_kwargs.get("model_kwargs", {})}
                | kwargs
            ),
        )
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, embed_partial, preprocessed)  # type: ignore
        _ = self._fire_and_forget(lambda: self._update_token_stats(from_docs=preprocessed))

        formatted_results = [self._to_sparse_format(emb) for emb in results]
        self._update_token_stats(token_count=sum(len(emb.indices) for emb in formatted_results))
        return formatted_results

    async def _embed_query(self, query: Sequence[str], **kwargs: Any) -> list[SparseEmbedding]:
        """Embed a sequence of queries into sparse vectors."""
        preprocessed = cast(list[str], query)
        embed_partial = rpartial(  # type: ignore
            self.client.encode,  # type: ignore
            **(
                self.query_kwargs.get("client_options", {})
                | {"model_kwargs": self.query_kwargs.get("model_kwargs", {})}
                | kwargs
            ),
        )
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, embed_partial, preprocessed)  # type: ignore
        _ = self._fire_and_forget(lambda: self._update_token_stats(from_docs=preprocessed))

        formatted_results = [self._to_sparse_format(emb) for emb in results]
        self._update_token_stats(token_count=sum(len(emb.indices) for emb in formatted_results))
        return formatted_results


__all__ = ("SentenceTransformersEmbeddingProvider", "SentenceTransformersSparseProvider")
