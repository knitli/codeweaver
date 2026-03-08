# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider types and shared classes."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.types.circuit_breaker import CircuitBreakerState
    from codeweaver.providers.types.embedding import (
        ConfiguredCapability,
        EmbeddingCapabilityGroup,
        InvalidEmbeddingModelError,
    )
    from codeweaver.providers.types.resolvers import (
        BaseCapabilityResolver,
        BaseEmbeddingCapabilityResolver,
        BaseRerankingCapabilityResolver,
        BaseResolver,
        BaseSparseEmbeddingCapabilityResolver,
        EmbeddingCapabilityType,
        MappingProxyType,
        RerankingCapabilityType,
    )
    from codeweaver.providers.types.search import ModelCapDict, ModelNameDict, SearchPackage
    from codeweaver.providers.types.vector_store import (
        CollectionMetadata,
        CollectionPolicy,
        HybridVectorPayload,
        ModelSwitchError,
        PayloadFieldDict,
        TransformationRecord,
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
    "CollectionPolicy": (__spec__.parent, "vector_store"),
    "ConfiguredCapability": (__spec__.parent, "embedding"),
    "EmbeddingCapabilityGroup": (__spec__.parent, "embedding"),
    "EmbeddingCapabilityType": (__spec__.parent, "resolvers"),
    "HybridVectorPayload": (__spec__.parent, "vector_store"),
    "RerankingCapabilityType": (__spec__.parent, "resolvers"),
    "InvalidEmbeddingModelError": (__spec__.parent, "embedding"),
    "MappingProxyType": (__spec__.parent, "resolvers"),
    "ModelCapDict": (__spec__.parent, "search"),
    "ModelNameDict": (__spec__.parent, "search"),
    "ModelSwitchError": (__spec__.parent, "vector_store"),
    "PayloadFieldDict": (__spec__.parent, "vector_store"),
    "SearchPackage": (__spec__.parent, "search"),
    "TransformationRecord": (__spec__.parent, "vector_store"),
    "VectorConfig": (__spec__.parent, "vectors"),
    "VectorRole": (__spec__.parent, "vectors"),
    "VectorSet": (__spec__.parent, "vectors"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "BaseCapabilityResolver",
    "BaseEmbeddingCapabilityResolver",
    "BaseRerankingCapabilityResolver",
    "BaseResolver",
    "BaseSparseEmbeddingCapabilityResolver",
    "CircuitBreakerState",
    "CollectionMetadata",
    "CollectionPolicy",
    "ConfiguredCapability",
    "EmbeddingCapabilityGroup",
    "EmbeddingCapabilityType",
    "HybridVectorPayload",
    "InvalidEmbeddingModelError",
    "MappingProxyType",
    "ModelCapDict",
    "ModelNameDict",
    "ModelSwitchError",
    "PayloadFieldDict",
    "RerankingCapabilityType",
    "SearchPackage",
    "TransformationRecord",
    "VectorConfig",
    "VectorRole",
    "VectorSet",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
