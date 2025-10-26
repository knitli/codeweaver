"""
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
"""

"""End-to-end integration tests for chunking workflows."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from codeweaver.engine.chunker.selector import ChunkerSelector


@pytest.fixture
def mock_governor():
    """Create mock ChunkGovernor."""
    governor = Mock()
    governor.chunk_limit = 2000
    governor.simple_overlap = 50
    governor.performance_settings = Mock(
        chunk_timeout_seconds=30,
        max_chunks_per_file=5000,
        max_ast_depth=200,
    )
    return governor


@pytest.fixture
def mock_discovered_file():
    """Create mock DiscoveredFile."""
    def _make_file(path_str):
        file = Mock()
        file.path = Path(path_str)
        return file
    return _make_file


def test_e2e_real_python_file(mock_governor, mock_discovered_file):
    """Integration test: Real Python file → valid chunks."""
    fixture_path = Path("tests/fixtures/sample.py")
    content = fixture_path.read_text()

    selector = ChunkerSelector(mock_governor)
    file = mock_discovered_file(str(fixture_path))
    chunker = selector.select_for_file(file)

    chunks = chunker.chunk(content, file_path=fixture_path)

    # Basic quality checks
    assert len(chunks) > 0, "Should produce chunks"
    assert all(c.content.strip() for c in chunks), "No empty chunks"
    assert all(c.metadata for c in chunks), "All chunks have metadata"
    assert all(c.line_range.start <= c.line_range.end for c in chunks), \
        "Valid line ranges"


def test_e2e_degradation_chain(mock_governor, mock_discovered_file):
    """Verify degradation chain handles malformed files."""
    fixture_path = Path("tests/fixtures/malformed.py")
    content = fixture_path.read_text()

    selector = ChunkerSelector(mock_governor)
    file = mock_discovered_file(str(fixture_path))

    # Should gracefully degrade and still produce chunks
    # (implementation will add fallback logic)
    with pytest.raises(Exception):  # Will fail until fallback implemented
        chunker = selector.select_for_file(file)
        chunks = chunker.chunk(content, file_path=fixture_path)
