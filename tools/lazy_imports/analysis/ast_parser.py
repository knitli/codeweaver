#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""AST parser for extracting exports from Python files.

Parses Python source code and extracts exportable symbols:
- Classes
- Functions (top-level only)
- Variables
- Constants (SCREAMING_SNAKE_CASE)
- Type aliases (TypeAlias annotation)
"""

from __future__ import annotations

import ast
import hashlib
import re
import time

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tools.lazy_imports.common.types import (
    AnalysisResult,
    ExportNode,
    MemberType,
    PropagationLevel,
    RuleAction,
)


if TYPE_CHECKING:
    from tools.lazy_imports.export_manager.rules import RuleEngine


@dataclass
class ParsedSymbol:
    """A symbol extracted from AST."""

    name: str
    member_type: MemberType
    line_number: int
    docstring: str | None


class ASTParser:
    """Parse Python files and extract exports."""

    def __init__(self, rule_engine: RuleEngine):
        """Initialize AST parser.

        Args:
            rule_engine: Rule engine for determining propagation levels
        """
        self.rule_engine = rule_engine

    def parse_file(self, file_path: Path, module_path: str) -> AnalysisResult:
        """Parse a Python file and extract exports.

        Args:
            file_path: Path to Python file
            module_path: Module path (e.g., "codeweaver.core.types")

        Returns:
            AnalysisResult with exports and metadata

        Example:
            >>> parser = ASTParser(rule_engine)
            >>> result = parser.parse_file(Path("core/types.py"), "codeweaver.core.types")
            >>> len(result.exports)
            45
        """
        # Read and hash file
        content = file_path.read_text(encoding="utf-8")
        file_hash = hashlib.sha256(content.encode()).hexdigest()

        # Try to parse
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            # Return empty result for syntax errors
            # The validator will catch these
            return AnalysisResult(
                exports=[],
                imports=[],
                file_hash=file_hash,
                analysis_timestamp=time.time(),
                schema_version="1.0",
            )

        # Extract symbols
        symbols = self._extract_symbols(tree, file_path)

        # Convert to ExportNodes with rule evaluation
        exports = []
        for symbol in symbols:
            # Evaluate rules to determine action and propagation
            result = self.rule_engine.evaluate(symbol.name, module_path, symbol.member_type)

            # Skip if excluded
            if result.action == RuleAction.EXCLUDE:
                continue

            # Skip if no decision (shouldn't happen with proper rules)
            if result.action == RuleAction.NO_DECISION:
                continue

            # Create ExportNode
            export = ExportNode(
                name=symbol.name,
                module=module_path,
                member_type=symbol.member_type,
                propagation=result.propagation or PropagationLevel.PARENT,
                source_file=file_path,
                line_number=symbol.line_number,
                defined_in=module_path,
                docstring=symbol.docstring,
                propagates_to=set(),  # Will be populated by PropagationGraph
                dependencies=set(),  # Will be populated by PropagationGraph
            )
            exports.append(export)

        # Extract imports
        imports = self._extract_imports(tree)

        return AnalysisResult(
            exports=exports,
            imports=imports,
            file_hash=file_hash,
            analysis_timestamp=time.time(),
            schema_version="1.0",
        )

    def _extract_symbols(self, tree: ast.Module, file_path: Path) -> list[ParsedSymbol]:
        """Extract all exportable symbols from AST.

        Args:
            tree: Parsed AST module
            file_path: Path to source file (for error reporting)

        Returns:
            List of parsed symbols
        """
        symbols = []

        # Only process top-level nodes
        for node in tree.body:
            # Classes
            if isinstance(node, ast.ClassDef):
                symbols.append(
                    ParsedSymbol(
                        name=node.name,
                        member_type=MemberType.CLASS,
                        line_number=node.lineno,
                        docstring=ast.get_docstring(node),
                    )
                )

            # Functions (top-level only, not methods)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                symbols.append(
                    ParsedSymbol(
                        name=node.name,
                        member_type=MemberType.FUNCTION,
                        line_number=node.lineno,
                        docstring=ast.get_docstring(node),
                    )
                )

            # Variables and constants (annotated assignments)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    member_type = self._determine_variable_type(node.target.id, node.annotation)
                    symbols.append(
                        ParsedSymbol(
                            name=node.target.id,
                            member_type=member_type,
                            line_number=node.lineno,
                            docstring=None,
                        )
                    )

            # Variables and constants (regular assignments)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        member_type = self._determine_variable_type(target.id, None)
                        symbols.append(
                            ParsedSymbol(
                                name=target.id,
                                member_type=member_type,
                                line_number=node.lineno,
                                docstring=None,
                            )
                        )

        return symbols

    def _determine_variable_type(self, name: str, annotation: ast.expr | None) -> MemberType:
        """Determine if variable is a constant, type alias, or regular variable.

        Args:
            name: Variable name
            annotation: Type annotation (if any)

        Returns:
            Appropriate MemberType
        """
        # Check for TypeAlias annotation
        if annotation:
            if isinstance(annotation, ast.Name) and annotation.id == "TypeAlias":
                return MemberType.TYPE_ALIAS
            # Also check for typing.TypeAlias
            if isinstance(annotation, ast.Attribute) and annotation.attr == "TypeAlias":
                return MemberType.TYPE_ALIAS

        # Check for SCREAMING_SNAKE_CASE constant pattern
        if re.match(r"^[A-Z][A-Z0-9_]*$", name):
            return MemberType.CONSTANT

        # Default to variable
        return MemberType.VARIABLE

    def _extract_imports(self, tree: ast.Module) -> list[str]:
        """Extract import statements as strings.

        Args:
            tree: Parsed AST module

        Returns:
            List of import statement strings
        """
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_str = f"import {alias.name}"
                    if alias.asname:
                        import_str += f" as {alias.asname}"
                    imports.append(import_str)

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level = "." * node.level  # Relative imports
                for alias in node.names:
                    import_str = f"from {level}{module} import {alias.name}"
                    if alias.asname:
                        import_str += f" as {alias.asname}"
                    imports.append(import_str)

        return imports


__all__ = ["ASTParser", "ParsedSymbol"]
