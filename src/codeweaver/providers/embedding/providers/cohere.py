"""Cohere embedding provider."""
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar, Literal, cast

from cohere import EmbedByTypeResponse
from pydantic import SkipValidation

from codeweaver.core import CodeChunk, ConfigurationError, Provider
from codeweaver.providers.config import CohereEmbeddingConfig, EmbeddingProviderSettings
from codeweaver.providers.embedding.providers.base import (
    EmbeddingCustomDeps,
    EmbeddingImplementationDeps,
    EmbeddingProvider,
)


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

    config: EmbeddingProviderSettings | CohereEmbeddingConfig

    def _initialize(
        self,
        impl_deps: EmbeddingImplementationDeps = None,
        custom_deps: EmbeddingCustomDeps = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the FastEmbed client."""
        from codeweaver.providers.config.embedding import CohereEmbeddingConfig
        from codeweaver.providers.config.kinds import EmbeddingProviderSettings

        config = self.config or kwargs.get("config")
        if not config:
            return

        # Handle CohereEmbeddingConfig (has .embedding and .query attributes)
        if isinstance(config, CohereEmbeddingConfig):
            if (embedding_config := config.embedding) and not embedding_config.get("model"):
                self.config = config.model_copy(
                    update={"embedding": {**embedding_config, "model": config.model_name}}
                )
            if (query_config := config.query) and not query_config.get("model"):
                self.config = config.model_copy(
                    update={"query": {**query_config, "model": config.model_name}}
                )
        # Handle EmbeddingProviderSettings (uses .get_embed_kwargs() and .get_query_embed_kwargs())
        elif isinstance(config, EmbeddingProviderSettings):
            embedding_config = config.get_embed_kwargs()
            query_config = config.get_query_embed_kwargs()

            # For EmbeddingProviderSettings, we need to update the underlying embedding_config
            if embedding_config and not embedding_config.get("model"):
                # Create updated options
                updated_embedding = {**embedding_config, "model": config.model_name}
                # Update the underlying CohereEmbeddingConfig
                self.config = config.model_copy(
                    update={
                        "embedding_config": config.embedding_config.model_copy(
                            update={"embedding": updated_embedding}
                        )
                    }
                )
            if query_config and not query_config.get("model"):
                updated_query = {**query_config, "model": config.model_name}
                self.config = config.model_copy(
                    update={
                        "embedding_config": config.embedding_config.model_copy(
                            update={"query": updated_query}
                        )
                    }
                )

    def model_post_init(self, __context: Any, /) -> None:
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
        return self.client._client_wrapper.get_base_url()

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
