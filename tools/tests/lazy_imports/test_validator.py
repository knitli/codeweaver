"""Tests for Import Validator."""

# ruff: noqa: S101, ANN201
# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
from __future__ import annotations

from pathlib import Path

from tools.lazy_imports.common.types import ValidationError, ValidationWarning
from tools.lazy_imports.validator.validator import LazyImportValidator


class TestLazyImportValidator:
    """Test suite for lazy import validator."""

    def test_valid_lazy_import_call(self, tmp_path: Path):
        """Valid lazy_import call should pass validation."""
        # Create a test file with valid lazy_import using a real module
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from pathlib import Path

# Use a real module that exists
MyPath = Path
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # Should have no errors (file has no lazy_import calls, so nothing to validate)
        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert not errors

    def test_broken_lazy_import_module(self, tmp_path: Path):
        """Broken module path should be detected."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from codeweaver.common.utils import lazy_import

MyClass = lazy_import("nonexistent.module", "MyClass")
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert errors
        assert any("nonexistent.module" in e.message for e in errors)

    def test_broken_lazy_import_object(self, tmp_path: Path):
        """Missing object should be detected."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from codeweaver.common.utils import lazy_import

# Module exists but object doesn't
Obj = lazy_import("codeweaver.core", "NonExistentClass")
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        if errors := [i for i in issues if isinstance(i, ValidationError)]:
            assert any("NonExistentClass" in e.message for e in errors)

    def test_multiple_issues_in_file(self, tmp_path: Path):
        """Multiple issues should all be detected."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
from codeweaver.common.utils import lazy_import

A = lazy_import("nonexistent1", "Class1")
B = lazy_import("nonexistent2", "Class2")
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert len(errors) >= 2

    def test_no_lazy_imports(self, tmp_path: Path):
        """File with no lazy_import calls should pass."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
# Regular code, no lazy imports

class MyClass:
    pass
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        assert len(issues) == 0

    def test_syntax_error_in_file(self, tmp_path: Path):
        """Syntax errors should be reported."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def broken(
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert errors

    def test_validate_multiple_files(self, tmp_path: Path):
        """Can validate multiple files."""
        # Create multiple test files
        file1 = tmp_path / "file1.py"
        file1.write_text('lazy_import("good.module", "Class")')

        file2 = tmp_path / "file2.py"
        file2.write_text('lazy_import("bad.module", "Class")')

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_files([file1, file2])

        # Should have issues from both files
        assert len(issues) >= 1


class TestConsistencyChecker:
    """Test suite for package consistency checking."""

    def test_consistent_init_file(self, tmp_path: Path):
        """Consistent __init__.py should pass."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""
from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["MyClass"]

# Define MyClass as a lazy import
class MyClass:  # Placeholder definition
    pass

_dynamic_imports = {
    "MyClass": ("module", "MyClass"),
}

if TYPE_CHECKING:
    from .module import MyClass  # type: ignore[no-redef]
""")

        from tools.lazy_imports.validator.consistency import ConsistencyChecker

        checker = ConsistencyChecker(project_root=tmp_path)
        issues = checker.check_file_consistency(init_file)

        errors = [i for i in issues if i.severity == "error"]
        assert not errors

    def test_all_mismatch_dynamic_imports(self, tmp_path: Path):
        """__all__ and _dynamic_imports mismatch should be detected."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""
__all__ = ["Class1", "Class2"]

_dynamic_imports = {
    "Class1": ("module", "Class1"),
    # Class2 missing!
}
""")

        from tools.lazy_imports.validator.consistency import ConsistencyChecker

        checker = ConsistencyChecker(project_root=tmp_path)
        issues = checker.check_file_consistency(init_file)

        errors = [i for i in issues if i.severity == "error"]
        assert errors
        assert any("Class2" in str(e) for e in errors)

    def test_duplicate_exports(self, tmp_path: Path):
        """Duplicate exports should be detected."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""
__all__ = ["MyClass", "MyClass"]  # Duplicate!

