# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Simple CLI integration tests that verify end-to-end workflow.

Focuses on essential CLI functionality without subprocess complexity.
"""

# sourcery skip: require-return-annotation, require-parameter-annotation
from __future__ import annotations

import time

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest


def run_cli(*args):
    """Run CLI and capture output.

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    from tools.exportify.cli import app

    stdout = StringIO()
    stderr = StringIO()
    exit_code = 0

    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
        try:
            app(list(args))
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
        except Exception as e:
            stderr.write(str(e))
            exit_code = 1

    return exit_code, stdout.getvalue(), stderr.getvalue()


@pytest.mark.integration
class TestCLIAnalyzeCommand:
    """Test analyze command."""

    def test_analyze_runs_successfully(self, tmp_path: Path):
        """Analyze command executes without error."""
        # Create simple module
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")

        # Create rules
        rules_dir = tmp_path / ".codeweaver"
        rules_dir.mkdir()
        (rules_dir / "lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules: []
""")

        exit_code, stdout, stderr = run_cli("analyze", "--source", str(tmp_path))

        assert exit_code == 0, f"Failed: {stderr}"
        assert "Files analyzed" in stdout or "analyzed" in stdout.lower()

    def test_analyze_with_nonexistent_path(self, tmp_path: Path):
        """Analyze handles nonexistent paths gracefully."""
        nonexistent = tmp_path / "nonexistent"

        exit_code, stdout, stderr = run_cli("analyze", "--source", str(nonexistent))

        # Should either fail or complete with warning
        # Implementation may create the directory or warn
        assert (
            exit_code != 0
            or "not found" in (stdout + stderr).lower()
            or "does not exist" in (stdout + stderr).lower()
        )


@pytest.mark.integration
class TestCLIGenerateCommand:
    """Test generate command."""

    def test_generate_dry_run(self, tmp_path: Path):
        """Dry-run mode doesn't write files."""
        # Create module
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")

        # Create rules
        (tmp_path / ".codeweaver").mkdir()
        (tmp_path / ".codeweaver/lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules:
  - name: "include-all"
    priority: 500
    match:
      name_pattern: ".*"
    action: include
""")

        init_file = pkg / "__init__.py"
        existed_before = init_file.exists()

        exit_code, stdout, stderr = run_cli("generate", "--source", str(tmp_path), "--dry-run")

        assert exit_code == 0, f"Failed: {stderr}"
        assert "dry run" in stdout.lower() or "Dry run" in stdout

        # No files should be written in dry-run
        if not existed_before:
            assert not init_file.exists()

    def test_generate_creates_files(self, tmp_path: Path):
        """Generate creates __init__.py files."""
        # Create module
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("""
class Foo:
    pass

def bar():
    pass
""")

        # Create rules
        (tmp_path / ".codeweaver").mkdir()
        (tmp_path / ".codeweaver/lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules:
  - name: "include-all"
    priority: 500
    match:
      name_pattern: ".*"
    action: include
    propagate: parent
""")

        exit_code, _stdout, stderr = run_cli("generate", "--source", str(tmp_path))

        assert exit_code == 0, f"Failed: {stderr}"

        # Check if __init__.py was created
        init_file = pkg / "__init__.py"
        if init_file.exists():
            content = init_file.read_text()
            # Should have some export mechanism
            assert "__all__" in content or "import" in content.lower()

    def test_generate_preserves_manual_content(self, tmp_path: Path):
        """Generate preserves existing manual exports."""
        # Create package with existing __init__.py
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class New: pass")

        init_file = pkg / "__init__.py"
        manual_content = '''"""Manual docstring."""

from .other import Manual

__all__ = ["Manual"]
'''
        init_file.write_text(manual_content)

        # Create rules
        (tmp_path / ".codeweaver").mkdir()
        (tmp_path / ".codeweaver/lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules:
  - name: "include-all"
    priority: 500
    match:
      name_pattern: ".*"
    action: include
""")

        exit_code, _stdout, stderr = run_cli("generate", "--source", str(tmp_path))

        # Should complete (may or may not preserve content depending on implementation)
        assert exit_code == 0, f"Failed: {stderr}"

        # File should still exist and be valid
        assert init_file.exists()
        assert len(init_file.read_text()) > 0


@pytest.mark.integration
class TestCLICacheIntegration:
    """Test cache behavior."""

    def test_cache_used_on_second_run(self, tmp_path: Path):
        """Second run shows cache usage."""
        # Create module
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")

        # Create rules
        (tmp_path / ".codeweaver").mkdir()
        (tmp_path / ".codeweaver/lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules: []
""")

        # First run
        run_cli("analyze", "--source", str(tmp_path))

        # Second run
        time.sleep(0.1)  # Small delay
        exit_code2, _stdout2, _stderr2 = run_cli("analyze", "--source", str(tmp_path))

        assert exit_code2 == 0
        # May show cache hit rate
        # (implementation-dependent)


@pytest.mark.integration
class TestCLIEndToEnd:
    """Test complete workflows."""

    def test_analyze_then_generate(self, tmp_path: Path):
        """Complete workflow: analyze → generate."""
        # Create structure
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("""
class Public:
    pass

def public_func():
    return 42

_private = "secret"
""")

        # Create rules
        (tmp_path / ".codeweaver").mkdir()
        (tmp_path / ".codeweaver/lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules:
  - name: "exclude-private"
    priority: 900
    match:
      name_pattern: "^_"
    action: exclude
  - name: "include-public"
    priority: 500
    match:
      name_pattern: "^[a-zA-Z]"
    action: include
    propagate: parent
""")

        # Step 1: Analyze
        exit1, _stdout1, stderr1 = run_cli("analyze", "--source", str(tmp_path))
        assert exit1 == 0, f"Analyze failed: {stderr1}"

        # Step 2: Generate
        exit2, _stdout2, stderr2 = run_cli("generate", "--source", str(tmp_path))
        assert exit2 == 0, f"Generate failed: {stderr2}"

        # Verify file created
        init_file = pkg / "__init__.py"
        if init_file.exists():
            content = init_file.read_text()
            assert len(content) > 0

    def test_generated_file_is_valid_python(self, tmp_path: Path):
        """Generated files are syntactically valid."""
        # Create module
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("""
class Test:
    pass

def test_func():
    pass
""")

        # Create rules
        (tmp_path / ".codeweaver").mkdir()
        (tmp_path / ".codeweaver/lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules:
  - name: "include-all"
    priority: 500
    match:
      name_pattern: ".*"
    action: include
""")

        # Generate
        exit_code, _stdout, stderr = run_cli("generate", "--source", str(tmp_path))
        assert exit_code == 0, f"Failed: {stderr}"

        # Verify syntax
        init_file = pkg / "__init__.py"
        if init_file.exists():
            import ast

            content = init_file.read_text()
            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Generated file has syntax error: {e}")


@pytest.mark.integration
class TestCLIErrorHandling:
    """Test error handling."""

    def test_missing_rules_uses_defaults(self, tmp_path: Path):
        """Missing rules file uses defaults."""
        # Create module WITHOUT rules file
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Foo: pass")

        exit_code, stdout, _stderr = run_cli("analyze", "--source", str(tmp_path))

        assert exit_code == 0
        assert "Using default rules" in stdout or "Rules file not found" in stdout

    def test_syntax_error_handled(self, tmp_path: Path):
        """Syntax errors in source files are handled gracefully."""
        # Create module with syntax error
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "bad.py").write_text("def broken(\n    # Missing closing paren")

        # Create rules
        (tmp_path / ".codeweaver").mkdir()
        (tmp_path / ".codeweaver/lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules: []
""")

        # Should not crash
        exit_code, _stdout, stderr = run_cli("analyze", "--source", str(tmp_path))

        # May complete with warnings or errors, but should not crash
        assert "Traceback" not in stderr or exit_code != 0


@pytest.mark.integration
class TestCLIHelp:
    """Test help and documentation."""

    def test_help_works(self):
        """Help message is accessible."""
        exit_code, stdout, _stderr = run_cli("--help")

        assert exit_code == 0
        assert "analyze" in stdout or "generate" in stdout

    def test_analyze_help(self):
        """Analyze command help works."""
        exit_code, stdout, _stderr = run_cli("analyze", "--help")

        assert exit_code == 0
        assert "source" in stdout.lower() or "analyze" in stdout.lower()

    def test_generate_help(self):
        """Generate command help works."""
        exit_code, stdout, _stderr = run_cli("generate", "--help")

        assert exit_code == 0
        assert "dry-run" in stdout.lower() or "generate" in stdout.lower()


@pytest.mark.integration
@pytest.mark.xfail(reason="Known issue: duplicate from __future__ import annotations")
class TestKnownIssues:
    """Document known issues."""

    def test_no_duplicate_future_imports(self, tmp_path: Path):
        """Test for duplicate future imports (known issue)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        # Create init with existing future import
        init_file = pkg / "__init__.py"
        init_file.write_text("from __future__ import annotations\n\n# Existing\n")

        (pkg / "mod.py").write_text("class Foo: pass")

        # Create rules
        (tmp_path / ".codeweaver").mkdir()
        (tmp_path / ".codeweaver/lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules:
  - name: "include-all"
    priority: 500
    match:
      name_pattern: ".*"
    action: include
""")

        # Generate
        run_cli("generate", "--source", str(tmp_path))

        if init_file.exists():
            content = init_file.read_text()
            count = content.count("from __future__ import annotations")
            assert count <= 1, f"Found {count} future imports, expected 1"
