#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""AST-based section parser for __init__.py code preservation.

This module implements Phase 2 of the code preservation system by parsing
existing __init__.py files and identifying:
- Managed sections (TYPE_CHECKING, _dynamic_imports, __all__, __dir__, __getattr__)
- Preserved sections (user imports, classes, functions, type aliases, constants)

The parser uses Python's ast module to accurately identify different code
sections while preserving formatting and comments.
"""

from __future__ import annotations

import ast

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast


if TYPE_CHECKING:
    from collections.abc import Sequence


class _PreservedData(TypedDict):
    """Internal type for preserved code extraction."""

    code: str
    docstring: str | None
    managed_lines: list[tuple[int, int]]
    preserved_lines: list[tuple[int, int]]


@dataclass(frozen=True)
class ParsedSections:
    """Result of parsing an existing __init__.py file.

    Attributes:
        preserved_code: User code to preserve (formatted, ready for injection)
        had_type_checking: Whether file had a TYPE_CHECKING block
        had_dynamic_imports: Whether file had _dynamic_imports assignment
        had_getattr: Whether file had __getattr__ assignment
        had_all: Whether file had __all__ assignment
        had_dir: Whether file had __dir__() function
        docstring: Module docstring if present
        managed_lines: Line numbers of managed sections for debugging
        preserved_lines: Line numbers of preserved sections for debugging
    """

    preserved_code: str
    had_type_checking: bool
    had_dynamic_imports: bool
    had_getattr: bool
    had_all: bool
    had_dir: bool
    docstring: str | None
    managed_lines: list[tuple[int, int]]  # (start, end) for each managed section
    preserved_lines: list[tuple[int, int]]  # (start, end) for each preserved section


class SectionParser:
    """AST-based parser for identifying managed vs preserved code sections."""

    # Sentinel comment for existing managed sections
    SENTINEL = "# === MANAGED EXPORTS ==="

    def __init__(self):
        """Initialize section parser."""
        self._managed_nodes: list[ast.AST] = []
        self._preserved_nodes: list[ast.AST] = []

    def parse_file(self, file_path: Path) -> ParsedSections:
        """Parse an existing __init__.py file and identify sections.

        Args:
            file_path: Path to __init__.py file to parse

        Returns:
            ParsedSections with preserved code and metadata

        Raises:
            SyntaxError: If file has syntax errors
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        return self.parse_content(content)

    def parse_content(self, content: str) -> ParsedSections:
        """Parse __init__.py content and identify sections.

        Args:
            content: File content to parse

        Returns:
            ParsedSections with preserved code and metadata

        Raises:
            SyntaxError: If content has syntax errors
        """
        # Check for sentinel-based managed section (legacy/current system)
        if self.SENTINEL in content:
            return self._parse_sentinel_based(content)

        # Parse with AST for detailed section identification
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            raise SyntaxError(f"Syntax error at line {e.lineno}: {e.msg}") from e

        # Identify sections
        flags = self._identify_managed_sections(tree)
        preserved = self._extract_preserved_code(tree, content)

        return ParsedSections(
            preserved_code=preserved["code"],
            had_type_checking=flags["had_type_checking"],
            had_dynamic_imports=flags["had_dynamic_imports"],
            had_getattr=flags["had_getattr"],
            had_all=flags["had_all"],
            had_dir=flags["had_dir"],
            docstring=preserved["docstring"],
            managed_lines=preserved["managed_lines"],
            preserved_lines=preserved["preserved_lines"],
        )

    def _parse_sentinel_based(self, content: str) -> ParsedSections:
        """Parse file using sentinel-based section detection.

        This is for backwards compatibility with the current system
        that uses SENTINEL comments to mark managed sections.

        Args:
            content: File content with sentinel marker

        Returns:
            ParsedSections with preserved code above sentinel
        """
        parts = content.split(self.SENTINEL)
        if len(parts) != 2:
            # Multiple sentinels or malformed - fall back to AST parsing
            return self.parse_content(content.replace(self.SENTINEL, ""))

        preserved = parts[0].rstrip()
        managed = parts[1].lstrip()

        # Detect what's in the managed section
        flags = {
            "had_type_checking": "if TYPE_CHECKING:" in managed,
            "had_dynamic_imports": "_dynamic_imports" in managed,
            "had_getattr": "__getattr__" in managed,
            "had_all": "__all__" in managed,
            "had_dir": "def __dir__()" in managed,
        }

        # Extract docstring from preserved section
        docstring: str | None = None
        try:
            tree = ast.parse(preserved)
            if (
                tree.body
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)
            ):
                docstring = tree.body[0].value.value
        except SyntaxError:
            pass

        # Count lines for debugging
        preserved_lines_count = preserved.count("\n") + 1
        managed_lines = [(preserved_lines_count + 1, content.count("\n") + 1)]
        preserved_lines = [(1, preserved_lines_count)]

        return ParsedSections(
            preserved_code=preserved,
            docstring=docstring,
            managed_lines=managed_lines,
            preserved_lines=preserved_lines,
            **flags,
        )

    def _identify_managed_sections(self, tree: ast.Module) -> dict[str, bool]:  # noqa: C901
        """Identify which managed sections are present in the AST.

        Args:
            tree: Parsed AST

        Returns:
            Dict with boolean flags for each managed section type
        """
        flags = {
            "had_type_checking": False,
            "had_dynamic_imports": False,
            "had_getattr": False,
            "had_all": False,
            "had_dir": False,
        }

        for node in ast.walk(tree):
            # TYPE_CHECKING block: if TYPE_CHECKING:
            if isinstance(node, ast.If):
                if self._is_type_checking_block(node):
                    flags["had_type_checking"] = True

            # Assignments: _dynamic_imports = ..., __getattr__ = ..., __all__ = ...
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "_dynamic_imports":
                            flags["had_dynamic_imports"] = True
                        elif target.id == "__getattr__":
                            flags["had_getattr"] = True
                        elif target.id == "__all__":
                            flags["had_all"] = True

            # __dir__() function definition
            elif isinstance(node, ast.FunctionDef) and node.name == "__dir__":
                flags["had_dir"] = True

        return flags

    def _is_type_checking_block(self, node: ast.If) -> bool:
        """Check if an If node is a TYPE_CHECKING block.

        Args:
            node: AST If node to check

        Returns:
            True if this is 'if TYPE_CHECKING:'
        """
        # Pattern: if TYPE_CHECKING:
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            return True

        # Pattern: if typing.TYPE_CHECKING: (less common)
        return (
            isinstance(node.test, ast.Attribute)
            and node.test.attr == "TYPE_CHECKING"
            and isinstance(node.test.value, ast.Name)
            and node.test.value.id == "typing"
        )

    def _is_managed_node(self, node: ast.AST) -> bool:
        """Check if a node is part of a managed section.

        Args:
            node: AST node to check

        Returns:
            True if node is part of managed code
        """
        # TYPE_CHECKING blocks
        if isinstance(node, ast.If) and self._is_type_checking_block(node):
            return True

        # Managed assignments
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in (
                    "_dynamic_imports",
                    "__getattr__",
                    "__all__",
                ):
                    return True

        # __dir__() function
        if isinstance(node, ast.FunctionDef) and node.name == "__dir__":
            return True

        # Required imports for lazy loading infrastructure
        return isinstance(node, (ast.Import, ast.ImportFrom)) and self._is_required_import(node)

    def _is_required_import(self, node: ast.Import | ast.ImportFrom) -> bool:
        """Check if an import is part of required lazy loading infrastructure.

        Args:
            node: Import or ImportFrom node

        Returns:
            True if this is a required infrastructure import
        """
        # from __future__ import annotations
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            return any(alias.name == "annotations" for alias in node.names)

        # from typing import TYPE_CHECKING
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            return any(alias.name == "TYPE_CHECKING" for alias in node.names)

        # from types import MappingProxyType
        if isinstance(node, ast.ImportFrom) and node.module == "types":
            return any(alias.name == "MappingProxyType" for alias in node.names)

        # from codeweaver.core.utils.lazy_importer import create_lazy_getattr
        if isinstance(node, ast.ImportFrom) and node.module and "lazy_importer" in node.module:
            return any(alias.name == "create_lazy_getattr" for alias in node.names)

        return False

    def _extract_preserved_code(self, tree: ast.Module, original_content: str) -> _PreservedData:
        """Extract preserved code sections from the AST.

        Args:
            tree: Parsed AST
            original_content: Original file content for extracting text

        Returns:
            Preserved data with code, docstring, and line numbers
        """
        # Module docstring (first node if it's a string constant)
        docstring = None
        start_index = 0

        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            docstring = tree.body[0].value.value
            start_index = 1  # Skip docstring node

        # Collect preserved nodes (all non-managed top-level nodes)
        preserved_nodes: list[ast.AST] = []
        managed_lines: list[tuple[int, int]] = []

        for node in tree.body[start_index:]:
            if self._is_managed_node(node):
                # Track managed section lines
                if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    managed_lines.append((node.lineno, node.end_lineno or node.lineno))
            else:
                preserved_nodes.append(node)

        # Extract preserved code using line numbers
        preserved_code = self._extract_code_for_nodes(preserved_nodes, original_content)

        # Track preserved lines
        preserved_lines = cast(
            list[tuple[int, int]],
            [
                (node.lineno, node.end_lineno or node.lineno)
                for node in preserved_nodes
                if hasattr(node, "lineno") and hasattr(node, "end_lineno")
            ],
        )

        return _PreservedData(
            code=preserved_code,
            docstring=docstring,
            managed_lines=managed_lines,
            preserved_lines=preserved_lines,
        )

    def _extract_code_for_nodes(self, nodes: Sequence[ast.AST], original_content: str) -> str:
        """Extract source code for given AST nodes.

        Args:
            nodes: AST nodes to extract code for
            original_content: Original file content

        Returns:
            Extracted code as formatted string
        """
        if not nodes:
            return ""

        lines = original_content.splitlines()
        extracted_sections = []

        for node in nodes:
            if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
                continue

            # Extract lines for this node (1-indexed to 0-indexed)
            start = node.lineno - 1  # ty: ignore[unsupported-operator]
            end = node.end_lineno or node.lineno

            node_lines = lines[start:end]
            if node_lines:
                extracted_sections.append("\n".join(node_lines))

        # Join sections with double newline for readability
        return "\n\n".join(extracted_sections).rstrip()


def parse_init_file(file_path: Path) -> ParsedSections:
    """Parse an existing __init__.py file (convenience function).

    Args:
        file_path: Path to __init__.py file

    Returns:
        ParsedSections with preserved code and metadata
    """
    parser = SectionParser()
    return parser.parse_file(file_path)


__all__ = ["ParsedSections", "SectionParser", "parse_init_file"]
