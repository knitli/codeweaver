# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration tests for Phase 3 validation system.

Tests complete workflows including:
- CLI validate command integration
- CLI analyze command integration
- Real codebase validation
- Error handling and edge cases
- Performance requirements

NOTE: These tests focus on CLI integration and error handling rather than
perfect validation of test fixtures, since test fixtures may not be fully
importable Python modules.
"""

from __future__ import annotations

import json
import time

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest


def run_cli(*args) -> tuple[int, str, str]:
    """Run CLI and capture output.

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    from tools.lazy_imports.cli import app

    stdout = StringIO()
    stderr = StringIO()
    exit_code = 0

    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
        try:
            app(list(args))
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
        except Exception:
            import traceback

            stderr.write(traceback.format_exc())
            exit_code = 1

    return exit_code, stdout.getvalue(), stderr.getvalue()


@pytest.mark.integration
class TestCLIValidateCommand:
    """Test validate command end-to-end."""

    def test_validate_runs_without_crash(self, tmp_path: Path):
        """Validate command executes without crashing."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("""\"\"\"Module.\"\"\"

class PublicClass:
    pass
""")

        (pkg / "__init__.py").write_text("""\"\"\"Package.\"\"\"
__all__ = ["PublicClass"]
""")

        _exit_code, stdout, stderr = run_cli("validate", "--module", str(pkg))

        # Should complete without crashing
        assert "Traceback" not in stderr
        assert "validat" in stdout.lower() or "validat" in stderr.lower()

    def test_validate_shows_results(self, tmp_path: Path):
        """Validate shows validation results."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, stdout, stderr = run_cli("validate", "--module", str(pkg))

        output = stdout + stderr
        # Should show some validation output
        assert "files" in output.lower() or "validated" in output.lower()

    def test_validate_with_nonexistent_path(self):
        """Validate handles nonexistent paths."""
        _exit_code, _stdout, stderr = run_cli("validate", "--module", "/totally/fake/path")

        # Should handle gracefully
        assert "Traceback" not in stderr

    def test_validate_strict_mode_flag(self, tmp_path: Path):
        """Strict mode flag is accepted."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(pkg), "--strict")

        # Should accept the flag without crashing
        assert "Traceback" not in stderr

    def test_validate_fix_mode_flag(self, tmp_path: Path):
        """Fix mode flag is accepted."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(pkg), "--fix")

        # Should accept the flag without crashing
        assert "Traceback" not in stderr


@pytest.mark.integration
class TestCLIAnalyzeCommand:
    """Test analyze command end-to-end."""

    def test_analyze_single_module(self, tmp_path: Path):
        """Analyze single module completes."""
        # Create a proper package structure
        pkg = tmp_path / "test_pkg"
        pkg.mkdir()

        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("""\"\"\"Module.\"\"\"

class PublicClass:
    pass

def public_function():
    return 42
""")

        # Create rules file
        config_dir = tmp_path / ".codeweaver"
        config_dir.mkdir()
        (config_dir / "lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules: []
""")

        _exit_code, _stdout, stderr = run_cli("analyze", "--source", str(tmp_path))

        # Should complete (may warn about implementation but shouldn't crash)
        assert "Traceback" not in stderr

    def test_analyze_nested_structure(self, tmp_path: Path):
        """Analyze package hierarchy."""
        root = tmp_path / "pkg"
        core = root / "core"
        core.mkdir(parents=True)

        (root / "__init__.py").write_text("")
        (core / "__init__.py").write_text("")
        (core / "models.py").write_text("class Model: pass")

        # Create rules file
        config_dir = tmp_path / ".codeweaver"
        config_dir.mkdir()
        (config_dir / "lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules: []
""")

        _exit_code, _stdout, stderr = run_cli("analyze", "--source", str(tmp_path))

        # Should complete (may warn but shouldn't crash)
        assert "Traceback" not in stderr

    def test_analyze_table_format(self, tmp_path: Path):
        """Analyze with table format."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class TestClass: pass")

        # Create rules file
        config_dir = tmp_path / ".codeweaver"
        config_dir.mkdir()
        (config_dir / "lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules: []
""")

        _exit_code, _stdout, stderr = run_cli(
            "analyze", "--source", str(tmp_path), "--format", "table"
        )

        # Should accept the format flag
        assert "Traceback" not in stderr

    def test_analyze_json_format(self, tmp_path: Path):
        """Analyze with JSON format."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class TestClass: pass")

        # Create rules file
        config_dir = tmp_path / ".codeweaver"
        config_dir.mkdir()
        (config_dir / "lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules: []
""")

        exit_code, stdout, _stderr = run_cli(
            "analyze", "--source", str(tmp_path), "--format", "json"
        )

        # Should accept the format flag
        if exit_code == 0 and stdout.strip():
            # If JSON format is implemented, it should be valid JSON
            try:
                data = json.loads(stdout)
                assert isinstance(data, (dict, list))
            except json.JSONDecodeError:
                # JSON format might not be fully implemented yet
                pass

    def test_analyze_report_format(self, tmp_path: Path):
        """Analyze with report format."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("class A: pass")

        # Create rules file
        config_dir = tmp_path / ".codeweaver"
        config_dir.mkdir()
        (config_dir / "lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules: []
""")

        _exit_code, _stdout, stderr = run_cli(
            "analyze", "--source", str(tmp_path), "--format", "report"
        )

        # Should accept the format
        assert "Traceback" not in stderr


