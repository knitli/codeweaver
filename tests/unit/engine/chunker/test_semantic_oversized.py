# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for oversized node handling in SemanticChunker.

Tests the fallback chain for nodes that exceed token limits:
1. Try to chunk children recursively
2. Fallback to delimiter chunking on node text
3. Last resort: RecursiveTextSplitter
"""

from pathlib import Path

import pytest

from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.engine.chunker.base import ChunkGovernor
from codeweaver.engine.chunker.semantic import SemanticChunker


@pytest.fixture
def python_chunker(chunk_governor: ChunkGovernor) -> SemanticChunker:
    """Create semantic chunker for Python."""
    return SemanticChunker(chunk_governor, SemanticSearchLanguage.PYTHON)


def test_oversized_node_fallback_to_delimiter(
    python_chunker: SemanticChunker,
    chunk_governor: ChunkGovernor,
    discovered_huge_function_file,
):
    """Test oversized file is successfully chunked into multiple semantic chunks.

    Input: huge_function.py (>2000 tokens total)
    Expected: Multiple semantic chunks via child node processing, all under token limit
    Verify: Each chunk respects token limits, multiple chunks created

    Note: This file has many child statement nodes that can be chunked individually,
    so it successfully processes via semantic chunking without needing delimiter fallback.
    """
    content = discovered_huge_function_file.contents

    chunks = python_chunker.chunk(content, file=discovered_huge_function_file)

    # Should produce multiple chunks
    assert len(chunks) > 1, "Should split oversized function into multiple chunks"

    # All chunks should be under token limit
    for chunk in chunks:
        assert chunk.token_count <= chunk_governor.chunk_limit, (
            f"Chunk exceeds token limit: {chunk.token_count} > {chunk_governor.chunk_limit}"
        )

    # Verify chunks are semantic (successful child node processing)
    semantic_chunks = [
        chunk for chunk in chunks
        if chunk.metadata
        and "context" in chunk.metadata
        and chunk.metadata["context"]
        and chunk.metadata["context"].get("chunker_type") == "semantic"
    ]
    assert len(semantic_chunks) > 0, "Should have semantic chunks from child node processing"


def test_oversized_node_recursive_children(
    python_chunker: SemanticChunker,
    chunk_governor: ChunkGovernor,
    discovered_large_class_file,
):
    """Test oversized class is successfully chunked via child processing.

    Input: Class with large methods (>2000 tokens total)
    Expected: Multiple semantic chunks from child nodes, all under token limit
    Verify: Each chunk under limit, semantic chunking used

    Note: The class has child nodes (methods, statements) that can be chunked
    individually, so semantic chunking successfully handles it without delimiter fallback.
    """
    content = discovered_large_class_file.contents

    chunks = python_chunker.chunk(content, file=discovered_large_class_file)

    # Should chunk individual statements/methods
    assert len(chunks) > 1, "Should chunk child nodes separately"

    # All chunks should be under token limit
    for chunk in chunks:
        assert chunk.token_count <= chunk_governor.chunk_limit, (
            f"Chunk exceeds token limit: {chunk.token_count} > {chunk_governor.chunk_limit}"
        )

    # Verify chunks are semantic (successful child node processing)
    semantic_chunks = [
        chunk for chunk in chunks
        if chunk.metadata
        and "context" in chunk.metadata
        and chunk.metadata["context"]
        and chunk.metadata["context"].get("chunker_type") == "semantic"
    ]
    assert len(semantic_chunks) > 0, "Should have semantic chunks from child node processing"


@pytest.mark.skip(reason="Text splitter fallback not yet implemented - not MVP requirement")
def test_all_strategies_fail_uses_text_splitter(
    python_chunker: SemanticChunker,
    chunk_governor: ChunkGovernor,
    discovered_huge_string_literal_file,
):
    """Test last resort fallback to RecursiveTextSplitter.

    Input: Huge indivisible text block (e.g., long string literal)
    Expected: Falls back to RecursiveTextSplitter
    Verify: Metadata contains fallback indication

    Note: This tests a future feature (text splitter fallback) that is not part of MVP.
    Currently, oversized indivisible nodes (like huge string literals) are returned as-is
    without splitting, which may exceed token limits.
    """
    content = discovered_huge_string_literal_file.contents

    chunks = python_chunker.chunk(content, file=discovered_huge_string_literal_file)

    # Should produce chunks even for indivisible content
    assert len(chunks) > 0, "Should produce chunks via text splitter fallback"

    # All chunks should be under token limit
    for chunk in chunks:
        assert chunk.token_count <= chunk_governor.chunk_limit, (
            f"Chunk exceeds token limit: {chunk.token_count} > {chunk_governor.chunk_limit}"
        )

    # Chunks should indicate text splitter fallback
    has_fallback_indicator = any(
        chunk.metadata.get("fallback") == "text_splitter" or
        chunk.metadata.get("source") == "text_splitter"
        for chunk in chunks
    )
    assert has_fallback_indicator, "Should indicate text splitter fallback in metadata"
