# SPDX-FileCopyrightText: 2022-2025 Qdrant Solutions GmbH
# SPDX-License-Identifier: Apache-2.0
#
# Modification and changes from the original:
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""
This module defines the models used for filtering and matching in vector stores.  It defines various conditions and filters that can be applied to payloads in a vector store, such as Qdrant. Some can also be used for other filtering operations, such as in a search engine.

Nearly all of this file and its contents were adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/), and fall under Qdrant's copyright and Apache 2.0 license. Any modifications or changes made to the original code are copyrighted by Knitli Inc. and are licensed under MIT OR Apache-2.0, whichever you want.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, Field, StrictBool, StrictInt, StrictStr


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
            serialization_alias="except",
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


type AnyVariants = Sequence[StrictStr] | Sequence[StrictInt]
type ExtendedPointId = StrictInt | StrictStr
type ValueVariants = StrictBool | StrictInt | StrictStr
type Match = MatchValue | MatchText | MatchPhrase | MatchAny | MatchExcept


__all__ = (
    "AnyVariants",
    "ExtendedPointId",
    "Match",
    "MatchAny",
    "MatchExcept",
    "MatchPhrase",
    "MatchText",
    "MatchValue",
    "ValueVariants",
)
