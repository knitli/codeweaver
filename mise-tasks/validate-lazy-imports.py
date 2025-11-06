#!/usr/bin/env -S uv run -s

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-complex-if-expressions
# ///script
# python-version: ">=3.12"
# dependencies: ["rich"]
# ////script
"""Validate lazy imports in the codebase.

This script validates two types of lazy imports:

1. lazy_import() function calls:
   Our `lazy_import` function is useful for reducing startup time and avoiding
   circular imports, but when modules or objects are renamed or removed, the
   lazy imports can break silently until runtime.

2. Package-level lazy imports (__init__.py style):
   Validates __all__, _dynamic_imports, __getattr__, and TYPE_CHECKING blocks
   to ensure consistency and correctness of pydantic-style lazy imports.
"""

import ast
import importlib
import re
import sys

from pathlib import Path
from typing import NamedTuple

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from codeweaver.cli.utils import format_file_link, is_tty


console = Console(markup=True, emoji=True)

# Pattern for lazy_import() function calls
LAZY_IMPORT_PATTERN = re.compile(
    r'lazy_import\([\s\n]*"(?P<module>[A-Za-z0-9_.]+)"\s*,?[\s\n]*"(?P<object>[A-Za-z0-9_.]+)"\s*?[\s\n]*\)'
)

# All mise tasks operate relative to the src/codeweaver directory
SRC_DIR = Path("src/codeweaver")

# Modules to check for package-level lazy imports
PACKAGE_MODULES = ["codeweaver.core", "codeweaver.config", "codeweaver.common"]


# ============================================================================
# SECTION 1: lazy_import() Function Call Validation
# ============================================================================


class FunctionCallError(NamedTuple):
    """Tuple representing a lazy_import() function call validation error."""

    file_ref: str
    module: str
    obj: str
    status: str


def display_function_errors_as_panels(errors: list[FunctionCallError]) -> None:
    """Display lazy_import() function call errors as individual panels."""
    console.print(
        f"\n[bold red]Found {len(errors)} lazy_import() Function Call Error{'s' if len(errors) != 1 else ''}[/bold red]\n"
    )

    for error in errors:
        content = (
            f"[cyan]{error.file_ref}[/cyan]\n"
            f"[yellow]Module:[/yellow] {error.module}  "
            f"[yellow]Object:[/yellow] {error.obj}  "
            f"[yellow bold]Status:[/yellow bold] {error.status}"
        )
        console.print(Panel(content, border_style="red", padding=(0, 1)))


def line_number_from_position(text: str, position: int) -> int:
    """Get the line number from a character position in the text."""
    return text.count("\n", 0, position) + 1


def create_function_error_tuple(
    py_file: Path, line_num: int, module: str, obj: str, status: str
) -> FunctionCallError:
    """Create an error tuple for lazy_import() function calls."""
    if is_tty():
        return FunctionCallError(
            file_ref=format_file_link(py_file, line_num),
            module=module,
            obj=obj,
            status=f"[bold red]{status}[/bold red]" if "ERROR" in status else status,
        )
    return FunctionCallError(
        file_ref=f"{py_file}:{line_num}", module=module, obj=obj, status=status
    )


def validate_import(module: str, obj: str) -> str | None:
    """Validate a lazy import. Returns error status or None if valid."""
    try:
        imported_module = importlib.import_module(module)
        return "MISSING OBJECT" if obj and not hasattr(imported_module, obj) else None
    except ImportError:
        return "IMPORT ERROR"
    except Exception as e:
        return f"ERROR: {e!s}"


def collect_python_files(paths: list[Path] | None) -> list[Path]:
    """Collect all Python files to validate from the given paths or default location."""
    if not paths:
        return list(SRC_DIR.rglob("*.py"))

    temp_paths: set[Path] = set()
    for path in paths:
        if path.is_dir():
            temp_paths.update(path.rglob("*.py"))
        elif path.suffix == ".py":
            temp_paths.add(path)
    return list(temp_paths)


def validate_function_calls(paths: list[Path] | None = None) -> list[FunctionCallError]:
    """Validate lazy_import() function calls in the codebase."""
    errors = []
    search_paths = collect_python_files(paths)

    for py_file in search_paths:
        content = py_file.read_text(encoding="utf-8")

        for match in LAZY_IMPORT_PATTERN.finditer(content):
            module = match.group("module").strip('" \n\t')
            obj = match.group("object")
            if obj:
                obj = obj.strip(', " \n\t')  # noqa: B005

            if error_status := validate_import(module, obj):
                line_num = line_number_from_position(content, match.span()[0])
                errors.append(create_function_error_tuple(py_file, line_num, module, obj, error_status))

    return errors


# ============================================================================
# SECTION 2: Package-Level Lazy Imports Validation
# ============================================================================


