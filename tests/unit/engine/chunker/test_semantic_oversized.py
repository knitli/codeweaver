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
    """Test oversized node falls back to delimiter chunking.

    Input: huge_function.py (>2000 tokens)
    Expected: Multiple chunks, all under token limit
    Verify: Chunks have parent_semantic_node in metadata
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

    # Chunks should have parent semantic node in metadata
    # (This indicates fallback from semantic to delimiter)
    def has_fallback_indicator(chunk):
        if not chunk.metadata or "context" not in chunk.metadata or not chunk.metadata["context"]:
            return False
        context = chunk.metadata["context"]
        return "parent_semantic_node" in context or "fallback" in context

    has_parent_metadata = any(has_fallback_indicator(chunk) for chunk in chunks)
    assert has_parent_metadata, "Chunks should indicate semantic fallback in metadata"


def test_oversized_node_recursive_children(
    python_chunker: SemanticChunker,
    chunk_governor: ChunkGovernor,
    discovered_large_class_file,
):
    """Test oversized composite node chunks children individually.

    Input: Class with large methods
    Expected: Children (methods) chunked individually
    Verify: Each chunk under limit
    """
    content = discovered_large_class_file.contents

    chunks = python_chunker.chunk(content, file=discovered_large_class_file)

    # Should chunk individual methods
    assert len(chunks) > 1, "Should chunk methods separately"

    # All chunks should be under token limit
    for chunk in chunks:
        assert chunk.token_count <= chunk_governor.chunk_limit, (
            f"Chunk exceeds token limit: {chunk.token_count} > {chunk_governor.chunk_limit}"
        )

    # At least some chunks should be methods
    method_chunks = [
        chunk for chunk in chunks
        if chunk.metadata.get("classification") == "FUNCTION"
    ]
    assert len(method_chunks) > 0, "Should have individual method chunks"


def test_all_strategies_fail_uses_text_splitter(
    python_chunker: SemanticChunker,
    chunk_governor: ChunkGovernor,
):
    """Test last resort fallback to RecursiveTextSplitter.

    Input: Huge indivisible text block (e.g., long string literal)
    Expected: Falls back to RecursiveTextSplitter
    Verify: Metadata contains fallback indication
    """
    # Create an indivisible large string literal that can't be split semantically
    huge_string_code = '''
long_text = """
''' + ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 500) + '''
"""
'''

    chunks = python_chunker.chunk(huge_string_code)

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
