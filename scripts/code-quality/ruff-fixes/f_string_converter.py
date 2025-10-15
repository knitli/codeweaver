#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: snake-case-functions
"""
Convert logging f-strings to extra="" argument using AST parsing.
Handles G004 violations that ast-grep can't easily transform.
"""

import ast
import re
import sys

from pathlib import Path
from typing import cast


class FStringConverter(ast.NodeTransformer):
    """Convert f-strings in logging calls to %-style and move complex values to extra=."""

    def __init__(self) -> None:
        """Initialize FStringConverter."""
        self.changes_made = False

    def visit_Call(self, node: ast.Call) -> ast.Call:
        """Convert f-strings in logging method calls."""
        self.generic_visit(node)

        # Check if this is a logging call
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in ("logger", "logging", "log")
            and node.func.attr in ("debug", "info", "warning", "error", "critical", "exception")
            and node.args
            and isinstance(node.args[0], ast.JoinedStr)
        ):
            format_str, msg_args, extra_items = self._convert_fstring(node.args[0])

            # Replace f-string with format string
            node.args[0] = ast.Constant(value=format_str)

            # Add extracted variables as additional arguments for message rendering
            node.args.extend(msg_args)

            # Add complex values to `extra=`
            self._add_extra_items(node, extra_items)

            self.changes_made = True

        return node

    def _is_simple_expr(self, expr: ast.expr) -> bool:
        """Return True if expr is a literal simple constant (str, bytes, int, float, complex, bool, None)."""
        if isinstance(expr, ast.Constant):
            return isinstance(expr.value, str | bytes | int | float | complex | bool | type(None))
        return False

    def _key_for_expr(self, expr: ast.expr) -> str:
        """Create a stable key name for an expression to use in extra={}."""
        try:
            raw = ast.unparse(expr)
        except Exception:
            raw = "value"
        key = re.sub(r"[^0-9a-zA-Z_]+", "_", raw).strip("_") or "value"
        if key[0].isdigit():
            key = f"v_{key}"
        return key[:80]

    def _build_repr(self, expr: ast.expr) -> ast.Call:
        """Wrap an expression in repr() for lightweight message rendering."""
        return ast.Call(func=ast.Name(id="repr", ctx=ast.Load()), args=[expr], keywords=[])

    def _add_extra_items(self, node: ast.Call, items: list[tuple[str, ast.expr]]) -> None:
        """Merge items into node.keywords under extra=.

        If extra exists and is a dict literal, extend it. Otherwise, create
        a merged dict with dict-unpack: {**existing_extra, ...}.
        """
        if not items:
            return

        new_keys: list[ast.expr | None] = [ast.Constant(k) for k, _ in items]
        new_vals: list[ast.expr] = [v for _, v in items]

        existing_kw = next((kw for kw in node.keywords if kw.arg == "extra"), None)

        if existing_kw is None:
            node.keywords.append(
                ast.keyword(arg="extra", value=ast.Dict(keys=new_keys, values=new_vals))
            )
            return

        # Merge with existing extra
        if isinstance(existing_kw.value, ast.Dict):
            existing_kw.value.keys.extend(new_keys)
            existing_kw.value.values.extend(new_vals)
        else:
            # Build {**existing_extra, ...new items...}
            merged = ast.Dict(keys=[None, *new_keys], values=[existing_kw.value, *new_vals])
            existing_kw.value = merged

    def _convert_fstring(
        self, fstring: ast.JoinedStr
    ) -> tuple[str, list[ast.expr], list[tuple[str, ast.expr]]]:
        """Convert JoinedStr (f-string) to format string, message args, and extra items.

        - Simple literal constants become message args directly.
        - Non-simple expressions use repr(expr) in the message args and are
          added to extra={key: expr} for structured logging.
        """
        format_parts: list[str] = []
        msg_args: list[ast.expr] = []
        extra_items: list[tuple[str, ast.expr]] = []

        for value in fstring.values:
            if isinstance(value, ast.Constant):
                # String literal part
                format_parts.append(cast(str, value.value))
            elif isinstance(value, ast.FormattedValue):
                # Expression part - always %s in message
                format_parts.append("%s")
                expr = value.value
                if self._is_simple_expr(expr):
                    msg_args.append(expr)
                else:
                    msg_args.append(self._build_repr(expr))
                    extra_items.append((self._key_for_expr(expr), expr))

        format_string = "".join(format_parts)
        return format_string, msg_args, extra_items


def convert_file(file_path: Path) -> bool:
    """Convert f-strings in a single file. Returns True if changes were made."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        converter = FStringConverter()
        new_tree = converter.visit(tree)
        ast.fix_missing_locations(new_tree)

        if converter.changes_made:
            # Convert back to source
            new_content = ast.unparse(new_tree)
            file_path.write_text(new_content, encoding="utf-8")
            return True

    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Warning: Could not process {file_path}: {e}", file=sys.stderr)

    return False


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python fstring_converter.py <file_or_directory> [file2] ...")
        sys.exit(1)

    files_changed = 0
    total_files = 0

    for arg in sys.argv[1:]:
        path = Path(arg)

        if path.is_file() and path.suffix == ".py":
            total_files += 1
            if convert_file(path):
                files_changed += 1
                print(f"✅ Converted f-strings in: {path}")

        elif path.is_dir():
            for py_file in path.rglob("*.py"):
                total_files += 1
                if convert_file(py_file):
                    files_changed += 1
                    print(f"✅ Converted f-strings in: {py_file}")

        else:
            print(f"Warning: {path} is not a Python file or directory", file=sys.stderr)

    print(f"\n📊 Processed {total_files} files, converted f-strings in {files_changed} files")


if __name__ == "__main__":
    main()
