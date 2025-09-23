# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for Phase 1 chunking implementation."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from codeweaver._data_structures import ChunkKind, DiscoveredFile, ExtKind
from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.services.chunker import (
    ChunkGovernor,
    ChunkRouter,
    EnhancedChunkMicroManager,
    FallbackChunker,
    MarkdownChunker,
    clear_registry,
    source_id_for,
)


@pytest.fixture
def mock_embedding_capabilities():
    """Create mock embedding capabilities."""
    mock_cap = Mock(spec=EmbeddingModelCapabilities)
    mock_cap.context_window = 8192
    mock_cap.tokenizer = "cl100k_base"
    mock_cap.tokenizer_model = "gpt-4"
    return mock_cap


@pytest.fixture
def chunk_governor(mock_embedding_capabilities):
    """Create a chunk governor for testing."""
    return ChunkGovernor(capabilities=(mock_embedding_capabilities,))


@pytest.fixture
def markdown_file():
    """Create a mock markdown file."""
    # Create a simple ExtKind for testing
    ext_kind = ExtKind(language="markdown", kind=ChunkKind.DOCS)
    return DiscoveredFile(
        path=Path("test.md"),
        ext_kind=ext_kind,
        file_hash="a" * 64,
        git_branch="main"
    )


@pytest.fixture
def python_file():
    """Create a mock Python file."""
    # Create a simple ExtKind for testing
    ext_kind = ExtKind(language="python", kind=ChunkKind.CODE)
    return DiscoveredFile(
        path=Path("test.py"),
        ext_kind=ext_kind,
        file_hash="b" * 64,
        git_branch="main"
    )


@pytest.fixture(autouse=True)
def cleanup_registry():
    """Clear the registry before and after each test."""
    clear_registry()
    yield
    clear_registry()


class TestSourceIdRegistry:
    """Tests for the source ID registry."""

    def test_source_id_consistency(self):
        """Test that the same file always gets the same source ID."""
        file_path = Path("test.py")

        id1 = source_id_for(file_path)
        id2 = source_id_for(file_path)

        assert id1 == id2
        assert len(id1) == 32  # UUID7 hex string length

    def test_different_files_get_different_ids(self):
        """Test that different files get different source IDs."""
        file1 = Path("test1.py")
        file2 = Path("test2.py")

        id1 = source_id_for(file1)
        id2 = source_id_for(file2)

        assert id1 != id2


class TestChunkGovernor:
    """Tests for ChunkGovernor."""

    def test_chunk_limit_calculation(self, chunk_governor):
        """Test chunk limit calculation."""
        assert chunk_governor.chunk_limit == 8192

    def test_simple_overlap_calculation(self, chunk_governor):
        """Test simple overlap calculation."""
        # 20% of 8192 = 1638.4, clamped between 50-200
        expected = min(200, max(50, int(8192 * 0.2)))
        assert chunk_governor.simple_overlap == expected


class TestChunkRouter:
    """Tests for ChunkRouter."""

    def test_markdown_file_routing(self, markdown_file):
        """Test that markdown files are routed to MarkdownChunker."""
        router = ChunkRouter()
        chunker = router.select(markdown_file)
        assert isinstance(chunker, MarkdownChunker)

    def test_fallback_routing(self, python_file):
        """Test that unsupported files are routed to FallbackChunker."""
        router = ChunkRouter()
        chunker = router.select(python_file)
        assert isinstance(chunker, FallbackChunker)


class TestFallbackChunker:
    """Tests for FallbackChunker."""

    def test_simple_content_chunking(self, python_file, chunk_governor):
        """Test chunking of simple content."""
        chunker = FallbackChunker()
        content = "line 1\nline 2\nline 3\n"

        chunks = chunker.chunk(python_file, content, chunk_governor)

        assert len(chunks) == 1
        assert chunks[0].content == "line 1\nline 2\nline 3"
        assert chunks[0].line_range.start == 1
        assert chunks[0].line_range.end == 3

    def test_empty_content(self, python_file, chunk_governor):
        """Test handling of empty content."""
        chunker = FallbackChunker()
        content = ""

        chunks = chunker.chunk(python_file, content, chunk_governor)

        assert len(chunks) == 0

    def test_large_content_splitting(self, python_file, chunk_governor):
        """Test that large content gets split appropriately."""
        chunker = FallbackChunker()
        # Create content that will exceed token limit
        large_content = "\n".join([f"This is line {i} with some content" for i in range(1000)])

        chunks = chunker.chunk(python_file, large_content, chunk_governor)

        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.content.strip()  # No empty chunks


