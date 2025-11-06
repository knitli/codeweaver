#!/usr/bin/env -S uv run -s
# sourcery skip: no-complex-if-expressions
# ///script
# python-version: ">=3.12"
# dependencies: ["rich"]
# ////script
"""Validate lazy imports in the codebase.

Our `lazy_import` function is really useful for reducing startup time and avoiding circular imports, but when modules or objects are renamed or removed, the lazy imports can break silently until runtime. This script scans the codebase for all instances of `lazy_import` and attempts to import the specified modules and objects to ensure they exist.
"""

import importlib
import re

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from codeweaver.cli.utils import format_file_link, is_tty


console = Console(markup=True, emoji=True)


IMPORT_PATTERN = re.compile(
    r'lazy_import\([\s\n]*"(?P<module>[A-Za-z0-9_.]+)"\s*,?[\s\n]*"(?P<object>[A-Za-z0-9_.]+)"\s*?[\s\n]*\)'
)

# All mise tasks operate relative to the src/codeweaver directory
SRC_DIR = Path("src/codeweaver")


def display_errors_as_panels(errors: list[tuple[str, str, str, str]]) -> None:
    """Display errors as individual panels with full-width links."""
    console.print(
        f"\n[bold red]Found {len(errors)} Lazy Import Validation Error{'s' if len(errors) != 1 else ''}[/bold red]\n"
    )

    for file_ref, module, obj, status in errors:
        # Full-width link on first line, details below
        content = (
            f"[cyan]{file_ref}[/cyan]\n"
            f"[yellow]Module:[/yellow] {module}  "
            f"[yellow]Object:[/yellow] {obj}  "
            f"[yellow bold]Status:[/yellow bold] {status}"
        )
        console.print(Panel(content, border_style="red", padding=(0, 1)))


def line_number_from_position(text: str, position: int) -> int:
    """Get the line number from a character position in the text."""
    return text.count("\n", 0, position) + 1


def validate_lazy_imports(paths: list[Path] | None = None) -> None:
    """Validate lazy imports in the codebase."""
    errors = []
    console.print("[bold blue]Validating lazy imports...[/bold blue]")
    search_paths: list[Path] = [] if paths else list(SRC_DIR.rglob("*.py"))
    if paths:
        temp_paths: set[Path] = set()
        for path in paths:
            if path.is_dir():
                temp_paths.update(path.rglob("*.py"))
            elif path.suffix == ".py":
                temp_paths.add(path)
        search_paths = list(temp_paths)
    for py_file in search_paths:
        content = py_file.read_text(encoding="utf-8")

        for match in IMPORT_PATTERN.finditer(content):
            module = match.group("module").strip('" \n\t')
            obj = match.group("object")
            if obj:
                # ruff thinks this is misleading, so let's be clear: we're stripping any commas, quotes or spaces from both sides:
                obj = obj.strip(', " \n\t')  # noqa: B005

            # Attempt to import the module and object
            try:
                imported_module = importlib.import_module(module)
                if obj and not hasattr(imported_module, obj):
                    errors.append(
                        # construct the tuple for table printing
                        (
                            f"{format_file_link(py_file, line_number_from_position(content, match.span()[0]))}",
                            module,
                            obj,
                            "[bold red]MISSING OBJECT[/bold red]",
                        )
                        if is_tty()
                        else (
                            f"{py_file}:{line_number_from_position(content, match.span()[0])}",
                            module,
                            obj,
                            "MISSING OBJECT",
                        )
                    )
            except ImportError:
                errors.append(
                    (
                        f"{format_file_link(py_file, line_number_from_position(content, match.span()[0]))}",
                        module,
                        obj,
                        "[bold red]IMPORT ERROR[/bold red]",
                    )
                    if is_tty()
                    else (
                        f"{py_file}:{line_number_from_position(content, match.span()[0])}",
                        module,
                        obj,
                        "IMPORT ERROR",
                    )
                )
            except Exception as e:
                errors.append(
                    (
                        f"{format_file_link(py_file, line_number_from_position(content, match.span()[0]))}",
                        module,
                        obj,
                        f"[bold red]ERROR: {e!s}[/bold red]",
                    )
                    if is_tty()
                    else (
                        f"{py_file}:{line_number_from_position(content, match.span()[0])}",
                        module,
                        obj,
                        f"ERROR: {e!s}",
                    )
                )

    if errors:
        if is_tty():
            display_errors_as_panels(errors)
        else:
            for error in errors:
                console.print(" | ".join(error))
        raise RuntimeError(
            f"Lazy import validation failed with {len(errors)} error{'s' if len(errors) > 1 else ''}."
        )
    console.print("[bold green]All lazy imports are valid.[/bold green]")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Allow specifying paths via command line arguments
        paths = [Path(arg) for arg in sys.argv[1:]]
        validate_lazy_imports(paths)
    else:
        validate_lazy_imports()
