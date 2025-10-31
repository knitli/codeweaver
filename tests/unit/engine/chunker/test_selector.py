# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for ChunkerSelector intelligent routing."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from codeweaver.engine.chunker.base import ChunkGovernor
from codeweaver.engine.chunker.delimiter import DelimiterChunker
from codeweaver.engine.chunker.selector import ChunkerSelector
from codeweaver.engine.chunker.semantic import SemanticChunker


pytestmark = [pytest.mark.unit]


def test_selector_chooses_semantic_for_python(chunk_governor: ChunkGovernor) -> None:
    """Verify selector picks semantic for supported language."""
    selector = ChunkerSelector(chunk_governor)

    # Create mock file with .py extension
    file = Mock()
    file.path = Path("test.py")

    chunker = selector.select_for_file(file)
    assert isinstance(chunker, SemanticChunker)


def test_selector_falls_back_to_delimiter_for_unknown(chunk_governor: ChunkGovernor) -> None:
    """Verify selector uses delimiter for unsupported language."""
    selector = ChunkerSelector(chunk_governor)

    # Create mock file with unknown extension
    file = Mock()
    file.path = Path("test.xyz")

    chunker = selector.select_for_file(file)
    assert isinstance(chunker, DelimiterChunker), (
        "Should use DelimiterChunker for unsupported languages"
    )


def test_selector_creates_fresh_instances(chunk_governor: ChunkGovernor) -> None:
    """Verify selector creates new instance each time (no reuse)."""
    selector = ChunkerSelector(chunk_governor)

    # Create mock file
    file = Mock()
    file.path = Path("test.py")

    chunker1 = selector.select_for_file(file)
    chunker2 = selector.select_for_file(file)

    assert id(chunker1) != id(chunker2), "Should create fresh instances"