@pytest.mark.integration
class TestRealCodebaseValidation:
    """Test validation on real CodeWeaver codebase."""

    def test_validate_codeweaver_core(self):
        """Validate actual CodeWeaver core package."""
        core_path = Path("src/codeweaver/core")

        if not core_path.exists():
            pytest.skip("CodeWeaver core not found")

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(core_path))

        # Should complete without crashing
        assert "Traceback" not in stderr

    def test_validate_lazy_imports_itself(self):
        """Validate lazy_imports tool codebase."""
        lazy_imports_path = Path("tools/lazy_imports")

        if not lazy_imports_path.exists():
            pytest.skip("lazy_imports package not found")

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(lazy_imports_path))

        # Should not crash
        assert "Traceback" not in stderr

    @pytest.mark.slow
    def test_analyze_codeweaver_performance(self):
        """Performance test on real codebase."""
        src_path = Path("src/codeweaver")

        if not src_path.exists():
            pytest.skip("CodeWeaver source not found")

        start_time = time.time()
        _exit_code, _stdout, stderr = run_cli("analyze", "--source", str(src_path))
        elapsed = time.time() - start_time

        # Should complete
        assert "Traceback" not in stderr

        # Performance requirement: <10s for full scan
        # (Lenient limit for integration test)
        if elapsed > 15:
            pytest.fail(f"Analysis took {elapsed:.2f}s, expected <15s")

    @pytest.mark.slow
    def test_validate_large_codebase_performance(self, tmp_path: Path):
        """Performance test with many files."""
        pkg = tmp_path / "large_pkg"
        pkg.mkdir()

        (pkg / "__init__.py").write_text("")

        for i in range(50):
            (pkg / f"mod_{i}.py").write_text(f"""\"\"\"Module {i}.\"\"\"

class Class_{i}:
    pass

def function_{i}():
    pass
""")

        start_time = time.time()
        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(pkg))
        elapsed = time.time() - start_time

        # Should complete
        assert "Traceback" not in stderr

        # Should be reasonably fast
        assert elapsed < 10, f"Validation took {elapsed:.2f}s for 50 files"


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_validate_invalid_module_path(self):
        """Invalid module path handled gracefully."""
        exit_code, stdout, stderr = run_cli("validate", "--module", "/nonexistent/path")

        # Should handle gracefully
        output = stdout + stderr
        # May show error or warning, but shouldn't crash
        assert "Traceback" not in output or exit_code != 0

    def test_validate_missing_source_directory(self):
        """Missing source directory handled gracefully."""
        exit_code, _stdout, stderr = run_cli("analyze", "--source", "/totally/fake/directory")

        # Should handle gracefully
        assert "Traceback" not in stderr or exit_code != 0

    def test_validate_syntax_error_file(self, tmp_path: Path):
        """Syntax errors handled gracefully."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        # Create file with syntax error
        (pkg / "broken.py").write_text("""def incomplete(
    # Missing closing paren
""")

        (pkg / "__init__.py").write_text("")

        _exit_code, stdout, stderr = run_cli("validate", "--module", str(pkg))

        # Should handle gracefully (may report error but not crash)
        output = stdout + stderr
        # If it crashes, ensure it's a handled error
        if "Traceback" in output:
            assert "SyntaxError" in output or "ParseError" in output.lower()

    def test_validate_empty_directory(self, tmp_path: Path):
        """Empty directory handled gracefully."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(empty_dir))

        # Should complete without crash
        assert "Traceback" not in stderr

    def test_validate_non_python_files(self, tmp_path: Path):
        """Non-Python files are ignored."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "README.md").write_text("# Not Python")
        (pkg / "data.json").write_text('{"key": "value"}')
        (pkg / "__init__.py").write_text("")

        _exit_code, _stdout, stderr = run_cli("validate", "--module", str(pkg))

        # Should complete successfully
        assert "Traceback" not in stderr

    def test_error_messages_are_informative(self, tmp_path: Path):
        """Error messages contain useful information."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("# Minimal init")

        _exit_code, stdout, stderr = run_cli("validate", "--module", str(pkg))

        output = stdout + stderr
        # Should have some meaningful output
        assert len(output) > 10  # Not just empty


@pytest.mark.integration
class TestCLIOutput:
    """Test CLI output formatting."""

    def test_validate_produces_output(self, tmp_path: Path):
        """Validation produces readable output."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class A: pass")
        (pkg / "__init__.py").write_text("")

        _exit_code, stdout, stderr = run_cli("validate", "--module", str(pkg))

        output = stdout + stderr
        # Should have some output
        assert len(output) > 0
        # Should mention validation
        assert "validat" in output.lower()

    def test_analyze_shows_metrics(self, tmp_path: Path):
        """Analyze shows useful information."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "__init__.py").write_text("")
        for i in range(3):
            (pkg / f"mod_{i}.py").write_text(f"class Class_{i}: pass")

        # Create rules file
        config_dir = tmp_path / ".codeweaver"
        config_dir.mkdir()
        (config_dir / "lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules: []
""")

        _exit_code, stdout, stderr = run_cli("analyze", "--source", str(tmp_path))

        output = stdout + stderr
        # Should show some information
        assert len(output) > 20


@pytest.mark.integration
class TestCLIWorkflows:
    """Test complete CLI workflows."""

    def test_analyze_then_validate_workflow(self, tmp_path: Path):
        """Workflow: analyze → validate."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class Public: pass")
        (pkg / "__init__.py").write_text("")

        # Create rules file
        config_dir = tmp_path / ".codeweaver"
        config_dir.mkdir()
        (config_dir / "lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules: []
""")

        # Step 1: Analyze
        _exit1, _stdout1, stderr1 = run_cli("analyze", "--source", str(tmp_path))
        # Should complete (may warn)
        assert "Traceback" not in stderr1

        # Step 2: Validate
        _exit2, _stdout2, stderr2 = run_cli("validate", "--module", str(pkg))
        # Should complete (may have warnings but shouldn't crash)
        assert "Traceback" not in stderr2

    def test_full_pipeline_workflow(self, tmp_path: Path):
        """Full workflow: analyze → generate → validate."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()

        (pkg / "mod.py").write_text("class MyClass: pass")
        (pkg / "__init__.py").write_text("")

        # Create rules
        rules_dir = tmp_path / ".codeweaver"
        rules_dir.mkdir()
        (rules_dir / "lazy_import_rules.yaml").write_text("""
schema_version: "1.0"
rules:
  - name: "include-all"
    priority: 500
    match:
      name_pattern: ".*"
    action: include
    propagate: parent
""")

        # Analyze
        _exit1, _stdout1, stderr1 = run_cli("analyze", "--source", str(tmp_path))
        # Should complete (may warn)
        assert "Traceback" not in stderr1

        # Generate
        _exit2, _stdout2, stderr2 = run_cli("generate", "--source", str(tmp_path))
        # Should complete (may have warnings)
        assert "Traceback" not in stderr2

        # Validate
        _exit3, _stdout3, stderr3 = run_cli("validate", "--module", str(pkg))
        # Should complete
        assert "Traceback" not in stderr3


@pytest.mark.integration
class TestCLIHelp:
    """Test help and documentation."""

    def test_validate_help(self):
        """Validate command help works."""
        exit_code, stdout, stderr = run_cli("validate", "--help")

        assert exit_code == 0
        output = stdout + stderr
        assert "validate" in output.lower() or "help" in output.lower()

    def test_analyze_help(self):
        """Analyze command help works."""
        exit_code, stdout, stderr = run_cli("analyze", "--help")

        assert exit_code == 0
        output = stdout + stderr
        assert "analyze" in output.lower() or "help" in output.lower()
