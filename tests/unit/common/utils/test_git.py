# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Comprehensive tests for git utility functions.

Tests cover:
- Happy path: Normal git repository operations
- Error paths: Git not installed, outside repositories, etc.
- Edge cases: Worktrees, submodules, broken symlinks, complex branch names
"""

from __future__ import annotations

import shutil
import subprocess

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from codeweaver.common.utils.git import (
    MISSING,
    Missing,
    _get_branch_from_origin,
    _get_git_dir,
    _root_path_checks_out,
    _walk_up_to_git_root,
    get_git_branch,
    get_git_revision,
    get_project_path,
    has_git,
    in_codeweaver_clone,
    is_git_dir,
    set_relative_path,
    try_git_rev_parse,
)


if TYPE_CHECKING:
    from pytest_mock import MockerFixture


# ===========================================================================
# *                            Fixtures
# ===========================================================================


@pytest.fixture
def mock_git_exists(mocker: MockerFixture) -> MagicMock:
    """Mock git as installed and available."""
    mock = mocker.patch("shutil.which", return_value="/usr/bin/git")
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout="git version 2.40.0\n"),
    )
    return mock


@pytest.fixture
def mock_no_git(mocker: MockerFixture) -> MagicMock:
    """Mock git as not installed."""
    return mocker.patch("shutil.which", return_value=None)


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    return repo_dir


@pytest.fixture
def temp_git_worktree(tmp_path: Path) -> Path:
    """Create a temporary git worktree (where .git is a file, not directory)."""
    worktree_dir = tmp_path / "test_worktree"
    worktree_dir.mkdir()
    # In a worktree, .git is a file pointing to the actual git directory
    (worktree_dir / ".git").write_text("gitdir: /path/to/main/.git/worktrees/test")
    return worktree_dir


@pytest.fixture
def temp_non_git_dir(tmp_path: Path) -> Path:
    """Create a temporary non-git directory."""
    non_git_dir = tmp_path / "not_a_repo"
    non_git_dir.mkdir()
    return non_git_dir


# ===========================================================================
# *                            has_git() Tests
# ===========================================================================


class TestHasGit:
    """Tests for has_git() function."""

    def test_git_installed_and_working(self, mocker: MockerFixture) -> None:
        """Test has_git returns True when git is installed and functional."""
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(returncode=0),
        )
        assert has_git() is True

    def test_git_not_installed(self, mock_no_git: MagicMock) -> None:
        """Test has_git returns False when git is not installed."""
        assert has_git() is False

    def test_git_command_fails(self, mocker: MockerFixture) -> None:
        """Test has_git returns False when git command fails."""
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(returncode=1),
        )
        assert has_git() is False

    def test_git_exists_but_not_executable(self, mocker: MockerFixture) -> None:
        """Test has_git returns False when git exists but isn't executable."""
        # shutil.which returns None for non-executable files
        mocker.patch("shutil.which", return_value=None)
        assert has_git() is False


# ===========================================================================
# *                            is_git_dir() Tests
# ===========================================================================


