"""Cohere embedding provider."""
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)

from __future__ import annotations

import os

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from pydantic import SkipValidation

from codeweaver.core import ConfigurationError, Provider
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.providers.base import EmbeddingProvider


if TYPE_CHECKING:
    from codeweaver.core import CodeChunk


def try_for_heroku_endpoint(kwargs: Any) -> str:
    """Try to identify the Heroku endpoint."""
    if kwargs.get("base_url"):
        return kwargs["base_url"]
    if kwargs.get("api_base"):
        return kwargs["api_base"]
    if (
        env_set := os.getenv("INFERENCE_URL")
        or os.getenv("CO_API_URL")
        or os.getenv("HEROKU_INFERENCE_URL")
        or os.getenv("COHERE_BASE_URL")
        or os.getenv("HEROKU_BASE_URL")
    ):
        return env_set
    return ""


try:
    from cohere import AsyncClientV2 as CohereClient

except ImportError as e:
    raise ConfigurationError(
        r'Please install the `cohere` package to use the Cohere provider, \nyou can use the `cohere` optional group -- `pip install "code-weaver\[cohere]"`'
    ) from e


class CohereEmbeddingProvider(EmbeddingProvider[CohereClient]):
    """Cohere embedding provider."""

    client: SkipValidation[CohereClient]
    _provider = Provider.COHERE  # can also be Heroku or Azure, but default to Cohere
    caps: EmbeddingModelCapabilities

    def __init__(
        self, caps: EmbeddingModelCapabilities, _client: CohereClient | None = None, **kwargs: Any
    ) -> None:
        """Initialize the Cohere embedding provider."""
        # Store kwargs for _initialize to use
        config_kwargs = kwargs or {}

        # Initialize client if not provided
        if _client is None:
            # Extract client_options if explicitly provided, otherwise use only known client params
            if "client_options" in config_kwargs:
                client_options = config_kwargs["client_options"].copy()
            else:
                # Only extract known Cohere client options from kwargs
                known_client_options = {
                    "api_key",
                    "base_url",
                    "timeout",
                    "max_retries",
                    "httpx_client",
                }
                client_options = {
                    k: v for k, v in config_kwargs.items() if k in known_client_options
                }
            client_options["client_name"] = "codeweaver"

            # Determine provider to get correct API key
            provider = caps.provider or Provider.COHERE

            if not client_options.get("api_key") or not kwargs.get("api_key"):
                if provider == Provider.COHERE:
                    client_options["api_key"] = config_kwargs.get("api_key") or os.getenv(
                        "COHERE_API_KEY"
                    )
                elif provider == Provider.AZURE:
                    client_options["api_key"] = (
                        config_kwargs.get("api_key")
                        or os.getenv("AZURE_COHERE_API_KEY")
                        or os.getenv("COHERE_API_KEY")
                    )
                else:  # Heroku
                    client_options["api_key"] = (
                        config_kwargs.get("api_key")
                        or os.getenv("HEROKU_API_KEY")
                        or os.getenv("INFERENCE_KEY")
                        or os.getenv("COHERE_API_KEY")
                    )
                if not client_options.get("api_key"):
                    raise ConfigurationError(
                        "Cohere API key not found in client_options or COHERE_API_KEY environment variable."
                    )

            # Get base URL based on provider (can't use self.base_url yet)
            base_urls = {
                Provider.COHERE: "https://api.cohere.com",
                Provider.AZURE: try_for_azure_endpoint(client_options),
                Provider.HEROKU: try_for_heroku_endpoint(client_options),
            }
            client_options["base_url"] = client_options.get("base_url") or base_urls[provider]
            # Store model separately - it's not a client option but an embed() parameter
            model = caps.name

            _client = CohereClient(**client_options)
            # Store client_options for later use (will be set after super().__init__)
            client_opts_to_store = client_options | {"model": model}
        else:
            # Client was provided - extract or use default client_options
            client_opts_to_store = config_kwargs.get(
                "client_options", {"model": caps.name, "client_name": "codeweaver"}
            )

        # Call super with correct signature (client, caps, kwargs as dict)
        # This initializes the Pydantic model and sets up all the attributes
        super().__init__(client=_client, caps=caps, kwargs=config_kwargs)

        # Now set client_options after super().__init__()
        self.client_options = client_opts_to_store

    @property
    def base_url(self) -> str:
        """Get the base URL for the current provider."""
        return self._base_urls()[type(self)._provider]

    def _base_urls(self) -> dict[Provider, str]:
        """Get the base URLs for each provider."""
        # Access client_options through self if available, otherwise use empty dict
        client_opts = getattr(self, "client_options", {}) or {}
        return {
            Provider.COHERE: "https://api.cohere.com",
            Provider.AZURE: try_for_azure_endpoint(client_opts),
            Provider.HEROKU: try_for_heroku_endpoint(client_opts),
        }

    async def _fetch_embeddings(
        self, texts: list[str], *, is_query: bool, **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Fetch embeddings from the Cohere API."""
        embed_kwargs = {
            **kwargs,
            **self.client_options,
            "input_type": "search_query" if is_query else "search_document",
        }
        if self.model_name.endswith("4.0") and not embed_kwargs.get("embedding_types"):
            embed_kwargs["embedding_types"] = ["float"]
            attr = "float"
        else:
            attr = self.client_options.get("output_dtype") or self.caps.default_dtype or "float"

        # Extract model from embed_kwargs to avoid passing it twice
        model = embed_kwargs.pop("model", self.model_name)
        response = await self.client.embed(texts=texts, model=model, **embed_kwargs)
        embed_obj = response.embeddings
        embeddings = getattr(embed_obj, attr, None)
        tokens = (
            (response.meta.tokens.output_tokens or response.meta.tokens.input_tokens)
            if response.meta and response.meta.tokens
            else None
        )
        if tokens:
            self._fire_and_forget(lambda: self._update_token_stats(token_count=int(tokens)))
        else:
            self._fire_and_forget(lambda: self._update_token_stats(from_docs=texts))
        return embeddings or [[]]

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a list of documents."""
        kwargs = (
            self.embed_options.get("client_options", {})  # ty:ignore[unresolved-attribute]
            | self.embed_options.get("model_kwargs", {})  # ty:ignore[unresolved-attribute]
            | kwargs
        )
        readied_texts = self.chunks_to_strings(documents)
        return await self._fetch_embeddings(
            cast(list[str], readied_texts), is_query=False, **kwargs
        )

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a query or list of queries."""
        kwargs = (
            self.query_options.get("client_options", {})  # ty:ignore[unresolved-attribute]
            | self.query_options.get("model_kwargs", {})  # ty:ignore[unresolved-attribute]
            | kwargs
        )
        return await self._fetch_embeddings(cast(list[str], query), is_query=True, **kwargs)


__all__ = ("CohereEmbeddingProvider",)
