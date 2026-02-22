# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Consistency checker for package integrity.

Validates consistency between __init__.py and module definitions.
"""

from __future__ import annotations

import ast

from pathlib import Path

from tools.exportify.common.types import ConsistencyIssue


class ConsistencyChecker:
    """Checks consistency between __init__.py and source files.

    Validates that:
    - __all__ declarations match _dynamic_imports
    - _dynamic_imports entries exist in source modules
    - TYPE_CHECKING blocks are properly structured
    """

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize consistency checker.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root or Path.cwd()

    def check_file_consistency(self, init_file: Path) -> list[ConsistencyIssue]:
        """Check consistency of an __init__.py file.

        Args:
            init_file: Path to __init__.py file

        Returns:
            List of consistency issues found
        """
        issues: list[ConsistencyIssue] = []

        try:
            self._validate_file_exports(init_file, issues)
        except SyntaxError as e:
            issues.append(
                ConsistencyIssue(
                    severity="error",
                    location=init_file,
                    message=f"Syntax error: {e}",
                    line=e.lineno,
                )
            )
        except Exception as e:
            issues.append(
                ConsistencyIssue(
                    severity="error",
                    location=init_file,
                    message=f"Failed to check consistency: {e}",
                    line=None,
                )
            )

        return issues

    def _validate_file_exports(self, init_file: Path, issues: list[ConsistencyIssue]) -> None:
        content = init_file.read_text()
        tree = ast.parse(content)

        # Extract __all__ and _dynamic_imports
        all_exports = self._extract_all(tree)
        dynamic_imports = self._extract_dynamic_imports(tree)

        # Check if __all__ and _dynamic_imports match
        if all_exports is not None and dynamic_imports is not None:
            self._collect_warnings_and_errors(all_exports, dynamic_imports, issues, init_file)
        # Check for duplicates in __all__
        if all_exports is not None:
            duplicates = [x for x in all_exports if all_exports.count(x) > 1]
            unique_duplicates = set(duplicates)
            issues.extend([
                ConsistencyIssue(
                    severity="warning",
                    location=init_file,
                    message=f"Duplicate export '{name}' in __all__",
                    line=None,
                )
                for name in unique_duplicates
            ])

    def _collect_warnings_and_errors(
        self,
        all_exports: list[str],
        dynamic_imports: dict[str, tuple[str, str]],
        issues: list[ConsistencyIssue],
        init_file: Path,
    ) -> None:
        unique_all_members = set(all_exports)
        unique_dynamic_imports = set(dynamic_imports)

        # Find mismatches
        missing_in_dynamic = unique_all_members - unique_dynamic_imports
        extra_in_dynamic = unique_dynamic_imports - unique_all_members

        issues.extend(
            ConsistencyIssue(
                severity="error",
                location=init_file,
                message=f"Export '{name}' in __all__ but not in _dynamic_imports",
                line=None,
            )
            for name in missing_in_dynamic
        )

        issues.extend(
            ConsistencyIssue(
                severity="warning",
                location=init_file,
                message=f"Export '{name}' in _dynamic_imports but not in __all__",
                line=None,
            )
            for name in extra_in_dynamic
        )

    def _extract_all(self, tree: ast.AST) -> list[str] | None:
        """Extract __all__ declaration from AST.

        Args:
            tree: Parsed AST

        Returns:
            List of export names or None if not found
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "__all__"
                        and isinstance(node.value, ast.List)
                    ):
                        exports = []
                        exports.extend(
                            elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)
                        )
                        return exports
        return None

    def _extract_dynamic_imports(self, tree: ast.AST) -> dict[str, tuple[str, str]] | None:
        """Extract _dynamic_imports declaration from AST.

        Args:
            tree: Parsed AST

        Returns:
            Dict mapping export names to (module, obj) tuples, or None if not found
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "_dynamic_imports"
                        and isinstance(node.value, ast.Dict)
                    ):
                        imports = {}
                        for key, value in zip(node.value.keys, node.value.values, strict=False):
                            if (
                                isinstance(key, ast.Constant)
                                and isinstance(value, ast.Tuple)
                                and len(value.elts) >= 2
                            ):
                                module_node = value.elts[0]
                                obj_node = value.elts[1]
                                if isinstance(module_node, ast.Constant) and isinstance(
                                    obj_node, ast.Constant
                                ):
                                    imports[key.value] = (module_node.value, obj_node.value)
                        return imports
        return None


__all__ = ["ConsistencyChecker"]
