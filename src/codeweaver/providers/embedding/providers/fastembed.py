# sourcery skip: lambdas-should-be-short, no-complex-if-expressions
# SPDX=FileCopyrightText: 2024-2025 (c) Qdrant Solutions GmBh
# SPDX-LicenseIdentifier: Apache-2.0
# This file is partly derived from code in the `mcp-server-qdrant` project
#
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""FastEmbed embedding provider implementation.

FastEmbed is a lightweight and efficient library for generating embeddings locally.
"""

from __future__ import annotations

import asyncio
import logging

from collections.abc import Callable, Iterable, Sequence
from typing import Any, ClassVar, Literal, cast, override

import numpy as np

from pydantic import SkipValidation

from codeweaver.core import (
    CodeChunk,
    CodeWeaverSparseEmbedding,
    ConfigurationError,
    Provider,
    rpartial,
)
from codeweaver.providers.embedding.capabilities.base import SparseEmbeddingModelCapabilities
from codeweaver.providers.embedding.providers.base import (
    EmbeddingCustomDeps,
    EmbeddingImplementationDeps,
    EmbeddingProvider,
    SparseEmbeddingProvider,
)


try:
    from fastembed.sparse import SparseTextEmbedding
    from fastembed.text import TextEmbedding

    from codeweaver.providers.embedding.fastembed_extensions import (
        get_sparse_embedder,
        get_text_embedder,
    )
except ImportError as e:
    raise ConfigurationError(
        r"FastEmbed is not installed. Please install it with `pip install code-weaver\[fastembed]` or `code-weaver\[fastembed-gpu]`."
    ) from e

_TextEmbedding = get_text_embedder()
_SparseTextEmbedding = get_sparse_embedder()


logger = logging.getLogger(__name__)


def fastembed_output_transformer(output: list[np.ndarray]) -> list[list[float]] | list[list[int]]:
    """Transform the output of FastEmbed into a more usable format."""
    return [emb.tolist() for emb in output]


def fastembed_sparse_output_transformer(
    output: list[np.ndarray] | list[CodeWeaverSparseEmbedding],
) -> list[CodeWeaverSparseEmbedding]:
    """Transform the sparse output of FastEmbed into indices and values format.

    FastEmbed's SparseTextEmbedding returns SparseEmbedding objects with
    indices and values attributes. We transform them into CodeWeaver SparseEmbedding objects.
    """
    if not output:
        return [CodeWeaverSparseEmbedding(indices=[], values=[])]

    if isinstance(output[0], CodeWeaverSparseEmbedding):
        return cast(list[CodeWeaverSparseEmbedding], output)

    return [
        CodeWeaverSparseEmbedding(
            cast(np.ndarray, emb.indices).tolist(), cast(np.ndarray, emb.values).tolist()
        )
        if isinstance(emb, np.ndarray)
        else CodeWeaverSparseEmbedding(emb.indices, emb.values)
        for emb in output
    ]


class FastEmbedEmbeddingProvider(EmbeddingProvider[TextEmbedding]):
    """
    FastEmbed implementation of the embedding provider.

    model_name: The name of the FastEmbed model to use.
    """

    client: SkipValidation[TextEmbedding]
    _provider: ClassVar[Literal[Provider.FASTEMBED]] = Provider.FASTEMBED

    _output_transformer: Callable[[Any], list[list[float]] | list[list[int]]] = (
        fastembed_output_transformer
    )

    def _initialize(
        self,
        impl_deps: EmbeddingImplementationDeps = None,
        custom_deps: EmbeddingCustomDeps = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the FastEmbed client."""

    @property
    def base_url(self) -> str | None:
        """FastEmbed does not use a base URL."""
        return None

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a list of documents into vectors."""
        logger.debug("Embedding documents with FastEmbed.")
        logger.debug("Document embedding kwargs %s", kwargs)
        logger.debug(
            "`_embed_documents` called with %d documents of type %s",
            len(documents),
            type(documents[0]),
        )
        ready_documents = self.chunks_to_strings(documents)
        logger.debug("Ready documents for embedding: %s", ready_documents[:2])
        logger.debug("Embedding documents of type %s", type(ready_documents))
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: list(self.client.embed(texts=cast(Iterable[str], ready_documents), **kwargs)),
        )
        partial_tokens = rpartial(self._update_token_stats, from_docs=ready_documents)
        self._fire_and_forget(partial_tokens, loop=loop)
        return await loop.run_in_executor(None, lambda: self._process_output(embeddings))

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a query into a vector."""
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: list(self.client.query_embed(query=query, **kwargs))
        )
        await asyncio.sleep(0)
        self._fire_and_forget(lambda: self._update_token_stats(from_docs=query), loop=loop)
        return self._process_output(embeddings)

    @property
    def dimension(self) -> int:
        """Get the size of the vector for the Qdrant collection."""
        return self.client.embedding_size


class FastEmbedSparseProvider(SparseEmbeddingProvider[SparseTextEmbedding]):
    """
    FastEmbed implementation for sparse embeddings.
    """

    client: type[SparseTextEmbedding] | SparseTextEmbedding = _SparseTextEmbedding
    caps: SparseEmbeddingModelCapabilities | None = None
    _output_transformer: Callable[[Any], list[CodeWeaverSparseEmbedding]] = (
        fastembed_sparse_output_transformer
    )

    @override
    def _initialize(self, caps: SparseEmbeddingModelCapabilities | None = None) -> None:
        """Initialize the FastEmbed client."""
        # 1. Set _caps from parameter, not from self
        self.caps = caps

        # 2. Configure model name in kwargs if not already set
        if "model_name" not in self.embed_options:
            model = caps.name  # Use caps parameter, not self.caps
            self.embed_options["model_name"] = model
            # Note: model_name should NOT be in query_options - it's only for client init

        # 3. Initialize client if it's still a class (not an instance)
        # The _client class variable is set to the class type, so we need to instantiate it
        if isinstance(self.client, type):
            client_options = self.embed_options.get("client_options") or self.embed_options
            self.client = self.client(**client_options)

        # 4. Remove model_name from runtime kwargs - it was only needed for initialization
        self.embed_options.pop("model_name", None)
        self.query_options.pop("model_name", None)

    def base_url(self) -> str | None:
        """FastEmbed does not use a base URL."""
        return None

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[CodeWeaverSparseEmbedding]:
        """Embed a list of documents into sparse vectors."""
        ready_documents = self.chunks_to_strings(documents)
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: list(
                self.client.embed(
                    documents=cast(Sequence[str], ready_documents), parallel=1, **kwargs
                )
            ),
        )
        features = sum(len(emb.indices) for emb in embeddings)
        self._update_token_stats(token_count=features, sparse=True)
        return await loop.run_in_executor(None, lambda: self._process_output(embeddings))

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[CodeWeaverSparseEmbedding]:
        """Embed a query into a sparse vector."""
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: list(self.client.query_embed(query=query, **kwargs))
        )
        features = sum(len(emb.indices) for emb in embeddings)
        self._update_token_stats(token_count=features, sparse=True)
        return await loop.run_in_executor(None, lambda: self._process_output(embeddings))


__all__ = (
    "FastEmbedEmbeddingProvider",
    "FastEmbedSparseProvider",
    "fastembed_output_transformer",
    "fastembed_sparse_output_transformer",
)
