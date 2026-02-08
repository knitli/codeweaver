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
from typing import Any, ClassVar, Self, cast

from pydantic import create_model
from triton.runtime.cache import CacheManager

from codeweaver.core import (
    INJECTED,
    CodeChunk,
    ConfigurationError,
    Provider,
    ProviderError,
    TypeIs,
    asyncio_or_uvloop,
)
from codeweaver.core import ValidationError as CodeWeaverValidationError
from codeweaver.core.types import ModelName
from codeweaver.providers.config import EmbeddingProviderSettings
from codeweaver.providers.config.embedding import OpenAIEmbeddingConfig
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.providers.base import (
    EmbeddingCustomDeps,
    EmbeddingImplementationDeps,
    EmbeddingProvider,
    EmbeddingRegistry,
)


try:
    from openai import AsyncOpenAI
    from openai.types.create_embedding_response import CreateEmbeddingResponse
except ImportError as _import_error:
    raise ConfigurationError(
        r'Please install the `openai` package to use the OpenAI provider, \nyou can use the `openai` optional group -- `pip install "code-weaver\[openai]"`'
    ) from _import_error


def _is_embedding_model_capabilities(obj: Any) -> TypeIs[EmbeddingModelCapabilities]:
    """Appease the type checking gods for capability resolution."""
    return isinstance(obj, EmbeddingModelCapabilities)


def _raise_configuration_error(model_name: str, provider: Provider, resolved_type: Any) -> None:
    raise ConfigurationError(
        f"Could not resolve embedding model capabilities for model '{model_name}' and provider '{provider}'",
        details={
            "model_name": model_name,
            "provider": str(provider),
            "resolved_type": type(resolved_type).__name__,
        },
        suggestions=[
            "Ensure the model name is correct",
            "Check that the provider supports the specified model",
            "Verify that the capabilities resolver is functioning properly",
        ],
    )


