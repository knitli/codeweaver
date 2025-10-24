# sourcery skip: avoid-single-character-names-variables
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)
"""Mistral embedding provider."""

import os

from collections.abc import Sequence
from typing import Any, cast

from codeweaver.core.chunks import CodeChunk
from codeweaver.exceptions import ConfigurationError
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.providers.base import EmbeddingProvider
from codeweaver.providers.provider import Provider


try:
    from mistralai import Mistral
    from mistralai.models import EmbeddingDtype
except ImportError as e:
    raise ConfigurationError(
        'Please install the `mistralai` package to use the Mistral provider, \nyou can use the `mistral` optional group — `pip install "codeweaver[provider-mistral]"`'
    ) from e


# TODO: Add support for batch jobs. Ideal for most usage, but becomes more difficult to manage state.
class MistralEmbeddingProvider(EmbeddingProvider[Mistral]):
    """Mistral embedding provider."""

    _client: Mistral
    _provider = Provider.MISTRAL
    _caps: EmbeddingModelCapabilities

    def __init__(
        self, caps: EmbeddingModelCapabilities, client: Mistral | None = None, **kwargs: Any
    ) -> None:
        """Initialize the Mistral embedding provider."""
        kwargs = kwargs or {}
        self._caps = caps
        client_kwargs = kwargs.get("client_kwargs", {})
        if not client:
            api_key = os.environ.get("MISTRAL_API_KEY", kwargs.get("api_key")) or client_kwargs.get(
                "api_key"
            )
            self._client = Mistral(api_key=api_key, **client_kwargs)
        self.model = caps.name
        super().__init__(caps=caps, client=cast(Mistral, client), **kwargs)

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
                    output_dtype=cast(EmbeddingDtype, self._caps.default_dtype),
                    **kwargs,
                )
                embeddings = [cast(list[float], item.embedding) for item in results.data]
                if token_counts := results.usage.total_tokens:
                    _ = self._update_token_stats(token_count=token_counts)  # pyright: ignore[reportGeneralTypeIssues]
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
        kwargs = (kwargs or {}) | self.doc_kwargs.get("client_kwargs", {})
        return await self._fetch_embeddings(cast(list[str], readied_documents), **kwargs)

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        kwargs = (kwargs or {}) | self.query_kwargs.get("client_kwargs", {})
        return await self._fetch_embeddings(cast(list[str], query), **kwargs)


__all__ = ("MistralEmbeddingProvider",)
