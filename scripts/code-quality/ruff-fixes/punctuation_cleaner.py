#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: snake-case-functions
"""
Clean up trailing punctuation when removing redundant exceptions from logging calls.
This handles the cases that ast-grep can't handle with complex pattern matching.
"""

import ast
import re
import sys

from pathlib import Path


class PunctuationCleaner(ast.NodeTransformer):
    """Clean up logging.exception calls that have redundant exception references with trailing punctuation."""

    def __init__(self) -> None:
        """Initialize the cleaner."""
        self.changes_made = False

    def visit_Call(self, node: ast.Call) -> ast.Call:
        """Clean up logging.exception calls with redundant exception references."""
        self.generic_visit(node)

        # Check if this is a logging.exception call and % format call with redundant exception
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in ("logger", "logging", "log")
            and node.func.attr == "exception"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and self._is_exception_variable(node.args[-1])
        ):
            cleaned_message = self._clean_message_punctuation(node.args[0].value)
            if cleaned_message != node.args[0].value:
                # Update the message and remove the exception argument
                node.args[0] = ast.Constant(value=cleaned_message)
                node.args = node.args[:-1]  # Remove the exception argument
                self.changes_made = True

        return node

    def _is_exception_variable(self, node: ast.expr) -> bool:
        """Check if this is likely an exception variable (e, exc, exception)."""
        if isinstance(node, ast.Name):
            return node.id in ("e", "exc", "exception")
        return False

    def _clean_message_punctuation(self, message: str) -> str:
        """Clean trailing punctuation patterns when removing exception from logging message."""
        # Common patterns to clean up
        patterns = [
            (r": %s$", ""),  # "Error: %s" -> "Error"
            (r":\s*%s$", ""),  # "Error: %s" -> "Error"
            (r" - %s$", ""),  # "Error - %s" -> "Error"
            (r"-\s*%s$", ""),  # "Error-%s" -> "Error"
            (r", %s$", ""),  # "Error, %s" -> "Error"
            (r",\s*%s$", ""),  # "Error,%s" -> "Error"
            (r" \(%s\)$", ""),  # "Error (%s)" -> "Error"
            (r"\(%s\)$", ""),  # "Error(%s)" -> "Error"
            (r" %s\.$", ""),  # "Error %s." -> "Error"
            (r"\s*%s\.$", ""),  # "Error%s." -> "Error"
        ]

        for pattern, replacement in patterns:
            message = re.sub(pattern, replacement, message)

        return message.rstrip()  # Remove any trailing whitespace


def clean_file(file_path: Path) -> bool:
    """Clean punctuation in a single file. Returns True if changes were made."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        cleaner = PunctuationCleaner()
        new_tree = cleaner.visit(tree)

        if cleaner.changes_made:
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
        print("Usage: python punctuation_cleaner.py <file_or_directory> [file2] ...")
        sys.exit(1)

    files_changed = 0
    total_files = 0

    for arg in sys.argv[1:]:
        path = Path(arg)

        if path.is_file() and path.suffix == ".py":
            total_files += 1
            if clean_file(path):
                files_changed += 1
                print(f"✅ Cleaned punctuation in: {path}")

        elif path.is_dir():
            for py_file in path.rglob("*.py"):
                total_files += 1
                if clean_file(py_file):
                    files_changed += 1
                    print(f"✅ Cleaned punctuation in: {py_file}")

        else:
            print(f"Warning: {path} is not a Python file or directory", file=sys.stderr)

    print(f"\n📊 Processed {total_files} files, cleaned punctuation in {files_changed} files")


if __name__ == "__main__":
    main()
