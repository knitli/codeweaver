# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for ChunkerSelector intelligent routing."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from codeweaver.engine import ChunkerSelector, ChunkGovernor, DelimiterChunker, SemanticChunker


pytestmark = [pytest.mark.unit]


def _create_mock_file(file_path: Path) -> Mock:
    """Create a properly configured Mock object that simulates a DiscoveredFile.

    The Mock needs to simulate:
    - file.path: Path object with stat() method
    - file.path.stat().st_size: File size in bytes
    - file.ext_category: ExtCategory object with language attribute
    """
    # Create mock stat result
    mock_stat = Mock()
    mock_stat.st_size = 1024  # 1KB file size

    # Create mock path with stat() method
    mock_path = Mock(spec=Path)
    mock_path.stat.return_value = mock_stat
    mock_path.suffix = file_path.suffix
    mock_path.__str__ = Mock(return_value=str(file_path))

    # Create mock ExtCategory
    from codeweaver.core import SemanticSearchLanguage

    mock_ext_category = Mock()
    if file_path.suffix == ".py":
        mock_ext_category.language = SemanticSearchLanguage.PYTHON
    else:
        mock_ext_category.language = file_path.suffix.lstrip(".")

    # Create mock DiscoveredFile
    file = Mock()
    file.path = mock_path
    file.absolute_path = mock_path
    file.ext_category = mock_ext_category

    return file


def test_selector_chooses_semantic_for_python(chunk_governor: ChunkGovernor) -> None:
    """Verify selector picks semantic for supported language."""
    from codeweaver.engine import GracefulChunker

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
    from codeweaver.core import SemanticSearchLanguage

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


def test_selector_raises_error_for_oversized_file(chunk_governor: ChunkGovernor) -> None:
    """Verify selector raises FileTooLargeError for files exceeding max_file_size_mb."""
    from codeweaver.engine.chunker.exceptions import FileTooLargeError

    selector = ChunkerSelector(chunk_governor)

    # Create mock file that exceeds the configured max_file_size_mb limit
    file = _create_mock_file(Path("test.py"))
    max_size_mb = chunk_governor.settings.performance.max_file_size_mb
    oversized_mb = max_size_mb + 5
    # Set file size to a value that exceeds the configured limit
    file.absolute_path.stat.return_value.st_size = oversized_mb * 1024 * 1024

    with pytest.raises(FileTooLargeError) as exc_info:
        selector.select_for_file(file)

    # Verify error details
    error = exc_info.value
    assert error.file_size_mb == float(oversized_mb)
    assert error.max_size_mb == max_size_mb
    assert error.file_path == str(file.absolute_path)
    assert f"{oversized_mb:.2f} MB > {max_size_mb} MB" in str(error)


def test_selector_handles_oserror_on_stat(
    chunk_governor: ChunkGovernor, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify selector handles OSError gracefully when checking file size."""
    import logging

    from codeweaver.engine import GracefulChunker, SemanticChunker

    selector = ChunkerSelector(chunk_governor)
    file = _create_mock_file(Path("test.py"))

    # Force stat() to raise OSError
    file.absolute_path.stat.side_effect = OSError("Permission denied")

    caplog.clear()

    # Should not raise an exception, but proceed and return the chunker
    with caplog.at_level(logging.WARNING):
        chunker = selector.select_for_file(file)

    # Returns SemanticChunker wrapped in GracefulChunker because it's a Python file
    assert isinstance(chunker, GracefulChunker)
    assert isinstance(chunker.primary, SemanticChunker)

    # Verify warning was logged
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "Could not stat file" in r.message and "Permission denied" in r.message
        for r in warning_records
    )
