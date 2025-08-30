# sourcery skip: avoid-single-character-names-variables
# Copyright (c) 2024 to present Pydantic Services Inc
# SPDX-License-Identifier: MIT
# Applies to original code in this directory (`src/codeweaver/embedding_providers/`) from `pydantic_ai`.
#
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)
"""OpenAI embedding provider."""

from __future__ import annotations as _annotations

import asyncio

from collections.abc import Sequence
from types import MethodType
from typing import Any, Self, cast

from pydantic import create_model

from codeweaver._data_structures import CodeChunk
from codeweaver._settings import Provider
from codeweaver.embedding.capabilities import (
    EmbeddingModelCapabilities,
    get_capabilities_by_model_and_provider,
)
from codeweaver.embedding.providers.base import EmbeddingProvider


try:
    from openai import AsyncOpenAI
    from openai.types.create_embedding_response import CreateEmbeddingResponse
except ImportError as _import_error:
    raise ImportError(
        'Please install the `openai` package to use the OpenAI provider, \nyou can use the `openai` optional group — `pip install "codeweaver[openai]"`'
    ) from _import_error


class OpenAIEmbeddingBase(EmbeddingProvider[AsyncOpenAI]):
    """A class for producing embedding provider classes for OpenAI compatible providers."""

    @classmethod
    def get_provider_class(
        cls,
        model_name: str,
        provider: Provider,
        *,
        base_url: str | None = None,
        provider_kwargs: dict[str, Any] | None = None,
        client: AsyncOpenAI | None = None,
    ) -> type[Self]:
        """
        Create a new embedding provider class for the specified model and provider.
        """
        name = f"{str(provider).title()}EmbeddingProvider"
        capabilities = get_capabilities_by_model_and_provider(model_name, provider)

        def make_init(
            base: type,
            model_name: str,
            provider: Provider,
            base_url: str | None,
            provider_kwargs: dict[str, Any] | None,
            client: AsyncOpenAI | None = None,
        ) -> MethodType:
            """
            Construct an __init__ method for our newborn provider class.
            """

            def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: N807  # it's an __init__! It has to be __init__
                """
                Initialize the embedding provider.
                """
                self._provider = provider
                self._caps = capabilities
                if client is not None:
                    self._client = client
                kwargs.setdefault("model", model_name)
                if base_url is not None:
                    kwargs.setdefault("base_url", base_url)
                if provider_kwargs:
                    kwargs.setdefault("provider_kwargs", provider_kwargs)
                base.__init__(self, *args, **kwargs)

            return __init__

        attrs: dict[str, Any] = {
            "_default_model_name": model_name,
            "_default_provider": provider,
            "_default_base_url": base_url,
            "_default_provider_kwargs": provider_kwargs or {},
        }
        parent_cls = cls
        # Because this is a BaseModel, we need to set __init__ on the parent class
        # so that it's there *before* pydantic does its thing so it can account for it.
        # there are other ways to do this, but this is the simplest.
        parent_cls.__init__ = make_init(
            cls, model_name, provider, base_url, provider_kwargs or {}, client=client
        )
        return create_model(
            name,
            __doc__=f"An embedding provider class for {str(provider).title()}.\n\nI was proudly made in the `codeweaver.embedding.providers.openai_base` module by hardworking electrons.",
            __base__=parent_cls,
            __module__="codeweaver.embedding.providers.openai_factory",
            __validators__=None,
            __cls_kwargs__=attrs,
            _client=(AsyncOpenAI, ...),
            _provider=(Provider, provider),
            _caps=(EmbeddingModelCapabilities, capabilities),
        )

    _client: AsyncOpenAI
    _provider: Provider
    _caps: EmbeddingModelCapabilities

    def _initialize(self) -> None:
        """Initialize the OpenAI embedding provider."""
        self._shared_kwargs = {"model": self.model_name, "encoding_format": "float", "timeout": 30}
        self.valid_client_kwargs = (
            "model",
            "encoding_format",
            "timeout",
            "dimensions",
            "user",
            "extra_headers",
            "extra_query",
            "extra_body",
        )
        self.doc_kwargs = {
            k: v
            for k, v in (self._shared_kwargs | (self.doc_kwargs or {})).items()
            if k in self.valid_client_kwargs
        }
        self.query_kwargs = {
            k: v
            for k, v in (self._shared_kwargs | (self.query_kwargs or {})).items()
            if k in self.valid_client_kwargs
        }

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the OpenAI client."""
        return self.client.base_url

    @property
    def dimension(self) -> int | None:
        """Get the dimension of the embeddings."""
        return self.doc_kwargs.get("dimensions") or self._caps.default_dimension

    def _report(self, response: CreateEmbeddingResponse, texts: Sequence[str]) -> None:
        loop = asyncio.get_event_loop()
        if response.usage and (token_count := response.usage.total_tokens):
            _ = loop.run_in_executor(
                None, lambda: self._update_token_stats(token_count=token_count)
            )
        else:
            _ = loop.run_in_executor(None, lambda: self._update_token_stats(from_docs=texts))

    async def _get_vectors(
        self, texts: Sequence[str], **kwargs: dict[str, Any] | None
    ) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
        """Get vectors for a sequence of texts."""
        response = await self._client.embeddings.create(
            input=cast(list[str], texts),
            **(  # pyright: ignore[reportArgumentType]
                self.doc_kwargs
                | (
                    {k: v for k, v in kwargs.items() if k in self.valid_client_kwargs}
                    if kwargs
                    else {}
                )
            ),
        )
        if not response or not response.data:
            raise ValueError("No response from OpenAI embeddings endpoint")
        self._report(response, cast(list[str], texts))
        results = sorted(response.data, key=lambda x: x.index)
        return [result.embedding for result in results]

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: dict[str, Any]
    ) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
        """Embed a sequence of documents."""
        if not isinstance(next(iter(documents), CodeChunk), CodeChunk):
            raise TypeError("Expected a sequence of CodeChunk instances")
        texts = self.chunks_to_strings(documents)
        return await self._get_vectors(cast(list[str], texts), **kwargs)

    async def _embed_query(
        self, query: Sequence[str], **kwargs: dict[str, Any] | None
    ) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
        return await self._get_vectors(query, **kwargs)
