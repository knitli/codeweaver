# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for delimiter chunker basic functionality.

Tests cover:
- JavaScript nested function handling
- Priority resolution for overlapping delimiters
- Python class and function boundary detection
- Nesting level tracking in metadata
- Chunk boundary correctness

All tests are designed to FAIL initially until DelimiterChunker is implemented.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codeweaver.engine.chunker.base import ChunkGovernor
from codeweaver.engine.chunker.delimiter import DelimiterChunker
from codeweaver.engine.chunker.delimiters.kind import DelimiterKind


@pytest.fixture
def governor() -> ChunkGovernor:
    """Create a basic ChunkGovernor for testing."""
    return ChunkGovernor(capabilities=())


@pytest.fixture
def delimiter_chunker(governor: ChunkGovernor) -> DelimiterChunker:
    """Create a DelimiterChunker instance."""
    return DelimiterChunker(governor=governor)


class TestDelimiterChunksJavaScriptNested:
    """Test delimiter chunker with JavaScript nested functions."""

    def test_delimiter_chunks_javascript_nested(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Test that nested JavaScript functions are properly chunked.

        Input: JavaScript code with nested functions
        Expected: Chunks respect function boundaries
        Assert: Chunks contain complete function blocks
        Verify: Nesting levels tracked in metadata
        """
        # JavaScript code with nested functions
        js_code = """
function createDataProcessor(config) {
  const cache = new Map();
  const stats = { hits: 0, misses: 0 };

  function processItem(item) {
    const cached = cache.get(item.id);
    if (cached) {
      stats.hits++;
      return cached;
    }

    stats.misses++;
    const result = {
      id: item.id,
      value: transformValue(item.value),
      timestamp: Date.now()
    };

    cache.set(item.id, result);
    return result;
  }

  function transformValue(value) {
    return config.multiplier ? value * config.multiplier : value;
  }

  function getStats() {
    return { ...stats };
  }

  return {
    process: processItem,
    stats: getStats,
    cache
  };
}
"""

        # Create temporary file
        test_file = tmp_path / "nested.js"
        test_file.write_text(js_code)

        # Chunk the code
        chunks = delimiter_chunker.chunk(js_code, file_path=test_file)

        # Verify chunks were created
        assert len(chunks) > 0, "Should create at least one chunk"

        # Find the outer function chunk
        outer_function_chunks = [
            c
            for c in chunks
            if "createDataProcessor" in c.content
            and c.metadata.get("kind") == DelimiterKind.FUNCTION
        ]
        assert outer_function_chunks, "Should have chunk for outer function"

        outer_chunk = outer_function_chunks[0]

        # Verify outer function contains nested functions
        assert "processItem" in outer_chunk.content, "Outer function should contain processItem"
        assert "transformValue" in outer_chunk.content, (
            "Outer function should contain transformValue"
        )
        assert "getStats" in outer_chunk.content, "Outer function should contain getStats"

        # Verify nesting metadata is tracked
        assert "nesting_level" in outer_chunk.metadata, "Should track nesting level"
        assert outer_chunk.metadata["nesting_level"] >= 0, "Nesting level should be non-negative"

        # Verify complete function block
        assert outer_chunk.content.startswith("function createDataProcessor"), (
            "Should start with function declaration"
        )
        assert "return {" in outer_chunk.content, "Should include return statement"

        # Verify function boundaries are respected (proper brace matching)
        open_braces = outer_chunk.content.count("{")
        close_braces = outer_chunk.content.count("}")
        assert open_braces == close_braces, "Braces should be balanced in function chunk"


class TestDelimiterPriorityResolution:
    """Test delimiter priority resolution for overlapping boundaries."""

    def test_delimiter_priority_resolution(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Test that higher priority delimiters win for overlaps.

        Input: Code with overlapping delimiters (e.g., class containing methods)
        Expected: Higher priority delimiter wins
        Assert: Only non-overlapping boundaries selected
        Verify: Chunks don't overlap
        """
        # Python code with class containing methods (overlapping boundaries)
        py_code = """
class DataProcessor:
    '''Process and validate data.'''

    def __init__(self, name: str):
        self.name = name

    def process_item(self, item: dict) -> dict:
        if not item.get("id"):
            raise ValueError("Missing id")
        return {"id": item["id"], "processed": True}

    def _transform_value(self, value: int) -> int:
        return value * 2
"""

        # Create temporary file
        test_file = tmp_path / "overlapping.py"
        test_file.write_text(py_code)

        # Chunk the code
        chunks = delimiter_chunker.chunk(py_code, file_path=test_file)

        # Verify chunks were created
        assert len(chunks) > 0, "Should create at least one chunk"

        if class_chunks := [c for c in chunks if c.metadata.get("kind") == DelimiterKind.CLASS]:
            class_chunk = class_chunks[0]

            # Class chunk should contain the entire class including methods
            assert "def __init__" in class_chunk.content, "Class should include __init__"
            assert "def process_item" in class_chunk.content, "Class should include process_item"
            assert "def _transform_value" in class_chunk.content, (
                "Class should include _transform_value"
            )

            # Verify priority in metadata
            assert "priority" in class_chunk.metadata, "Should have priority in metadata"
            assert class_chunk.metadata["priority"] >= 70, "Class priority should be high"

        # Verify no chunks overlap
        sorted_chunks = sorted(chunks, key=lambda c: c.start_line)
        for i in range(len(sorted_chunks) - 1):
            current = sorted_chunks[i]
            next_chunk = sorted_chunks[i + 1]

            # Chunks should not overlap
            assert current.end_line <= next_chunk.start_line, (
                f"Chunks should not overlap: chunk {i} ends at {current.end_line}, "
                f"chunk {i + 1} starts at {next_chunk.start_line}"
            )


class TestDelimiterChunksPython:
    """Test delimiter chunker with Python code."""

    def test_delimiter_chunks_python(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Test proper boundary detection for Python delimiters.

        Input: Python code with class/function delimiters
        Expected: Proper boundary detection
        Assert: Classes and functions properly chunked
        """
        # Python code with clear class and function boundaries
        py_code = """
class CacheManager:
    '''Manage caching operations with TTL support.'''

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._storage: dict[str, tuple[any, float]] = {}

    def get(self, key: str) -> any:
        '''Retrieve value from cache if not expired.'''
        if key not in self._storage:
            return None

        value, timestamp = self._storage[key]
        import time
        if time.time() - timestamp > self.ttl:
            del self._storage[key]
            return None
        return value

    def set(self, key: str, value: any) -> None:
        '''Store value in cache with current timestamp.'''
        import time
        self._storage[key] = (value, time.time())


def validate_config(config: dict) -> bool:
    '''Validate configuration dictionary.'''
    required_keys = ["host", "port", "timeout"]

    for key in required_keys:
        if key not in config:
            return False

    def check_port(port: int) -> bool:
        return 1 <= port <= 65535

    if not check_port(config["port"]):
        return False

    return True
"""

        # Create temporary file
        test_file = tmp_path / "boundaries.py"
        _ = test_file.write_text(py_code)

        # Chunk the code
        chunks = delimiter_chunker.chunk(py_code, file_path=test_file)

        # Verify chunks were created
        assert len(chunks) > 0, "Should create at least one chunk"

        # Check for class chunks
        class_chunks = [
            c
            for c in chunks
            if c.metadata.get("kind") == DelimiterKind.CLASS and "CacheManager" in c.content
        ]

        # Check for standalone function chunks
        function_chunks = [
            c
            for c in chunks
            if c.metadata.get("kind") == DelimiterKind.FUNCTION and "validate_config" in c.content
        ]

        # Verify boundaries are detected
        # Note: Depending on delimiter detection, we might get class + methods or separate chunks
        has_class_boundary = len(class_chunks) > 0
        has_function_boundary = len(function_chunks) > 0

        assert has_class_boundary or has_function_boundary, (
            "Should detect at least class or function boundaries"
        )

        # If class chunk exists, verify it contains methods
        if class_chunks:
            class_chunk = class_chunks[0]
            assert "def __init__" in class_chunk.content, "Class chunk should contain __init__"
            assert "def get" in class_chunk.content, "Class chunk should contain get method"
            assert "def set" in class_chunk.content, "Class chunk should contain set method"

        # If standalone function chunk exists, verify content
        if function_chunks:
            func_chunk = function_chunks[0]
            assert func_chunk.content.startswith("def validate_config"), (
                "Function chunk should start with function definition"
            )
            assert "check_port" in func_chunk.content, (
                "Function chunk should contain nested function"
            )
            assert "return True" in func_chunk.content, (
                "Function chunk should contain return statement"
            )

        # Verify all chunks have valid line ranges
        for chunk in chunks:
            assert chunk.start_line > 0, "Start line should be positive"
            assert chunk.end_line >= chunk.start_line, "End line should be >= start line"
            assert chunk.end_line - chunk.start_line >= 0, "Line range should be non-negative"


class TestDelimiterNestingHandling:
    """Test nesting handling for nested delimiters."""

    def test_nested_control_structures(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Test handling of nested control structures."""
        # Code with nested if statements and loops
        code = """
function processData(items) {
    for (let i = 0; i < items.length; i++) {
        if (items[i].valid) {
            if (items[i].priority > 5) {
                console.log("High priority:", items[i]);
            } else {
                console.log("Normal priority:", items[i]);
            }
        }
    }
}
"""

        test_file = tmp_path / "nested_control.js"
        test_file.write_text(code)

        chunks = delimiter_chunker.chunk(code, file_path=test_file)

        # Should have at least one chunk
        assert len(chunks) > 0, "Should create chunks for nested structures"

        if function_chunks := [
            c for c in chunks if c.metadata.get("kind") == DelimiterKind.FUNCTION
        ]:
            func_chunk = function_chunks[0]

            # Verify nested structures are included
            assert "for" in func_chunk.content, "Should include for loop"
            assert "if" in func_chunk.content, "Should include if statements"

            # Verify nesting metadata
            assert "nesting_level" in func_chunk.metadata, "Should track nesting level"


class TestDelimiterBoundaryDetection:
    """Test boundary detection accuracy."""

    def test_start_end_marker_accuracy(
        self, delimiter_chunker: DelimiterChunker, tmp_path: Path
    ) -> None:
        """Test that start and end markers are accurately detected."""
        code = """
def simple_function():
    return 42

def another_function():
    return 100
"""

        test_file = tmp_path / "boundaries.py"
        _ = test_file.write_text(code)

        chunks = delimiter_chunker.chunk(code, file_path=test_file)

        # Should have chunks for both functions
        assert len(chunks) >= 2, "Should detect both function boundaries"

        if first_func := [c for c in chunks if "simple_function" in c.content]:
            chunk = first_func[0]
            assert chunk.content.strip().startswith("def simple_function"), (
                "Should start at function definition"
            )
            assert "return 42" in chunk.content, "Should include function body"
            # Should not bleed into next function
            assert "another_function" not in chunk.content, "Should not include next function"

        if second_func := [c for c in chunks if "another_function" in c.content]:
            chunk = second_func[0]
            assert chunk.content.strip().startswith("def another_function"), (
                "Should start at function definition"
            )
            assert "return 100" in chunk.content, "Should include function body"
            # Should not bleed into previous function
            assert "simple_function" not in chunk.content, "Should not include previous function"
