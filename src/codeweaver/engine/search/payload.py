# SPDX-FileCopyrightText: 2024-2025 Qdrant Solutions GmbH
# SPDX-License-Identifier: Apache-2.0
# This file was adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/)
#
# Modification/changes:
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Models for vector search payload handling.

Nearly all of this file and its contents were adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/), and fall under Qdrant's copyright and Apache 2.0 license. Any modifications or changes made to the original code are copyrighted by Knitli Inc. and are licensed under MIT OR Apache-2.0, whichever you want.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field

from codeweaver.core.types.enum import BaseEnum


PayloadMetadata = dict[str, Any]


class PayloadSchemaType(str, BaseEnum):
    """
    The types of payload fields that can be indexed.
    """

    KEYWORD = "keyword"
    INTEGER = "integer"
    FLOAT = "float"
    GEO = "geo"
    TEXT = "text"
    BOOL = "bool"
    DATETIME = "datetime"
    UUID = "uuid"

    __slots__ = ()


class Entry(BaseModel):
    """
    A single entry in the Qdrant collection.
    """

    content: str
    Metadata: PayloadMetadata | None = None


class PayloadField(BaseModel, extra="forbid"):
    """
    Payload field.
    """

    key: Annotated[str, Field(description="""Payload field name""")]


__all__ = ("Entry", "PayloadField", "PayloadSchemaType")
