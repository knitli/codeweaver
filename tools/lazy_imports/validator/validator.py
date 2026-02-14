#!/usr/bin/env python3
"""Main validator for lazy import system.

Coordinates all validation activities:
- Import resolution
- Consistency checking
- Auto-fixing
"""

from __future__ import annotations

import ast
import time

from pathlib import Path
from typing import TYPE_CHECKING

from .consistency import ConsistencyChecker
from .fixer import AutoFixer
from .resolver import ImportResolver


if TYPE_CHECKING:
    from ..common.types import (
        CallError,
        ConsistencyIssue,
        UpdatedFile,
        ValidationConfig,
        ValidationReport,
    )


class LazyImportValidator:
    """Validates lazy import correctness.

    Provides comprehensive validation of the lazy import system:
    - Checks that all lazy_import() calls resolve correctly
    - Verifies package consistency (__all__ matches exports)
    - Validates TYPE_CHECKING imports
    - Auto-fixes broken imports
    """

    def __init__(self, project_root: Path, config: ValidationConfig | None = None) -> None:
        """Initialize validator.

        Args:
            project_root: Root directory of the project
            config: Validation configuration (uses defaults if None)
        """
        self.project_root = project_root
        self.config = config or self._default_config()

        # Create components
        self.resolver = ImportResolver(project_root)
        self.consistency_checker = ConsistencyChecker(project_root)
        self.fixer = AutoFixer(project_root, dry_run=self.config.dry_run_by_default)

    def validate_file(self, file_path: Path) -> list:
        """Validate a single file.

        Args:
            file_path: Path to the file to validate

        Returns:
            List of validation issues found in the file
        """
        from ..common.types import ValidationError, ValidationWarning

        errors: list = []

        # Check if file exists
        if not file_path.exists():
            errors.append(
                ValidationError(
                    file=file_path,
                    line=0,
                    message=f"File not found: {file_path}",
                    suggestion="Check the file path",
                    code="FILE_NOT_FOUND",
                )
            )
            return errors

        # Check for syntax errors first
        try:
            content = file_path.read_text()
            ast.parse(content, str(file_path))
        except SyntaxError as e:
            errors.append(
                ValidationError(
                    file=file_path,
                    line=e.lineno or 0,
                    message=f"Syntax error: {e.msg}",
                    suggestion="Fix the syntax error",
                    code="SYNTAX_ERROR",
                )
            )
            return errors  # Can't validate further if syntax is broken
        except Exception as e:
            errors.append(
                ValidationError(
                    file=file_path,
                    line=0,
                    message=f"Error reading file: {e}",
                    suggestion="Check file encoding and permissions",
                    code="READ_ERROR",
                )
            )
            return errors

        # Find lazy_import() calls
        if self.config.check_lazy_import_calls:
            call_errors = self._find_lazy_import_calls(file_path)

            # Check each call
            for module, obj, line in call_errors:
                resolution = self.resolver.resolve_lazy_import(module, obj)
                if not resolution.exists:
                    errors.append(
                        ValidationError(
                            file=file_path,
                            line=line,
                            message=f"Broken import: lazy_import({module!r}, {obj!r})",
                            suggestion=f"Check if module '{module}' exports '{obj}'",
                            code="BROKEN_IMPORT",
                        )
                    )

        # Check TYPE_CHECKING imports
        if self.config.check_type_checking_imports:
            type_checking_imports = self._find_type_checking_imports(file_path)
            for module, obj, line in type_checking_imports:
                if not self.resolver.check_type_checking_import(module, obj):
                    errors.append(
                        ValidationWarning(
                            file=file_path,
                            line=line,
                            message=f"TYPE_CHECKING import may not exist: from {module} import {obj}",
                            suggestion="Verify this import is valid",
                        )
                    )

        return errors

    def validate_files(self, file_paths: list[Path]) -> list:
        """Validate multiple files.

        Args:
            file_paths: List of file paths to validate

        Returns:
            Combined list of validation issues from all files
        """
        all_issues = []
        for file_path in file_paths:
            all_issues.extend(self.validate_file(file_path))
        return all_issues

    def validate_imports(self) -> ValidationReport:  # noqa: C901
        """Validate all lazy_import() calls.

        Returns:
            Complete validation report
        """
        from ..common.types import (
            ValidationError,
            ValidationMetrics,
            ValidationReport,
            ValidationWarning,
        )

        start_time = time.perf_counter()
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []

        # Find all Python files
        src_path = self.project_root / "src"
        if not src_path.exists():
            src_path = self.project_root

        python_files = list(src_path.rglob("*.py"))

        # Filter ignored files
        if self.config.ignore_patterns:
            python_files = [f for f in python_files if not self._is_ignored(f)]

        files_validated = 0
        imports_checked = 0

        # Validate each file
        for file_path in python_files:
            # Skip test files
            if "test" in file_path.parts:
                continue

            files_validated += 1

            # Find lazy_import() calls
            if self.config.check_lazy_import_calls:
                call_errors = self._find_lazy_import_calls(file_path)
                imports_checked += len(call_errors)

                # Check each call
                for module, obj, line in call_errors:
                    resolution = self.resolver.resolve_lazy_import(module, obj)
                    if not resolution.exists:
                        errors.append(
                            ValidationError(
                                file=file_path,
                                line=line,
                                message=f"Broken import: lazy_import({module!r}, {obj!r})",
                                suggestion=f"Check if module '{module}' exports '{obj}'",
                                code="BROKEN_IMPORT",
                            )
                        )

            # Check TYPE_CHECKING imports
            if self.config.check_type_checking_imports:
                type_checking_imports = self._find_type_checking_imports(file_path)
                for module, obj, line in type_checking_imports:
                    if not self.resolver.check_type_checking_import(module, obj):
                        warnings.append(
                            ValidationWarning(
                                file=file_path,
                                line=line,
                                message=f"TYPE_CHECKING import may not exist: from {module} import {obj}",
                                suggestion="Verify this import is valid",
                            )
                        )

        # Check package consistency
        consistency_checks = 0
        if self.config.check_package_consistency:
            issues = self.check_consistency()
            consistency_checks = len(issues)

            for issue in issues:
                if issue.severity == "error":
                    errors.append(
                        ValidationError(
                            file=issue.location,
                            line=issue.line,
                            message=issue.message,
                            suggestion="Fix this consistency issue",
                            code="CONSISTENCY_ERROR",
                        )
                    )
                else:
                    warnings.append(
                        ValidationWarning(
                            file=issue.location,
                            line=issue.line,
                            message=issue.message,
                            suggestion="Consider fixing this issue",
                        )
                    )

        # Calculate metrics
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        metrics = ValidationMetrics(
            files_validated=files_validated,
            imports_checked=imports_checked,
            consistency_checks=consistency_checks,
            validation_time_ms=elapsed_ms,
        )

        return ValidationReport(
            errors=errors, warnings=warnings, metrics=metrics, success=not errors
        )

    def check_consistency(self) -> list[ConsistencyIssue]:
        """Check package consistency.

        Returns:
            List of consistency issues
        """
        src_path = self.project_root / "src"
        if not src_path.exists():
            src_path = self.project_root

        return self.consistency_checker.check_package_consistency(src_path)

    def auto_fix(self, *, dry_run: bool = True) -> list[UpdatedFile]:
        """Auto-fix broken imports.

        Args:
            dry_run: If True, don't actually modify files

        Returns:
            List of files that were (or would be) updated
        """
        # Update fixer dry_run setting
        self.fixer.dry_run = dry_run

        # Validate to find errors
        report = self.validate_imports()

        return self.fixer.fix_validation_errors(report.errors) if report.errors else []

    def fix_broken_imports(
        self, call_errors: list[CallError], *, dry_run: bool = True
    ) -> list[UpdatedFile]:
        """Fix specific broken imports.

        Args:
            call_errors: List of broken import calls
            dry_run: If True, don't actually modify files

        Returns:
            List of files that were (or would be) updated
        """
        self.fixer.dry_run = dry_run
        return self.fixer.fix_broken_imports(call_errors)

    def _find_lazy_import_calls(self, file_path: Path) -> list[tuple[str, str, int]]:
        """Find all lazy_import() calls in a file.

        Args:
            file_path: Path to Python file

        Returns:
            List of (module, obj, line) tuples
        """
        try:
            content = file_path.read_text()
        except Exception:
            return []

        try:
            tree = ast.parse(content, str(file_path))
        except SyntaxError:
            return []

        calls = []
        calls.extend(
            (node.args[0].s, node.args[1].s, node.lineno)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (isinstance(node.func, ast.Name) and node.func.id == "lazy_import")
            and len(node.args) >= 2
            and (isinstance(node.args[0], ast.Constant) and isinstance(node.args[1], ast.Constant))
        )
        return calls

    def _find_type_checking_imports(self, file_path: Path) -> list[tuple[str, str, int]]:
        """Find all TYPE_CHECKING imports in a file.

        Args:
            file_path: Path to Python file

        Returns:
            List of (module, obj, line) tuples
        """
        try:
            content = file_path.read_text()
        except Exception:
            return []

        try:
            tree = ast.parse(content, str(file_path))
        except SyntaxError:
            return []

        imports = []

        # Find TYPE_CHECKING blocks
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and (
                isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"
            ):
                for stmt in node.body:
                    if isinstance(stmt, ast.ImportFrom):
                        module = stmt.module or ""
                        imports.extend((module, alias.name, stmt.lineno) for alias in stmt.names)
        return imports

    def _is_ignored(self, file_path: Path) -> bool:
        """Check if file matches ignore patterns.

        Args:
            file_path: Path to check

        Returns:
            True if file should be ignored
        """
        import re

        return any(re.search(pattern, str(file_path)) for pattern in self.config.ignore_patterns)

    def _default_config(self) -> ValidationConfig:
        """Create default validation configuration.

        Returns:
            Default ValidationConfig
        """
        from ..common.types import ValidationConfig

        return ValidationConfig(
            check_lazy_import_calls=True,
            check_package_consistency=True,
            check_broken_imports=True,
            check_type_checking_imports=True,
            strict_mode=False,
            ignore_patterns=["test_.*\\.py", ".*_test\\.py"],
            auto_fix_enabled=True,
            dry_run_by_default=True,
            backup_before_fix=True,
        )
