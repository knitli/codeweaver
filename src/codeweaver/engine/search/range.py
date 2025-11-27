# SPDX-FileCopyrightText: 2024-2025 Qdrant Solutions GmbH
# SPDX-License-Identifier: Apache-2.0
# This file was adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/)
#
# Modification/changes:
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Range filter request models.

Nearly all of this file and its contents were adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/), and fall under Qdrant's copyright and Apache 2.0 license. Any modifications or changes made to the original code are copyrighted by Knitli Inc. and are licensed under MIT OR Apache-2.0, whichever you want.
"""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field


class DatetimeRange(BaseModel, extra="forbid"):
    """
    Range filter request.
    """

    lt: Annotated[datetime | date | None, Field(description="""point.key < range.lt""")] = None
    gt: Annotated[datetime | date | None, Field(description="""point.key > range.gt""")] = None
    gte: Annotated[datetime | date | None, Field(description="""point.key >= range.gte""")] = None
    lte: Annotated[datetime | date | None, Field(description="""point.key <= range.lte""")] = None


class Range(BaseModel, extra="forbid"):
    """
    Range filter request.
    """

    lt: Annotated[float | None, Field(description="""point.key < range.lt""")] = None
    gt: Annotated[float | None, Field(description="""point.key > range.gt""")] = None
    gte: Annotated[float | None, Field(description="""point.key >= range.gte""")] = None
    lte: Annotated[float | None, Field(description="""point.key <= range.lte""")] = None


type RangeInterface = Range | DatetimeRange

__all__ = ("DatetimeRange", "Range", "RangeInterface")
