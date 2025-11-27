# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Vector store interfaces and implementations for CodeWeaver."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from codeweaver.exceptions import ConfigurationError


if TYPE_CHECKING:
    from codeweaver.config.providers import VectorStoreProviderSettings
    from codeweaver.providers.vector_stores.base import VectorStoreProvider
    from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider
    from codeweaver.providers.vector_stores.metadata import CollectionMetadata, HybridVectorPayload
    from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider
    from codeweaver.providers.vector_stores.utils import resolve_dimensions


def get_vector_store_provider(settings: VectorStoreProviderSettings) -> VectorStoreProvider[Any]:
    """Create vector store provider from settings.

    Args:
        settings: Vector store configuration with provider selection and config.
        embedder: Optional embedding provider for dimension validation (required for Qdrant).
        reranking: Optional reranking provider for search result optimization.

    Returns:
        Configured vector store provider instance (QdrantVectorStoreProvider or MemoryVectorStoreProvider).

    Raises:
        ValueError: If provider type is not recognized or required config is missing.
        ImportError: If required dependencies for selected provider are not installed.

    Examples:
        >>> from codeweaver.config.providers import VectorStoreProviderSettings
        >>> settings = VectorStoreProviderSettings(provider=Provider.MEMORY)
        >>> provider = get_vector_store_provider(settings)
        >>> isinstance(provider, MemoryVectorStoreProvider)
        True

        >>> from unittest.mock import MagicMock
        >>> qdrant_settings = VectorStoreProviderSettings(
        ...     provider="qdrant",
        ...     qdrant={"url": "http://localhost:6333", "collection_name": "test"},
        ... )
        >>> mock_embedder = MagicMock()
        >>> provider = get_vector_store_provider(qdrant_settings)
        >>> isinstance(provider, QdrantVectorStoreProvider)
        True
    """
    from codeweaver.providers.provider import Provider
    from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider
    from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider

    provider_type = settings.get("provider", Provider.MEMORY)

    if provider_type == Provider.QDRANT:
        if qdrant_config := settings.get("qdrant", {}):
            return QdrantVectorStoreProvider.model_construct(
                config=qdrant_config, _client=None, _metadata=None
            )

        raise ConfigurationError(
            "Qdrant configuration missing",
            details={"provider": "qdrant", "config_location": "QdrantConfig parameter"},
            suggestions=[
                "Provide QdrantConfig when using Qdrant provider",
                "Set QDRANT_URL and QDRANT_API_KEY environment variables",
                "Check qdrant section in configuration file",
            ],
        )
    if provider_type == Provider.MEMORY:
        memory_config = settings.get("memory", {})
        return MemoryVectorStoreProvider.model_construct(config=memory_config, _client=None)

    raise ConfigurationError(
        f"Unknown vector store provider: {provider_type}",
        details={
            "provided_provider": str(provider_type),
            "supported_providers": ["qdrant", "memory"],
        },
        suggestions=[
            "Use one of the supported providers: qdrant, memory",
            "Check provider name spelling in configuration",
            "Install required provider package",
        ],
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "MemoryVectorStoreProvider": (__spec__.parent, "inmemory"),
    "QdrantVectorStoreProvider": (__spec__.parent, "qdrant"),
    "VectorStoreProvider": (__spec__.parent, "base"),
    "HybridVectorPayload": (__spec__.parent, "metadata"),
    "CollectionMetadata": (__spec__.parent, "metadata"),
    "resolve_dimensions": (__spec__.parent, "utils"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the vector_stores package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = (
    "CollectionMetadata",
    "HybridVectorPayload",
    "MemoryVectorStoreProvider",
    "QdrantVectorStoreProvider",
    "VectorStoreProvider",
    "get_vector_store_provider",
    "resolve_dimensions",
)


def __dir__() -> list[str]:
    """List available attributes for the module."""
    return list(__all__)
