import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.metadata import ExtCategory
from codeweaver.core.utils import get_blake_hash

@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Provides a temporary directory representing a project root."""
    return tmp_path

def test_from_path_with_matching_hash(temp_project: Path, caplog: pytest.LogCaptureFixture) -> None:
    test_file = temp_project / "test.py"
    test_content = b"print('hello')"
    test_file.write_bytes(test_content)

    expected_hash = get_blake_hash(test_content)

    with caplog.at_level(logging.WARNING):
        df = DiscoveredFile.from_path(test_file, file_hash=expected_hash, project_path=temp_project)

    assert df is not None
    assert df.file_hash == expected_hash
    assert "Provided file_hash does not match" not in caplog.text

def test_from_path_with_mismatching_hash(temp_project: Path, caplog: pytest.LogCaptureFixture) -> None:
    test_file = temp_project / "test.py"
    test_content = b"print('hello')"
    test_file.write_bytes(test_content)

    mismatch_hash = get_blake_hash(b"print('world')")
    computed_hash = get_blake_hash(test_content)

    with caplog.at_level(logging.WARNING):
        df = DiscoveredFile.from_path(test_file, file_hash=mismatch_hash, project_path=temp_project)

    assert df is not None
    assert df.file_hash == computed_hash
    assert "Provided file_hash does not match computed hash" in caplog.text

def test_from_path_without_hash(temp_project: Path) -> None:
    test_file = temp_project / "test.py"
    test_content = b"print('hello')"
    test_file.write_bytes(test_content)

    computed_hash = get_blake_hash(test_content)

    df = DiscoveredFile.from_path(test_file, project_path=temp_project)

    assert df is not None
    assert df.file_hash == computed_hash

def test_from_path_with_directory_resolves_git_branch(temp_project: Path) -> None:
    test_dir = temp_project / "src"
    test_dir.mkdir()

    with patch("codeweaver.core.discovery.get_git_branch", return_value="custom-branch") as mock_git:
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.core.metadata import ChunkKind
        mock_ext = ExtCategory(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE)
        with patch("codeweaver.core.discovery.ExtCategory.from_file", return_value=mock_ext), patch("codeweaver.core.discovery.get_blake_hash", return_value="fake_hash"), patch("pathlib.Path.read_bytes", return_value=b"fake"):
            df = DiscoveredFile.from_path(test_dir, project_path=temp_project)

    assert df is not None
    assert df.git_branch == "custom-branch"
    mock_git.assert_called_once_with(test_dir)

def test_from_path_with_file_resolves_git_branch(temp_project: Path) -> None:
    test_file = temp_project / "test.py"
    test_file.write_text("print('hello')")

    with patch("codeweaver.core.discovery.get_git_branch", return_value="custom-branch") as mock_git:
        df = DiscoveredFile.from_path(test_file, project_path=temp_project)

    assert df is not None
    assert df.git_branch == "custom-branch"
    mock_git.assert_called_once_with(temp_project)

def test_from_path_with_invalid_ext_category(temp_project: Path) -> None:
    test_file = temp_project / "test.invalidext12345"
    test_file.write_text("invalid")

    df = DiscoveredFile.from_path(test_file, project_path=temp_project)

    assert df is None

def test_from_path_with_injected_project_path(temp_project: Path) -> None:
    test_file = temp_project / "test.py"
    test_file.write_text("print('hello')")

    with patch("codeweaver.core.utils.filesystem.get_project_path", return_value=temp_project):
        from codeweaver.core.di import INJECTED
        df = DiscoveredFile.from_path(test_file, project_path=INJECTED)

    assert df is not None
    assert df.project_path == temp_project
