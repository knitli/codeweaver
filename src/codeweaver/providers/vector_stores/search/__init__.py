# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Search filtering and matching utilities.

This package is heavily derived from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant). We've made small modifications to fit our use case, and those changes are copyrighted by Knitli Inc. and licensed under MIT OR Apache-2.0, whichever you want. Original code from Qdrant remains under their copyright and Apache 2.0 license.
"""

from __future__ import annotations


parent = __spec__.parent or "codeweaver.providers.vector_stores.search"

# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
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
    from codeweaver.providers.vector_stores.search.filter_factory import (
        make_filter,
        make_indexes,
        to_qdrant_filter,
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
    from codeweaver.providers.vector_stores.search.wrap_filters import (
        make_partial_function,
        wrap_filters,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DatetimeRange": (__spec__.parent, "range"),
    "Entry": (__spec__.parent, "payload"),
    "FieldCondition": (__spec__.parent, "condition"),
    "Filter": (__spec__.parent, "condition"),
    "FilterableField": (__spec__.parent, "condition"),
    "GeoBoundingBox": (__spec__.parent, "geo"),
    "GeoLineString": (__spec__.parent, "geo"),
    "GeoPoint": (__spec__.parent, "geo"),
    "GeoPolygon": (__spec__.parent, "geo"),
    "GeoRadius": (__spec__.parent, "geo"),
    "HasIdCondition": (__spec__.parent, "condition"),
    "HasVectorCondition": (__spec__.parent, "condition"),
    "IsEmptyCondition": (__spec__.parent, "condition"),
    "IsNullCondition": (__spec__.parent, "condition"),
    "MatchAny": (__spec__.parent, "match"),
    "MatchExcept": (__spec__.parent, "match"),
    "MatchPhrase": (__spec__.parent, "match"),
    "MatchText": (__spec__.parent, "match"),
    "MatchValue": (__spec__.parent, "match"),
    "MinShould": (__spec__.parent, "condition"),
    "Nested": (__spec__.parent, "condition"),
    "NestedCondition": (__spec__.parent, "condition"),
    "PayloadField": (__spec__.parent, "payload"),
    "PayloadSchemaType": (__spec__.parent, "condition"),
    "Range": (__spec__.parent, "range"),
    "ValuesCount": (__spec__.parent, "condition"),
    "make_filter": (__spec__.parent, "filter_factory"),
    "make_indexes": (__spec__.parent, "filter_factory"),
    "make_partial_function": (__spec__.parent, "wrap_filters"),
    "to_qdrant_filter": (__spec__.parent, "filter_factory"),
    "wrap_filters": (__spec__.parent, "wrap_filters"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "AnyVariants",
    "Condition",
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
    "MinShould",
    "Nested",
    "NestedCondition",
    "PayloadField",
    "PayloadSchemaType",
    "Range",
    "RangeInterface",
    "ValueVariants",
    "ValuesCount",
    "make_filter",
    "make_indexes",
    "make_partial_function",
    "to_qdrant_filter",
    "wrap_filters",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
