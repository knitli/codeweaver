# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: avoid-single-character-names-variables
"""Provider for Sentence Transformers models."""

import asyncio

from collections.abc import Sequence
from typing import Any, ClassVar, cast

import numpy as np

from codeweaver.common.utils.utils import rpartial
from codeweaver.core import CodeChunk
from codeweaver.exceptions import ConfigurationError
from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    SparseEmbeddingModelCapabilities,
)
from codeweaver.providers.embedding.providers.base import EmbeddingProvider
from codeweaver.providers.provider import Provider


try:
    from sentence_transformers import SentenceTransformer, SparseEncoder
except ImportError as e:
    raise ConfigurationError(
        'Please install the `sentence-transformers` package to use the Sentence Transformers provider, \nyou can use the `sentence-transformers` optional group — `pip install "codeweaver[sentence-transformers]"` or `codeweaver[sentence-transformers-gpu]`'
    ) from e


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


class SentenceTransformersEmbeddingProvider(EmbeddingProvider[SentenceTransformer | SparseEncoder]):
    """Sentence Transformers embedding provider."""

    _client: SentenceTransformer | SparseEncoder
    _provider: Provider = Provider.SENTENCE_TRANSFORMERS
    _caps: EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities  # pyright: ignore[reportIncompatibleVariableOverride]

    _doc_kwargs: ClassVar[dict[str, Any]] = {"client_kwargs": {"trust_remote_code": True}}
    _query_kwargs: ClassVar[dict[str, Any]] = {"client_kwargs": {"trust_remote_code": True}}

    def __init__(
        self,
        capabilities: EmbeddingModelCapabilities,
        client: SentenceTransformer | SparseEncoder | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Sentence Transformers embedding provider."""
        self._caps = capabilities  # pyright: ignore[reportIncompatibleVariableOverride]
        self.doc_kwargs = {**self._doc_kwargs, **(kwargs or {})}
        self.query_kwargs = {**self._query_kwargs, **(kwargs or {})}
        if client is None:
            _client = (
                SentenceTransformer
                if isinstance(self._caps, EmbeddingModelCapabilities)  # pyright: ignore[reportUnnecessaryIsInstance]
                else SparseEncoder
            )
            self._client = _client(
                model_name_or_path=capabilities.name, **self.doc_kwargs["client_kwargs"]
            )
        else:
            self._client = client
        super().__init__(caps=capabilities, client=self._client, **kwargs)

    def _initialize(self) -> None:
        """Initialize the Sentence Transformers embedding provider."""
        for keyword_args in (self.doc_kwargs, self.query_kwargs):
            keyword_args.setdefault("client_kwargs", {})
            if "normalize_embeddings" not in keyword_args["client_kwargs"]:
                keyword_args["client_kwargs"]["normalize_embeddings"] = True
            if "trust_remote_code" not in keyword_args["client_kwargs"]:
                keyword_args["client_kwargs"]["trust_remote_code"] = True
            if (
                "model_name" not in keyword_args["client_kwargs"]
                and "model_name_or_path" not in keyword_args["client_kwargs"]
            ):
                keyword_args["client_kwargs"]["model_name_or_path"] = self._caps.name
        name = self.doc_kwargs.pop("model_name", self.doc_kwargs.pop("model_name_or_path"))
        self.query_kwargs.pop("model_name", self.query_kwargs.pop("model_name_or_path", None))
        self._client = self._client(name, **(self.doc_kwargs or {}))
        if (
            (other := self._caps.other)
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
            self._client.encode,  # type: ignore
            **(
                self.doc_kwargs.get("client_kwargs", {})
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
            self._client.encode,  # type: ignore
            **(
                self.query_kwargs.get("client_kwargs", {})
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
        # pyright doesn't like these because the model doesn't exist statically
        if isinstance(self._client, SentenceTransformer) and callable(self._client[1]):  # type: ignore
            return self._client[1].get_config_dict()  # type: ignore
        return {}

    @property
    def transformer_config(self) -> dict[str, Any]:
        """Returns the transformer configuration for the SentenceTransformer."""
        if isinstance(self._client, SentenceTransformer) and callable(self._client[0]):  # type: ignore
            return self._client[0].get_config_dict()  # type: ignore
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
            self.doc_kwargs["client_kwargs"]["model_kwargs"]["attention_implementation"] = (
                "flash_attention_2"
            )

    def _decode_sparse_vectors(
        self, vectors: Sequence[Sequence[float]]
    ) -> list[list[tuple[str, float]]]:
        """Decode sparse vectors from the model output."""
        if not isinstance(self._client, SparseEncoder):
            raise TypeError("The model is not a SparseEncoder.")
        return cast(list[list[tuple[str, float]]], self._client.decode(vectors))  # type: ignore


__all__ = ("SentenceTransformersEmbeddingProvider",)
