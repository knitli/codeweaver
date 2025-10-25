# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Edge case tests for SemanticChunker."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.engine.chunker import SemanticChunker
from codeweaver.engine.chunker.exceptions import BinaryFileError


@pytest.fixture
def mock_governor() -> Mock:
    """Create mock ChunkGovernor for testing."""
    from unittest.mock import Mock

    governor = Mock()
    governor.chunk_limit = 2000
    governor.simple_overlap = 50
    governor.performance_settings = Mock(
        chunk_timeout_seconds=30, max_chunks_per_file=5000, max_ast_depth=200
    )
    return governor


def test_empty_file(mock_governor: Mock) -> None:
    """Verify empty file returns empty list."""
    fixture_path = Path("tests/fixtures/empty.py")
    content = fixture_path.read_text()

    chunker = SemanticChunker(mock_governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(content, file_path=fixture_path)

    assert len(chunks) == 0, "Empty file should return no chunks"


def test_whitespace_only_file(mock_governor: Mock) -> None:
    """Verify whitespace-only file returns single chunk with edge_case metadata."""
    fixture_path = Path("tests/fixtures/whitespace_only.py")
    content = fixture_path.read_text()

    chunker = SemanticChunker(mock_governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(content, file_path=fixture_path)

    assert len(chunks) == 1, "Whitespace-only file should return single chunk"
    assert chunks[0].metadata.get("edge_case") == "whitespace_only"


def test_single_line_file(mock_governor: Mock) -> None:
    """Verify single-line file returns single chunk with edge_case metadata."""
    fixture_path = Path("tests/fixtures/single_line.py")
    content = fixture_path.read_text()

    chunker = SemanticChunker(mock_governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(content, file_path=fixture_path)

    assert len(chunks) == 1, "Single-line file should return single chunk"
    assert chunks[0].metadata.get("edge_case") == "single_line"


def test_binary_file_detection(mock_governor: Mock) -> None:
    """Verify binary file detection raises BinaryFileError."""
    fixture_path = Path("tests/fixtures/binary_mock.txt")
    content = fixture_path.read_text(encoding="utf-8", errors="ignore")

    chunker = SemanticChunker(mock_governor, SemanticSearchLanguage.PYTHON)

    with pytest.raises(BinaryFileError):
        _ = chunker.chunk(content, file_path=fixture_path)