class PackageError(NamedTuple):
    """Tuple representing a package-level lazy import validation error."""

    module_name: str
    category: str  # "ERROR", "WARNING", "INFO"
    message: str


class PackageValidator:
    """Validate package-level lazy import patterns."""

    def __init__(self) -> None:
        """Initialize the validator."""
        self.errors: list[PackageError] = []
        self.warnings: list[PackageError] = []
        self.info: list[PackageError] = []

    def validate_module(self, module_name: str) -> None:
        """Validate __init__.py style lazy imports in a module."""
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            self.errors.append(PackageError(module_name, "ERROR", f"Cannot import module - {e}"))
            return

        # Check for __all__
        __all__ = getattr(module, "__all__", None)
        if __all__ is None:
            self.warnings.append(PackageError(module_name, "WARNING", "No __all__ defined"))
            return

        # Check for _dynamic_imports
        _dynamic_imports = getattr(module, "_dynamic_imports", None)
        if _dynamic_imports is None:
            self.info.append(
                PackageError(
                    module_name, "INFO", "No _dynamic_imports (not using lazy import pattern)"
                )
            )
            return

        # Check for __getattr__
        __getattr__ = getattr(module, "__getattr__", None)
        if __getattr__ is None:
            self.errors.append(
                PackageError(module_name, "ERROR", "Has _dynamic_imports but no __getattr__")
            )
            return

        # Check consistency
        self._check_consistency(module_name, __all__, _dynamic_imports)

        # Check TYPE_CHECKING block
        self._check_type_checking_block(module_name, module)

        # Validate import paths
        self._validate_import_paths(module_name, _dynamic_imports)

    def _check_consistency(
        self, module_name: str, all_: tuple[str, ...], dynamic_imports: dict[str, tuple[str, str]]
    ) -> None:
        """Check consistency between __all__ and _dynamic_imports."""
        if missing_in_dynamic := [name for name in all_ if name not in dynamic_imports]:
            module = importlib.import_module(module_name)
            for name in missing_in_dynamic:
                if hasattr(module, name):
                    value = getattr(module, name)
                    if not callable(value) and not isinstance(value, type):
                        self.info.append(
                            PackageError(
                                module_name,
                                "INFO",
                                f"'{name}' in __all__ but not _dynamic_imports (appears to be a constant)",
                            )
                        )
                    else:
                        self.warnings.append(
                            PackageError(
                                module_name,
                                "WARNING",
                                f"'{name}' in __all__ but not in _dynamic_imports",
                            )
                        )
                else:
                    self.errors.append(
                        PackageError(
                            module_name,
                            "ERROR",
                            f"'{name}' in __all__ but not in _dynamic_imports and not found in module",
                        )
                    )

        if missing_in_all := [name for name in dynamic_imports if name not in all_]:
            for name in missing_in_all:
                self.warnings.append(
                    PackageError(
                        module_name, "WARNING", f"'{name}' in _dynamic_imports but not in __all__"
                    )
                )

    def _check_type_checking_block(self, module_name: str, module) -> None:
        """Check if module has TYPE_CHECKING block for IDE support."""
        module_file = Path(module.__file__)
        if not module_file.exists():
            return

        source = module_file.read_text()

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            self.errors.append(PackageError(module_name, "ERROR", f"Cannot parse source - {e}"))
            return

        has_type_checking_import = False
        has_type_checking_block = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "typing":
                for alias in node.names:
                    if alias.name == "TYPE_CHECKING":
                        has_type_checking_import = True

            if isinstance(node, ast.If) and (
                isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"
            ):
                has_type_checking_block = True

        if not has_type_checking_import:
            self.warnings.append(
                PackageError(
                    module_name,
                    "WARNING",
                    "No TYPE_CHECKING import (IDE may not resolve types)",
                )
            )

        if not has_type_checking_block:
            self.warnings.append(
                PackageError(
                    module_name,
                    "WARNING",
                    "No TYPE_CHECKING block (IDE may not resolve types)",
                )
            )

    def _validate_import_paths(
        self, module_name: str, _dynamic_imports: dict[str, tuple[str, str]]
    ) -> None:
        """Validate that import paths in _dynamic_imports are correct."""
        for name, (parent, submodule) in _dynamic_imports.items():
            # Construct full module path
            if submodule.startswith("."):
                full_module = f"{parent}{submodule}"
            else:
                full_module = f"{parent}.{submodule}"

            try:
                target_module = importlib.import_module(full_module)

                if not hasattr(target_module, name):
                    self.errors.append(
                        PackageError(
                            module_name,
                            "ERROR",
                            f"'{name}' -> {full_module}.{name} - Module exists but attribute doesn't",
                        )
                    )
            except ImportError as e:
                self.errors.append(
                    PackageError(
                        module_name, "ERROR", f"'{name}' -> Cannot import {full_module} - {e}"
                    )
                )


