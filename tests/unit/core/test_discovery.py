# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for core discovery logic."""

from pathlib import Path
from unittest.mock import patch

import pytest

from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.metadata import ChunkKind, ExtCategory
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.utils import get_blake_hash


pytestmark = [pytest.mark.unit]


@pytest.fixture
def temp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fixture to provide a temporary project directory and set the environment variable."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("CODEWEAVER_PROJECT_PATH", str(project_dir))
    return project_dir


def test_absolute_path_when_path_is_absolute() -> None:
    """Test absolute_path property when the file path is already absolute."""
    abs_path = Path("/tmp/some_absolute_file.txt").resolve()
    df = DiscoveredFile(
        path=abs_path,
        ext_category=ExtCategory.from_file(abs_path),
        project_path=Path("/tmp/project")
    )
    result = df.absolute_path
    assert result == abs_path


def test_absolute_path_when_path_is_relative_and_project_path_set() -> None:
    """Test absolute_path property when the file path is relative and project_path is set."""
    rel_path = Path("src/main.py")
    proj_path = Path("/home/user/project")
    df = DiscoveredFile(
        path=rel_path,
        ext_category=ExtCategory.from_file(rel_path),
        project_path=proj_path
    )
    result = df.absolute_path
    assert result == proj_path / rel_path


def test_absolute_path_when_project_path_is_none_success(temp_project: Path) -> None:
    """Test absolute_path property when project_path is falsy and get_project_path succeeds."""
    rel_path = Path("src/main.py")
    df = DiscoveredFile(
        path=rel_path,
        ext_category=ExtCategory.from_file(rel_path),
        project_path=temp_project
    )
    # The property checks `if self.project_path:`. We can fake this by setting it to empty.
    object.__setattr__(df, "project_path", "")

    result = df.absolute_path

    # It should fall back to get_project_path() which is temp_project due to the fixture
    assert result == temp_project / rel_path


@patch('codeweaver.core.utils.get_project_path')
def test_absolute_path_when_project_path_is_none_filenotfound(mock_get_project_path) -> None:
    """Test absolute_path property when project_path is falsy and get_project_path raises FileNotFoundError."""
    mock_get_project_path.side_effect = FileNotFoundError()

    rel_path = Path("src/main.py")
    df = DiscoveredFile(
        path=rel_path,
        ext_category=ExtCategory.from_file(rel_path),
        project_path=Path("/tmp")
    )
    # The property checks `if self.project_path:`. We can fake this by setting it to empty.
    object.__setattr__(df, "project_path", "")

    result = df.absolute_path

    # It should catch FileNotFoundError and return self.path
    assert result == rel_path


@patch('codeweaver.core.discovery.ExtCategory.from_file')
def test_from_path_ext_category_none(mock_from_file, tmp_path: Path) -> None:
    """Test from_path returns None when ExtCategory.from_file returns None."""
    mock_from_file.return_value = None
    test_file = tmp_path / "test.unknown"
    test_file.write_text("content")

    result = DiscoveredFile.from_path(test_file, project_path=tmp_path)
    assert result is None


@patch('codeweaver.core.discovery.get_blake_hash')
@patch('codeweaver.core.discovery.get_git_branch')
@patch('codeweaver.core.discovery.ExtCategory.from_file')
def test_from_path_directory_path(mock_from_file, mock_get_git_branch, mock_get_blake_hash, tmp_path: Path) -> None:
    """Test from_path correctly handles a directory path for git branch check."""
    real_ext = ExtCategory(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE)
    mock_from_file.return_value = real_ext
    mock_get_git_branch.return_value = "feature-branch"
    mock_get_blake_hash.return_value = "fake_hash"

    test_dir = tmp_path / "somedir"
    test_dir.mkdir()

    # from_path requires the path to be read, which fails for a directory in read_bytes
    # We mock read_bytes to avoid IsADirectoryError and focus on the branch logic
    with patch.object(Path, 'read_bytes', return_value=b"content"):
        result = DiscoveredFile.from_path(test_dir, project_path=tmp_path)

    mock_get_git_branch.assert_called_once_with(test_dir)
    assert result is not None
    assert result.git_branch == "feature-branch"