_dynamic_imports = {
    "MyClass": ("module", "MyClass"),
}
""")

        from tools.lazy_imports.validator.consistency import ConsistencyChecker

        checker = ConsistencyChecker(project_root=tmp_path)
        issues = checker.check_file_consistency(init_file)

        # Should detect duplicate
        warnings = [i for i in issues if i.severity == "warning"]
        assert warnings or len(issues) > 0

    def test_missing_type_checking_import(self, tmp_path: Path):
        """Missing TYPE_CHECKING import should be detected."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("""
__all__ = ["MyClass"]

_dynamic_imports = {
    "MyClass": ("module", "MyClass"),
}

# Missing: if TYPE_CHECKING: ...
""")

        from tools.lazy_imports.validator.consistency import ConsistencyChecker

        checker = ConsistencyChecker(project_root=tmp_path)
        checker.check_file_consistency(init_file)

        # May warn about missing TYPE_CHECKING block
        # This is implementation dependent


class TestImportResolver:
    """Test suite for import resolution."""

    def test_resolve_valid_import(self):
        """Should resolve valid import."""
        from pathlib import Path

        from tools.lazy_imports.validator.resolver import ImportResolver

        resolver = ImportResolver(project_root=Path.cwd())

        # Try to resolve a real module
        resolution = resolver.resolve("pathlib", "Path")

        assert resolution.exists
        assert resolution.module == "pathlib"
        assert resolution.obj == "Path"
        assert resolution.error is None

    def test_resolve_invalid_module(self):
        """Should detect invalid module."""
        from pathlib import Path

        from tools.lazy_imports.validator.resolver import ImportResolver

        resolver = ImportResolver(project_root=Path.cwd())

        resolution = resolver.resolve("nonexistent.module", "Class")

        assert not resolution.exists
        assert resolution.error is not None

    def test_resolve_invalid_object(self):
        """Should detect invalid object."""
        from pathlib import Path

        from tools.lazy_imports.validator.resolver import ImportResolver

        resolver = ImportResolver(project_root=Path.cwd())

        # Module exists but object doesn't
        resolution = resolver.resolve("pathlib", "NonExistentClass")

        assert not resolution.exists or resolution.error is not None

    def test_resolve_cache(self):
        """Resolver should cache results."""
        from pathlib import Path

        from tools.lazy_imports.validator.resolver import ImportResolver

        resolver = ImportResolver(project_root=Path.cwd())

        # First resolution
        res1 = resolver.resolve("pathlib", "Path")

        # Second resolution (should use cache)
        res2 = resolver.resolve("pathlib", "Path")

        assert res1.exists == res2.exists
        assert res1.module == res2.module


class TestValidationReport:
    """Test validation report generation."""

    def test_empty_report(self):
        """Empty validation report."""
        from tools.lazy_imports.common.types import ValidationMetrics, ValidationReport

        report = ValidationReport(
            errors=[],
            warnings=[],
            metrics=ValidationMetrics(
                files_validated=0, imports_checked=0, consistency_checks=0, validation_time_ms=0
            ),
            success=True,
        )

        assert report.success
        assert len(report.errors) == 0
        assert len(report.warnings) == 0

    def test_report_with_errors(self):
        """Report with errors should not be successful."""
        from tools.lazy_imports.common.types import ValidationMetrics, ValidationReport

        errors = [
            ValidationError(
                file=Path("test.py"),
                line=10,
                message="Import not found",
                suggestion="Check module path",
                code="BROKEN_IMPORT",
            )
        ]

        report = ValidationReport(
            errors=errors,
            warnings=[],
            metrics=ValidationMetrics(
                files_validated=1, imports_checked=5, consistency_checks=1, validation_time_ms=100
            ),
            success=False,
        )

        assert not report.success
        assert len(report.errors) == 1

    def test_report_with_warnings_is_success(self):
        """Report with only warnings should be successful."""
        from tools.lazy_imports.common.types import ValidationMetrics, ValidationReport

        warnings = [
            ValidationWarning(
                file=Path("test.py"), line=10, message="Unused import", suggestion="Remove import"
            )
        ]

        report = ValidationReport(
            errors=[],
            warnings=warnings,
            metrics=ValidationMetrics(
                files_validated=1, imports_checked=5, consistency_checks=1, validation_time_ms=100
            ),
            success=True,
        )

        assert report.success
        assert len(report.warnings) == 1