class OpenAIEmbeddingBase(EmbeddingProvider[AsyncOpenAI]):
    """A class for producing embedding provider classes for OpenAI compatible providers."""

    @classmethod
    def get_provider_class(
        cls,
        model_name: ModelName,
        provider: Provider,
        config: EmbeddingProviderSettings,
        client: AsyncOpenAI,
        registry: EmbeddingRegistry,
        cache_manager: CacheManager | None = None,
        caps: EmbeddingModelCapabilities | None = None,
        initialize_method: Callable[
            [
                OpenAIEmbeddingBase,
                EmbeddingImplementationDeps | None,
                EmbeddingCustomDeps | None,
                Any,
            ],
            None,
        ]
        | None = None,
    ) -> type[Self]:
        """
        Create a new embedding provider class for the specified model and provider.
        """
        name = f"{str(provider).title()}EmbeddingProvider"

        def make_init(
            _base: type,
            _provider: Provider,
            _client: AsyncOpenAI,
            _config: EmbeddingProviderSettings,
            _registry: EmbeddingRegistry,
            _caps: EmbeddingModelCapabilities | None = None,
            _impl_deps: EmbeddingImplementationDeps = INJECTED,
            _custom_deps: EmbeddingCustomDeps = INJECTED,
            _cache_manager: CacheManager | None = None,
        ) -> Callable[..., None]:
            """
            Construct an __init__ method for our newborn provider class.
            """

            def __init__(  # noqa: N807
                self: EmbeddingProvider[AsyncOpenAI],
                provider: Provider = _provider,
                client: AsyncOpenAI = _client,
                registry: EmbeddingRegistry = _registry,
                caps: EmbeddingModelCapabilities | None = _caps,
                **kwargs: Any,
            ) -> None:  # it's an __init__! It has to be __init__
                """
                Initialize the embedding provider.
                """
                cls.provider = provider
                cls.__init__(
                    self,  # ty:ignore[invalid-argument-type]
                    client=client,
                    config=config,
                    caps=caps,
                    registry=registry,
                    **kwargs,
                )
                # 4. Set provider-specific attributes AFTER parent initialization

            return __init__

        parent_cls = cls
        # Because this is a BaseModel, we need to set __init__ on the parent class
        # so that it's there *before* pydantic does its thing so it can account for it.
        # there are other ways to do this, but this is the simplest.
        if not _is_embedding_model_capabilities(caps):
            raise ConfigurationError(
                "Capabilities must be an instance of EmbeddingModelCapabilities",
                details={"provided_type": type(caps).__name__},
                suggestions=[
                    "Ensure the capabilities resolver returns the correct type",
                    "Check the implementation of the capabilities resolver",
                ],
            )
        object.__setattr__(
            parent_cls,
            "__init__",
            make_init(
                cls, provider, _client=client, _config=config, _registry=registry, _caps=caps
            ),
        )
        if initialize_method:
            object.__setattr__(parent_cls, "_initialize", initialize_method)

        # Create the new provider class with proper field definitions
        new_class = create_model(
            name,
            __doc__=f"An embedding provider class for {str(provider).title()}.\n\nI was proudly made in the `codeweaver.providers.embedding.providers.openai_factory` module by hardworking electrons.",
            __base__=parent_cls,
            __module__="codeweaver.providers.embedding.providers.openai_factory",
            __validators__=None,
            client=(AsyncOpenAI, client),
            _provider=(Provider, provider),
            config=(OpenAIEmbeddingConfig, config),
            registry=(EmbeddingRegistry, registry),
            caps=(EmbeddingModelCapabilities, caps),
        )

        # Set metadata attributes that aren't Pydantic fields
        new_class._default_model_name = model_name
        new_class._default_provider = provider
        new_class._default_config = config or {}
        new_class._default_registry = registry
        return new_class

    client: AsyncOpenAI
    provider: ClassVar[Provider]

    def _initialize(
        self,
        impl_deps: EmbeddingImplementationDeps = None,
        custom_deps: EmbeddingCustomDeps = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the OpenAI client."""
        # Nothing to initialize here - options are set in model_post_init

    @property
    def base_url(self) -> str:
        """Get the base URL for the OpenAI client."""
        return (
            self.client._base_url  # type: ignore[attr-defined]
            if hasattr(self.client, "_base_url") and self.client._base_url
            else os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
        )

    @property
    def dimension(self) -> int:
        """Get the dimension of the embeddings."""
        return self.embed_options.get("dimensions") or self.caps.default_dimension or 1024

    def _report(
        self,
        response: CreateEmbeddingResponse,
        texts: Sequence[str],
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Report token usage statistics.

        Note: This sync method is only called from async contexts.
        """
        try:
            loop = loop or asyncio_or_uvloop().get_running_loop()
            if response.usage and (token_count := response.usage.total_tokens):
                _ = loop.call_soon_threadsafe(
                    lambda: self._update_token_stats(token_count=token_count)
                )
            else:
                _ = loop.call_soon_threadsafe(lambda: self._update_token_stats(from_docs=texts))
        except RuntimeError:
            # No running loop - shouldn't happen in normal usage since called from async methods
            # Fall back to synchronous execution
            if response.usage and (token_count := response.usage.total_tokens):
                self._fire_and_forget(
                    lambda: self._update_token_stats(token_count=token_count), loop=loop
                )
            else:
                self._fire_and_forget(lambda: self._update_token_stats(from_docs=texts), loop=loop)

    async def _get_vectors(
        self, texts: Sequence[str], *, is_query: bool = False, **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Get vectors for a sequence of texts."""
        kwargs = (self.query_options if is_query else self.embed_options) | kwargs
        response = await self.client.embeddings.create(input=cast(list[str], texts), **kwargs)
        if not response or not response.data:
            raise ProviderError(
                "OpenAI embeddings endpoint returned empty response",
                details={
                    "provider": str(type(self)._provider),
                    "model": self.model_name,
                    "base_url": self.base_url,
                    "has_response": response is not None,
                    "has_data": response.data is not None if response else False,
                },
                suggestions=[
                    "Check API key is valid and has correct permissions",
                    "Verify the model name is correct",
                    "Check network connectivity to the API endpoint",
                    "Review API rate limits and quotas",
                ],
            )
        loop = await self._get_loop()
        self._report(response, cast(list[str], texts), loop=loop)
        results = sorted(response.data, key=lambda x: x.index)
        return [result.embedding for result in results]

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a sequence of documents."""
        if not isinstance(next(iter(documents), CodeChunk), CodeChunk):
            raise CodeWeaverValidationError(
                "Documents must be CodeChunk instances for embedding",
                details={
                    "received_type": type(next(iter(documents), None)).__name__,
                    "document_count": len(documents),
                },
                suggestions=[
                    "Ensure documents are CodeChunk objects",
                    "Convert documents to CodeChunk format before embedding",
                ],
            )
        await asyncio.sleep(0)
        texts = self.chunks_to_strings(documents)
        await asyncio.sleep(0)
        return await self._get_vectors(cast(list[str], texts), **kwargs)

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        await asyncio.sleep(0)
        return await self._get_vectors(query, is_query=True, **kwargs)


__all__ = ("OpenAIEmbeddingBase",)
