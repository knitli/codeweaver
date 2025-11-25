# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Conversion utilities for search results.

This module handles the conversion between different result formats,
primarily converting SearchResult objects from vector stores to
CodeMatch objects for API responses.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from codeweaver.agent_api.find_code.types import CodeMatch, CodeMatchType
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.spans import Span


if TYPE_CHECKING:
    from codeweaver.agent_api.find_code.results import SearchResult


def convert_search_result_to_code_match(result: SearchResult) -> CodeMatch:
    """Convert SearchResult from vector store to CodeMatch for response.

    Args:
        result: SearchResult from vector store search

    Returns:
        CodeMatch with all required fields populated
    """
    # Extract CodeChunk (VectorStore always returns CodeChunk objects)
    chunk = result.content

    # Get file info (prefer from chunk, fallback to result.file_path, then create fallback)
    file: DiscoveredFile | None = None
    if hasattr(chunk, "file_path") and chunk.file_path:
        file = DiscoveredFile.from_path(chunk.file_path)
    elif result.file_path:
        file = DiscoveredFile.from_path(result.file_path)

    # Ensure we always have a DiscoveredFile (CodeMatch requires non-None)
    if file is None:
        # Create fallback DiscoveredFile with unknown path
        from codeweaver.core.metadata import ExtKind

        unknown_path = Path("unknown")
        ext_kind = ExtKind.from_language("text", "other")
        # DiscoveredFile constructor accepts path and ext_kind directly
        file = DiscoveredFile(path=unknown_path, ext_kind=ext_kind)

    # Extract span (line range) - ensure it's a Span object
    if hasattr(chunk, "line_range"):
        span = chunk.line_range
    else:
        # Fallback span - positional args: start, end, source_id
        span = Span(
            1, chunk.content.count("\n") + 1 if hasattr(chunk, "content") else 1, file.source_id
        )

    # Use relevance_score if set, otherwise use base score
    relevance = getattr(result, "relevance_score", result.score)

    # Extract related symbols from chunk metadata if available
    # Metadata is a TypedDict, check for semantic_meta which may contain symbols
    related_symbols = ()
    if hasattr(chunk, "metadata") and chunk.metadata:
        meta = chunk.metadata
        # Check if semantic_meta exists and has symbol information
        semantic_meta = meta.get("semantic_meta")
        if (
            semantic_meta is not None
            and hasattr(semantic_meta, "symbol")
            and (symbol := getattr(semantic_meta, "symbol", None))
        ):
            related_symbols = (symbol,)

    return CodeMatch(
        file=file,
        content=chunk,
        span=span,
        relevance_score=relevance,
        match_type=CodeMatchType.SEMANTIC,  # Vector search is always semantic
        related_symbols=related_symbols,
    )


__all__ = ("convert_search_result_to_code_match",)