def display_package_errors_as_panels(
    errors: list[PackageError], warnings: list[PackageError], info: list[PackageError]
) -> None:
    """Display package-level lazy import issues as panels."""
    if errors:
        console.print(
            f"\n[bold red]Found {len(errors)} Package-Level Lazy Import Error{'s' if len(errors) != 1 else ''}[/bold red]\n"
        )
        for error in errors:
            content = f"[cyan]{error.module_name}[/cyan]\n[yellow bold]ERROR:[/yellow bold] {error.message}"
            console.print(Panel(content, border_style="red", padding=(0, 1)))

    if warnings:
        console.print(
            f"\n[bold yellow]Found {len(warnings)} Package-Level Lazy Import Warning{'s' if len(warnings) != 1 else ''}[/bold yellow]\n"
        )
        for warning in warnings:
            content = f"[cyan]{warning.module_name}[/cyan]\n[yellow]WARNING:[/yellow] {warning.message}"
            console.print(Panel(content, border_style="yellow", padding=(0, 1)))

    if info:
        console.print(
            f"\n[bold blue]Package-Level Lazy Import Info ({len(info)})[/bold blue]\n"
        )
        for i in info:
            content = f"[cyan]{i.module_name}[/cyan]\n[blue]INFO:[/blue] {i.message}"
            console.print(Panel(content, border_style="blue", padding=(0, 1)))


def validate_package_level_imports() -> tuple[list[PackageError], list[PackageError], list[PackageError]]:
    """Validate package-level lazy imports."""
    validator = PackageValidator()

    for module_name in PACKAGE_MODULES:
        validator.validate_module(module_name)

    return validator.errors, validator.warnings, validator.info


# ============================================================================
# MAIN VALIDATION ORCHESTRATION
# ============================================================================


def main(paths: list[Path] | None = None) -> int:
    """Run all lazy import validations."""
    exit_code = 0

    console.print(Rule("[bold cyan]CodeWeaver Lazy Import Validator[/bold cyan]", style="cyan"))

    # Section 1: lazy_import() Function Calls
    console.print(
        "\n[bold blue]Section 1: Validating lazy_import() Function Calls[/bold blue]"
    )
    console.print("[dim]Scanning for lazy_import(module, object) patterns...[/dim]\n")

    function_errors = validate_function_calls(paths)

    if function_errors:
        if is_tty():
            display_function_errors_as_panels(function_errors)
        else:
            for error in function_errors:
                console.print(" | ".join(error))
        exit_code = 1
    else:
        if is_tty():
            console.print("[bold green]✓ All lazy_import() function calls are valid.[/bold green]")
        else:
            console.print("All lazy_import() function calls are valid.")

    # Section 2: Package-Level Lazy Imports
    console.print(Rule("", style="dim"))
    console.print(
        "\n[bold blue]Section 2: Validating Package-Level Lazy Imports[/bold blue]"
    )
    console.print("[dim]Checking __init__.py lazy import patterns (__all__, _dynamic_imports, __getattr__)...[/dim]\n")

    pkg_errors, pkg_warnings, pkg_info = validate_package_level_imports()

    if pkg_errors or pkg_warnings or pkg_info:
        if is_tty():
            display_package_errors_as_panels(pkg_errors, pkg_warnings, pkg_info)
        else:
            for error in pkg_errors:
                console.print(f"ERROR | {error.module_name} | {error.message}")
            for warning in pkg_warnings:
                console.print(f"WARNING | {warning.module_name} | {warning.message}")
            for i in pkg_info:
                console.print(f"INFO | {i.module_name} | {i.message}")

        if pkg_errors:
            exit_code = 1
    else:
        if is_tty():
            console.print("[bold green]✓ All package-level lazy imports are valid.[/bold green]")
        else:
            console.print("All package-level lazy imports are valid.")

    # Final Summary
    console.print(Rule("", style="dim"))

    total_function_errors = len(function_errors)
    total_pkg_errors = len(pkg_errors)
    total_pkg_warnings = len(pkg_warnings)

    if exit_code == 0:
        console.print("\n[bold green]✅ All lazy import validations passed![/bold green]\n")
    else:
        console.print(
            f"\n[bold red]❌ Validation failed:[/bold red] "
            f"{total_function_errors} function call error(s), "
            f"{total_pkg_errors} package-level error(s), "
            f"{total_pkg_warnings} package-level warning(s)\n"
        )

    return exit_code


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Allow specifying paths via command line arguments
        paths = [Path(arg) for arg in sys.argv[1:]]
        sys.exit(main(paths))
    else:
        sys.exit(main())
