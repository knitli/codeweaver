"""Cohere embedding provider."""
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from cohere import EmbedByTypeResponse
from pydantic import SkipValidation

from codeweaver.core import ConfigurationError, Provider
from codeweaver.providers.embedding.providers.base import (
    EmbeddingCustomDeps,
    EmbeddingImplementationDeps,
    EmbeddingProvider,
)


if TYPE_CHECKING:
    from codeweaver.core import CodeChunk

try:
    from cohere import AsyncClientV2 as CohereClient

except ImportError as e:
    raise ConfigurationError(
        r'Please install the `cohere` package to use the Cohere provider, \nyou can use the `cohere` optional group -- `pip install "code-weaver\[cohere]"`'
    ) from e


class CohereEmbeddingProvider(EmbeddingProvider[CohereClient]):
    """Cohere embedding provider."""

    client: SkipValidation[CohereClient]
    _provider: ClassVar[Literal[Provider.COHERE]] = (
        Provider.COHERE
    )  # can also be Heroku or Azure, but default to Cohere

    def _initialize(
        self, impl_deps: EmbeddingImplementationDeps = None, custom_deps: EmbeddingCustomDeps = None
    ) -> None:
        """Initialize the provider."""
        # Nothing to initialize here - options are set in model_post_init
        pass

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization hook to set embedding options.

        Args:
            __context: Pydantic context (unused).
        """
        # We always embed with float but quantize based on the config when we store it
        # v4 models require embedding_types as a list, v3 and earlier use string
        self.embed_options["embedding_types"] = ["float"]
        self.query_options["embedding_types"] = ["float"]

    @property
    def base_url(self) -> str:
        """Get the base URL for the current provider."""
        if self.config.client_options:
            return self.config.client_options.get("base_url", "https://api.cohere.com")  # ty:ignore[unresolved-attribute]
        return "https://api.cohere.com"

    async def _fetch_embeddings(
        self, texts: list[str], *, is_query: bool, **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Fetch embeddings from the Cohere API."""
        embed_kwargs = {
            **kwargs,
            **(self.query_options if is_query else self.embed_options),  # ty:ignore[unresolved-attribute]
            "input_type": "search_query" if is_query else "search_document",
        }
        # Extract model from embed_kwargs to avoid passing it twice
        model = embed_kwargs.pop("model", self.model_name)
        response: EmbedByTypeResponse = await self.client.embed(
            texts=texts, model=model, **embed_kwargs
        )
        tokens = (
            (response.meta.tokens.output_tokens or response.meta.tokens.input_tokens)
            if response.meta and response.meta.tokens
            else None
        )
        if tokens:
            self._fire_and_forget(lambda: self._update_token_stats(token_count=int(tokens)))
        else:
            self._fire_and_forget(lambda: self._update_token_stats(from_docs=texts))
        return response.embeddings.float_ or [[]]

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a list of documents."""
        readied_texts = self.chunks_to_strings(documents)
        return await self._fetch_embeddings(
            cast(list[str], readied_texts), is_query=False, **kwargs
        )

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a query or list of queries."""
        return await self._fetch_embeddings(cast(list[str], query), is_query=True, **kwargs)


__all__ = ("CohereEmbeddingProvider",)
