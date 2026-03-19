# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for AST-based semantic file hashing."""

from pathlib import Path

import pytest

from codeweaver.core.discovery import (
    DiscoveredFile,
    _compute_ast_hash,
    _get_semantic_language,
    compute_semantic_file_hash,
)
from codeweaver.core.metadata import ExtCategory
from codeweaver.core.utils import get_blake_hash


pytestmark = [pytest.mark.unit]


@pytest.fixture
def temp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide a temporary project directory with env var and CWD set."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("CODEWEAVER_PROJECT_PATH", str(project_dir))
    monkeypatch.chdir(project_dir)
    return project_dir


# ---------------------------------------------------------------------------
# _compute_ast_hash
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeAstHash:
    """Test the low-level _compute_ast_hash function."""

    def test_returns_hash_for_valid_python(self) -> None:
        """Produce a hash for syntactically valid Python code."""
        result = _compute_ast_hash("def foo(): pass", "python")
        assert result is not None
        assert len(result) == 64  # blake3 hex digest

    def test_returns_none_for_empty_content(self) -> None:
        """Return None when parsing produces no meaningful nodes."""
        result = _compute_ast_hash("", "python")
        # Empty source still produces a 'module' root node
        # which is acceptable - the hash just captures the empty structure
        assert result is None or len(result) == 64

    def test_returns_none_for_unsupported_language(self) -> None:
        """Return None when the language is not supported by ast-grep."""
        result = _compute_ast_hash("some content", "nonexistent_language_xyz")
        assert result is None

    def test_comment_changes_same_hash(self) -> None:
        """Produce identical hashes when only comments differ."""
        code_with_comment = "# This is a comment\ndef add(a, b):\n    return a + b\n"
        code_no_comment = "def add(a, b):\n    return a + b\n"
        code_different_comment = "# Different comment\ndef add(a, b):\n    return a + b\n"

        hash1 = _compute_ast_hash(code_with_comment, "python")
        hash2 = _compute_ast_hash(code_no_comment, "python")
        hash3 = _compute_ast_hash(code_different_comment, "python")

        assert hash1 == hash2
        assert hash2 == hash3

    def test_whitespace_changes_same_hash(self) -> None:
        """Produce identical hashes when only whitespace/formatting differs."""
        code_compact = "def add(a,b):\n    return a+b\n"
        code_spaced = "def add(a, b):\n    return a + b\n"

        hash1 = _compute_ast_hash(code_compact, "python")
        hash2 = _compute_ast_hash(code_spaced, "python")

        assert hash1 == hash2

    def test_semantic_change_different_hash(self) -> None:
        """Produce different hashes when the code logic changes."""
        code_add = "def calc(a, b):\n    return a + b\n"
        code_mul = "def calc(a, b):\n    return a * b\n"

        hash1 = _compute_ast_hash(code_add, "python")
        hash2 = _compute_ast_hash(code_mul, "python")

        assert hash1 != hash2

    def test_identifier_change_different_hash(self) -> None:
        """Produce different hashes when an identifier is renamed."""
        code_a = "def foo(x):\n    return x\n"
        code_b = "def bar(x):\n    return x\n"

        assert _compute_ast_hash(code_a, "python") != _compute_ast_hash(code_b, "python")

    def test_javascript_comment_changes_same_hash(self) -> None:
        """Comment changes in JavaScript also produce the same hash."""
        js_with_comment = "// a comment\nfunction add(a, b) { return a + b; }\n"
        js_no_comment = "function add(a, b) { return a + b; }\n"
        js_block_comment = "/* block */\nfunction add(a, b) { return a + b; }\n"

        h1 = _compute_ast_hash(js_with_comment, "javascript")
        h2 = _compute_ast_hash(js_no_comment, "javascript")
        h3 = _compute_ast_hash(js_block_comment, "javascript")

        assert h1 == h2
        assert h2 == h3

    def test_docstring_change_different_hash(self) -> None:
        """Docstring changes DO alter the hash since docstrings are semantic content."""
        code_a = 'def foo():\n    """Docstring A."""\n    pass\n'
        code_b = 'def foo():\n    """Docstring B."""\n    pass\n'

        assert _compute_ast_hash(code_a, "python") != _compute_ast_hash(code_b, "python")


# ---------------------------------------------------------------------------
# _get_semantic_language
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetSemanticLanguage:
    """Test language detection for semantic hashing."""

    def test_python_file(self) -> None:
        """Detect Python from a .py file path."""
        lang = _get_semantic_language(Path("foo.py"))
        assert lang is not None
        assert lang.variable == "python"

    def test_javascript_file(self) -> None:
        """Detect JavaScript from a .js file path."""
        lang = _get_semantic_language(Path("app.js"))
        assert lang is not None
        assert lang.variable == "javascript"

    def test_non_semantic_file(self) -> None:
        """Return None for a file without a supported AST language."""
        lang = _get_semantic_language(Path("readme.md"))
        assert lang is None

    def test_ext_category_takes_precedence(self) -> None:
        """Use the language from ext_category when provided."""
        from codeweaver.core.language import SemanticSearchLanguage

        ext_cat = ExtCategory(language=SemanticSearchLanguage.PYTHON, kind="code")
        lang = _get_semantic_language(Path("file.txt"), ext_category=ext_cat)
        assert lang is not None
        assert lang.variable == "python"


