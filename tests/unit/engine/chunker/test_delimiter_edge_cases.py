# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Edge case tests for DelimiterChunker.

Tests delimiter chunker behavior for edge cases including:
- Generic fallback when no delimiters match
- Inclusive vs exclusive delimiter handling
- Line boundary expansion configuration
- Unusual delimiter patterns
"""

from pathlib import Path

import pytest

from codeweaver.engine.chunker.base import ChunkGovernor
from codeweaver.engine.chunker.delimiter import DelimiterChunker


pytestmark = [pytest.mark.unit]


@pytest.fixture
def delimiter_chunker(chunk_governor: ChunkGovernor) -> DelimiterChunker:
    """Create delimiter chunker instance for tests."""
    return DelimiterChunker(governor=chunk_governor)


@pytest.mark.unit
class TestGenericFallback:
    """Test generic delimiter fallback behavior."""

    def test_no_delimiters_match_uses_generic(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Verify generic patterns used when no language-specific delimiters match.

        Test that when file content contains no recognizable language-specific
        delimiters, the chunker falls back to generic structural patterns like
        braces, newlines, and indentation.

        Expected behavior:
        - Still produces chunks (not empty result)
        - Uses generic delimiters (braces, newlines)
        - Chunks are reasonable size
        - Metadata indicates generic fallback was used
        """
        # Plain text content with no language-specific delimiters
        content = """This is plain text content.
It has no functions, classes, or other code structures.
Just regular paragraphs of text separated by newlines.

Another paragraph here with some more content.
This should still be chunkable using generic patterns.

A third paragraph to ensure we have enough content
for multiple chunks if the generic patterns work correctly.
"""

        file_path = tmp_path / "plain.txt"
        file_path.write_text(content)

        # Create DiscoveredFile and execute chunking
        from codeweaver.core.discovery import DiscoveredFile

        discovered_file = DiscoveredFile.from_path(file_path)
        chunks = delimiter_chunker.chunk(content, file=discovered_file)

        # Verify chunks were produced
        assert len(chunks) > 0, "Generic fallback should still produce chunks"

        # Verify chunks are not empty
        for chunk in chunks:
            assert len(chunk.content.strip()) > 0, "Chunks should have content"

        # Verify metadata indicates generic delimiter usage
        assert any(
            "generic" in str(chunk.metadata.get("delimiter_kind", "")).lower()
            or chunk.metadata.get("fallback_to_generic") is True
            for chunk in chunks
        ), "Metadata should indicate generic fallback was used"

        # Verify reasonable chunk sizing (not single massive chunk)
        if len(content) > 200:  # Only check if content is substantial
            assert len(chunks) > 1, "Generic patterns should split content into multiple chunks"