class TestIsGitDir:
    """Tests for is_git_dir() function."""

    def test_normal_git_repository(self, temp_git_repo: Path) -> None:
        """Test is_git_dir returns True for normal git repository."""
        assert is_git_dir(temp_git_repo) is True

    def test_git_worktree(self, temp_git_worktree: Path) -> None:
        """Test is_git_dir returns True for git worktree (.git is file)."""
        assert is_git_dir(temp_git_worktree) is True

    def test_non_git_directory(self, temp_non_git_dir: Path) -> None:
        """Test is_git_dir returns False for non-git directory."""
        assert is_git_dir(temp_non_git_dir) is False

    def test_no_dot_git(self, tmp_path: Path) -> None:
        """Test is_git_dir returns False when .git doesn't exist."""
        no_git_dir = tmp_path / "no_git"
        no_git_dir.mkdir()
        assert is_git_dir(no_git_dir) is False

    def test_broken_symlink(self, tmp_path: Path) -> None:
        """Test is_git_dir handles broken symlink gracefully."""
        broken_dir = tmp_path / "broken_symlink_dir"
        broken_dir.mkdir()
        # Create a broken symlink for .git
        git_link = broken_dir / ".git"
        git_link.symlink_to(tmp_path / "nonexistent")

        # Should return False for broken symlink
        assert is_git_dir(broken_dir) is False

    def test_defaults_to_cwd(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test is_git_dir uses current directory when no path provided."""
        mocker.patch("pathlib.Path.cwd", return_value=temp_git_repo)
        assert is_git_dir() is True


# ===========================================================================
# *                            try_git_rev_parse() Tests
# ===========================================================================


class TestTryGitRevParse:
    """Tests for try_git_rev_parse() function."""

    def test_no_git_installed(self, mock_no_git: MagicMock) -> None:
        """Test returns None when git is not installed."""
        assert try_git_rev_parse() is None

    def test_in_superproject(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Test returns superproject path when in git submodule."""
        superproject = tmp_path / "superproject"
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(
                returncode=0,
                stdout=str(superproject) + "\n",
            ),
        )
        result = try_git_rev_parse()
        assert result == superproject

    def test_normal_repository(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Test returns toplevel path for normal repository."""
        repo = tmp_path / "repo"
        mocker.patch("shutil.which", return_value="/usr/bin/git")

        def mock_run(cmd: list[str], **kwargs):
            if "--show-superproject-working-tree" in cmd:
                return MagicMock(returncode=0, stdout="")
            return MagicMock(returncode=0, stdout=str(repo) + "\n")

        mocker.patch("subprocess.run", side_effect=mock_run)
        result = try_git_rev_parse()
        assert result == repo

    def test_not_in_git_repo(self, mocker: MockerFixture) -> None:
        """Test returns None when not in a git repository."""
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(returncode=128, stdout=""),
        )
        result = try_git_rev_parse()
        assert result is None


# ===========================================================================
# *                            _walk_up_to_git_root() Tests
# ===========================================================================


class TestWalkUpToGitRoot:
    """Tests for _walk_up_to_git_root() function."""

    def test_finds_git_root(self, temp_git_repo: Path) -> None:
        """Test walks up to find git root directory."""
        subdir = temp_git_repo / "nested" / "deep" / "path"
        subdir.mkdir(parents=True)

        result = _walk_up_to_git_root(subdir)
        assert result == temp_git_repo

    def test_file_path_uses_parent(self, temp_git_repo: Path) -> None:
        """Test handles file paths by using parent directory."""
        test_file = temp_git_repo / "test.txt"
        test_file.write_text("test")

        result = _walk_up_to_git_root(test_file)
        assert result == temp_git_repo

    def test_raises_when_no_git_found(self, temp_non_git_dir: Path) -> None:
        """Test raises FileNotFoundError when no git directory found."""
        with pytest.raises(FileNotFoundError, match=r"No \.git directory found"):
            _walk_up_to_git_root(temp_non_git_dir)

    def test_uses_cwd_as_default(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test uses current working directory when no path provided."""
        mocker.patch("pathlib.Path.cwd", return_value=temp_git_repo)
        result = _walk_up_to_git_root()
        assert result == temp_git_repo


# ===========================================================================
# *                            _root_path_checks_out() Tests
# ===========================================================================


class TestRootPathChecksOut:
    """Tests for _root_path_checks_out() function."""

    def test_valid_git_directory(self, temp_git_repo: Path) -> None:
        """Test returns True for valid git repository directory."""
        assert _root_path_checks_out(temp_git_repo) is True

    def test_non_directory(self, tmp_path: Path) -> None:
        """Test returns False for non-directory path."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("test")
        assert _root_path_checks_out(test_file) is False

    def test_directory_without_git(self, temp_non_git_dir: Path) -> None:
        """Test returns False for directory without .git."""
        assert _root_path_checks_out(temp_non_git_dir) is False


# ===========================================================================
# *                            get_project_path() Tests
# ===========================================================================


class TestGetProjectPath:
    """Tests for get_project_path() function."""

    def test_with_valid_root_path(self, temp_git_repo: Path) -> None:
        """Test returns provided root path when it's valid."""
        result = get_project_path(temp_git_repo)
        assert result == temp_git_repo

    def test_uses_git_rev_parse(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test uses git rev-parse when no root_path provided."""
        mocker.patch(
            "codeweaver.common.utils.git.try_git_rev_parse",
            return_value=temp_git_repo,
        )
        result = get_project_path()
        assert result == temp_git_repo

    def test_walks_up_when_git_rev_parse_fails(
        self, mocker: MockerFixture, temp_git_repo: Path
    ) -> None:
        """Test walks up directory tree when git rev-parse fails."""
        mocker.patch("codeweaver.common.utils.git.try_git_rev_parse", return_value=None)
        subdir = temp_git_repo / "nested"
        subdir.mkdir()
        mocker.patch("pathlib.Path.cwd", return_value=subdir)

        result = get_project_path()
        assert result == temp_git_repo

    def test_invalid_root_path_walks_up(
        self, mocker: MockerFixture, temp_git_repo: Path, temp_non_git_dir: Path
    ) -> None:
        """Test walks up when provided root_path is invalid."""
        # Create nested structure: git_repo/non_git/current
        non_git_nested = temp_git_repo / "non_git"
        non_git_nested.mkdir()

        result = get_project_path(non_git_nested)
        assert result == temp_git_repo


# ===========================================================================
# *                            set_relative_path() Tests
# ===========================================================================


class TestSetRelativePath:
    """Tests for set_relative_path() function."""

    def test_none_returns_none(self) -> None:
        """Test returns None when path is None."""
        assert set_relative_path(None) is None

    def test_relative_path_unchanged(self) -> None:
        """Test returns relative path unchanged."""
        rel_path = Path("src/module/file.py")
        result = set_relative_path(rel_path)
        assert result == rel_path

    def test_absolute_path_inside_project(
        self, mocker: MockerFixture, temp_git_repo: Path
    ) -> None:
        """Test makes absolute path relative when inside project."""
        mocker.patch(
            "codeweaver.common.utils.git.get_project_path",
            return_value=temp_git_repo,
        )

        abs_path = temp_git_repo / "src" / "module" / "file.py"
        result = set_relative_path(abs_path)
        assert result == Path("src/module/file.py")

    def test_absolute_path_outside_project(
        self, mocker: MockerFixture, temp_git_repo: Path, tmp_path: Path
    ) -> None:
        """Test returns absolute path unchanged when outside project."""
        mocker.patch(
            "codeweaver.common.utils.git.get_project_path",
            return_value=temp_git_repo,
        )

        outside_path = tmp_path / "external" / "file.py"
        result = set_relative_path(outside_path)
        assert result == outside_path

    def test_not_in_git_repo(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Test handles gracefully when not in git repository."""
        mocker.patch(
            "codeweaver.common.utils.git.get_project_path",
            side_effect=FileNotFoundError,
        )

        abs_path = tmp_path / "file.py"
        result = set_relative_path(abs_path)
        assert result == abs_path

    def test_string_path_conversion(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test handles string paths correctly."""
        mocker.patch(
            "codeweaver.common.utils.git.get_project_path",
            return_value=temp_git_repo,
        )

        str_path = str(temp_git_repo / "src" / "file.py")
        result = set_relative_path(str_path)
        assert result == Path("src/file.py")


# ===========================================================================
# *                            _get_git_dir() Tests
# ===========================================================================


class TestGetGitDir:
    """Tests for _get_git_dir() function."""

    def test_valid_git_directory(self, temp_git_repo: Path) -> None:
        """Test returns directory when it's a valid git repository."""
        result = _get_git_dir(temp_git_repo)
        assert result == temp_git_repo

    def test_non_git_directory_finds_project(
        self, mocker: MockerFixture, temp_git_repo: Path
    ) -> None:
        """Test finds project path when directory is not git repository."""
        mocker.patch(
            "codeweaver.common.utils.git.get_project_path",
            return_value=temp_git_repo,
        )

        non_git = temp_git_repo.parent / "other"
        non_git.mkdir()

        result = _get_git_dir(non_git)
        assert result == temp_git_repo

    def test_returns_missing_when_not_found(
        self, mocker: MockerFixture, temp_non_git_dir: Path
    ) -> None:
        """Test returns MISSING when git directory not found."""
        mocker.patch(
            "codeweaver.common.utils.git.get_project_path",
            side_effect=FileNotFoundError,
        )

        result = _get_git_dir(temp_non_git_dir)
        assert result is MISSING
        assert isinstance(result, Missing)


# ===========================================================================
# *                            get_git_revision() Tests
# ===========================================================================


class TestGetGitRevision:
    """Tests for get_git_revision() function."""

    def test_returns_short_sha(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test returns short SHA-1 hash of HEAD."""
        mocker.patch("codeweaver.common.utils.git.has_git", return_value=True)
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(
                returncode=0,
                stdout="abc123f\n",
            ),
        )

        result = get_git_revision(temp_git_repo)
        assert result == "abc123f"

    def test_returns_missing_when_no_git(
        self, mocker: MockerFixture, temp_git_repo: Path
    ) -> None:
        """Test returns MISSING when git is not installed."""
        mocker.patch("codeweaver.common.utils.git.has_git", return_value=False)

        result = get_git_revision(temp_git_repo)
        assert result is MISSING

    def test_returns_missing_for_non_git_dir(
        self, mocker: MockerFixture, temp_non_git_dir: Path
    ) -> None:
        """Test returns MISSING for non-git directory."""
        mocker.patch(
            "codeweaver.common.utils.git.get_project_path",
            side_effect=FileNotFoundError,
        )

        result = get_git_revision(temp_non_git_dir)
        assert result is MISSING

    def test_git_command_fails(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test handles git command failure gracefully."""
        mocker.patch("codeweaver.common.utils.git.has_git", return_value=True)
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        )

        result = get_git_revision(temp_git_repo)
        assert result is MISSING


# ===========================================================================
# *                            _get_branch_from_origin() Tests
# ===========================================================================


class TestGetBranchFromOrigin:
    """Tests for _get_branch_from_origin() function."""

    def test_simple_branch_name(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test extracts simple branch name from origin/HEAD."""
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(
                returncode=0,
                stdout="origin/main\n",
            ),
        )

        result = _get_branch_from_origin(temp_git_repo)
        assert result == "main"

    def test_complex_branch_name(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test handles branch names with slashes (e.g., feature/my-feature)."""
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(
                returncode=0,
                stdout="origin/feature/my-feature\n",
            ),
        )

        result = _get_branch_from_origin(temp_git_repo)
        # Should preserve full branch name after removing "origin/" prefix
        assert result == "feature/my-feature"

    def test_no_git_installed(self, mock_no_git: MagicMock, temp_git_repo: Path) -> None:
        """Test returns MISSING when git not installed."""
        result = _get_branch_from_origin(temp_git_repo)
        assert result is MISSING

    def test_git_command_fails(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test returns MISSING when git command fails."""
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        )

        result = _get_branch_from_origin(temp_git_repo)
        assert result is MISSING


# ===========================================================================
# *                            get_git_branch() Tests
# ===========================================================================


class TestGetGitBranch:
    """Tests for get_git_branch() function."""

    def test_normal_branch(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test returns current branch name."""
        mocker.patch("codeweaver.common.utils.git.has_git", return_value=True)
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(
                returncode=0,
                stdout="feature-branch\n",
            ),
        )

        result = get_git_branch(temp_git_repo)
        assert result == "feature-branch"

    def test_detached_head_with_origin(
        self, mocker: MockerFixture, temp_git_repo: Path
    ) -> None:
        """Test falls back to origin branch when HEAD is detached."""
        mocker.patch("codeweaver.common.utils.git.has_git", return_value=True)
        mocker.patch("shutil.which", return_value="/usr/bin/git")

        def mock_run(cmd: list[str], **kwargs):
            if "--abbrev-ref" in cmd and "HEAD" in cmd:
                return MagicMock(returncode=0, stdout="HEAD\n")
            if "origin/HEAD" in cmd:
                return MagicMock(returncode=0, stdout="origin/main\n")
            return MagicMock(returncode=1)

        mocker.patch("subprocess.run", side_effect=mock_run)

        result = get_git_branch(temp_git_repo)
        assert result == "main"

    def test_detached_head_no_origin(
        self, mocker: MockerFixture, temp_git_repo: Path
    ) -> None:
        """Test returns 'detached' when HEAD is detached and no origin."""
        mocker.patch("codeweaver.common.utils.git.has_git", return_value=True)
        mocker.patch("shutil.which", return_value="/usr/bin/git")

        # Mock _get_branch_from_origin to return MISSING
        mocker.patch(
            "codeweaver.common.utils.git._get_branch_from_origin",
            return_value=MISSING,
        )

        def mock_run(cmd: list[str], **kwargs):
            if "--abbrev-ref" in cmd and "HEAD" in cmd:
                return MagicMock(returncode=0, stdout="HEAD\n")
            return MagicMock(returncode=1)

        mocker.patch("subprocess.run", side_effect=mock_run)

        result = get_git_branch(temp_git_repo)
        assert result == "detached"

    def test_no_git_installed(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test returns 'detached' when git not installed."""
        mocker.patch("codeweaver.common.utils.git.has_git", return_value=False)

        result = get_git_branch(temp_git_repo)
        assert result == "detached"

    def test_not_in_git_repo(self, mocker: MockerFixture, temp_non_git_dir: Path) -> None:
        """Test returns 'detached' when not in git repository."""
        mocker.patch("codeweaver.common.utils.git.has_git", return_value=True)
        mocker.patch(
            "codeweaver.common.utils.git.get_project_path",
            side_effect=FileNotFoundError,
        )

        result = get_git_branch(temp_non_git_dir)
        assert result == "detached"

    def test_git_command_fails(self, mocker: MockerFixture, temp_git_repo: Path) -> None:
        """Test returns 'detached' when git command fails."""
        mocker.patch("codeweaver.common.utils.git.has_git", return_value=True)
        mocker.patch("shutil.which", return_value="/usr/bin/git")
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        )

        result = get_git_branch(temp_git_repo)
        assert result == "detached"


# ===========================================================================
# *                            in_codeweaver_clone() Tests
# ===========================================================================


class TestInCodeweaverClone:
    """Tests for in_codeweaver_clone() function."""

    def test_path_contains_codeweaver(self, tmp_path: Path) -> None:
        """Test returns True when path contains 'codeweaver'."""
        path = tmp_path / "codeweaver-mcp"
        assert in_codeweaver_clone(path) is True

    def test_path_contains_code_weaver(self, tmp_path: Path) -> None:
        """Test returns True when path contains 'code-weaver'."""
        path = tmp_path / "code-weaver-project"
        assert in_codeweaver_clone(path) is True

    def test_case_insensitive(self, tmp_path: Path) -> None:
        """Test matching is case-insensitive."""
        path = tmp_path / "CodeWeaver-MCP"
        assert in_codeweaver_clone(path) is True

    def test_git_root_contains_codeweaver(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test checks git root directory name."""
        mocker.patch(
            "codeweaver.common.utils.git.try_git_rev_parse",
            return_value=tmp_path / "codeweaver",
        )

        path = tmp_path / "other"
        assert in_codeweaver_clone(path) is True

    def test_unrelated_repository(self, mocker: MockerFixture) -> None:
        """Test returns False for non-codeweaver paths."""
        # Use a path that definitely doesn't contain 'codeweaver' or 'code-weaver'
        other_repo = Path("/home/user/my-project")

        mocker.patch(
            "codeweaver.common.utils.git.try_git_rev_parse",
            return_value=other_repo,
        )

        assert in_codeweaver_clone(other_repo) is False


# ===========================================================================
# *                            Integration Tests
# ===========================================================================


class TestGitUtilsIntegration:
    """Integration tests for git utilities with real scenarios."""

    @pytest.mark.skipif(not shutil.which("git"), reason="Git not installed")
    def test_real_git_repo_workflow(self, tmp_path: Path) -> None:
        """Test complete workflow in a real git repository."""
        # Create real git repo
        repo = tmp_path / "test_repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # Create and commit a file
        test_file = repo / "test.txt"
        test_file.write_text("test content")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # Test functions with real repo
        assert is_git_dir(repo) is True
        assert get_project_path(repo) == repo

        revision = get_git_revision(repo)
        assert revision is not MISSING
        assert isinstance(revision, str)
        assert len(revision) > 0

        # Note: Default branch might be 'master' or 'main' depending on git config
        branch = get_git_branch(repo)
        assert branch in {"master", "main"}

    def test_nested_directory_navigation(self, temp_git_repo: Path) -> None:
        """Test navigating from deeply nested directory to git root."""
        deep_path = temp_git_repo / "a" / "b" / "c" / "d" / "e"
        deep_path.mkdir(parents=True)

        result = _walk_up_to_git_root(deep_path)
        assert result == temp_git_repo

    def test_worktree_detection(self, temp_git_worktree: Path) -> None:
        """Test proper detection of git worktrees."""
        assert is_git_dir(temp_git_worktree) is True
