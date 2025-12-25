# SPDX-FileCopyrightText: 2024-2025 Qdrant Solutions GmbH
# SPDX-License-Identifier: Apache-2.0
# This file was adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/)
#
# Modification/changes:
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Search filtering and matching utilities.

This package is heavily derived from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant). We've made small modifications to fit our use case, and those changes are copyrighted by Knitli Inc. and licensed under MIT OR Apache-2.0, whichever you want. Original code from Qdrant remains under their copyright and Apache 2.0 license.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.common.utils.lazy_getter import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.vector_stores.search.condition import (
        Condition,
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
        ValuesCount,
    )
    from codeweaver.providers.vector_stores.search.filter_factory import (
        ArbitraryFilter,
        make_filter,
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
        ExtendedPointId,
        Match,
        MatchAny,
        MatchExcept,
        MatchPhrase,
        MatchText,
        MatchValue,
        ValueVariants,
    )
    from codeweaver.providers.vector_stores.search.payload import (
        Entry,
        PayloadField,
        PayloadMetadata,
        PayloadSchemaType,
    )
    from codeweaver.providers.vector_stores.search.range import DatetimeRange, Range, RangeInterface
    from codeweaver.providers.vector_stores.search.wrap_filters import (
        make_partial_function,
        wrap_filters,
    )


parent = __spec__.parent or "codeweaver.providers.vector_stores.search"

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "Condition": (parent, "condition"),
    "FieldCondition": (parent, "condition"),
    "Filter": (parent, "condition"),
    "FilterableField": (parent, "condition"),
    "HasIdCondition": (parent, "condition"),
    "HasVectorCondition": (parent, "condition"),
    "IsEmptyCondition": (parent, "condition"),
    "IsNullCondition": (parent, "condition"),
    "MinShould": (parent, "condition"),
    "Nested": (parent, "condition"),
    "NestedCondition": (parent, "condition"),
    "ValuesCount": (parent, "condition"),
    "ArbitraryFilter": (parent, "filter_factory"),
    "make_filter": (parent, "filter_factory"),
    "to_qdrant_filter": (parent, "filter_factory"),
    "GeoBoundingBox": (parent, "geo"),
    "GeoPoint": (parent, "geo"),
    "GeoPolygon": (parent, "geo"),
    "GeoRadius": (parent, "geo"),
    "GeoLineString": (parent, "geo"),
    "MatchAny": (parent, "match"),
    "MatchExcept": (parent, "match"),
    "MatchPhrase": (parent, "match"),
    "MatchText": (parent, "match"),
    "MatchValue": (parent, "match"),
    "ValueVariants": (parent, "match"),
    "AnyVariants": (parent, "match"),
    "ExtendedPointId": (parent, "match"),
    "Match": (parent, "match"),
    "RangeInterface": (parent, "range"),
    "Range": (parent, "range"),
    "DatetimeRange": (parent, "range"),
    "wrap_filters": (parent, "wrap_filters"),
    "make_partial_function": (parent, "wrap_filters"),
    "Entry": (parent, "payload"),
    "PayloadField": (parent, "payload"),
    "PayloadMetadata": (parent, "payload"),
    "PayloadSchemaType": (parent, "payload"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "AnyVariants",
    "ArbitraryFilter",
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
    "PayloadMetadata",
    "PayloadSchemaType",
    "Range",
    "RangeInterface",
    "ValueVariants",
    "ValuesCount",
    "make_filter",
    "make_partial_function",
    "to_qdrant_filter",
    "wrap_filters",
)
