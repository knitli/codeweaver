# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for semantic chunker error conditions.

This module tests error handling in the semantic chunker system including:
- Parse errors from malformed code
- AST depth exceeded errors from deep nesting
- Timeout errors from slow operations
- Chunk limit exceeded errors from excessive chunking

All tests follow TDD principles and are designed to FAIL initially until
the corresponding implementation is complete.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from codeweaver.engine.chunker.exceptions import (
    ASTDepthExceededError,
    ChunkingTimeoutError,
    ChunkLimitExceededError,
    ParseError,
)


if TYPE_CHECKING:
    from pytest import MonkeyPatch

# Path to test fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures"


@pytest.fixture
def mock_governor() -> MagicMock:
    """Create properly configured mock governor for testing."""
    governor = MagicMock()
    governor.chunk_limit = 2000
    governor.simple_overlap = 50
    # Match the actual governor.settings.performance structure
    governor.settings = MagicMock()
    governor.settings.performance = MagicMock(
        chunk_timeout_seconds=30,
        max_chunks_per_file=5000,
        max_ast_depth=200
    )
    governor.settings.semantic_importance_threshold = 0.3
    return governor


class TestParseErrors:
    """Tests for parse error handling with malformed code."""

    def test_parse_error_raises(self, mock_governor: MagicMock) -> None:
        """Verify that malformed code raises ParseError.

        Input: malformed.py fixture with syntax errors
        Expected: ParseError raised with descriptive message
        Verifies: Exception contains file path and error details
        """
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.engine.chunker.semantic import SemanticChunker

        # Arrange: Load malformed Python file
        malformed_file = FIXTURES_DIR / "malformed.py"
        assert malformed_file.exists(), "malformed.py fixture must exist"
        content = malformed_file.read_text()

        # Create chunker with mock governor
        chunker = SemanticChunker(governor=mock_governor, language=SemanticSearchLanguage.PYTHON)

        # Create DiscoveredFile and verify ParseError raised
        from codeweaver.core.discovery import DiscoveredFile
        discovered_file = DiscoveredFile.from_path(malformed_file)
        with pytest.raises(ParseError) as exc_info:
            chunker.chunk(content, file=discovered_file)

        # Verify error details
        error = exc_info.value
        assert str(malformed_file) in str(error), "Error should include file path"
        assert error.file_path == str(malformed_file), "Exception should track file path"
        assert "syntax" in str(error).lower() or "parse" in str(error).lower(), (
            "Error message should indicate parsing failure"
        )

    def test_parse_error_suggestions_present(self, mock_governor: MagicMock) -> None:
        """Verify that ParseError includes actionable suggestions.

        Confirms that parse errors provide helpful guidance for resolution.
        """
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.engine.chunker.semantic import SemanticChunker

        malformed_file = FIXTURES_DIR / "malformed.py"
        content = malformed_file.read_text()

        chunker = SemanticChunker(governor=mock_governor, language=SemanticSearchLanguage.PYTHON)

        from codeweaver.core.discovery import DiscoveredFile
        discovered_file = DiscoveredFile.from_path(malformed_file)
        with pytest.raises(ParseError) as exc_info:
            chunker.chunk(content, file=discovered_file)

        error = exc_info.value
        assert hasattr(error, "suggestions"), "ParseError should have suggestions attribute"
        assert len(error.suggestions) > 0, "ParseError should provide actionable suggestions"


class TestASTDepthErrors:
    """Tests for AST depth limit enforcement."""

    def test_ast_depth_exceeded_error(self, mock_governor: MagicMock) -> None:
        """Verify that deeply nested code raises ASTDepthExceededError.

        Input: deep_nesting.py fixture with >200 nesting levels
        Expected: ASTDepthExceededError raised with depth metrics
        Verifies: Exception contains actual depth and configured limit
        """
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.engine.chunker.semantic import SemanticChunker

        # Arrange: Load deeply nested Python file
        deep_file = FIXTURES_DIR / "deep_nesting.py"
        assert deep_file.exists(), "deep_nesting.py fixture must exist"
        content = deep_file.read_text()

        # Create mock governor with depth limit        mock_governor.max_ast_depth = 200  # Standard limit
        chunker = SemanticChunker(governor=mock_governor, language=SemanticSearchLanguage.PYTHON)

        # Act & Assert: Verify ASTDepthExceededError raised
        from codeweaver.core.discovery import DiscoveredFile
        discovered_file = DiscoveredFile.from_path(deep_file)
        with pytest.raises(ASTDepthExceededError) as exc_info:
            chunker.chunk(content, file=discovered_file)

        # Verify error details
        error = exc_info.value
        assert error.actual_depth is not None, "Error should track actual depth"
        assert error.max_depth is not None, "Error should track configured limit"
        assert error.actual_depth > error.max_depth, "Actual depth must exceed limit"
        assert error.file_path == str(deep_file), "Error should track file path"

    def test_ast_depth_error_message_descriptive(self, mock_governor: MagicMock) -> None:
        """Verify that AST depth error messages are clear and actionable.

        Confirms that depth errors provide helpful diagnostics and suggestions.
        """
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.engine.chunker.semantic import SemanticChunker

        deep_file = FIXTURES_DIR / "deep_nesting.py"
        content = deep_file.read_text()
        mock_governor.performance_settings.max_ast_depth = 200
        chunker = SemanticChunker(governor=mock_governor, language=SemanticSearchLanguage.PYTHON)

        from codeweaver.core.discovery import DiscoveredFile
        discovered_file = DiscoveredFile.from_path(deep_file)
        with pytest.raises(ASTDepthExceededError) as exc_info:
            chunker.chunk(content, file=discovered_file)

        error = exc_info.value
        error_msg = str(error)
        assert "depth" in error_msg.lower(), "Error message should mention depth"
        assert "nest" in error_msg.lower(), "Error message should mention nesting"
        assert hasattr(error, "suggestions"), "Error should provide suggestions"
        assert len(error.suggestions) > 0, "Error should include actionable guidance"


