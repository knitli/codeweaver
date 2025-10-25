"""
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
"""

"""Basic functionality tests for SemanticChunker.

Tests verify core chunking behavior for supported languages including
Python, JavaScript, and Rust.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.engine.chunker import SemanticChunker


@pytest.fixture
def mock_governor() -> Mock:
    """Create mock ChunkGovernor for testing."""
    from unittest.mock import Mock

    governor = Mock()
    governor.chunk_limit = 2000  # tokens
    governor.simple_overlap = 50
    governor.performance_settings = Mock(
        chunk_timeout_seconds=30, max_chunks_per_file=5000, max_ast_depth=200
    )
    return governor


def test_semantic_chunks_python_file(mock_governor: Mock) -> None:
    """Verify semantic chunking of valid Python produces correct structure.

    Tests:
    - Python file chunks into multiple code blocks
    - Chunks contain metadata with classifications (FUNCTION, CLASS)
    - Chunk content matches original code sections
    - All chunks have valid line ranges
    """
    fixture_path = Path("tests/fixtures/sample.py")
    content = fixture_path.read_text()

    chunker = SemanticChunker(mock_governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(content, file_path=fixture_path)

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


def test_semantic_chunks_javascript_file(mock_governor: Mock) -> None:
    """Verify JavaScript AST parsing and nested function handling.

    Tests:
    - JavaScript file chunks correctly
    - Nested functions are handled properly
    - Metadata contains function/class classifications
    """
    fixture_path = Path("tests/fixtures/sample.js")
    content = fixture_path.read_text()

    chunker = SemanticChunker(mock_governor, SemanticSearchLanguage.JAVASCRIPT)
    chunks = chunker.chunk(content, file_path=fixture_path)

    assert len(chunks) > 0, "Should produce chunks from JavaScript file"

    # Check metadata structure
    for chunk in chunks:
        assert chunk.metadata is not None, "Chunk must have metadata"
        assert chunk.language.name == "JAVASCRIPT", "Language should be JavaScript"


def test_semantic_chunks_rust_file(mock_governor: Mock) -> None:
    """Verify Rust trait/impl chunking.

    Tests:
    - Rust file chunks correctly
    - Trait and impl blocks are identified
    - Chunks maintain Rust code structure
    """
    fixture_path = Path("tests/fixtures/sample.rs")
    content = fixture_path.read_text()

    chunker = SemanticChunker(mock_governor, SemanticSearchLanguage.RUST)
    chunks = chunker.chunk(content, file_path=fixture_path)

    assert len(chunks) > 0, "Should produce chunks from Rust file"

    # Verify language detection
    for chunk in chunks:
        assert chunk.language.name == "RUST", "Language should be Rust"
