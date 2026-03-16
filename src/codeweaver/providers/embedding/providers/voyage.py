# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""VoyageAI embedding provider."""

from __future__ import annotations

import asyncio

from collections.abc import Callable, Sequence
from typing import Annotated, Any, ClassVar, cast

from pydantic import PrivateAttr, SkipValidation
from voyageai.object.embeddings import EmbeddingsObject

from codeweaver.core import CodeChunk, ConfigurationError, Provider
from codeweaver.providers.embedding.providers.base import (
    EmbeddingCustomDeps,
    EmbeddingImplementationDeps,
    EmbeddingProvider,
)


try:
    from voyageai.client_async import AsyncClient
    from voyageai.object.contextualized_embeddings import ContextualizedEmbeddingsObject
    from voyageai.object.embeddings import EmbeddingsObject
except ImportError as _import_error:
    raise ConfigurationError(
        'Please install the `voyageai` package to use the Voyage provider, you can use the `voyage` optional group -- `pip install "code-weaver\\[voyage]"`'
    ) from _import_error


def voyage_context_output_transformer(
    result: ContextualizedEmbeddingsObject,
) -> list[list[int | float]] | list[list[int]]:
    """Transform the output of the Voyage AI context chunk embedding model."""
    results = result.results
    embeddings = [res.embeddings for res in results if res and res.embeddings]
    if embeddings and isinstance(embeddings[0][0][0], list):
        embeddings = cast(
            list[list[int | float]], [emb for sublist in embeddings for emb in sublist]
        )
    return cast(list[list[int | float]] | list[list[int]], embeddings)


def voyage_output_transformer(
    result: EmbeddingsObject,
) -> list[list[int | float]] | list[list[int]]:
    """Transform the output of the Voyage AI model."""
    return cast(list[list[int | float]] | list[list[int]], result.embeddings)


class VoyageEmbeddingProvider(EmbeddingProvider[AsyncClient]):
    """VoyageAI embedding provider."""

    client: SkipValidation[AsyncClient]
    _provider: ClassVar[Provider] = Provider.VOYAGE
    _output_transformer: Callable[[Any], list[list[float]] | list[list[int]]] = (
        voyage_output_transformer
    )
    _is_context_model: Annotated[bool, PrivateAttr()] = False

    def _initialize(
        self,
        impl_deps: EmbeddingImplementationDeps = None,
        custom_deps: EmbeddingCustomDeps = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the VoyageAI client."""

    def model_post_init(self, __context: Any, /) -> None:
        """Post-initialization hook to detect context models and set options.

        Args:
            __context: Pydantic context (unused).
        """
        config = self.config.embedding_config
        # Set model name, input type, and output parameters for embedding and query options
        self.embed_options["model"] = self.model_name
        self.embed_options["input_type"] = "document"
        self.embed_options["output_dimension"] = config.dimension or self.caps.default_dimension
        self.embed_options["output_dtype"] = config.datatype or self.caps.default_dtype

        self.query_options["model"] = self.model_name
        self.query_options["input_type"] = "query"
        self.query_options["output_dimension"] = config.dimension or self.caps.default_dimension
        self.query_options["output_dtype"] = config.datatype or self.caps.default_dtype
        # Detect if this is a context model based on the model name
        if self.caps and "context" in self.caps.name.lower():
            object.__setattr__(self, "_is_context_model", True)

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
    ) -> list[list[int | float]] | list[list[int]]:
        """Embed a list of documents into vectors."""
        import logging

        logger = logging.getLogger(__name__)
        ready_documents = cast(list[str], self.chunks_to_strings(documents))
        try:
            results: EmbeddingsObject = await self.client.embed(
                texts=ready_documents, **kwargs | self.embed_options
            )
            await asyncio.sleep(0)
            loop = await self._get_loop()
            self._fire_and_forget(
                lambda: self._update_token_stats(token_count=results.total_tokens), loop=loop
            )
        except Exception as e:
            error_msg = str(e)
            if "max allowed tokens per submitted batch" in error_msg.lower() and len(documents) > 1:
                logger.warning(
                    "Voyage batch token limit exceeded (%s), splitting batch of %d chunks in half and retrying",
                    error_msg.split("Your batch has")[1].split("tokens")[0].strip()
                    if "Your batch has" in error_msg
                    else "unknown",
                    len(documents),
                )
                mid = len(documents) // 2
                first_half = await self._embed_documents(documents[:mid], **kwargs)
                second_half = await self._embed_documents(documents[mid:], **kwargs)
                return cast(list[list[int | float]] | list[list[int]], first_half + second_half)
            raise
        else:
            return self._process_output(results)

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[int | float]] | list[list[int]]:
        """Embed a query or group of queries into vectors."""
        results: EmbeddingsObject = await self.client.embed(
            texts=list(query), **kwargs | self.query_options
        )
        loop = await self._get_loop()
        self._fire_and_forget(
            lambda: self._update_token_stats(token_count=results.total_tokens), loop=loop
        )
        return self._process_output(results)

    @property
    def dimension(self) -> int:
        """Get the size of the vector for the collection."""
        return self.embed_options.get("output_dimension", self.caps.default_dimension)


def _rebuild_voyage_embedding_provider() -> None:
    from codeweaver.core import CodeChunk as CodeChunk

    VoyageEmbeddingProvider.model_rebuild()


_rebuild_voyage_embedding_provider()

__all__ = (
    "VoyageEmbeddingProvider",
    "voyage_context_output_transformer",
    "voyage_output_transformer",
)
