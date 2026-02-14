#!/usr/bin/env python3
"""Consistency checking for lazy import system.

Verifies package consistency:
- __all__ declarations match actual exports
- lazy_import() calls are consistent with exports
- No duplicate exports
"""

from __future__ import annotations

import ast

from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ..common.types import ConsistencyIssue


class ConsistencyChecker:
    """Checks consistency of lazy import system."""

    def __init__(self, project_root: Path) -> None:
        """Initialize checker.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root
        self.src_path = project_root / "src"

    def check_file_consistency(self, file_path: Path) -> list[ConsistencyIssue]:
        """Check consistency of a single file.

        Args:
            file_path: Path to Python file

        Returns:
            List of consistency issues found
        """
        from ..common.types import ConsistencyIssue

        issues = []

        # Read file
        try:
            content = file_path.read_text()
        except Exception as e:
            return [
                ConsistencyIssue(
                    severity="error", location=file_path, message=f"Cannot read file: {e}"
                )
            ]

        # Parse AST
        try:
            tree = ast.parse(content, str(file_path))
        except SyntaxError as e:
            return [
                ConsistencyIssue(
                    severity="error",
                    location=file_path,
                    message=f"Syntax error: {e}",
                    line=e.lineno,
                )
            ]

        # Find __all__ declaration
        all_exports = self._find_all_exports(tree)

        # Find lazy_import calls
        lazy_imports = self._find_lazy_imports(tree)

        # Find actual definitions
        definitions = self._find_definitions(tree)

        # Check for issues
        issues.extend(self._check_all_consistency(file_path, all_exports, definitions))
        issues.extend(self._check_lazy_import_consistency(file_path, lazy_imports))
        issues.extend(self._check_duplicate_exports(file_path, all_exports))

        return issues

    def check_package_consistency(self, package_path: Path) -> list[ConsistencyIssue]:
        """Check consistency of entire package.

        Args:
            package_path: Path to package directory

        Returns:
            List of consistency issues found
        """
        issues = []

        # Find all Python files
        python_files = list(package_path.rglob("*.py"))

        for file_path in python_files:
            # Skip test files
            if "test" in file_path.parts:
                continue

            issues.extend(self.check_file_consistency(file_path))

        return issues

    def _find_all_exports(self, tree: ast.AST) -> list[str]:
        """Find __all__ exports in AST.

        Args:
            tree: AST of file

        Returns:
            List of exported names
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "__all__"
                        and isinstance(node.value, (ast.List, ast.Tuple))
                    ):
                        return [
                            str(elt.value)
                            for elt in node.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        ]
        return []

    def _find_lazy_imports(self, tree: ast.AST) -> list[tuple[str, str, int]]:
        """Find lazy_import() calls in AST.

        Args:
            tree: AST of file

        Returns:
            List of (module, obj, line) tuples
        """
        lazy_imports = []

        lazy_imports.extend(
            (node.args[0].s, node.args[1].s, node.lineno)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (isinstance(node.func, ast.Name) and node.func.id == "lazy_import")
            and len(node.args) >= 2
            and (isinstance(node.args[0], ast.Constant) and isinstance(node.args[1], ast.Constant))
        )
        return lazy_imports

    def _find_definitions(self, tree: ast.AST) -> set[str]:
        """Find all top-level definitions in AST.

        Args:
            tree: AST of file

        Returns:
            Set of defined names
        """
        if not isinstance(tree, ast.Module):
            return set()

        definitions = set()

        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                definitions.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        definitions.add(target.id)

        return definitions

    def _check_all_consistency(
        self, file_path: Path, all_exports: list[str], definitions: set[str]
    ) -> list[ConsistencyIssue]:
        """Check __all__ consistency with definitions.

        Args:
            file_path: Path to file
            all_exports: Names in __all__
            definitions: Actual definitions

        Returns:
            List of issues
        """
        from ..common.types import ConsistencyIssue

        issues = []

        # If no __all__, no issues
        if not all_exports:
            return issues

        # Check each export exists
        issues.extend(
            ConsistencyIssue(
                severity="error",
                location=file_path,
                message=f"Export '{name}' in __all__ but not defined in file",
            )
            for name in all_exports
            if name not in definitions and not name.startswith("_")
        )
        return issues

    def _check_lazy_import_consistency(
        self, file_path: Path, lazy_imports: list[tuple[str, str, int]]
    ) -> list[ConsistencyIssue]:
        """Check lazy_import() call consistency.

        Args:
            file_path: Path to file
            lazy_imports: List of (module, obj, line) tuples

        Returns:
            List of issues
        """
        from ..common.types import ConsistencyIssue

        issues = []

        # Check for duplicate lazy_imports
        seen = {}
        for module, obj, line in lazy_imports:
            key = (module, obj)
            if key in seen:
                issues.append(
                    ConsistencyIssue(
                        severity="warning",
                        location=file_path,
                        message=f"Duplicate lazy_import({module!r}, {obj!r})",
                        line=line,
                    )
                )
            else:
                seen[key] = line

        return issues

    def _check_duplicate_exports(
        self, file_path: Path, all_exports: list[str]
    ) -> list[ConsistencyIssue]:
        """Check for duplicate exports in __all__.

        Args:
            file_path: Path to file
            all_exports: Names in __all__

        Returns:
            List of issues
        """
        from ..common.types import ConsistencyIssue

        issues = []

        # Check for duplicates
        seen = set()
        for name in all_exports:
            if name in seen:
                issues.append(
                    ConsistencyIssue(
                        severity="error",
                        location=file_path,
                        message=f"Duplicate export '{name}' in __all__",
                    )
                )
            else:
                seen.add(name)

        return issues
