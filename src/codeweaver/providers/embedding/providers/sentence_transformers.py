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

    # No custom __init__ — inherit from `SparseEmbeddingProvider` which takes
    # `client, config, registry, cache_manager, caps, impl_deps, custom_deps,
    # **kwargs`. The previous override only declared `(client, caps, **kwargs)`
    # and then called `super().__init__(client=client, caps=caps, kwargs=kwargs)`
    # (literal `kwargs=` arg, not splat), both of which were broken:
    #   - Dropped required base-class args (config/registry/cache_manager)
    #     into **kwargs where the base init couldn't see them as named args.
    #   - Passed `kwargs=kwargs` instead of `**kwargs`, so even the drained
    #     kwargs never reached the base init.
    # The sibling `SentenceTransformersEmbeddingProvider` at line 71 has no
    # custom __init__ either and works fine through the base class's init
    # path, which calls `self._initialize(impl_deps, custom_deps, **kwargs)`
    # at line 307 of providers/embedding/providers/base.py. Same pattern here.

    def _initialize(self, impl_deps: Any = None, custom_deps: Any = None, **kwargs: Any) -> None:
        """Initialize the SparseEncoder-backed sparse provider.

        Called from `EmbeddingProvider.__init__` at line 307 after required
        fields (client, config, registry, cache_manager, embed/query options,
        namespace) have been set but before the pydantic `super().__init__`
        finalizes the model.

        Two responsibilities:

          1. Guard against a sentence-transformers version that doesn't ship
             `SparseEncoder`. In practice the `_SparseEncoderType` class-level
             alias would already resolve to `Any` (via the `HAS_SPARSE_ENCODER`
             check at module import), and the service card's lateimport of
             `SparseEncoder` would fail before we got here — but keep the
             defensive check so the failure message is specific and
             actionable instead of a confusing downstream `AttributeError`.

          2. Everything else is a no-op. The SparseEncoder instance is
             instantiated upstream by the service card's
             `_start_filtered_instance_in_thread` handler (which calls
             `SparseEncoder(**filtered_client_options)`) and passed into the
             base class's `__init__` as the `client` parameter. By the time
             `_initialize` runs, `self.client` is already a valid
             SparseEncoder instance and there's nothing left to do.

        Required by `SparseEmbeddingProvider.__abstractmethods__`; without
        this override the class can't be instantiated.
        """
        if not HAS_SPARSE_ENCODER:
            raise ConfigurationError(
                "SparseEncoder is not available in the installed version of "
                "sentence-transformers. CodeWeaver requires "
                "sentence-transformers>=4 for SparseEncoder support; we pin "
                "major 5."
            )
        # Nothing further to initialize — the SparseEncoder instance was
        # supplied to the base-class __init__ via the service card dispatch
        # chain, and embed/query options are set on self by the base init
        # before this method runs.

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
        # Use `embed_options` (set by the base class's __init__ from
        # config.sparse_embedding_config.embedding) rather than the
        # nonexistent `client_options` attribute. Previously this line
        # read `self.client_options | kwargs` which silently fell through
        # to a bound method from the pydantic BaseModel (probably
        # `model_copy` — every `foo_options` name happens to shadow
        # nothing, but `client_options` didn't, so Python resolved the
        # attribute via pydantic's __getattr__ which returns bound
        # methods). `method | dict` raises TypeError at call time, not
        # attribute-access time, so the bug was silent until the full
        # search pipeline actually reached this method with real
        # documents. Mirrors the dense sibling
        # `SentenceTransformersEmbeddingProvider._embed_documents` which
        # uses `self.embed_options` on line 100.
        embed_partial = rpartial(self.client.encode, **(self.embed_options | kwargs))
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
        # `self.query_options` IS a valid base-class attribute (set
        # alongside `embed_options` in the parent __init__), so the
        # query path worked even when the document path was broken.
        # Kept explicit here for symmetry with `_embed_documents`.
        embed_partial = rpartial(self.client.encode, **(self.query_options | kwargs))
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, embed_partial, preprocessed)
        _ = self._fire_and_forget(lambda: self._update_token_stats(from_docs=preprocessed))

        formatted_results = [self._to_sparse_format(emb) for emb in results]
        self._update_token_stats(token_count=sum(len(emb.indices) for emb in formatted_results))
        return formatted_results


__all__ = (
    "SentenceTransformersEmbeddingProvider",
    "SentenceTransformersSparseProvider",
    "process_for_instruction_model",
)
