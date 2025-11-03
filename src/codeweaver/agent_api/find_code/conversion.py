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

from codeweaver.agent_api.models import CodeMatch, CodeMatchType
from codeweaver.common.utils import uuid7
from codeweaver.core.chunks import ChunkSource, CodeChunk, SearchResult
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.spans import Span


def convert_search_result_to_code_match(result: SearchResult) -> CodeMatch:
    """Convert SearchResult from vector store to CodeMatch for response.

    Args:
        result: SearchResult from vector store search

    Returns:
        CodeMatch with all required fields populated
    """
    # Extract CodeChunk (SearchResult.content can be str or CodeChunk)
    if isinstance(result.content, str):
        chunk = create_code_chunk_from_result(result)
    else:
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


def create_code_chunk_from_result(result: SearchResult) -> CodeChunk:
    """Create a CodeChunk from a SearchResult with string content.

    Args:
        result: SearchResult with string content

    Returns:
        CodeChunk with extracted information
    """
    from codeweaver.core.metadata import ExtKind

    if isinstance(result.content, CodeChunk):
        return result.content

    # Determine ext_kind from file_path or use default
    ext_kind = (
        ExtKind.from_file(result.file_path)
        if result.file_path
        else ExtKind.from_language("text", "other")
    )

    # Create Span for line_range with proper UUID7 source_id
    source_id = uuid7()
    line_count = (result.content.count("\n") + 1) if result.content else 1
    line_span = Span(1, line_count, source_id)  # Positional args: start, end, source_id

    return CodeChunk(
        content=result.content,
        line_range=line_span,
        file_path=result.file_path,
        language=None,
        ext_kind=ext_kind,
        source=ChunkSource.TEXT_BLOCK,
        chunk_id=uuid7(),
    )


__all__ = ("convert_search_result_to_code_match", "create_code_chunk_from_result")
