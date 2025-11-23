#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: avoid-single-character-names-variables, name-type-suffix
"""
Programmatic fixer for common ruff patterns that can't be auto-fixed.
Handles TRY401, G004, and TRY300 violations using regex-based source transformation.
"""

import ast
import re
import sys

from pathlib import Path


class SourcePatternFixer:
    """Source-code based fixer for ruff violations."""

    def __init__(self) -> None:
        """Initialize the fixer."""
        self.changes_made = False
        self.fixes_applied: set[str] = set()

    def fix_logging_fstrings(self, content: str) -> str:
        """Fix G004: Convert f-strings in logging calls to % formatting."""
        # Pattern for logging calls with f-strings
        pattern = r'((?:logger|logging|log)\.(?:debug|info|warning|error|critical|exception))\(f"([^"]*?)"\)'

        def replace_fstring(match: re.Match[str]) -> str:
            method_call = match.group(1)
            fstring_content = match.group(2)

            # Convert {variable} to %s and collect variables
            variables = []

            def extract_var(var_match: re.Match[str]) -> str:
                var_name = var_match.group(1)
                variables.append(var_name)
                return "%s"

            # Replace {var} with %s
            format_str = re.sub(r"\{([^}]+)\}", extract_var, fstring_content)

            if variables:
                serialized_vars = ", ".join(variables)
                result = f'{method_call}("{format_str}", {serialized_vars})'
            else:
                result = f'{method_call}("{format_str}")'

            self.changes_made = True
            self.fixes_applied.add("G004")
            return result

        return re.sub(pattern, replace_fstring, content)

    def fix_redundant_exception_logging(self, content: str) -> str:
        """Fix TRY401: Remove redundant exception references in logging.exception calls."""
        patterns = [
            # logging.exception("Error: ")
            (r'(\.exception\([f"]?)([^"]*?)\{(e|exc|exception)\}([^"]*?)(["]?\))', r"\1\2\4\5"),
            # logging.exception("Error: ")
            (
                r'(\.exception\(["]?)([^"]*?)%s([^"]*?)(["]?),\s*(e|exc|exception)\s*\)',
                r"\1\2\3\4)",
            ),
            # logging.exception("Error occurred")  -> logging.exception("Error occurred")
            (r'(\.exception\(["][^"]*?["])\s*,\s*(e|exc|exception)\s*\)', r"\1)"),
        ]

        for pattern, replacement in patterns:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                self.changes_made = True
                self.fixes_applied.add("TRY401")

        return content

    def fix_try_return_statements(self, content: str) -> str:
        # sourcery skip: no-long-functions
        """Fix TRY300: Move return statements from try to else block."""
        lines = content.split("\n")
        result_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]
            result_lines.append(line)

            i += 1

            # Look for try: statements
            if re.match(r"\s*try\s*:", line):
                try_indent = len(line) - len(line.lstrip())
                try_block_lines = []
                # Collect try block
                while i < len(lines):
                    current_line = lines[i]
                    if not current_line.strip():  # Empty line
                        try_block_lines.append(current_line)
                        i += 1
                        continue

                    current_indent = len(current_line) - len(current_line.lstrip())

                    if current_indent <= try_indent:
                        break

                    try_block_lines.append(current_line)
                    i += 1
                # Check if try block ends with return
                non_empty_lines = [l for l in try_block_lines if l.strip()]  # noqa: E741
                if non_empty_lines and re.match(r"\s*return\b", non_empty_lines[-1]):
                    # Look for except blocks
                    has_except = False
                    except_blocks = []

                    while i < len(lines):
                        current_line = lines[i]
                        if not current_line.strip():
                            except_blocks.append(current_line)
                            i += 1
                            continue

                        current_indent = len(current_line) - len(current_line.lstrip())

                        if current_indent != try_indent or not re.match(
                            r"\s*except\b", current_line
                        ):
                            break

                        has_except = True
                        except_blocks.append(current_line)
                        i += 1

                        # Collect except block content
                        while i < len(lines):
                            except_line = lines[i]
                            if not except_line.strip():
                                except_blocks.append(except_line)
                                i += 1
                                continue

                            except_indent = len(except_line) - len(except_line.lstrip())
                            if except_indent <= try_indent:
                                break
                            except_blocks.append(except_line)
                            i += 1
                    if has_except:
                        # Move return to else block
                        return_line = try_block_lines.pop()

                        # Add modified try block
                        result_lines.extend(try_block_lines)

                        # Add except blocks
                        result_lines.extend(except_blocks)

                        # Add else block with return
                        else_indent = " " * try_indent
                        result_lines.extend((f"{else_indent}else:", return_line))

                        self.changes_made = True
                        self.fixes_applied.add("TRY300")
                        continue

                # No fixes needed, add try block as-is
                result_lines.extend(try_block_lines)
        return "\n".join(result_lines)

    def fix_content(self, content: str) -> str:
        """Apply all fixes to the content."""
        self.changes_made = False
        self.fixes_applied.clear()

        # Apply fixes in order
        content = self.fix_logging_fstrings(content)
        content = self.fix_redundant_exception_logging(content)
        return self.fix_try_return_statements(content)


def fix_file(file_path: Path) -> bool:
    """Fix a single Python file. Returns True if changes were made."""
    try:
        content = file_path.read_text(encoding="utf-8")

        # Validate syntax before processing
        _ = ast.parse(content)

        fixer = SourcePatternFixer()
        new_content = fixer.fix_content(content)

        if fixer.changes_made:
            _ = file_path.write_text(new_content, encoding="utf-8")
            print(f"Applied fixes: {', '.join(sorted(fixer.fixes_applied))}")
            return True
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Warning: Could not process {file_path}: {e}")
    return False


def main() -> None:
    """Main entry point."""
    args = sys.argv
    if len(args) < 2 or args[1] == ".":
        args = [args[0], "./src", "./tests", "./scripts"]
    files_changed = 0
    total_files = 0

    for arg in sys.argv[1:]:
        path = Path(arg)

        if path.is_file() and path.suffix == ".py":
            total_files += 1
            if fix_file(path):
                files_changed += 1
                print(f"Fixed: {path}")

        elif path.is_dir():
            for py_file in path.rglob("*.py"):
                total_files += 1
                if fix_file(py_file):
                    files_changed += 1
                    print(f"Fixed: {py_file}")

        else:
            print(f"Warning: {path} is not a Python file or directory")

    print(f"\nProcessed {total_files} files, fixed {files_changed} files")


if __name__ == "__main__":
    main()
