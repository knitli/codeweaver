import pytest
from pathlib import Path

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.spans import Span
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.utils import uuid7

def test_from_chunk_valid_file(tmp_path: Path):
    """Test creating a DiscoveredFile from a CodeChunk with a valid, existing file."""
    test_file = tmp_path / "valid_file.py"
    test_file.write_text("print('hello world')")

    chunk = CodeChunk(
        content="print('hello world')",
        line_range=Span(start=1, end=1, source_id=uuid7()),
        file_path=test_file
    )

    discovered_file = DiscoveredFile.from_chunk(chunk)

    assert isinstance(discovered_file, DiscoveredFile)
    assert discovered_file.path.name == "valid_file.py"

def test_from_chunk_invalid_file(tmp_path: Path):
    """Test that creating a DiscoveredFile from a CodeChunk fails when the file_path is invalid."""
    # Condition 1: file_path is None
    chunk_no_path = CodeChunk(
        content="print('hello')",
        line_range=Span(start=1, end=1, source_id=uuid7()),
        file_path=None
    )
    with pytest.raises(ValueError, match="CodeChunk must have a valid file_path"):
        DiscoveredFile.from_chunk(chunk_no_path)

    # Condition 2: file_path points to a non-existent file
    chunk_bad_path = CodeChunk(
        content="print('hello')",
        line_range=Span(start=1, end=1, source_id=uuid7()),
        file_path=tmp_path / "does_not_exist.py"
    )
    with pytest.raises(ValueError, match="CodeChunk must have a valid file_path"):
        DiscoveredFile.from_chunk(chunk_bad_path)

    # Condition 3: file_path points to an existing directory instead of a file
    chunk_dir = CodeChunk(
        content="print('hello')",
        line_range=Span(start=1, end=1, source_id=uuid7()),
        file_path=tmp_path
    )
    with pytest.raises(ValueError, match="CodeChunk must have a valid file_path"):
        DiscoveredFile.from_chunk(chunk_dir)
