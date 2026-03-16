# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for core discovery logic."""

from pathlib import Path
from unittest.mock import patch

import pytest

from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.metadata import ExtCategory


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
