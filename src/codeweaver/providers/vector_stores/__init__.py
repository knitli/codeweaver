# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Vector store interfaces and implementations for CodeWeaver."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.vector_stores.base import (
        CircuitBreakerOpenError,
        MixedQueryInput,
        VectorStoreProvider,
    )
    from codeweaver.providers.vector_stores.inmemory import (
        AsyncPath,
        MemoryVectorStoreProvider,
        PersistenceError,
        ProviderError,
    )
    from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider
    from codeweaver.providers.vector_stores.qdrant_base import (
        ConfigurationError,
        QdrantBaseProvider,
        ResolvedProjectNameDep,
    )
    from codeweaver.providers.vector_stores.qdrant_service import (
        ProviderSettingsDep,
        QdrantVectorStoreService,
        create_qdrant_service,
    )
    from codeweaver.providers.vector_stores.search import MappingProxyType
    from codeweaver.providers.vector_stores.search.condition import (
        Condition,
        ExtendedPointId,
        FieldCondition,
        Filter,
        FilterableField,
        HasIdCondition,
        HasVectorCondition,
        IsEmptyCondition,
        IsNullCondition,
        MinShould,
        Nested,
        NestedCondition,
        PayloadSchemaType,
        ValuesCount,
    )
    from codeweaver.providers.vector_stores.search.geo import (
        GeoBoundingBox,
        GeoLineString,
        GeoPoint,
        GeoPolygon,
        GeoRadius,
    )
    from codeweaver.providers.vector_stores.search.match import (
        AnyVariants,
        Match,
        MatchAny,
        MatchExcept,
        MatchPhrase,
        MatchText,
        MatchValue,
        ValueVariants,
    )
    from codeweaver.providers.vector_stores.search.payload import Entry, PayloadField
    from codeweaver.providers.vector_stores.search.range import DatetimeRange, Range, RangeInterface

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AsyncPath": (__spec__.parent, "inmemory"),
    "CircuitBreakerOpenError": (__spec__.parent, "base"),
    "ConfigurationError": (__spec__.parent, "qdrant_base"),
    "DatetimeRange": (__spec__.parent, "search.range"),
    "Entry": (__spec__.parent, "search.payload"),
    "FieldCondition": (__spec__.parent, "search.condition"),
    "Filter": (__spec__.parent, "search.condition"),
    "FilterableField": (__spec__.parent, "search.condition"),
    "GeoBoundingBox": (__spec__.parent, "search.geo"),
    "GeoLineString": (__spec__.parent, "search.geo"),
    "GeoPoint": (__spec__.parent, "search.geo"),
    "GeoPolygon": (__spec__.parent, "search.geo"),
    "GeoRadius": (__spec__.parent, "search.geo"),
    "HasIdCondition": (__spec__.parent, "search.condition"),
    "HasVectorCondition": (__spec__.parent, "search.condition"),
    "IsEmptyCondition": (__spec__.parent, "search.condition"),
    "IsNullCondition": (__spec__.parent, "search.condition"),
    "MappingProxyType": (__spec__.parent, "search"),
    "MatchAny": (__spec__.parent, "search.match"),
    "MatchExcept": (__spec__.parent, "search.match"),
    "MatchPhrase": (__spec__.parent, "search.match"),
    "MatchText": (__spec__.parent, "search.match"),
    "MatchValue": (__spec__.parent, "search.match"),
    "MemoryVectorStoreProvider": (__spec__.parent, "inmemory"),
    "MinShould": (__spec__.parent, "search.condition"),
    "Nested": (__spec__.parent, "search.condition"),
    "NestedCondition": (__spec__.parent, "search.condition"),
    "PayloadField": (__spec__.parent, "search.payload"),
    "PayloadSchemaType": (__spec__.parent, "search.condition"),
    "PersistenceError": (__spec__.parent, "inmemory"),
    "ProviderError": (__spec__.parent, "inmemory"),
    "ProviderSettingsDep": (__spec__.parent, "qdrant_service"),
    "QdrantBaseProvider": (__spec__.parent, "qdrant_base"),
    "QdrantVectorStoreProvider": (__spec__.parent, "qdrant"),
    "QdrantVectorStoreService": (__spec__.parent, "qdrant_service"),
    "Range": (__spec__.parent, "search.range"),
    "ResolvedProjectNameDep": (__spec__.parent, "qdrant_base"),
    "ValuesCount": (__spec__.parent, "search.condition"),
    "VectorStoreProvider": (__spec__.parent, "base"),
    "create_qdrant_service": (__spec__.parent, "qdrant_service"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "AnyVariants",
    "AsyncPath",
    "CircuitBreakerOpenError",
    "Condition",
    "ConfigurationError",
    "DatetimeRange",
    "Entry",
    "ExtendedPointId",
    "FieldCondition",
    "Filter",
    "FilterableField",
    "GeoBoundingBox",
    "GeoLineString",
    "GeoPoint",
    "GeoPolygon",
    "GeoRadius",
    "HasIdCondition",
    "HasVectorCondition",
    "IsEmptyCondition",
    "IsNullCondition",
    "MappingProxyType",
    "Match",
    "MatchAny",
    "MatchExcept",
    "MatchPhrase",
    "MatchText",
    "MatchValue",
    "MemoryVectorStoreProvider",
    "MinShould",
    "MixedQueryInput",
    "Nested",
    "NestedCondition",
    "PayloadField",
    "PayloadSchemaType",
    "PersistenceError",
    "ProviderError",
    "ProviderSettingsDep",
    "QdrantBaseProvider",
    "QdrantVectorStoreProvider",
    "QdrantVectorStoreService",
    "Range",
    "RangeInterface",
    "ResolvedProjectNameDep",
    "ValueVariants",
    "ValuesCount",
    "VectorStoreProvider",
    "create_qdrant_service",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
