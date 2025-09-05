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
import os

from collections.abc import Callable, Sequence
from typing import Any, Self, cast

from pydantic import AnyHttpUrl, create_model

from codeweaver._data_structures import CodeChunk
from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.embedding.providers.base import EmbeddingProvider
from codeweaver.provider import Provider


def ensure_v1(url: str) -> str:
    """Ensure the URL ends with /v1."""
    return url if url.rstrip("/").endswith("/v1") else f"{url.rstrip('/')}/v1"


def try_for_heroku_endpoint(kwargs: dict[str, Any]) -> str:
    """Try to identify the Heroku endpoint."""
    if "base_url" in kwargs:
        return ensure_v1(kwargs["base_url"])
    if "api_base" in kwargs:
        return ensure_v1(kwargs["api_base"])
    if (
        env_set := os.getenv("INFERENCE_URL")
        or os.getenv("HEROKU_INFERENCE_URL")
        or os.getenv("OPENAI_API_BASE")
    ):
        return ensure_v1(env_set)
    return ""


def parse_endpoint(endpoint: str, region: str | None = None) -> str:
    """Parse the Azure endpoint URL."""
    if endpoint.startswith("http"):
        if endpoint.endswith("v1"):
            return endpoint
        endpoint = endpoint.split("//", 1)[1].split(".")[0]
        region = region or endpoint.split(".")[1]
        return f"https://{endpoint}.{region}.inference.ai.azure.com/v1"
    endpoint = endpoint.split(".")[0]
    region = region or endpoint.split(".")[1]
    return f"https://{endpoint}.{region}.inference.ai.azure.com/v1"


def try_for_azure_endpoint(kwargs: dict[str, Any]) -> str:
    """Try to identify the Azure endpoint.

    Azure uses this format: `https://<endpoint>.<region_name>.inference.ai.azure.com/v1`,
    But because people often conflate `endpoint` and `url`, we try to be flexible.
    """
    endpoint, region = kwargs.get("endpoint"), kwargs.get("region_name")
    if endpoint and region:
        if not endpoint.startswith("http") or "azure" not in endpoint:
            # URL looks right
            return f"{endpoint}.{region}.inference.ai.azure.com/v1"
        return parse_endpoint(endpoint, region)
    if endpoint and (region := os.getenv("AZURE_OPENAI_REGION")):
        return f"https://{endpoint}.{region}.inference.ai.azure.com/v1"
    if region and (endpoint := os.getenv("AZURE_OPENAI_ENDPOINT")):
        return parse_endpoint(endpoint, region)
    if "base_url" in kwargs:
        return ensure_v1(kwargs["base_url"])
    if "api_base" in kwargs:
        return ensure_v1(kwargs["api_base"])
    if env_set := os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_API_BASE"):
        return parse_endpoint(env_set, region or os.getenv("AZURE_OPENAI_REGION"))
    return ""


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
        capabilities: EmbeddingModelCapabilities,
        *,
        base_url: str | None = None,
        provider_kwargs: dict[str, Any] | None = None,
        client: AsyncOpenAI | None = None,
    ) -> type[Self]:
        """
        Create a new embedding provider class for the specified model and provider.
        """
        name = f"{str(provider).title()}EmbeddingProvider"
        caps: EmbeddingModelCapabilities = capabilities

        def make_init(
            base: type,
            model_name: str,
            provider: Provider,
            base_url: str | None,
            provider_kwargs: dict[str, Any] | None,
            client: AsyncOpenAI | None = None,
        ) -> Callable[..., None]:
            """
            Construct an __init__ method for our newborn provider class.
            """

            def __init__(self: EmbeddingProvider[AsyncOpenAI], *args: Any, **kwargs: Any) -> None:  # noqa: N807  # it's an __init__! It has to be __init__
                """
                Initialize the embedding provider.
                """
                self._provider = provider
                self._caps = caps
                if client is not None:
                    self._client = client
                kwargs.setdefault("model", model_name)
                if base_url is not None:
                    kwargs.setdefault("base_url", base_url)
                if provider_kwargs:
                    kwargs.setdefault("provider_kwargs", provider_kwargs)
                if self._provider == Provider.OLLAMA:
                    kwargs.setdefault("api_key", "ollama")
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
            __doc__=f"An embedding provider class for {str(provider).title()}.\n\nI was proudly made in the `codeweaver.embedding.providers.openai_factory` module by hardworking electrons.",
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
    def base_url(self) -> str:
        """Get the base URL for the OpenAI client."""
        expected_url = self._base_urls()[self._provider]
        return cast(str, str(self.client.base_url) if self.client.base_url else expected_url)

    @property
    def dimension(self) -> int:
        """Get the dimension of the embeddings."""
        return self.doc_kwargs.get("dimensions") or self._caps.default_dimension or 1024  # type: ignore

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

    def _base_urls(self) -> dict[Provider, AnyHttpUrl | str]:
        return {
            Provider.FIREWORKS: "https://api.fireworks.ai/inference/v1",
            Provider.GROQ: "https://api.groq.com/openai/v1",
            Provider.OPENAI: "https://api.openai.com/v1",
            Provider.TOGETHER: "https://api.together.xyz/v1",
            Provider.OLLAMA: self.doc_kwargs.get(
                "endpoint", self.doc_kwargs.get("api_base", "http://localhost:11434/v1")
            ),  # pyright: ignore[reportReturnType]
            Provider.HEROKU: try_for_heroku_endpoint(self.doc_kwargs or {}),  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType,reportUnknownAssignmentType]
            Provider.AZURE: try_for_azure_endpoint(self.doc_kwargs or {}),
        }
