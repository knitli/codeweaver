# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import logging

from pathlib import Path
from unittest.mock import patch

import pytest

from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.utils import get_blake_hash


pytestmark = [pytest.mark.unit]

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
        df = DiscoveredFile.from_path(test_dir, project_path=temp_project)

    assert df is None  # ExtCategory.from_file returns None for directories
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

def test_from_path_when_read_bytes_raises_exception(temp_project: Path) -> None:
    test_file = temp_project / "test.py"
    test_file.write_text("print('hello')")

    with patch("pathlib.Path.read_bytes", side_effect=PermissionError("Access denied")):
        with pytest.raises(PermissionError):
            DiscoveredFile.from_path(test_file, project_path=temp_project)

def test_from_path_with_symbolic_link(temp_project: Path) -> None:
    target_file = temp_project / "target.py"
    target_file.write_text("print('hello')")

    symlink_file = temp_project / "symlink.py"
    symlink_file.symlink_to(target_file)

    df = DiscoveredFile.from_path(symlink_file, project_path=temp_project)

    assert df is not None
    assert df.file_hash == get_blake_hash(b"print('hello')")

def test_from_path_with_git_branch_failure(temp_project: Path) -> None:
    test_file = temp_project / "test.py"
    test_file.write_text("print('hello')")

    with patch("codeweaver.core.discovery.get_git_branch", side_effect=Exception("Git not found")):
        with pytest.raises(Exception, match="Git not found"):
            DiscoveredFile.from_path(test_file, project_path=temp_project)

def test_absolute_path_with_absolute_path(temp_project: Path) -> None:
    test_file = temp_project / "test.py"
    test_file.write_text("print('hello')")
    df = DiscoveredFile.from_path(test_file, project_path=temp_project)
    assert df is not None
    assert df.absolute_path == test_file

def test_absolute_path_with_relative_path(temp_project: Path) -> None:
    test_file = temp_project / "test.py"
    test_file.write_text("print('hello')")
    df = DiscoveredFile.from_path(test_file, project_path=temp_project)
    assert df is not None
    assert df.absolute_path == test_file

def test_absolute_path_fallback(temp_project: Path) -> None:
    test_file = temp_project / "test.py"
    test_file.write_text("print('hello')")
    df = DiscoveredFile.from_path(test_file, project_path=temp_project)
    assert df is not None

    with patch("codeweaver.core.utils.filesystem.get_project_path", return_value=temp_project):
        object.__setattr__(df, "project_path", None)
        assert df.absolute_path == test_file