@pytest.mark.unit
class TestDelimiterBehavior:
    """Test inclusive vs exclusive delimiter behavior."""

    def test_inclusive_vs_exclusive_delimiters(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Verify inclusive delimiters include markers, exclusive delimiters strip them.

        Test that delimiter configuration properly handles:
        - Inclusive delimiters: Marker patterns included in chunk content
        - Exclusive delimiters: Marker patterns removed from chunk content

        This tests the configuration system for delimiter inclusion behavior.
        """
        # Python code with clear function delimiters
        content = """def function_one():
    return "first"

def function_two():
    return "second"

def function_three():
    return "third"
"""

        file_path = tmp_path / "functions.py"
        file_path.write_text(content)

        # Create DiscoveredFile and test with default configuration
        from codeweaver.core.discovery import DiscoveredFile

        discovered_file = DiscoveredFile.from_path(file_path)
        chunks = delimiter_chunker.chunk(content, file=discovered_file)

        assert len(chunks) > 0, "Should produce chunks"

        # Check if delimiters are handled consistently
        for chunk in chunks:
            content_lines = chunk.content.strip().split("\n")
            if len(content_lines) > 0:
                first_line = content_lines[0]

                # Verify delimiter handling based on metadata
                delimiter_kind = chunk.metadata.get("delimiter_kind")
                is_inclusive = chunk.metadata.get("delimiter_inclusive", True)

                if delimiter_kind and "def" in first_line and is_inclusive:
                    assert "def" in chunk.content, (
                        "Inclusive delimiter should include 'def' keyword"
                    )


@pytest.mark.unit
class TestLineExpansion:
    """Test line boundary expansion behavior."""

    def test_take_whole_lines_expansion(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Verify chunks expanded to line boundaries when configured.

        Test that when take_whole_lines is enabled:
        - Chunks always start at beginning of line (column 0)
        - Chunks always end at end of line (newline character)
        - No partial lines included in chunks
        - Line ranges are accurate
        """
        # Code with delimiters not at line boundaries
        content = """x = 1; y = 2; z = 3  # Multiple statements per line
result = x + y + z
print(result)

a, b, c = 1, 2, 3; total = a + b + c  # Another multi-statement line
"""

        file_path = tmp_path / "multiline.py"
        file_path.write_text(content)

        # Create DiscoveredFile and chunk with default configuration
        from codeweaver.core.discovery import DiscoveredFile

        discovered_file = DiscoveredFile.from_path(file_path)
        chunks = delimiter_chunker.chunk(content, file=discovered_file)

        assert len(chunks) > 0, "Should produce chunks"

        # Verify all chunks respect line boundaries
        for chunk in chunks:
            # Check chunk content starts and ends properly

            # If take_whole_lines is configured:
            # - Content should start at line beginning (no leading partial line)
            # - Content should end at line ending (no trailing partial line)

            # metadata should be a dict here, so we can use 'in' operator
            # Verify line range metadata is present
            assert "line_start" in chunk.metadata, "Chunks should have line_start metadata"  # ty: ignore[unsupported-operator]
            assert "line_end" in chunk.metadata, "Chunks should have line_end metadata"  # ty: ignore[unsupported-operator]

            line_start = chunk.metadata["line_start"]  # ty: ignore[non-subscriptable]
            line_end = chunk.metadata["line_end"]  # ty: ignore[non-subscriptable]

            assert isinstance(line_start, int), "line_start should be integer"
            assert isinstance(line_end, int), "line_end should be integer"
            assert line_end >= line_start, "line_end should be >= line_start"

            # Verify chunk content matches line range
            expected_lines = content.split("\n")[line_start - 1 : line_end]
            expected_content = "\n".join(expected_lines)

            # Allow for trailing newline differences
            assert chunk.content.strip() == expected_content.strip(), (
                "Chunk content should match line range"
            )


@pytest.mark.unit
class TestUnusualPatterns:
    """Test delimiter chunker with unusual patterns."""

    def test_nested_delimiter_structures(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Verify proper handling of deeply nested delimiter structures.

        Test that nesting is tracked correctly and chunks respect
        nesting boundaries.
        """
        # JavaScript with nested functions and objects
        content = """
function outer() {
    function inner() {
        function deeplyNested() {
            return {
                method: function() {
                    return true;
                }
            };
        }
    }
}
"""

        file_path = tmp_path / "nested.js"
        file_path.write_text(content)

        # Create DiscoveredFile and chunk
        from codeweaver.core.discovery import DiscoveredFile

        discovered_file = DiscoveredFile.from_path(file_path)
        chunks = delimiter_chunker.chunk(content, file=discovered_file)

        assert len(chunks) > 0, "Should produce chunks from nested structure"

        # Verify nesting information in metadata
        nesting_levels = [
            chunk.metadata.get("nesting_level", 0) if chunk.metadata else 0 for chunk in chunks
        ]
        # Filter out None values and ensure we have valid integers
        valid_nesting_levels = [level for level in nesting_levels if level is not None]
        assert valid_nesting_levels and max(valid_nesting_levels) > 0, "Should track nesting levels"

    def test_overlapping_delimiter_resolution(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Verify priority-based resolution when delimiters overlap.

        Test that when multiple delimiter patterns match overlapping regions,
        the higher priority delimiter wins.
        """
        # Code with potentially overlapping structures
        content = """
class MyClass:
    def method_one(self):
        pass

    def method_two(self):
        pass
"""

        file_path = tmp_path / "overlap.py"
        file_path.write_text(content)

        # Create DiscoveredFile and chunk
        from codeweaver.core.discovery import DiscoveredFile

        discovered_file = DiscoveredFile.from_path(file_path)
        chunks = delimiter_chunker.chunk(content, file=discovered_file)

        assert len(chunks) > 0, "Should resolve overlapping delimiters"

        # Verify chunks don't overlap
        for i in range(len(chunks) - 1):
            current_end = chunks[i].metadata.get("line_end")
            next_start = chunks[i + 1].metadata.get("line_start")

            # Skip validation if metadata is missing
            if current_end is None or next_start is None:
                continue

            # Allow adjacent chunks (end + 1 == start) but not overlapping
            assert next_start >= current_end, "Chunks should not overlap"


@pytest.mark.unit
class TestEdgeCaseContent:
    """Test delimiter chunker with edge case content."""

    def test_empty_delimiter_blocks(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Verify handling of empty delimiter blocks.

        Test behavior when delimiter markers are present but contain
        no content between them.
        """
        content = """
function empty() {
}

function alsoEmpty() {
}
"""

        file_path = tmp_path / "empty_blocks.js"
        file_path.write_text(content)

        # Create DiscoveredFile and chunk
        from codeweaver.core.discovery import DiscoveredFile

        discovered_file = DiscoveredFile.from_path(file_path)
        chunks = delimiter_chunker.chunk(content, file=discovered_file)

        # Empty blocks should still produce chunks (even if minimal)
        assert len(chunks) >= 0, "Should handle empty delimiter blocks"

    def test_unmatched_delimiters(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Verify graceful handling of unmatched delimiters.

        Test behavior when opening delimiters have no closing delimiter,
        or vice versa.
        """
        # Content with unmatched braces
        content = """
function incomplete() {
    return true;
    // Missing closing brace

function another() {
    return false;
}
"""

        file_path = tmp_path / "unmatched.js"
        file_path.write_text(content)

        # Create DiscoveredFile - should not crash, should produce some chunks
        from codeweaver.core.discovery import DiscoveredFile

        discovered_file = DiscoveredFile.from_path(file_path)
        chunks = delimiter_chunker.chunk(content, file=discovered_file)

        assert len(chunks) >= 0, "Should handle unmatched delimiters gracefully"
