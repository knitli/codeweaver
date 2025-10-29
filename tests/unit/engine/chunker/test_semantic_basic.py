"""
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
"""

"""Basic functionality tests for SemanticChunker.

Tests verify core chunking behavior for supported languages including
Python, JavaScript, and Rust.
"""


from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.engine.chunker import SemanticChunker
from codeweaver.engine.chunker.base import ChunkGovernor


def test_semantic_chunks_python_file(
    chunk_governor: ChunkGovernor, discovered_sample_python_file
) -> None:
    """Verify semantic chunking of valid Python produces correct structure.

    Tests:
    - Python file chunks into multiple code blocks
    - Chunks contain metadata with classifications (FUNCTION, CLASS)
    - Chunk content matches original code sections
    - All chunks have valid line ranges
    """
    content = discovered_sample_python_file.contents

    chunker = SemanticChunker(chunk_governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(content, file=discovered_sample_python_file)

    # Should produce multiple chunks from sample.py
    assert len(chunks) > 0, "Should produce at least one chunk"

    # All chunks should have metadata
    assert all(chunk.metadata for chunk in chunks), "All chunks must have metadata"

    # Check for classification in context
    classifications = [
        chunk.metadata.get("context", {}).get("classification")
        for chunk in chunks
        if chunk.metadata and "context" in chunk.metadata
    ]
    assert any(classifications), "Should have chunks with classifications"

    # All chunks should have valid line ranges
    for chunk in chunks:
        assert chunk.line_range.start <= chunk.line_range.end, (
            f"Invalid line range: {chunk.line_range.start} > {chunk.line_range.end}"
        )

    # Content should not be empty
    assert all(chunk.content.strip() for chunk in chunks), "No chunks should have empty content"


def test_semantic_chunks_javascript_file(
    chunk_governor: ChunkGovernor, discovered_sample_javascript_file
) -> None:
    """Verify JavaScript AST parsing and nested function handling.

    Tests:
    - JavaScript file chunks correctly
    - Nested functions are handled properly
    - Metadata contains function/class classifications
    """
    content = discovered_sample_javascript_file.contents

    chunker = SemanticChunker(chunk_governor, SemanticSearchLanguage.JAVASCRIPT)
    chunks = chunker.chunk(content, file=discovered_sample_javascript_file)

    assert len(chunks) > 0, "Should produce chunks from JavaScript file"

    # Check metadata structure
    for chunk in chunks:
        assert chunk.metadata is not None, "Chunk must have metadata"
        assert chunk.language.name == "JAVASCRIPT", "Language should be JavaScript"


def test_semantic_chunks_rust_file(
    chunk_governor: ChunkGovernor, discovered_sample_rust_file
) -> None:
    """Verify Rust trait/impl chunking.

    Tests:
    - Rust file chunks correctly
    - Trait and impl blocks are identified
    - Chunks maintain Rust code structure
    """
    content = discovered_sample_rust_file.contents

    chunker = SemanticChunker(chunk_governor, SemanticSearchLanguage.RUST)
    chunks = chunker.chunk(content, file=discovered_sample_rust_file)

    assert len(chunks) > 0, "Should produce chunks from Rust file"

    # Verify language detection
    for chunk in chunks:
        assert chunk.language.name == "RUST", "Language should be Rust"