class TestTimeoutErrors:
    """Tests for chunking timeout enforcement."""

    def test_timeout_exceeded(
        self,
        mock_governor: MagicMock,
        monkeypatch: MonkeyPatch,
        discovered_sample_python_file,
    ) -> None:
        """Verify that slow operations raise ChunkingTimeoutError.

        Approach: Mock time.time() to simulate elapsed time exceeding timeout
        Expected: ChunkingTimeoutError raised with timing metrics
        Verifies: Exception contains timeout threshold and elapsed time
        """
        import time
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.engine.chunker.semantic import SemanticChunker

        # Arrange: Create chunker with very short timeout (10ms)
        mock_governor.settings.performance.chunk_timeout_seconds = 0.01

        chunker = SemanticChunker(governor=mock_governor, language=SemanticSearchLanguage.PYTHON)

        # Mock time.time() to simulate timeout
        start_time = 1000.0
        elapsed_time = 0.1  # 100ms elapsed, exceeds 10ms timeout

        call_count = [0]
        def mock_time():
            call_count[0] += 1
            # First call sets start time, subsequent calls show elapsed time
            if call_count[0] == 1:
                return start_time
            return start_time + elapsed_time

        monkeypatch.setattr(time, "time", mock_time)

        # Act & Assert: Verify ChunkingTimeoutError raised
        with pytest.raises(ChunkingTimeoutError) as exc_info:
            chunker.chunk(discovered_sample_python_file.contents, file=discovered_sample_python_file)

        # Verify error details
        error = exc_info.value
        assert error.timeout_seconds is not None, "Error should track timeout threshold"
        assert error.elapsed_seconds is not None, "Error should track elapsed time"
        assert error.elapsed_seconds > error.timeout_seconds, "Elapsed time should exceed timeout"

    def test_timeout_error_suggestions_present(self, mock_governor: MagicMock) -> None:
        """Verify that timeout errors include helpful suggestions.

        Confirms that timeout errors provide guidance for resolution.
        """
        # Create timeout error directly to verify suggestion structure
        error = ChunkingTimeoutError(
            "Timeout exceeded",
            timeout_seconds=30.0,
            elapsed_seconds=45.0,
            file_path="large_file.py",
        )

        assert hasattr(error, "suggestions"), "Timeout error should have suggestions"
        assert len(error.suggestions) > 0, "Timeout error should provide guidance"
        assert any("timeout" in s.lower() or "increase" in s.lower() for s in error.suggestions), (
            "Suggestions should mention timeout configuration"
        )


