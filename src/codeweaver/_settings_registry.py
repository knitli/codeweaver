# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Provider registry system for dynamic provider registration and management."""

from __future__ import annotations

import contextlib

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any

from codeweaver._settings import Provider, ProviderKind
from codeweaver.embedding.providers import EmbeddingProvider
from codeweaver.exceptions import ConfigurationError
from codeweaver.reranking.providers.base import RerankingProvider
from codeweaver.vector_stores.base import VectorStoreProvider


if TYPE_CHECKING:
    from codeweaver.settings import CodeWeaverSettings


class ProviderRegistry:
    """Registry for managing provider implementations and settings."""

    _instance: ProviderRegistry | None = None
    _settings: CodeWeaverSettings | None = None

    def __init__(self) -> None:
        """Initialize the provider registry."""
        # Provider implementation registries
        self._embedding_providers: MutableMapping[Provider, type[EmbeddingProvider[Any]]] = {}
        self._vector_store_providers: MutableMapping[
            Provider, type[VectorStoreProvider[Any, EmbeddingProvider[Any], RerankingProvider[Any]]]
        ] = {}
        self._embedding_instances: MutableMapping[Provider, EmbeddingProvider[Any]] = {}
        self._vector_store_instances: MutableMapping[
            Provider, VectorStoreProvider[Any, EmbeddingProvider[Any], RerankingProvider[Any]]
        ] = {}

        # Initialize with built-in providers
        self._register_builtin_providers()

    @classmethod
    def get_instance(cls) -> ProviderRegistry:
        """Get or create the global provider registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self, provider: Provider, provider_kind: ProviderKind, provider_class: type
    ) -> None:
        """Register a provider implementation.

        Args:
            provider: The provider enum identifier
            provider_kind: The type of provider (embedding or vector store)
            provider_class: The provider implementation class
        """
        if provider_kind == ProviderKind.EMBEDDING:
            self.register_embedding_provider(provider, provider_class)
        elif provider_kind == ProviderKind.VECTOR_STORE:
            self.register_vector_store_provider(provider, provider_class)

    def _register_builtin_providers(self) -> None:
        """Register built-in provider implementations."""
        # Register embedding providers dynamically
        with contextlib.suppress(ImportError):
            from codeweaver.embedding.providers.voyage import VoyageEmbeddingProvider

            self._embedding_providers[Provider.VOYAGE] = VoyageEmbeddingProvider

        with contextlib.suppress(ImportError):
            from codeweaver.embedding.providers.fastembed import FastEmbedProvider

            self._embedding_providers[Provider.FASTEMBED] = FastEmbedProvider

        with contextlib.suppress(ImportError):
            from codeweaver.embedding.providers.openai import OpenAIEmbeddingProvider

            self._embedding_providers[Provider.OPENAI] = OpenAIEmbeddingProvider

        # Register vector store providers dynamically
        with contextlib.suppress(ImportError):
            from codeweaver.vector_stores.qdrant import QdrantVectorStore

            self._vector_store_providers[Provider.QDRANT] = QdrantVectorStore

        with contextlib.suppress(ImportError):
            from codeweaver.vector_stores.memory import FastembedVectorstore

            self._vector_store_providers[Provider.FASTEMBED_VECTORSTORE] = FastembedVectorstore  # pyright: ignore[reportArgumentType]

    def add_settings(self, settings: CodeWeaverSettings) -> None:
        """Add settings to the provider registry."""
        self._settings = settings

    def register_embedding_provider(
        self, provider: Provider, provider_class: type[EmbeddingProvider[Any]]
    ) -> None:
        """Register an embedding provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        if not issubclass(provider_class, EmbeddingProvider):  # type: ignore
            raise TypeError(
                f"Provider class must be a subclass of EmbeddingProvider, got {provider_class}"
            )

        self._embedding_providers[provider] = provider_class

    def register_vector_store_provider(
        self,
        provider: Provider,
        provider_class: type[
            VectorStoreProvider[Any, EmbeddingProvider[Any], RerankingProvider[Any]]
        ],
    ) -> None:
        """Register a vector store provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        if not issubclass(provider_class, VectorStoreProvider):  # type: ignore  # this one of those "just check anyway" situations
            raise TypeError(
                f"Provider class must be a subclass of VectorStoreProvider, got {provider_class}"
            )

        self._vector_store_providers[provider] = provider_class

    def get_embedding_provider_class(self, provider: Provider) -> type[EmbeddingProvider[Any]]:
        """Get an embedding provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._embedding_providers:
            raise ConfigurationError(f"Embedding provider '{provider}' is not registered")

        return self._embedding_providers[provider]

    def get_vector_store_provider_class(
        self, provider: Provider
    ) -> type[VectorStoreProvider[Any, EmbeddingProvider[Any], RerankingProvider[Any]]]:
        """Get a vector store provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._vector_store_providers:
            raise ConfigurationError(f"Vector store provider '{provider}' is not registered")

        return self._vector_store_providers[provider]

    def create_embedding_provider(
        self, provider: Provider, **kwargs: Any
    ) -> EmbeddingProvider[Any]:
        """Create an embedding provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        provider_class = self.get_embedding_provider_class(provider)
        return provider_class(**kwargs)

    def create_vector_store_provider(
        self, provider: Provider, **kwargs: Any
    ) -> VectorStoreProvider[Any, EmbeddingProvider[Any], RerankingProvider[Any]]:
        """Create a vector store provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        provider_class = self.get_vector_store_provider_class(provider)
        return provider_class(**kwargs)

    def get_embedding_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> EmbeddingProvider[Any]:
        """Get an embedding provider instance, optionally cached.

        Args:
            provider: The provider enum identifier
            singleton: Whether to cache and reuse the instance
            **kwargs: Provider-specific initialization arguments

        Returns:
            A provider instance
        """
        if singleton and provider in self._embedding_instances:
            return self._embedding_instances[provider]

        instance = self.create_embedding_provider(provider, **kwargs)

        if singleton:
            self._embedding_instances[provider] = instance

        return instance

    def get_vector_store_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> VectorStoreProvider[Any, EmbeddingProvider[Any], RerankingProvider[Any]]:
        """Get a vector store provider instance, optionally cached.

        Args:
            provider: The provider enum identifier
            singleton: Whether to cache and reuse the instance
            **kwargs: Provider-specific initialization arguments

        Returns:
            A provider instance
        """
        if singleton and provider in self._vector_store_instances:
            return self._vector_store_instances[provider]

        instance = self.create_vector_store_provider(provider, **kwargs)

        if singleton:
            self._vector_store_instances[provider] = instance

        return instance

    def list_providers(self, provider_kind: ProviderKind) -> list[Provider]:
        """List available providers for a given provider kind.

        Args:
            provider_kind: The type of provider to list

        Returns:
            List of available provider enums
        """
        if provider_kind == ProviderKind.EMBEDDING:
            return list(self._embedding_providers.keys())
        if provider_kind == ProviderKind.VECTOR_STORE:
            return list(self._vector_store_providers.keys())
        return []

    def is_provider_available(self, provider: Provider, provider_kind: ProviderKind) -> bool:
        """Check if a provider is available for a given provider kind.

        Args:
            provider: The provider to check
            provider_kind: The type of provider to check

        Returns:
            True if the provider is available
        """
        if provider_kind == ProviderKind.EMBEDDING:
            return provider in self._embedding_providers
        if provider_kind == ProviderKind.VECTOR_STORE:
            return provider in self._vector_store_providers
        return False

    def clear_instances(self) -> None:
        """Clear all cached provider instances."""
        self._embedding_instances.clear()
        self._vector_store_instances.clear()


# Global registry instance
_registry = ProviderRegistry()


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance."""
    return _registry


def register_embedding_provider(
    provider: Provider, provider_class: type[EmbeddingProvider[Any]]
) -> None:
    """Register an embedding provider with the global registry.

    Args:
        provider: The provider enum identifier
        provider_class: The provider implementation class
    """
    _registry.register_embedding_provider(provider, provider_class)


def register_vector_store_provider(
    provider: Provider,
    provider_class: type[VectorStoreProvider[Any, EmbeddingProvider[Any], RerankingProvider[Any]]],
) -> None:
    """Register a vector store provider with the global registry.

    Args:
        provider: The provider enum identifier
        provider_class: The provider implementation class
    """
    _registry.register_vector_store_provider(provider, provider_class)
