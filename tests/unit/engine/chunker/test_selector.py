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


def _create_mock_file(file_path: Path) -> Mock:
    """Create a properly configured Mock object that simulates a DiscoveredFile.

    The Mock needs to simulate:
    - file.path: Path object with stat() method
    - file.path.stat().st_size: File size in bytes
    - file.ext_kind: ExtKind object with language attribute
    """
    # Create mock stat result
    mock_stat = Mock()
    mock_stat.st_size = 1024  # 1KB file size

    # Create mock path with stat() method
    mock_path = Mock(spec=Path)
    mock_path.stat.return_value = mock_stat
    mock_path.suffix = file_path.suffix
    mock_path.__str__ = Mock(return_value=str(file_path))

    # Create mock ExtKind
    from codeweaver.core.language import SemanticSearchLanguage

    mock_ext_kind = Mock()
    if file_path.suffix == ".py":
        mock_ext_kind.language = SemanticSearchLanguage.PYTHON
    else:
        mock_ext_kind.language = file_path.suffix.lstrip(".")

    # Create mock DiscoveredFile
    file = Mock()
    file.path = mock_path
    file.ext_kind = mock_ext_kind

    return file


def test_selector_chooses_semantic_for_python(chunk_governor: ChunkGovernor) -> None:
    """Verify selector picks semantic for supported language."""
    from codeweaver.engine.chunker.selector import GracefulChunker

    selector = ChunkerSelector(chunk_governor)

    # Create mock file with .py extension
    file = _create_mock_file(Path("test.py"))

    chunker = selector.select_for_file(file)
    # Selector now wraps SemanticChunker in GracefulChunker for automatic fallback
    assert isinstance(chunker, GracefulChunker)
    assert isinstance(chunker.primary, SemanticChunker)

    # Verify fallback configuration
    assert isinstance(chunker.fallback, DelimiterChunker), (
        "GracefulChunker should have DelimiterChunker as fallback"
    )

    # Verify fallback language matches the primary semantic language
    from codeweaver.core.language import SemanticSearchLanguage
    assert chunker.fallback._language == SemanticSearchLanguage.PYTHON, (
        "Fallback language should match semantic language for .py files"
    )


def test_selector_falls_back_to_delimiter_for_unknown(chunk_governor: ChunkGovernor) -> None:
    """Verify selector uses delimiter for unsupported language."""
    selector = ChunkerSelector(chunk_governor)

    # Create mock file with unknown extension
    file = _create_mock_file(Path("test.xyz"))

    chunker = selector.select_for_file(file)
    assert isinstance(chunker, DelimiterChunker), (
        "Should use DelimiterChunker for unsupported languages"
    )


def test_selector_creates_fresh_instances(chunk_governor: ChunkGovernor) -> None:
    """Verify selector creates new instance each time (no reuse)."""
    selector = ChunkerSelector(chunk_governor)

    # Create mock file
    file = _create_mock_file(Path("test.py"))

    chunker1 = selector.select_for_file(file)
    chunker2 = selector.select_for_file(file)

    assert id(chunker1) != id(chunker2), "Should create fresh instances"
