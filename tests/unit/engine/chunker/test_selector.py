# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for ChunkerSelector intelligent routing."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import pytest

from codeweaver.engine.chunker.delimiter import DelimiterChunker
from codeweaver.engine.chunker.selector import ChunkerSelector
from codeweaver.engine.chunker.semantic import SemanticChunker


@pytest.fixture
def mock_governor() -> Mock:
    """Create mock ChunkGovernor."""
    governor = Mock()
    governor.chunk_limit = 2000
    governor.simple_overlap = 50
    governor.performance_settings = Mock(
        chunk_timeout_seconds=30, max_chunks_per_file=5000, max_ast_depth=200
    )
    return governor


@pytest.fixture
def mock_discovered_file() -> Callable[..., Mock]:
    """Create mock DiscoveredFile class."""

    def _make_file(path_str) -> Mock:
        file = Mock()
        file.path = Path(path_str)
        return file

    return _make_file


def test_selector_chooses_semantic_for_python(mock_governor, mock_discovered_file) -> None:
    """Verify selector picks semantic for supported language."""
    selector = ChunkerSelector(mock_governor)
    file = mock_discovered_file("test.py")

    chunker = selector.select_for_file(file)
    assert isinstance(chunker, SemanticChunker)


def test_selector_falls_back_to_delimiter_for_unknown(mock_governor, mock_discovered_file) -> None:
    """Verify selector uses delimiter for unsupported language."""
    selector = ChunkerSelector(mock_governor)
    file = mock_discovered_file("test.xyz")

    chunker = selector.select_for_file(file)
    assert isinstance(chunker, DelimiterChunker)


def test_selector_creates_fresh_instances(mock_governor, mock_discovered_file) -> None:
    """Verify selector creates new instance each time (no reuse)."""
    selector = ChunkerSelector(mock_governor)
    file = mock_discovered_file("test.py")

    chunker1 = selector.select_for_file(file)
    chunker2 = selector.select_for_file(file)

    assert id(chunker1) != id(chunker2), "Should create fresh instances"
