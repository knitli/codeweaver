# SPDX-FileCopyrightText: 2024-2025 Qdrant Solutions GmbH
# SPDX-License-Identifier: Apache-2.0
# This file was adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/)
#
# Modification/changes:
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Module defining various search conditions for filtering points based on payload and other criteria.

Nearly all of this file and its contents were adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/), and fall under Qdrant's copyright and Apache 2.0 license. Any modifications or changes made to the original code are copyrighted by Knitli Inc. and are licensed under MIT OR Apache-2.0, whichever you want.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StrictInt, StrictStr

from codeweaver.engine.search.geo import GeoBoundingBox, GeoPolygon, GeoRadius
from codeweaver.engine.search.match import Match
from codeweaver.engine.search.payload import PayloadField, PayloadSchemaType
from codeweaver.engine.search.range import RangeInterface


class MinShould(BaseModel, extra="forbid"):
    """
    Minimum number of conditions that must match.
    """

    conditions: Annotated[Sequence[Condition], Field(description="""List of conditions""")]
    min_count: Annotated[int, Field(description="""Minimum count of conditions that must match""")]


class NestedCondition(BaseModel, extra="forbid"):
    """
    Select points with payload for a specified nested field.
    """

    nested: Annotated[
        Nested, Field(description="""Select points with payload for a specified nested field""")
    ]


class IsEmptyCondition(BaseModel, extra="forbid"):
    """
    Select points with empty payload for a specified field.
    """

    is_empty: Annotated[
        PayloadField,
        Field(description="""Select points with empty payload for a specified field"""),
    ]


class IsNullCondition(BaseModel, extra="forbid"):
    """
    Select points with null payload for a specified field.
    """

    is_null: Annotated[
        PayloadField, Field(description="""Select points with null payload for a specified field""")
    ]


type ExtendedPointId = StrictInt | StrictStr


class HasIdCondition(BaseModel, extra="forbid"):
    """
    ID-based filtering condition.
    """

    has_id: Annotated[
        Sequence[ExtendedPointId], Field(description="""ID-based filtering condition""")
    ]


class HasVectorCondition(BaseModel, extra="forbid"):
    """
    Filter points which have specific vector assigned.
    """

    has_vector: Annotated[
        str, Field(description="""Filter points which have specific vector assigned""")
    ]


class ValuesCount(BaseModel, extra="forbid"):
    """
    Values count filter request.
    """

    lt: Annotated[int | None, Field(description="""point.key.length() &lt; values_count.lt""")] = (
        None
    )
    gt: Annotated[int | None, Field(description="""point.key.length() &gt; values_count.gt""")] = (
        None
    )
    gte: Annotated[
        int | None, Field(description="""point.key.length() &gt;= values_count.gte""")
    ] = None
    lte: Annotated[
        int | None, Field(description="""point.key.length() &lt;= values_count.lte""")
    ] = None


class FieldCondition(BaseModel, extra="forbid"):
    """
    All possible payload filtering conditions.
    """

    key: str = Field(description="""Payload key""")
    match: Annotated[
        Match | None, Field(description="""Check if point has field with a given value""")
    ] = None
    range: Annotated[
        RangeInterface | None, Field(description="""Check if points value lies in a given range""")
    ] = None
    geo_bounding_box: Annotated[
        GeoBoundingBox | None,
        Field(description="""Check if points geolocation lies in a given area"""),
    ] = None
    geo_radius: Annotated[
        GeoRadius | None, Field(description="""Check if geo point is within a given radius""")
    ] = None
    geo_polygon: Annotated[
        GeoPolygon | None, Field(description="""Check if geo point is within a given polygon""")
    ] = None
    values_count: Annotated[
        ValuesCount | None, Field(description="""Check number of values of the field""")
    ] = None
    is_empty: Annotated[
        bool | None,
        Field(
            description="""Check that the field is empty, alternative syntax for `is_empty: 'field_name'`"""
        ),
    ] = None
    is_null: Annotated[
        bool | None,
        Field(
            description="""Check that the field is null, alternative syntax for `is_null: 'field_name'`"""
        ),
    ] = None


class Filter(BaseModel, extra="forbid"):
    """Filter conditions."""

    should: Annotated[
        Sequence[Condition] | Condition | None,
        Field(default=None, description="""At least one of those conditions should match"""),
    ] = None
    min_should: Annotated[
        MinShould | None,
        Field(
            default=None, description="""At least minimum amount of given conditions should match"""
        ),
    ] = None
    must: Annotated[
        Sequence[Condition] | Condition | None,
        Field(default=None, description="""All conditions must match"""),
    ] = None
    must_not: Annotated[
        Sequence[Condition] | Condition | None,
        Field(default=None, description="""All conditions must NOT match"""),
    ] = None


class Nested(BaseModel, extra="forbid"):
    """
    Select points with payload for a specified nested field.
    """

    key: Annotated[
        str, Field(description="""Select points with payload for a specified nested field""")
    ]
    filter: Annotated[
        Filter, Field(description="""Select points with payload for a specified nested field""")
    ]


class FilterableField(BaseModel):
    """Represents a field that can be filtered."""

    name: str = Field(description="""The name of the payload field to filter on""")
    description: str = Field(
        description="""A description for the field used in the tool description"""
    )
    field_type: PayloadSchemaType = Field(description="""The type of the field""")
    condition: Annotated[
        Literal["any", "except", "match", "range", "geo_bounding_box", "geo_radius", "geo_polygon"]
        | None,
        Field(description="""The type of condition applicable to the field"""),
    ] = None
    required: Annotated[
        bool, Field(description="""Whether the field is required for the filter.""")
    ] = False


type Condition = (
    FieldCondition
    | IsEmptyCondition
    | IsNullCondition
    | HasIdCondition
    | HasVectorCondition
    | NestedCondition
    | Filter
)


__all__ = (
    "Condition",
    "FieldCondition",
    "Filter",
    "FilterableField",
    "HasIdCondition",
    "HasVectorCondition",
    "IsEmptyCondition",
    "IsNullCondition",
    "MinShould",
    "Nested",
    "NestedCondition",
    "ValuesCount",
)