class TestChunkLimitErrors:
    """Tests for chunk limit enforcement."""

    def test_chunk_limit_exceeded(self, mock_governor: MagicMock) -> None:
        """Verify that excessive chunking raises ChunkLimitExceededError.

        Approach: Mock register_chunk to enforce low limit
        Expected: ChunkLimitExceededError raised with count metrics
        Verifies: Exception contains chunk count and configured limit
        """
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.engine.chunker.semantic import SemanticChunker

        # Arrange: Create chunker with very low chunk limit        mock_governor.max_chunks_per_file = 10  # Very low limit for testing

        # Track chunk registration and enforce limit
        chunk_count = 0

        def register_chunk_with_limit():
            nonlocal chunk_count
            chunk_count += 1
            if chunk_count > mock_governor.max_chunks_per_file:
                raise ChunkLimitExceededError(
                    "Chunk limit exceeded",
                    chunk_count=chunk_count,
                    max_chunks=mock_governor.max_chunks_per_file,
                    file_path="test.py",
                )

        mock_governor.register_chunk = register_chunk_with_limit

        chunker = SemanticChunker(governor=mock_governor, language=SemanticSearchLanguage.PYTHON)

        # Create content that would generate many chunks
        # Simulate a file with many small functions
        many_functions = "\n\n".join(
            f"def function_{i}():\n    pass"
            for i in range(15)  # More than the limit
        )

        # Act & Assert: Verify ChunkLimitExceededError raised
        # Note: Using None for file since we're testing chunk limits, not file handling
        with pytest.raises(ChunkLimitExceededError) as exc_info:
            chunker.chunk(many_functions, file=None)

        # Verify error details
        error = exc_info.value
        assert error.chunk_count is not None, "Error should track chunk count"
        assert error.max_chunks is not None, "Error should track configured limit"
        assert error.chunk_count > error.max_chunks, "Chunk count must exceed limit"
        assert error.file_path is not None, "Error should track file path"

    def test_chunk_limit_error_overflow_metrics(self, mock_governor: MagicMock) -> None:
        """Verify that chunk limit errors include overflow metrics.

        Confirms that errors track how many chunks exceeded the limit.
        """
        # Create error with specific counts to verify overflow calculation
        error = ChunkLimitExceededError(
            "Too many chunks", chunk_count=5500, max_chunks=5000, file_path="large_file.py"
        )

        assert error.chunk_count == 5500, "Error should track actual count"
        assert error.max_chunks == 5000, "Error should track limit"

        # Check that error details include overflow calculation
        assert hasattr(error, "details"), "Error should have details attribute"
        if "overflow_count" in error.details:
            assert error.details["overflow_count"] == 500, (
                "Overflow count should be difference between actual and max"
            )

    def test_chunk_limit_error_suggestions_present(self, mock_governor: MagicMock) -> None:
        """Verify that chunk limit errors include actionable suggestions.

        Confirms that errors provide guidance for handling excessive chunking.
        """
        error = ChunkLimitExceededError(
            "Too many chunks", chunk_count=6000, max_chunks=5000, file_path="complex_file.py"
        )

        assert hasattr(error, "suggestions"), "Error should have suggestions"
        assert len(error.suggestions) > 0, "Error should provide guidance"
        assert any(
            "chunk" in s.lower() or "limit" in s.lower() or "refactor" in s.lower()
            for s in error.suggestions
        ), "Suggestions should address chunk limits or code complexity"


class TestErrorMessageQuality:
    """Tests for error message quality and descriptiveness."""

    def test_all_error_types_have_descriptive_messages(self, mock_governor: MagicMock) -> None:
        """Verify that all chunking errors have clear, actionable messages.

        Confirms that error messages follow quality standards:
        - Clear description of what went wrong
        - Relevant context (file paths, metrics)
        - Actionable suggestions for resolution
        """
        # Test each error type for message quality
        errors = [
            ParseError("Failed to parse source code", file_path="test.py", line_number=42),
            ASTDepthExceededError(
                "AST nesting too deep", actual_depth=250, max_depth=200, file_path="nested.py"
            ),
            ChunkingTimeoutError(
                "Chunking operation timed out",
                timeout_seconds=30.0,
                elapsed_seconds=45.0,
                file_path="slow.py",
            ),
            ChunkLimitExceededError(
                "Too many chunks generated", chunk_count=6000, max_chunks=5000, file_path="large.py"
            ),
        ]

        for error in errors:
            error_msg = str(error)
            assert len(error_msg) > 20, f"{type(error).__name__} message too short"
            assert not error_msg.isspace(), f"{type(error).__name__} message is empty"

            # Verify suggestions present
            assert hasattr(error, "suggestions"), f"{type(error).__name__} should have suggestions"
            assert len(error.suggestions) > 0, (
                f"{type(error).__name__} should provide actionable guidance"
            )

    def test_error_details_are_structured(self, mock_governor: MagicMock) -> None:
        """Verify that error details are properly structured and accessible.

        Confirms that errors expose metrics and context in a consistent way.
        """
        # Create error with full details
        error = ParseError(
            "Syntax error in code",
            file_path="/path/to/file.py",
            line_number=123,
            details={"column": 45, "token": "unexpected_token"},
        )

        # Verify details are accessible
        assert hasattr(error, "details"), "Error should have details attribute"
        assert error.file_path == "/path/to/file.py", "File path should be accessible"
        assert error.line_number == 123, "Line number should be accessible"

        # Verify details dict contains expected fields
        if hasattr(error, "details"):
            assert "file_path" in error.details, "Details should include file path"
            assert "line_number" in error.details, "Details should include line number"
