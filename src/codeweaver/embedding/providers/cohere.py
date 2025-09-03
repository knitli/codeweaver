"""Cohere embedding provider."""
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)

"""
for Azure implementation, see: https://github.com/Azure/azureml-examples/blob/main/sdk/python/foundation-models/cohere/cohere-embed.ipynb

We'll need to make the provider flexible to handle both cohere.com, Azure, and Heroku endpoints. Bedrock uses the AWS API, but Azure uses Cohere for Cohere models.


"""

import os

from collections.abc import Sequence
from typing import Any, cast

from codeweaver._data_structures import CodeChunk
from codeweaver._settings import Provider
from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.embedding.providers.base import EmbeddingProvider
from codeweaver.exceptions import ConfigurationError


def try_for_heroku_endpoint(kwargs: dict[str, Any]) -> str:
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


def parse_endpoint(endpoint: str, region: str | None = None) -> str:
    """Parse the Azure endpoint URL."""
    if endpoint.startswith("http"):
        if endpoint.rstrip("/").endswith(("com", "com")):
            return endpoint
        endpoint = endpoint.split("//", 1)[1].split(".")[0]
        region = region or endpoint.split(".")[1]
        return f"https://{endpoint}.{region}.inference.ai.azure.com"
    endpoint = endpoint.split(".")[0]
    region = region or endpoint.split(".")[1]
    return f"https://{endpoint}.{region}.inference.ai.azure.com"


def try_for_azure_endpoint(kwargs: dict[str, Any]) -> str:
    """Try to identify the Azure endpoint.

    Azure uses this format: `https://<endpoint>.<region_name>.inference.ai.azure.com`,
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
    if kwargs.get("base_url"):
        return kwargs["base_url"]
    if kwargs.get("api_base"):
        return kwargs["api_base"]
    if (
        env_set := os.getenv("AZURE_COHERE_ENDPOINT")
        or os.getenv("AZURE_API_BASE")
        or os.getenv("AZURE_BASE_URL")
    ):
        return parse_endpoint(
            env_set, region or os.getenv("AZURE_COHERE_REGION") or os.getenv("AZURE_REGION")
        )
    return ""


try:
    from cohere import AsyncClientV2 as CohereClient

except ImportError as e:
    raise ConfigurationError(
        'Please install the `cohere` package to use the Cohere provider, \nyou can use the `cohere` optional group — `pip install "codeweaver[provider-cohere]"`'
    ) from e


class CohereEmbeddingProvider(EmbeddingProvider[CohereClient]):
    """Cohere embedding provider."""

    _client: CohereClient
    _provider = Provider.COHERE  # can also be Heroku or Azure, but default to Cohere
    _caps: EmbeddingModelCapabilities

    def __init__(
        self, caps: EmbeddingModelCapabilities, _client: CohereClient | None = None, **kwargs: Any
    ) -> None:
        """Initialize the Cohere embedding provider."""
        self._caps = caps
        self._provider = caps.provider or self._provider
        kwargs = kwargs or {}
        self.client_kwargs = kwargs.get("client", {}) or kwargs
        self.client_kwargs["client_name"] = "codeweaver"
        if not self.client_kwargs.get("api_key"):
            if self._provider == Provider.COHERE:
                self.client_kwargs["api_key"] = kwargs.get("api_key") or os.getenv("COHERE_API_KEY")
            elif self._provider == Provider.AZURE:
                self.client_kwargs["api_key"] = (
                    kwargs.get("api_key")
                    or os.getenv("AZURE_COHERE_API_KEY")
                    or os.getenv("COHERE_API_KEY")
                )
            else:  # Heroku
                self.client_kwargs["api_key"] = (
                    kwargs.get("api_key")
                    or os.getenv("HEROKU_API_KEY")
                    or os.getenv("INFERENCE_KEY")
                    or os.getenv("COHERE_API_KEY")
                )
            if not self.client_kwargs.get("api_key"):
                raise ConfigurationError(
                    "Cohere API key not found in client_kwargs or COHERE_API_KEY environment variable."
                )
        self.client_kwargs["base_url"] = self.client_kwargs.get("base_url") or self.base_url
        self.client_kwargs["model"] = self.model_name or caps.name
        self._client = _client or CohereClient(**self.client_kwargs)
        super().__init__(self._client, caps, **self.client_kwargs)

    @property
    def base_url(self) -> str:
        """Get the base URL for the current provider."""
        return self._base_urls()[self._provider]

    def _base_urls(self) -> dict[Provider, str]:
        """Get the base URLs for each provider."""
        return {
            Provider.COHERE: "https://api.cohere.com",
            Provider.AZURE: try_for_azure_endpoint(self.client_kwargs),
            Provider.HEROKU: try_for_heroku_endpoint(self.client_kwargs),
        }

    async def _fetch_embeddings(
        self, texts: list[str], *, is_query: bool, **kwargs: dict[str, Any]
    ) -> list[list[float]] | list[list[int]]:
        """Fetch embeddings from the Cohere API."""
        embed_kwargs = {
            **kwargs,
            **self.client_kwargs,
            "input_type": "search_query" if is_query else "search_document",
        }
        if self.model_name.endswith("4.0") and not embed_kwargs.get("embedding_types"):
            embed_kwargs["embedding_types"] = ["float"]  # pyright: ignore[reportArgumentType]
            attr = "float"
        else:
            attr = self.client_kwargs.get("output_dtype") or self._caps.default_dtype or "float"
        response = await self._client.embed(
            texts=texts,
            model=self.client_kwargs["model"],
            **embed_kwargs,  # pyright: ignore[reportArgumentType]
        )
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

    async def _embed_documents(self, documents: Sequence[CodeChunk], **kwargs):
        """Embed a list of documents."""
        kwargs = self.doc_kwargs.get("client", {}) | self.doc_kwargs.get("model", {}) | kwargs
        readied_texts = self.chunks_to_strings(documents)
        return await self._fetch_embeddings(
            cast(list[str], readied_texts), is_query=False, **kwargs
        )

    async def _embed_query(self, query: Sequence[str], **kwargs):
        """Embed a query or list of queries."""
        kwargs = self.query_kwargs.get("client", {}) | self.query_kwargs.get("model", {}) | kwargs
        return await self._fetch_embeddings(cast(list[str], query), is_query=True, **kwargs)
