# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for file discovery service."""

from tools.exportify.discovery import FileDiscovery


class TestFileDiscovery:
    """Test suite for file discovery service."""

    def test_discovers_all_py_files(self, tmp_path) -> None:
        """Should find all .py files in tree."""
        # Create test structure
        (tmp_path / "a.py").touch()
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "b.py").touch()
        (tmp_path / "subdir" / "nested").mkdir()
        (tmp_path / "subdir" / "nested" / "c.py").touch()

        discovery = FileDiscovery(respect_gitignore=False)
        files = discovery.discover_python_files(tmp_path)

        assert len(files) == 3
        assert all(f.suffix == ".py" for f in files)

    def test_excludes_pycache(self, tmp_path) -> None:
        """Should exclude __pycache__ directories."""
        (tmp_path / "a.py").touch()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "a.cpython-39.pyc").touch()

        discovery = FileDiscovery(respect_gitignore=False)
        files = discovery.discover_python_files(tmp_path)

        assert len(files) == 1
        assert "__pycache__" not in str(files[0])

    def test_respects_gitignore(self, tmp_path) -> None:
        """Should respect .gitignore patterns."""
        (tmp_path / ".gitignore").write_text("test_*.py\n")
        (tmp_path / "main.py").touch()
        (tmp_path / "test_main.py").touch()

        discovery = FileDiscovery(respect_gitignore=True)
        files = discovery.discover_python_files(tmp_path)

        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_include_patterns(self, tmp_path) -> None:
        """Should filter by include patterns."""
        (tmp_path / "test_a.py").touch()
        (tmp_path / "test_b.py").touch()
        (tmp_path / "main.py").touch()

        discovery = FileDiscovery(respect_gitignore=False)
        files = discovery.discover_python_files(tmp_path, include_patterns=["test_*.py"])

        assert len(files) == 2
        assert all("test_" in f.name for f in files)

    def test_exclude_patterns(self, tmp_path) -> None:
        """Should filter by exclude patterns."""
        (tmp_path / "test_a.py").touch()
        (tmp_path / "test_b.py").touch()
        (tmp_path / "main.py").touch()

        discovery = FileDiscovery(respect_gitignore=False)
        files = discovery.discover_python_files(tmp_path, exclude_patterns=["test_*.py"])

        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_empty_directory(self, tmp_path) -> None:
        """Should return empty list for empty directory."""
        discovery = FileDiscovery(respect_gitignore=False)
        files = discovery.discover_python_files(tmp_path)

        assert files == []

    def test_nested_structure(self, tmp_path) -> None:
        """Should handle deeply nested structures."""
        deep = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        (deep / "file.py").touch()

        discovery = FileDiscovery(respect_gitignore=False)
        files = discovery.discover_python_files(tmp_path)

        assert len(files) == 1
        assert files[0].name == "file.py"

    def test_returns_sorted_list(self, tmp_path) -> None:
        """Should return sorted list of files."""
        (tmp_path / "z.py").touch()
        (tmp_path / "a.py").touch()
        (tmp_path / "m.py").touch()

        discovery = FileDiscovery(respect_gitignore=False)
        files = discovery.discover_python_files(tmp_path)

        file_names = [f.name for f in files]
        assert file_names == sorted(file_names)

    def test_gitignore_with_comments(self, tmp_path) -> None:
        """Should ignore comments in .gitignore."""
        (tmp_path / ".gitignore").write_text("# Comment\ntest.py\n# Another comment\n")
        (tmp_path / "test.py").touch()
        (tmp_path / "main.py").touch()

        discovery = FileDiscovery(respect_gitignore=True)
        files = discovery.discover_python_files(tmp_path)

        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_no_gitignore_file(self, tmp_path) -> None:
        """Should work when .gitignore doesn't exist."""
        (tmp_path / "a.py").touch()

        discovery = FileDiscovery(respect_gitignore=True)
        files = discovery.discover_python_files(tmp_path)

        assert len(files) == 1
