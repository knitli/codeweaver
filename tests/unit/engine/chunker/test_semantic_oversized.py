# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for oversized node handling in SemanticChunker.

Tests the recursive child processing strategy for nodes that exceed token limits.
When a node is too large to fit in a single chunk, the chunker attempts to:
1. Chunk children recursively (tested here)
2. If that fails, fallback to delimiter chunking on node text
3. Last resort: Return single chunk as-is (may exceed token limit)

These tests verify that oversized files with chunkable children are successfully
processed via recursive child node chunking.
"""


import pytest

from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.engine.chunker.base import ChunkGovernor
from codeweaver.engine.chunker.semantic import SemanticChunker


@pytest.fixture
def python_chunker(chunk_governor: ChunkGovernor) -> SemanticChunker:
    """Create semantic chunker for Python."""
    return SemanticChunker(chunk_governor, SemanticSearchLanguage.PYTHON)


def test_oversized_file_chunks_via_child_nodes(
    python_chunker: SemanticChunker, chunk_governor: ChunkGovernor, discovered_huge_function_file
):
    """Test oversized file is successfully chunked via child node processing.

    Input: huge_function.py (>2000 tokens total)
    Expected: Multiple semantic chunks via child node processing, all under token limit
    Verify: Each chunk respects token limits, multiple chunks created

    This file has many child statement nodes that can be chunked individually,
    demonstrating the chunker's ability to recursively process children when a
    node is too large to fit in a single chunk.
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
        chunk
        for chunk in chunks
        if chunk.metadata
        and "context" in chunk.metadata
        and chunk.metadata["context"]
        and chunk.metadata["context"].get("chunker_type") == "semantic"
    ]
    assert len(semantic_chunks) > 0, "Should have semantic chunks from child node processing"


def test_oversized_class_chunks_via_methods(
    python_chunker: SemanticChunker, chunk_governor: ChunkGovernor, discovered_large_class_file
):
    """Test oversized class is successfully chunked via child processing.

    Input: Class with large methods (>2000 tokens total)
    Expected: Multiple semantic chunks from child nodes, all under token limit
    Verify: Each chunk under limit, semantic chunking used

    The class has child nodes (methods, statements) that can be chunked
    individually, demonstrating successful recursive child node processing
    for composite structures.
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
        chunk
        for chunk in chunks
        if chunk.metadata
        and "context" in chunk.metadata
        and chunk.metadata["context"]
        and chunk.metadata["context"].get("chunker_type") == "semantic"
    ]
    assert len(semantic_chunks) > 0, "Should have semantic chunks from child node processing"
