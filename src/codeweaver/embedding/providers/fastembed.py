# sourcery skip: lambdas-should-be-short
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

import asyncio
import multiprocessing

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, ClassVar, cast

import numpy as np

from codeweaver._data_structures import CodeChunk
from codeweaver._utils import rpartial
from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.embedding.providers import EmbeddingProvider
from codeweaver.exceptions import ConfigurationError
from codeweaver.provider import Provider


try:
    from fastembed.sparse import SparseTextEmbedding
    from fastembed.text import TextEmbedding

    from codeweaver.embedding.fastembed_extensions import get_sparse_embedder, get_text_embedder
except ImportError as e:
    raise ConfigurationError(
        "FastEmbed is not installed. Please install it with `pip install codeweaver[provider-fastembed]` or `codeweaver[provider-fastembed-gpu]`."
    ) from e

_TextEmbedding = get_text_embedder()
_SparseTextEmbedding = get_sparse_embedder()


def fastembed_all_kwargs(**kwargs: Mapping[str, Any] | None) -> dict[str, Any]:
    """Get all possible kwargs for FastEmbed embedding methods."""
    default_kwargs: Mapping[str, Any] = {"threads": multiprocessing.cpu_count(), "lazy_load": True}
    if kwargs:
        device_ids: list[int] | None = kwargs.get("device_ids")  # pyright: ignore[reportAssignmentType]
        cuda: bool | None = kwargs.get("cuda")  # pyright: ignore[reportAssignmentType]
        if cuda == False:  # user **explicitly** disabled cuda  # noqa: E712
            return default_kwargs | kwargs
        cuda = bool(cuda)
        from codeweaver._utils import decide_fastembed_runtime

        decision = decide_fastembed_runtime(explicit_cuda=cuda, explicit_device_ids=device_ids)
        if isinstance(decision, tuple) and len(decision) == 2:
            cuda = True
            device_ids = decision[1]
        elif decision == "gpu":
            cuda = True
            device_ids = [0]
        else:
            cuda = False
            device_ids = None
        if cuda:
            kwargs["cuda"] = True  # pyright: ignore[reportArgumentType]
            kwargs["device_ids"] = device_ids  # pyright: ignore[reportArgumentType]
            kwargs["providers"] = ["CUDAExecutionProvider"]  # pyright: ignore[reportArgumentType]
    return default_kwargs


def fastembed_output_transformer(output: list[np.ndarray]) -> list[list[float]] | list[list[int]]:
    """Transform the output of FastEmbed into a more usable format."""
    return [emb.tolist() for emb in output]


class FastEmbedProvider(EmbeddingProvider[TextEmbedding]):
    """
    FastEmbed implementation of the embedding provider.

    model_name: The name of the FastEmbed model to use.
    """

    _client: TextEmbedding
    _provider: Provider = Provider.FASTEMBED
    _caps: EmbeddingModelCapabilities

    _doc_kwargs: ClassVar[dict[str, Any]] = fastembed_all_kwargs()
    _query_kwargs: ClassVar[dict[str, Any]] = fastembed_all_kwargs()
    _output_transformer: ClassVar[Callable[[Any], list[list[float]] | list[list[int]]]] = (
        fastembed_output_transformer
    )

    def _initialize(self) -> None:
        """Initialize the FastEmbed client."""
        if "model_name" not in self._doc_kwargs:
            model = self._caps.name
            self.doc_kwargs["model_name"] = model
            self.query_kwargs["model_name"] = model
        self._client = _TextEmbedding(**self._doc_kwargs)

    @property
    def base_url(self) -> str | None:
        """FastEmbed does not use a base URL."""
        return None

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Mapping[str, Any] | None
    ) -> list[list[float]] | list[list[int]]:
        """Embed a list of documents into vectors."""
        ready_documents = self.chunks_to_strings(documents)
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: list(
                self._client.passage_embed(cast(Iterable[str], ready_documents), **kwargs)
            ),
        )
        partial_tokens = rpartial(self._update_token_stats, from_docs=ready_documents)
        self._fire_and_forget(partial_tokens)  # pyright: ignore[reportArgumentType]
        return await loop.run_in_executor(None, lambda: self._process_output(embeddings))

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Mapping[str, Any] | None
    ) -> list[list[float]] | list[list[int]]:
        """Embed a query into a vector."""
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: list(self._client.query_embed(query, **kwargs))
        )
        self._update_token_stats(from_docs=query)
        return self._process_output(embeddings)

    @property
    def dimension(self) -> int:
        """Get the size of the vector for the Qdrant collection."""
        return self._client.embedding_size


class FastEmbedSparseProvider(FastEmbedProvider):
    """
    FastEmbed implementation for sparse embeddings.
    """

    _client: SparseTextEmbedding

    def _initialize(self) -> None:
        """Initialize the FastEmbed client."""
        if "model_name" not in self._doc_kwargs:
            model = self._caps.name
            self.doc_kwargs["model_name"] = model
            self.query_kwargs["model_name"] = model
        self._client = _SparseTextEmbedding(**self._doc_kwargs)  # pyright: ignore[reportIncompatibleVariableOverride]

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Mapping[str, Any] | None
    ) -> list[list[float]] | list[list[int]]:
        """Embed a list of documents into vectors."""
        ready_documents = self.chunks_to_strings(documents)
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: list(self._client.embed(cast(Sequence[str], ready_documents), **kwargs)),  # pyright: ignore[reportArgumentType]
        )
        return await loop.run_in_executor(None, lambda: self._process_output(embeddings))  # type: ignore

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Mapping[str, Any] | None
    ) -> list[list[float]] | list[list[int]]:
        """Embed a query into a vector."""
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: list(self._client.query_embed(query, **kwargs))
        )
        return await loop.run_in_executor(None, lambda: self._process_output(embeddings))


__all__ = ("FastEmbedProvider", "FastEmbedSparseProvider")
