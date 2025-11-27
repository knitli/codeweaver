# SPDX-FileCopyrightText: 2024-2025 Qdrant Solutions GmbH
# SPDX-License-Identifier: Apache-2.0
# This file was adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/)
#
# Modification/changes:
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Geo filter request and payload schemas.

We may never use these, but they are here for completeness.

Nearly all of this file and its contents were adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/), and fall under Qdrant's copyright and Apache 2.0 license. Any modifications or changes made to the original code are copyrighted by Knitli Inc. and are licensed under MIT OR Apache-2.0, whichever you want.
"""

from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, Field


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
            description="""Geo filter request  Matches coordinates inside the rectangle, described by coordinates of lop-left and bottom-right edges"""
        ),
    ]
    bottom_right: Annotated[
        GeoPoint,
        Field(
            description="""Geo filter request  Matches coordinates inside the rectangle, described by coordinates of lop-left and bottom-right edges"""
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
            description="""Geo filter request  Matches coordinates inside the polygon, defined by `exterior` and `interiors`"""
        ),
    ]
    interiors: Annotated[
        Sequence[GeoLineString] | None,
        Field(
            description="""Interior lines (if present) bound holes within the surface each GeoLineString must consist of a minimum of 4 points, and the first and last points must be the same."""
        ),
    ] = None


class GeoRadius(BaseModel, extra="forbid"):
    """
    Geo filter request  Matches coordinates inside the circle of `radius` and center with coordinates `center`.
    """

    center: Annotated[
        GeoPoint,
        Field(
            description="""Geo filter request  Matches coordinates inside the circle of `radius` and center with coordinates `center`"""
        ),
    ]
    radius: Annotated[float, Field(description="""Radius of the area in meters""")]


__all__ = ("GeoBoundingBox", "GeoLineString", "GeoPoint", "GeoPolygon", "GeoRadius")
