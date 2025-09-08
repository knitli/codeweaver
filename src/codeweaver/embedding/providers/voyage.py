# Copyright (c) 2024 to present Pydantic Services Inc
# SPDX-License-Identifier: MIT
# Applies to original code in this directory (`src/codeweaver/embedding_providers/`) from `pydantic_ai`.
#
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)
"""VoyageAI embedding provider."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, ClassVar, cast

from voyageai.object.embeddings import EmbeddingsObject

from codeweaver._data_structures import CodeChunk
from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.embedding.providers import EmbeddingProvider
from codeweaver.embedding.providers.base import default_output_transformer
from codeweaver.provider import Provider


try:
    from voyageai.client_async import AsyncClient
    from voyageai.object.contextualized_embeddings import ContextualizedEmbeddingsObject
    from voyageai.object.embeddings import EmbeddingsObject

except ImportError as _import_error:
    raise ImportError(
        'Please install the `voyageai` package to use the Voyage provider, you can use the `voyage` optional group — `pip install "codeweaver[voyage]"`'
    ) from _import_error


def voyage_context_output_transformer(
    result: ContextualizedEmbeddingsObject,
) -> list[list[float]] | list[list[int]]:
    """Transform the output of the Voyage AI context chunk embedding model."""
    results = result.results
    embeddings = [res.embeddings for res in results if res and res.embeddings]
    if embeddings and isinstance(embeddings[0][0][0], list):
        # if we have three levels of lists, flatten to two levels
        embeddings = cast(list[list[float]], [emb for sublist in embeddings for emb in sublist])
    return embeddings  # type: ignore


def voyage_output_transformer(result: EmbeddingsObject) -> list[list[float]] | list[list[int]]:
    """Transform the output of the Voyage AI model."""
    return result.embeddings


class VoyageEmbeddingProvider(EmbeddingProvider[AsyncClient]):
    """VoyageAI embedding provider."""

    _client: AsyncClient
    _provider: Provider = Provider.VOYAGE
    _caps: EmbeddingModelCapabilities

    _doc_kwargs: ClassVar[dict[str, Any]] = {"input_type": "document"}
    _query_kwargs: ClassVar[dict[str, Any]] = {"input_type": "query"}
    _output_transformer: Callable[[Any], list[list[float]] | list[list[int]]] = (
        default_output_transformer
    )

    def _initialize(self) -> None:
        self._output_transformer = (
            staticmethod(voyage_context_output_transformer)
            if "context" in self._caps.name
            else staticmethod(voyage_output_transformer)
        )
        shared_kwargs = {
            "model": self._caps.name,
            "output_dimension": self._caps.default_dimension,
            "output_dtype": self._caps.default_dtype,
        }
        self.doc_kwargs |= shared_kwargs
        self.query_kwargs |= shared_kwargs

    @property
    def name(self) -> Provider:
        """Get the name of the embedding provider."""
        return Provider.VOYAGE

    @property
    def base_url(self) -> str | None:
        """Get the base URL of the embedding provider."""
        return "https://api.voyageai.com/v1"

    @property
    def client(self) -> AsyncClient:
        """Get the client for the embedding provider."""
        return self._client

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Mapping[str, Any]
    ) -> list[list[float]] | list[list[int]]:  # pyright: ignore[reportReturnType]
        """Embed a list of documents into vectors."""
        ready_documents = cast(list[str], self.chunks_to_strings(documents))
        results: EmbeddingsObject = await self._client.embed(texts=ready_documents, **kwargs)  # pyright: ignore[reportArgumentType]
        self._fire_and_forget(lambda: self._update_token_stats(token_count=results.total_tokens))
        return self._process_output(results)

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Mapping[str, Any]
    ) -> list[list[float]] | list[list[int]]:
        """Embed a query or group of queries into vectors."""
        results: EmbeddingsObject = await self._client.embed(texts=query, **kwargs)  # pyright: ignore[reportArgumentType]
        self._fire_and_forget(lambda: self._update_token_stats(token_count=results.total_tokens))
        return self._process_output(results)

    @property
    def dimension(self) -> int:
        """Get the size of the vector for the collection."""
        return self.doc_kwargs.get("output_dimension", self._caps.default_dimension)  # type: ignore
