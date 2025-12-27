# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Represents a search result from vector search operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from codeweaver.core.types.search import SearchResult


if TYPE_CHECKING:
    pass


# Re-export SearchResult from core for backward compatibility

__all__ = ("SearchResult",)