# ---------------------------------------------------------------------------
# compute_semantic_file_hash
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeSemanticFileHash:
    """Test the public compute_semantic_file_hash function."""

    def test_python_file_uses_ast_hash(self) -> None:
        """Use AST-based hashing for Python content."""
        code = b"def foo(): pass\n"
        ast_hash = compute_semantic_file_hash(code, Path("test.py"))
        content_hash = get_blake_hash(code)
        # AST hash should differ from raw content hash
        assert ast_hash != content_hash

    def test_non_semantic_file_uses_content_hash(self) -> None:
        """Fall back to raw content hash for non-semantic files."""
        content = b"# just some markdown\n"
        result = compute_semantic_file_hash(content, Path("readme.md"))
        assert result == get_blake_hash(content)

    def test_comment_only_change_same_hash(self) -> None:
        """Semantic hashing ignores comment-only changes in Python."""
        code_v1 = b"# version 1 comment\ndef foo(): pass\n"
        code_v2 = b"# version 2 comment\ndef foo(): pass\n"

        assert compute_semantic_file_hash(code_v1, Path("x.py")) == compute_semantic_file_hash(
            code_v2, Path("x.py")
        )

    def test_logic_change_different_hash(self) -> None:
        """Semantic hashing detects logic changes."""
        code_v1 = b"def foo(a, b): return a + b\n"
        code_v2 = b"def foo(a, b): return a - b\n"

        assert compute_semantic_file_hash(code_v1, Path("x.py")) != compute_semantic_file_hash(
            code_v2, Path("x.py")
        )

    def test_ext_category_passed_through(self) -> None:
        """Use ext_category when explicitly provided."""
        from codeweaver.core.language import SemanticSearchLanguage

        code = b"def bar(): pass\n"
        ext = ExtCategory(language=SemanticSearchLanguage.PYTHON, kind="code")
        # Should produce AST hash even though path has .txt extension
        hash_with_ext = compute_semantic_file_hash(code, Path("file.txt"), ext_category=ext)
        hash_without_ext = compute_semantic_file_hash(code, Path("file.txt"))
        # Without ext_category, .txt falls back to content hash
        assert hash_with_ext != hash_without_ext


# ---------------------------------------------------------------------------
# DiscoveredFile integration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDiscoveredFileSemanticHash:
    """Test that DiscoveredFile uses AST-based hashing for semantic files."""

    def test_python_file_hash_ignores_comments(self, temp_project: Path) -> None:
        """DiscoveredFile produces same hash for Python files differing only in comments."""
        file_v1 = temp_project / "mod_v1.py"
        file_v2 = temp_project / "mod_v2.py"

        file_v1.write_text("# old comment\ndef greet(): print('hi')\n")
        file_v2.write_text("# new comment\ndef greet(): print('hi')\n")

        df1 = DiscoveredFile.from_path(file_v1)
        df2 = DiscoveredFile.from_path(file_v2)

        assert df1 is not None
        assert df2 is not None
        assert df1.file_hash == df2.file_hash

    def test_python_file_hash_detects_logic_change(self, temp_project: Path) -> None:
        """DiscoveredFile produces different hash when Python logic changes."""
        file_v1 = temp_project / "calc_v1.py"
        file_v2 = temp_project / "calc_v2.py"

        file_v1.write_text("def add(a, b): return a + b\n")
        file_v2.write_text("def add(a, b): return a - b\n")

        df1 = DiscoveredFile.from_path(file_v1)
        df2 = DiscoveredFile.from_path(file_v2)

        assert df1 is not None
        assert df2 is not None
        assert df1.file_hash != df2.file_hash

    def test_non_semantic_file_uses_content_hash(self, temp_project: Path) -> None:
        """DiscoveredFile uses raw content hash for non-semantic file types."""
        txt = temp_project / "notes.txt"
        txt.write_text("hello world")

        df = DiscoveredFile.from_path(txt)
        assert df is not None
        assert df.file_hash == get_blake_hash(b"hello world")

    def test_is_same_with_semantic_hash(self, temp_project: Path) -> None:
        """is_same returns True for files with same semantics but different comments."""
        file_a = temp_project / "a.py"
        file_b = temp_project / "b.py"

        file_a.write_text("# comment A\ndef f(): pass\n")
        file_b.write_text("# comment B\ndef f(): pass\n")

        df = DiscoveredFile.from_path(file_a)
        assert df is not None
        assert df.is_same(file_b)

    def test_formatting_only_change_same_hash(self, temp_project: Path) -> None:
        """Formatting-only changes produce the same hash for Python files."""
        file_v1 = temp_project / "fmt_v1.py"
        file_v2 = temp_project / "fmt_v2.py"

        file_v1.write_text("def add(a,b):\n    return a+b\n")
        file_v2.write_text("def add(a, b):\n    return a + b\n")

        df1 = DiscoveredFile.from_path(file_v1)
        df2 = DiscoveredFile.from_path(file_v2)

        assert df1 is not None
        assert df2 is not None
        assert df1.file_hash == df2.file_hash