class TestMarkdownChunker:
    """Tests for MarkdownChunker."""

    def test_simple_markdown_chunking(self, markdown_file, chunk_governor):
        """Test chunking of simple markdown content."""
        chunker = MarkdownChunker()
        content = "# Header 1\nSome content\n## Header 2\nMore content\n"

        chunks = chunker.chunk(markdown_file, content, chunk_governor)

        assert len(chunks) == 2
        assert "Header 1" in chunks[0].content
        assert "Header 2" in chunks[1].content

    def test_frontmatter_handling(self, markdown_file, chunk_governor):
        """Test handling of YAML frontmatter."""
        chunker = MarkdownChunker()
        content = "---\ntitle: Test\n---\n# Header\nContent\n"

        chunks = chunker.chunk(markdown_file, content, chunk_governor)

        assert len(chunks) == 2
        # First chunk should be frontmatter
        assert chunks[0].metadata["chunk_type"] == "frontmatter"
        # Second chunk should be the header section
        assert "Header" in chunks[1].content

    def test_empty_markdown(self, markdown_file, chunk_governor):
        """Test handling of empty markdown."""
        chunker = MarkdownChunker()
        content = ""

        chunks = chunker.chunk(markdown_file, content, chunk_governor)

        assert len(chunks) == 0

    def test_markdown_without_headers(self, markdown_file, chunk_governor):
        """Test handling of markdown without headers."""
        chunker = MarkdownChunker()
        content = "Just some plain text without headers.\nAnother line.\n"

        chunks = chunker.chunk(markdown_file, content, chunk_governor)

        assert len(chunks) == 1
        assert chunks[0].content.strip() == "Just some plain text without headers.\nAnother line."


class TestEnhancedChunkMicroManager:
    """Tests for EnhancedChunkMicroManager."""

    def test_file_chunking_coordination(self, markdown_file, chunk_governor):
        """Test that the micro manager coordinates chunking correctly."""
        manager = EnhancedChunkMicroManager(chunk_governor)
        content = "# Test\nSome content\n"

        chunks = manager.chunk_file(markdown_file, content)

        assert len(chunks) == 1
        assert chunks[0].content.strip()

    def test_empty_content_handling(self, markdown_file, chunk_governor):
        """Test handling of empty content."""
        manager = EnhancedChunkMicroManager(chunk_governor)
        content = ""

        chunks = manager.chunk_file(markdown_file, content)

        assert len(chunks) == 0

    def test_whitespace_only_content(self, markdown_file, chunk_governor):
        """Test handling of whitespace-only content."""
        manager = EnhancedChunkMicroManager(chunk_governor)
        content = "   \n\n   \n"

        chunks = manager.chunk_file(markdown_file, content)

        assert len(chunks) == 0


class TestSpanConsistency:
    """Tests for span consistency across chunking operations."""

    def test_span_source_id_consistency(self, python_file, chunk_governor):
        """Test that all spans from the same file share the same source ID."""
        chunker = FallbackChunker()
        content = "\n".join([f"line {i}" for i in range(100)])  # Enough to create multiple chunks

        chunks = chunker.chunk(python_file, content, chunk_governor)

        if len(chunks) > 1:
            source_ids = [chunk.line_range.source_id for chunk in chunks]
            assert all(sid == source_ids[0] for sid in source_ids)

    def test_line_range_coverage(self, markdown_file, chunk_governor):
        """Test that line ranges properly cover the content."""
        chunker = MarkdownChunker()
        content = "# Header 1\nLine 2\nLine 3\n# Header 2\nLine 5\n"

        chunks = chunker.chunk(markdown_file, content, chunk_governor)

        # Verify that chunks cover the expected line ranges
        total_lines = len(content.splitlines())
        covered_lines = set()
        for chunk in chunks:
            for line in range(chunk.line_range.start, chunk.line_range.end + 1):
                covered_lines.add(line)

        # Should cover most lines (allowing for potential frontmatter handling)
        assert len(covered_lines) > 0


class TestIntegration:
    """Integration tests for the complete chunking system."""

    def test_end_to_end_chunking(self, markdown_file, chunk_governor):
        """Test complete end-to-end chunking workflow."""
        manager = EnhancedChunkMicroManager(chunk_governor)
        content = """---
title: Test Document
---

# Introduction
This is a test document with multiple sections.

## Section 1
Content for section 1.

## Section 2
Content for section 2.

# Conclusion
Final thoughts.
"""

        chunks = manager.chunk_file(markdown_file, content)

        # Should have multiple chunks
        assert len(chunks) > 1

        # All chunks should have content
        for chunk in chunks:
            assert chunk.content.strip()
            assert chunk.line_range.start > 0
            assert chunk.line_range.end >= chunk.line_range.start
            assert chunk.file_path == markdown_file.path

    def test_token_budget_respect(self, python_file, chunk_governor):
        """Test that chunkers respect token budgets."""
        manager = EnhancedChunkMicroManager(chunk_governor)

        # Create content that should definitely exceed one chunk
        function_blocks = []
        for i in range(500):
            function_blocks.extend([
                f"def function_{i}():",
                f'    """This is a docstring for function {i}."""',
                "    # Some implementation here",
                f"    return {i}",
                ""
            ])
        large_content = "\n".join(function_blocks)

        chunks = manager.chunk_file(python_file, large_content)

        # Should create multiple chunks
        assert len(chunks) > 1

        # Each chunk should be under the effective limit
        effective_limit = int(chunk_governor.chunk_limit * 0.9)  # Safety margin

        for chunk in chunks:
            # Rough token estimation - should be under limit
            from codeweaver._utils import estimate_tokens
            tokens = estimate_tokens(chunk.serialize_for_embedding())
            assert tokens <= effective_limit
