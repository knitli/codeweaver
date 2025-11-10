# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)
"""VoyageAI embedding provider."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Annotated, Any, ClassVar, cast

from pydantic import PrivateAttr, SkipValidation
from voyageai.object.embeddings import EmbeddingsObject

from codeweaver.core.chunks import CodeChunk
from codeweaver.exceptions import ConfigurationError
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.providers import EmbeddingProvider
from codeweaver.providers.provider import Provider


try:
    from voyageai.client_async import AsyncClient
    from voyageai.object.contextualized_embeddings import ContextualizedEmbeddingsObject
    from voyageai.object.embeddings import EmbeddingsObject

except ImportError as _import_error:
    raise ConfigurationError(
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

    client: SkipValidation[AsyncClient]
    _provider: ClassVar[Provider] = Provider.VOYAGE
    caps: EmbeddingModelCapabilities

    _doc_kwargs: ClassVar[dict[str, Any]] = {"input_type": "document"}
    _query_kwargs: ClassVar[dict[str, Any]] = {"input_type": "query"}
    _output_transformer: ClassVar[Callable[[Any], list[list[float]] | list[list[int]]]] = (
        voyage_output_transformer  # Default, overridden in _process_output for context models
    )

    # Store whether this is a context model (set during _initialize)
    _is_context_model: Annotated[bool, PrivateAttr()] = False

    def _initialize(self, caps: EmbeddingModelCapabilities) -> None:
        # Detect if this is a context model
        self._is_context_model = "context" in caps.name

        shared_kwargs = {
            "model": caps.name,
            "output_dimension": caps.default_dimension,
            "output_dtype": caps.default_dtype,
        }
        self.doc_kwargs |= shared_kwargs
        self.query_kwargs |= shared_kwargs

    def _process_output(self, output_data: Any) -> list[list[float]] | list[list[int]]:
        """Process output data using the appropriate transformer."""
        transformer = (
            voyage_context_output_transformer
            if self._is_context_model
            else voyage_output_transformer
        )
        return transformer(output_data)

    @property
    def name(self) -> Provider:
        """Get the name of the embedding provider."""
        return Provider.VOYAGE

    @property
    def base_url(self) -> str | None:
        """Get the base URL of the embedding provider."""
        return "https://api.voyageai.com/v1"

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a list of documents into vectors."""
        ready_documents = cast(list[str], self.chunks_to_strings(documents))
        results: EmbeddingsObject = await self.client.embed(texts=ready_documents, **kwargs)
        self._fire_and_forget(lambda: self._update_token_stats(token_count=results.total_tokens))
        return self._process_output(results)

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a query or group of queries into vectors."""
        results: EmbeddingsObject = await self.client.embed(texts=list(query), **kwargs)
        self._fire_and_forget(lambda: self._update_token_stats(token_count=results.total_tokens))
        return self._process_output(results)

    @property
    def dimension(self) -> int:
        """Get the size of the vector for the collection."""
        return self.doc_kwargs.get("output_dimension", self.caps.default_dimension)  # type: ignore


__all__ = ("VoyageEmbeddingProvider",)