@patch('codeweaver.core.discovery.get_git_branch')
@patch('codeweaver.core.discovery.ExtCategory.from_file')
def test_from_path_file_path(mock_from_file, mock_get_git_branch, tmp_path: Path) -> None:
    """Test from_path correctly handles a file path for git branch check."""
    real_ext = ExtCategory(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE)
    mock_from_file.return_value = real_ext
    mock_get_git_branch.return_value = "feature-branch"

    test_file = tmp_path / "test.py"
    test_file.write_text("content")

    result = DiscoveredFile.from_path(test_file, project_path=tmp_path)

    mock_get_git_branch.assert_called_once_with(tmp_path)
    assert result is not None
    assert result.git_branch == "feature-branch"


@patch('codeweaver.core.discovery.get_git_branch')
@patch('codeweaver.core.discovery.ExtCategory.from_file')
def test_from_path_git_branch_fallback(mock_from_file, mock_get_git_branch, tmp_path: Path) -> None:
    """Test from_path falls back to 'main' when get_git_branch returns None."""
    real_ext = ExtCategory(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE)
    mock_from_file.return_value = real_ext
    mock_get_git_branch.return_value = None

    test_file = tmp_path / "test.py"
    test_file.write_text("content")

    result = DiscoveredFile.from_path(test_file, project_path=tmp_path)

    assert result is not None
    assert result.git_branch == "main"


@patch('codeweaver.core.discovery.logger.warning')
@patch('codeweaver.core.discovery.ExtCategory.from_file')
def test_from_path_mismatched_file_hash(mock_from_file, mock_warning, tmp_path: Path) -> None:
    """Test from_path issues a warning when provided file_hash does not match computed hash."""
    real_ext = ExtCategory(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE)
    mock_from_file.return_value = real_ext

    test_file = tmp_path / "test.py"
    test_file.write_text("actual content")
    computed_hash = get_blake_hash(b"actual content")
    mismatched_hash = get_blake_hash(b"different content")

    result = DiscoveredFile.from_path(test_file, file_hash=mismatched_hash, project_path=tmp_path)

    assert result is not None
    assert result.file_hash == computed_hash
    mock_warning.assert_called_once_with(
        "Provided file_hash does not match computed hash for %s. Using computed hash.",
        test_file,
    )


@patch('codeweaver.core.discovery.logger.warning')
@patch('codeweaver.core.discovery.ExtCategory.from_file')
def test_from_path_matching_file_hash(mock_from_file, mock_warning, tmp_path: Path) -> None:
    """Test from_path does not issue a warning when provided file_hash matches computed hash."""
    real_ext = ExtCategory(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE)
    mock_from_file.return_value = real_ext

    test_file = tmp_path / "test.py"
    test_file.write_text("actual content")
    matching_hash = get_blake_hash(b"actual content")

    result = DiscoveredFile.from_path(test_file, file_hash=matching_hash, project_path=tmp_path)

    assert result is not None
    assert result.file_hash == matching_hash
    mock_warning.assert_not_called()


@patch('codeweaver.core.utils.filesystem.get_project_path')
@patch('codeweaver.core.discovery.ExtCategory.from_file')
def test_from_path_project_path_injected(mock_from_file, mock_get_project_path, tmp_path: Path) -> None:
    """Test from_path correctly handles the default INJECTED project_path."""
    real_ext = ExtCategory(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE)
    mock_from_file.return_value = real_ext

    # Mock get_project_path since it will be called when project_path is INJECTED
    mock_get_project_path.return_value = tmp_path

    test_file = tmp_path / "src" / "test.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("content")

    result = DiscoveredFile.from_path(test_file)

    assert result is not None
    assert result.project_path == tmp_path
    assert result.path == Path("src/test.py")


@patch('codeweaver.core.discovery.ExtCategory.from_file')
def test_from_path_project_path_explicit(mock_from_file, tmp_path: Path) -> None:
    """Test from_path correctly handles an explicitly provided project_path."""
    real_ext = ExtCategory(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE)
    mock_from_file.return_value = real_ext

    explicit_project_path = tmp_path / "explicit_project"
    explicit_project_path.mkdir()

    test_file = explicit_project_path / "src" / "test.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("content")

    result = DiscoveredFile.from_path(test_file, project_path=explicit_project_path)

    assert result is not None
    assert result.project_path == explicit_project_path
    assert result.path == Path("src/test.py")
