# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# sourcery skip: avoid-single-character-names-variables
"""Provider for Sentence Transformers models."""

from __future__ import annotations

import asyncio
import logging

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, cast

import numpy as np

from beartype.typing import ClassVar

from codeweaver.core import (
    CodeChunk,
    CodeWeaverSparseEmbedding,
    ConfigurationError,
    Provider,
    rpartial,
)
from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    SparseEmbeddingModelCapabilities,
)
from codeweaver.providers.embedding.providers.base import (
    EmbeddingCustomDeps,
    EmbeddingImplementationDeps,
    EmbeddingProvider,
    SparseEmbeddingProvider,
)


logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    raise ConfigurationError(
        r'Please install the `sentence-transformers` package to use the Sentence Transformers provider, \nyou can use the `sentence-transformers` optional group -- `pip install "code-weaver\[sentence-transformers]"` or `code-weaver\[sentence-transformers-gpu]`'
    ) from e

# SparseEncoder is not available in all versions of sentence-transformers
# Import it conditionally for sparse embedding support
try:
    from sentence_transformers.sparse_encoder import SparseEncoder

    HAS_SPARSE_ENCODER = True
except ImportError:
    HAS_SPARSE_ENCODER = False
    # Create a placeholder for type hints
    if TYPE_CHECKING:
        SparseEncoder = Any  # type: ignore


def process_for_instruction_model(queries: Sequence[str], instruction: str) -> list[str]:
    """Process documents for instruction models."""

    def format_doc(query: str) -> str:
        """Format a document for the instruction model."""
        return f"Instruct: {instruction}\nQuery: {query}"

    return [format_doc(query) for query in queries]


class SentenceTransformersEmbeddingProvider(EmbeddingProvider[SentenceTransformer]):
    """Sentence Transformers embedding provider for dense embeddings."""

    client: SentenceTransformer
    provider: ClassVar[Literal[Provider.SENTENCE_TRANSFORMERS]] = Provider.SENTENCE_TRANSFORMERS
    caps: EmbeddingModelCapabilities | None = None

    def _initialize(
        self,
        impl_deps: EmbeddingImplementationDeps = None,
        custom_deps: EmbeddingCustomDeps = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the SentenceTransformer client."""
        # Nothing to initialize here - options are set in initialize_async

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the provider, if applicable."""
        return None

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a sequence of documents."""
        preprocessed = cast(list[str], self.chunks_to_strings(documents))
        if "nomic" in str(self.model_name):
            preprocessed = [f"search_document: {doc}" for doc in preprocessed]

        embed_partial = rpartial(self.client.encode_document, **self.embed_options)
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
            preprocessed = self.preprocess(preprocessed)
        elif "nomic" in str(self.model_name):
            preprocessed = [f"search_query: {query}" for query in preprocessed]
        # Filter incoming kwargs to remove dict structure keys before merging
        embed_partial = rpartial(self.client.encode_query, **self.query_options)
        loop = asyncio.get_running_loop()
        results: np.ndarray = await loop.run_in_executor(None, embed_partial, preprocessed)  # type: ignore
        _ = self._fire_and_forget(
            lambda: self._update_token_stats(from_docs=cast(list[str], preprocessed))
        )
        return results.tolist()

    @property
    def st_pooling_config(self) -> dict[str, Any]:
        """The pooling configuration for the SentenceTransformer."""
        if self.client is None:
            return {}
        # ty doesn't like these because the model doesn't exist statically
        if isinstance(self.client, SentenceTransformer) and callable(self.client[1]):
            return self.client[1].get_config_dict()  # type: ignore
        return {}

    @property
    def transformer_config(self) -> dict[str, Any]:
        """Returns the transformer configuration for the SentenceTransformer."""
        if self.client is None:
            return {}
        if isinstance(self.client, SentenceTransformer) and callable(self.client[0]):
            return self.client[0].get_config_dict()  # type: ignore
        return {}


# Use SparseEncoder if available, otherwise use Any as a placeholder
_SparseEncoderType = SparseEncoder if HAS_SPARSE_ENCODER else Any


class SentenceTransformersSparseProvider(SparseEmbeddingProvider[_SparseEncoderType]):
    """Sentence Transformers sparse embedding provider.

    This provider handles sparse embeddings from SparseEncoder models,
    returning properly formatted sparse embeddings with indices and values.

    Note: This provider requires SparseEncoder which may not be available in all
    versions of sentence-transformers. The __init__ method will raise ConfigurationError
    if SparseEncoder is not available.
    """

    client: _SparseEncoderType
    provider: Provider = Provider.SENTENCE_TRANSFORMERS
    caps: SparseEmbeddingModelCapabilities | None = None

    def __init__(
        self,
        client: _SparseEncoderType,
        caps: SparseEmbeddingModelCapabilities | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Sentence Transformers sparse embedding provider.

        Args:
            caps: Model capabilities (matches base class parameter name)
            client: Optional pre-initialized SparseEncoder client
            **kwargs: Additional keyword arguments
        """
        if not HAS_SPARSE_ENCODER:
            raise ConfigurationError(
                "SparseEncoder is not available in the installed version of sentence-transformers. "
                "Sparse embedding support may require a different version or additional dependencies."
            )

        # Call super().__init__ with None for client if not provided
        # We'll initialize it asynchronously in initialize_async
        super().__init__(client=client, caps=caps, kwargs=kwargs)  # type: ignore

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the provider, if applicable."""
        return None

    def _to_sparse_format(self, embedding: Any) -> CodeWeaverSparseEmbedding:
        """Convert embedding to sparse format with indices and values."""
        if hasattr(embedding, "indices") and hasattr(embedding, "values"):
            return CodeWeaverSparseEmbedding(
                indices=list(embedding.indices), values=list(embedding.values)
            )
        return CodeWeaverSparseEmbedding(
            indices=list(embedding.get("indices", [])), values=list(embedding.get("values", []))
        )

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[CodeWeaverSparseEmbedding]:
        """Embed a sequence of documents into sparse vectors."""
        preprocessed = cast(list[str], self.chunks_to_strings(documents))
        embed_partial = rpartial(self.client.encode, **(self.client_options | kwargs))
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, embed_partial, preprocessed)
        _ = self._fire_and_forget(lambda: self._update_token_stats(from_docs=preprocessed))

        formatted_results = [self._to_sparse_format(emb) for emb in results]
        self._update_token_stats(token_count=sum(len(emb.indices) for emb in formatted_results))
        return formatted_results

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[CodeWeaverSparseEmbedding]:
        """Embed a sequence of queries into sparse vectors."""
        preprocessed = cast(list[str], query)
        embed_partial = rpartial(self.client.encode, **(self.query_options | kwargs))
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, embed_partial, preprocessed)
        _ = self._fire_and_forget(lambda: self._update_token_stats(from_docs=preprocessed))

        formatted_results = [self._to_sparse_format(emb) for emb in results]
        self._update_token_stats(token_count=sum(len(emb.indices) for emb in formatted_results))
        return formatted_results


__all__ = ("SentenceTransformersEmbeddingProvider", "SentenceTransformersSparseProvider")
