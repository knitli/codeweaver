# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider types and shared classes."""

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core.utils.lazy_importer import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.types.circuit_breaker import CircuitBreakerState
    from codeweaver.providers.types.embedding import ConfiguredCapability, EmbeddingCapabilityGroup
    from codeweaver.providers.types.resolvers import (
        BaseCapabilityResolver,
        BaseEmbeddingCapabilityResolver,
        BaseRerankingCapabilityResolver,
        BaseResolver,
        BaseSparseEmbeddingCapabilityResolver,
        EmbeddingCapabilityType,
        RerankingCapabilityType,
    )
    from codeweaver.providers.types.search import ModelCapDict, ModelNameDict, SearchPackage
    from codeweaver.providers.types.vector_store import (
        CollectionMetadata,
        HybridVectorPayload,
        PayloadFieldDict,
    )
    from codeweaver.providers.types.vectors import VectorConfig, VectorRole, VectorSet


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "BaseCapabilityResolver": (__spec__.parent, "resolvers"),
    "BaseEmbeddingCapabilityResolver": (__spec__.parent, "resolvers"),
    "BaseRerankingCapabilityResolver": (__spec__.parent, "resolvers"),
    "BaseResolver": (__spec__.parent, "resolvers"),
    "BaseSparseEmbeddingCapabilityResolver": (__spec__.parent, "resolvers"),
    "CircuitBreakerState": (__spec__.parent, "circuit_breaker"),
    "CollectionMetadata": (__spec__.parent, "vector_store"),
    "ConfiguredCapability": (__spec__.parent, "embedding"),
    "EmbeddingCapabilityGroup": (__spec__.parent, "embedding"),
    "EmbeddingCapabilityType": (__spec__.parent, "resolvers"),
    "HybridVectorPayload": (__spec__.parent, "vector_store"),
    "ModelCapDict": (__spec__.parent, "search"),
    "ModelNameDict": (__spec__.parent, "search"),
    "PayloadFieldDict": (__spec__.parent, "vector_store"),
    "RerankingCapabilityType": (__spec__.parent, "resolvers"),
    "SearchPackage": (__spec__.parent, "search"),
    "VectorConfig": (__spec__.parent, "vectors"),
    "VectorRole": (__spec__.parent, "vectors"),
    "VectorSet": (__spec__.parent, "vectors"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "BaseCapabilityResolver",
    "BaseEmbeddingCapabilityResolver",
    "BaseRerankingCapabilityResolver",
    "BaseResolver",
    "BaseSparseEmbeddingCapabilityResolver",
    "CircuitBreakerState",
    "CollectionMetadata",
    "ConfiguredCapability",
    "EmbeddingCapabilityGroup",
    "EmbeddingCapabilityType",
    "HybridVectorPayload",
    "ModelCapDict",
    "ModelNameDict",
    "PayloadFieldDict",
    "RerankingCapabilityType",
    "SearchPackage",
    "VectorConfig",
    "VectorRole",
    "VectorSet",
)


def __dir__():
    """Return the list of attributes for this module, including dynamically imported ones."""
    return list(__all__)
