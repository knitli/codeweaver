# sourcery skip: avoid-single-character-names-variables
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)
"""Mistral embedding provider."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from codeweaver.core import ConfigurationError, Provider
from codeweaver.providers.embedding.providers.base import (
    EmbeddingCustomDeps,
    EmbeddingImplementationDeps,
    EmbeddingProvider,
)


if TYPE_CHECKING:
    from codeweaver.core import CodeChunk

try:
    from mistralai import Mistral
    from mistralai.models import EmbeddingDtype
except ImportError as e:
    raise ConfigurationError(
        r'Please install the `mistralai` package to use the Mistral provider, \nyou can use the `mistral` optional group -- `pip install "code-weaver\[mistral]"`'
    ) from e


class MistralEmbeddingProvider(EmbeddingProvider[Mistral]):
    """Mistral embedding provider."""

    client: Mistral
    _provider: ClassVar[Literal[Provider.MISTRAL]] = Provider.MISTRAL

    def _initialize(
        self,
        impl_deps: EmbeddingImplementationDeps = None,
        custom_deps: EmbeddingCustomDeps = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Mistral client."""
        # Nothing to initialize here - options are set in model_post_init

    @property
    def base_url(self) -> str | None:
        """Get the base URL of the Mistral API."""
        return "https://api.mistral.ai"

    async def _fetch_embeddings(
        self, inputs: list[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Fetch embeddings from the Mistral API."""
        tokens_updated = False
        embeddings = []
        try:
            async with self.client as mistral:
                results = await mistral.embeddings.create_async(
                    model=self.model,
                    inputs=inputs,
                    output_dtype=cast(EmbeddingDtype, self.caps.default_dtype),
                    **kwargs,
                )
                embeddings = [cast("list[float]", item.embedding) for item in results.data]
                if token_counts := results.usage.total_tokens:
                    _ = self._update_token_stats(token_count=token_counts)
                    tokens_updated = True
        except Exception:
            if not embeddings:
                raise
        else:
            if not tokens_updated:
                # If we got embeddings but failed to get token counts, we can still return the embeddings.
                _ = self._fire_and_forget(lambda: self._update_token_stats(from_docs=inputs))
            return embeddings
        return embeddings or [[]]

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        readied_documents = self.chunks_to_strings(documents)
        kwargs = (kwargs or {}) | self.embed_options.get("client_options", {})
        return await self._fetch_embeddings(cast("list[str]", readied_documents), **kwargs)

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        kwargs = (kwargs or {}) | self.query_options.get("client_options", {})
        return await self._fetch_embeddings(cast("list[str]", query), **kwargs)


__all__ = ("MistralEmbeddingProvider",)
