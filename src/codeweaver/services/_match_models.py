# SPDX-FileCopyrightText: 2022-2025 Qdrant Solutions GmbH
# SPDX-License-Identifier: Apache-2.0
#
# Modification and changes from the original:
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""
This module defines the models used for filtering and matching in vector stores.  It defines various conditions and filters that can be applied to payloads in a vector store, such as Qdrant. Some can also be used for other filtering operations, such as in a search engine.

It is mostly copied from [qdrant-client](https://github.com/qdrant/qdrant-client/blob/master/qdrant_client/http/models/models.py)
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StrictBool, StrictInt, StrictStr


type AnyVariants = Sequence[StrictStr] | Sequence[StrictInt]
type Condition = (
    FieldCondition
    | IsEmptyCondition
    | IsNullCondition
    | HasIdCondition
    | HasVectorCondition
    | NestedCondition
    | Filter
)
type ExtendedPointId = StrictInt | StrictStr
type ValueVariants = StrictBool | StrictInt | StrictStr
type Match = MatchValue | MatchText | MatchPhrase | MatchAny | MatchExcept
type RangeInterface = Range | DatetimeRange


class PayloadField(BaseModel, extra="forbid"):
    """
    Payload field.
    """

    key: Annotated[str, Field(description="""Payload field name""")]


class MinShould(BaseModel, extra="forbid"):
    conditions: Annotated[Sequence[Condition], Field(description="""List of conditions""")]
    min_count: Annotated[int, Field(description="""Minimum count of conditions that must match""")]


class Filter(BaseModel, extra="forbid"):
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


class DatetimeRange(BaseModel, extra="forbid"):
    """
    Range filter request.
    """

    lt: Annotated[
        datetime | date | None, Field(default=None, description="""point.key &lt; range.lt""")
    ] = None
    gt: Annotated[
        datetime | date | None, Field(default=None, description="""point.key &gt; range.gt""")
    ] = None
    gte: Annotated[
        datetime | date | None, Field(default=None, description="""point.key &gt;= range.gte""")
    ] = None
    lte: Annotated[
        datetime | date | None, Field(default=None, description="""point.key &lt;= range.lte""")
    ] = None


class Range(BaseModel, extra="forbid"):
    """
    Range filter request.
    """

    lt: Annotated[float | None, Field(default=None, description="""point.key &lt; range.lt""")] = (
        None
    )
    gt: Annotated[float | None, Field(default=None, description="""point.key &gt; range.gt""")] = (
        None
    )
    gte: Annotated[
        float | None, Field(default=None, description="""point.key &gt;= range.gte""")
    ] = None
    lte: Annotated[
        float | None, Field(default=None, description="""point.key &lt;= range.lte""")
    ] = None


class MatchAny(BaseModel, extra="forbid"):
    """
    Exact match on any of the given values.
    """

    any: Annotated[
        AnyVariants | None, Field(description="""Exact match on any of the given values""")
    ] = None


class MatchExcept(BaseModel, extra="forbid"):
    """
    Should have at least one value not matching the any given values.
    """

    except_: Annotated[
        AnyVariants | None,
        Field(
            ...,
            description="""Should have at least one value not matching the any given values""",
            alias="except",
        ),
    ] = None


class MatchPhrase(BaseModel, extra="forbid"):
    """
    Full-text phrase match of the string.
    """

    phrase: Annotated[
        str | None, Field(description="""Full-text phrase match of the string.""")
    ] = None


class MatchText(BaseModel, extra="forbid"):
    """
    Full-text match of the strings.
    """

    text: Annotated[str | None, Field(description="""Full-text match of the strings.""")] = None


class MatchValue(BaseModel, extra="forbid"):
    """
    Exact match of the given value.
    """

    value: Annotated[
        ValueVariants | None, Field(description="""Exact match of the given value""")
    ] = None


class ValuesCount(BaseModel, extra="forbid"):
    """
    Values count filter request.
    """

    lt: Annotated[
        int | None, Field(default=None, description="""point.key.length() &lt; values_count.lt""")
    ] = None
    gt: Annotated[
        int | None, Field(default=None, description="""point.key.length() &gt; values_count.gt""")
    ] = None
    gte: Annotated[
        int | None, Field(default=None, description="""point.key.length() &gt;= values_count.gte""")
    ] = None
    lte: Annotated[
        int | None, Field(default=None, description="""point.key.length() &lt;= values_count.lte""")
    ] = None


class GeoPoint(BaseModel, extra="forbid"):
    """
    Geo point payload schema.
    """

    lon: Annotated[float, Field(description="""Geo point payload schema""")]
    lat: Annotated[float, Field(description="""Geo point payload schema""")]


class GeoBoundingBox(BaseModel, extra="forbid"):
    """
    Geo filter request  Matches coordinates inside the rectangle, described by coordinates of lop-left and bottom-right edges.
    """

    top_left: Annotated[
        GeoPoint,
        Field(
            ...,
            description="""Geo filter request  Matches coordinates inside the rectangle, described by coordinates of lop-left and bottom-right edges""",
        ),
    ]
    bottom_right: Annotated[
        GeoPoint,
        Field(
            ...,
            description="""Geo filter request  Matches coordinates inside the rectangle, described by coordinates of lop-left and bottom-right edges""",
        ),
    ]


class GeoLineString(BaseModel, extra="forbid"):
    """
    Ordered sequence of GeoPoints representing the line.
    """

    points: Annotated[
        Sequence[GeoPoint],
        Field(description="""Ordered sequence of GeoPoints representing the line"""),
    ]


class GeoPolygon(BaseModel, extra="forbid"):
    """
    Geo filter request  Matches coordinates inside the polygon, defined by `exterior` and `interiors`.
    """

    exterior: Annotated[
        GeoLineString,
        Field(
            ...,
            description="""Geo filter request  Matches coordinates inside the polygon, defined by `exterior` and `interiors`""",
        ),
    ]
    interiors: Annotated[
        Sequence[GeoLineString] | None,
        Field(
            default=None,
            description="""Interior lines (if present) bound holes within the surface each GeoLineString must consist of a minimum of 4 points, and the first and last points must be the same.""",
        ),
    ] = None


class GeoRadius(BaseModel, extra="forbid"):
    """
    Geo filter request  Matches coordinates inside the circle of `radius` and center with coordinates `center`.
    """

    center: Annotated[
        GeoPoint,
        Field(
            ...,
            description="""Geo filter request  Matches coordinates inside the circle of `radius` and center with coordinates `center`""",
        ),
    ]
    radius: Annotated[float, Field(description="""Radius of the area in meters""")]


class FieldCondition(BaseModel, extra="forbid"):
    """
    All possible payload filtering conditions.
    """

    key: str = Field(description="""Payload key""")
    match: Annotated[
        Match | None,
        Field(default=None, description="""Check if point has field with a given value"""),
    ] = None
    range: Annotated[
        RangeInterface | None,
        Field(default=None, description="""Check if points value lies in a given range"""),
    ] = None
    geo_bounding_box: Annotated[
        GeoBoundingBox | None,
        Field(default=None, description="""Check if points geolocation lies in a given area"""),
    ] = None
    geo_radius: Annotated[
        GeoRadius | None,
        Field(default=None, description="""Check if geo point is within a given radius"""),
    ] = None
    geo_polygon: Annotated[
        GeoPolygon | None,
        Field(default=None, description="""Check if geo point is within a given polygon"""),
    ] = None
    values_count: Annotated[
        ValuesCount | None,
        Field(default=None, description="""Check number of values of the field"""),
    ] = None
    is_empty: Annotated[
        bool | None,
        Field(
            default=None,
            description="""Check that the field is empty, alternative syntax for `is_empty: 'field_name'`""",
        ),
    ] = None
    is_null: Annotated[
        bool | None,
        Field(
            default=None,
            description="""Check that the field is null, alternative syntax for `is_null: 'field_name'`""",
        ),
    ] = None


__all__ = (
    "AnyVariants",
    "Condition",
    "DatetimeRange",
    "ExtendedPointId",
    "FieldCondition",
    "Filter",
    "GeoBoundingBox",
    "GeoLineString",
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
    "Range",
    "ValueVariants",
    "ValuesCount",
)
