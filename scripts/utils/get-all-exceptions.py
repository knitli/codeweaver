#!/usr/bin/env python3
# sourcery skip: require-parameter-annotation, require-return-annotation, snake-case-functions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Helper that retrieves all exceptions available in the CodeWeaver codebase, and also all used exceptions."""

import contextlib
import pkgutil

from types import ModuleType


def find_builtin_usage_in_source(module: ModuleType, builtins: set[str]) -> set[tuple[str, str]]:
    """Check if the module uses any built-in exceptions by analyzing source code."""
    import ast
    import inspect

    try:
        # Get the source code of the module
        source = inspect.getsource(module)
        tree = ast.parse(source)

        found_exceptions = set()

        class ExceptionVisitor(ast.NodeVisitor):
            """AST visitor to find built-in exception usage."""

            def visit_Raise(self, node):
                """Handle raise statements and exception calls."""
                # Handle raise statements: raise ValueError("message")
                if isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                    if node.exc.func.id in builtins:
                        found_exceptions.add((module.__name__, node.exc.func.id))
                elif isinstance(node.exc, ast.Name) and node.exc.id in builtins:
                    found_exceptions.add((module.__name__, node.exc.id))
                self.generic_visit(node)

            def visit_ExceptHandler(self, node):
                """Handle except clauses to find exception types."""
                # Handle except clauses: except ValueError:
                if node.type:
                    if isinstance(node.type, ast.Name) and node.type.id in builtins:
                        found_exceptions.add((module.__name__, node.type.id))
                    elif isinstance(node.type, ast.Tuple):
                        for elt in node.type.elts:
                            if isinstance(elt, ast.Name) and elt.id in builtins:
                                found_exceptions.add((module.__name__, elt.id))
                self.generic_visit(node)

            def visit_FunctionDef(self, node):
                """Check function signatures for exception annotations."""
                # Check function signatures for exception annotations
                if node.returns and (
                    isinstance(node.returns, ast.Name) and node.returns.id in builtins
                ):
                    found_exceptions.add((module.__name__, node.returns.id))
                self.generic_visit(node)

        visitor = ExceptionVisitor()
        visitor.visit(tree)

    except (OSError, TypeError, SyntaxError):
        # If we can't get source code, fall back to the old method
        return set()
    else:
        return found_exceptions


def safe_walk_packages(package, prefix) -> "iter[pkgutil.ModuleInfo]":
    """Walk packages safely, handling import errors during discovery."""

    def onerror(name):
        # Silently ignore errors during package walking
        pass

    with contextlib.suppress(Exception):
        yield from pkgutil.walk_packages(package.__path__, prefix, onerror=onerror)


def scan_source_files_for_exceptions(
    base_path: str, builtin_exceptions: set[str]
) -> tuple[set[tuple[str, str]], list[str]]:  # sourcery skip: low-code-quality
    """Scan Python source files directly for exception usage and definitions."""
    import ast
    import os

    from pathlib import Path

    builtin_usage = set()
    custom_exceptions = []

    for py_file in Path(base_path).rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")

            tree = ast.parse(source)
            relative_path = py_file.relative_to(base_path)
            module_name = str(relative_path.with_suffix("")).replace(os.sep, ".")

            # Find builtin exception usage
            class ExceptionVisitor(ast.NodeVisitor):
                """AST visitor to find exception usage and definitions."""

                def visit_Raise(self, node: ast.Raise, module_name: str = module_name):
                    """Handle raise statements to find exceptions."""
                    if isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                        if node.exc.func.id in builtin_exceptions:
                            builtin_usage.add((module_name, node.exc.func.id))
                    elif isinstance(node.exc, ast.Name) and node.exc.id in builtin_exceptions:
                        builtin_usage.add((module_name, node.exc.id))
                    self.generic_visit(node)

                def visit_ExceptHandler(
                    self, node: ast.Raise, module_name: str = module_name
                ) -> None:
                    """Handle except clauses to find exception types."""
                    if node.type:
                        if isinstance(node.type, ast.Name) and node.type.id in builtin_exceptions:
                            builtin_usage.add((module_name, node.type.id))
                        elif isinstance(node.type, ast.Tuple):
                            for elt in node.type.elts:
                                if isinstance(elt, ast.Name) and elt.id in builtin_exceptions:
                                    builtin_usage.add((module_name, elt.id))
                    self.generic_visit(node)

                def visit_ClassDef(self, node: ast.Raise, module_name: str = module_name) -> None:
                    """Handle class definitions to find custom exceptions."""
                    # Find custom exception classes
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "Exception":
                            if node.name not in builtin_exceptions:
                                custom_exceptions.append(f"{module_name}.{node.name}")
                        elif (
                            isinstance(base, ast.Attribute)
                            and hasattr(base, "attr")
                            and (
                                base.attr in ["Exception", "Error"]
                                or base.attr.endswith(("Error", "Exception"))
                            )
                            and node.name not in builtin_exceptions
                        ):
                            custom_exceptions.append(f"{module_name}.{node.name}")
                    self.generic_visit(node)

            visitor = ExceptionVisitor()
            visitor.visit(tree)

        except (SyntaxError, UnicodeDecodeError, PermissionError):
            # Skip files with syntax errors or encoding issues
            continue

    return builtin_usage, custom_exceptions


def main() -> None:  # sourcery skip: extract-duplicate-method
    """Main function to retrieve and print all exceptions."""
    from pathlib import Path

    # Define the path to search - entire codeweaver source
    source_path = Path("src/codeweaver")

    if not source_path.exists():
        print(f"Error: Source path {source_path} does not exist")
        return

    # Get builtin exceptions
    if hasattr(__builtins__, "__dict__"):
        builtin_exceptions = {
            e for e in __builtins__.__dict__ if e.endswith(("Error", "Exception"))
        }
    else:
        builtin_exceptions = {e for e in __builtins__ if e.endswith(("Error", "Exception"))}

    # Scan source files directly
    builtin_usage, custom_exceptions = scan_source_files_for_exceptions(
        str(source_path), builtin_exceptions
    )

    print(f"Scanned Python files in {source_path}\n")

    # Print all collected exceptions
    print(f"Found {len(custom_exceptions)} custom exceptions:\n")
    print("Custom Exceptions:")
    print("------------------")
    for exc in sorted(custom_exceptions, key=lambda x: x.split(".")[-1].lower()):
        print(f"{exc.split('.')[-1]}\npath: {exc}\n")

    if builtin_usage:
        print(f"Found {len(builtin_usage)} builtin exception usages:\n")
        print("Builtin Exception Usage:")
        print("------------------------")
        for modname, excname in sorted(builtin_usage):
            print(f"{excname} in {modname}")


if __name__ == "__main__":
    main()
