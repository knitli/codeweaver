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
import sys
import time

from pathlib import Path

from tools.lazy_imports.analysis.ast_parser_overload import group_functions_by_name
from tools.lazy_imports.common.types import (
    AnalysisResult,
    DetectedSymbol,
    MemberType,
    SourceLocation,
    SymbolProvenance,
)


class ASTParser:
    """Parse Python files and extract exports."""

    def __init__(self):
        """Initialize AST parser."""

    def parse_file(self, file_path: Path, module_path: str) -> AnalysisResult:
        """Parse a Python file and extract exports.

        Args:
            file_path: Path to Python file
            module_path: Module path (e.g., "codeweaver.core.types")

        Returns:
            AnalysisResult with symbols and metadata
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
                symbols=[],
                imports=[],
                file_hash=file_hash,
                analysis_timestamp=time.time(),
                schema_version="1.0",
            )

        # Extract symbols (both defined and imported)
        defined_symbols = self._extract_symbols(tree, file_path)
        imported_symbols = self._extract_import_symbols(tree, file_path)
        all_symbols = defined_symbols + imported_symbols

        # Extract imports as strings for backward compatibility/caching
        imports = self._extract_imports(tree)

        return AnalysisResult(
            symbols=all_symbols,
            imports=imports,
            file_hash=file_hash,
            analysis_timestamp=time.time(),
            schema_version="1.0",
        )

    def _extract_symbols(self, tree: ast.Module, file_path: Path) -> list[DetectedSymbol]:
        """Extract all exportable symbols from AST.

        Args:
            tree: Parsed AST module
            file_path: Path to source file (for error reporting)

        Returns:
            List of detected symbols
        """
        symbols = []

        # Group functions by name to handle @overload correctly
        function_groups = group_functions_by_name(tree)

        # Only process top-level nodes
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbols.append(self._handle_class(node))
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if symbol := self._handle_function(node, function_groups):
                    symbols.append(symbol)
            elif isinstance(node, ast.TypeAlias):
                symbols.append(self._handle_type_alias(node))
            elif isinstance(node, ast.AnnAssign):
                if symbol := self._handle_annotated_assign(node):
                    symbols.append(symbol)
            elif isinstance(node, ast.Assign):
                symbols.extend(self._handle_assign(node))

        return symbols

    def _handle_class(self, node: ast.ClassDef) -> DetectedSymbol:
        """Handle class definition."""
        return self._create_symbol(
            name=node.name,
            member_type=MemberType.CLASS,
            location=SourceLocation(line=node.lineno),
            docstring=ast.get_docstring(node),
            provenance=SymbolProvenance.DEFINED_HERE,
            is_private=node.name.startswith("_"),
        )

    def _handle_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, function_groups: dict
    ) -> DetectedSymbol | None:
        """Handle function definition. Returns None if not the first definition."""
        func_name = node.name
        group = function_groups[func_name]

        # Only add symbol once per function name
        if node is not group["first_definition"]:
            return None

        is_overloaded = group["has_overload"]
        overload_count = group["overload_count"]
        has_implementation = group["has_implementation"]

        # Get docstring from implementation if available, else from first overload
        docstring = ast.get_docstring(group["implementation"] or node)

        return self._create_symbol(
            name=func_name,
            member_type=MemberType.FUNCTION,
            location=SourceLocation(line=node.lineno),
            docstring=docstring,
            provenance=SymbolProvenance.DEFINED_HERE,
            is_private=func_name.startswith("_"),
            metadata={
                "is_overloaded": is_overloaded,
                "overload_count": overload_count,
                "has_implementation": has_implementation,
            },
        )

    def _handle_type_alias(self, node: ast.TypeAlias) -> DetectedSymbol:
        """Handle type alias definition."""
        name = node.name.id if isinstance(node.name, ast.Name) else str(node.name)
        return self._create_symbol(
            name=name,
            member_type=MemberType.TYPE_ALIAS,
            location=SourceLocation(line=node.lineno),
            provenance=SymbolProvenance.DEFINED_HERE,
            is_private=name.startswith("_"),
            metadata={"style": "python3.12+"},
        )

    def _handle_annotated_assign(self, node: ast.AnnAssign) -> DetectedSymbol | None:
        """Handle annotated assignment. Returns None if not a Name target."""
        if not isinstance(node.target, ast.Name):
            return None

        member_type = self._determine_variable_type(node.target.id, node.annotation)
        metadata = {}
        if member_type == MemberType.TYPE_ALIAS:
            metadata["style"] = "pre-python3.12"

        return self._create_symbol(
            name=node.target.id,
            member_type=member_type,
            location=SourceLocation(line=node.lineno),
            provenance=SymbolProvenance.DEFINED_HERE,
            is_private=node.target.id.startswith("_"),
            metadata=metadata,
        )

    def _handle_assign(self, node: ast.Assign) -> list[DetectedSymbol]:
        """Handle regular assignment. Returns list of symbols."""
        symbols = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                member_type = self._determine_variable_type(target.id, None)
                symbols.append(
                    self._create_symbol(
                        name=target.id,
                        member_type=member_type,
                        location=SourceLocation(line=node.lineno),
                        provenance=SymbolProvenance.DEFINED_HERE,
                        is_private=target.id.startswith("_"),
                    )
                )
        return symbols

    def _determine_variable_type(self, name: str, annotation: ast.expr | None) -> MemberType:
        """Determine if variable is a constant, type alias, or regular variable."""
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

    def _extract_import_symbols(self, tree: ast.Module, file_path: Path) -> list[DetectedSymbol]:
        """Extract import statements as ParsedSymbol objects.

        Categorizes imports with heuristic metadata to help distinguish likely re-exports
        from internal use. The heuristics are:

        - Aliased imports (import X as Y, from X import Y as Z) → is_likely_reexport=True
        - Non-aliased imports → is_likely_reexport=False
        - is_stdlib metadata tracked separately (for rule system to use)

        The logic: if you alias an import, you're likely planning to expose it publicly.
        Why else rename it? Non-aliased imports are typically for internal use.

        Note: These are heuristics only. Final re-export decisions are made by the
        rule system during the decision phase. This metadata helps inform those rules.
        For example, rules might choose to never re-export stdlib imports regardless
        of aliasing.
        """
        symbols = []

        # Only process top-level imports
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # alias.name = module name (e.g., "sys")
                    # alias.asname = alias (e.g., "system") or None
                    export_name = alias.asname or alias.name
                    is_stdlib = self._is_stdlib_module(alias.name)

                    # Aliased imports are likely re-exports
                    # (why else would you alias if not to re-export?)
                    is_likely_reexport = bool(alias.asname)

                    symbols.append(
                        self._create_symbol(
                            name=export_name,
                            member_type=MemberType.IMPORTED,
                            location=SourceLocation(line=node.lineno),
                            provenance=SymbolProvenance.ALIAS_IMPORTED
                            if alias.asname
                            else SymbolProvenance.IMPORTED,
                            is_private=False,  # Imports are presumably public unless named _
                            original_name=alias.name,
                            original_source=None,  # Standard import, source is the name
                            metadata={
                                "import_type": "module",
                                "is_likely_reexport": is_likely_reexport,
                                "is_stdlib": is_stdlib,
                            },
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level = "." * node.level  # Relative imports
                import_path = f"{level}{module}" if level or module else ""
                is_stdlib = self._is_stdlib_module(module) if module else False

                for alias in node.names:
                    # alias.name = imported name (e.g., "Path")
                    # alias.asname = alias (e.g., "P") or None
                    export_name = alias.asname or alias.name

                    # Aliased imports are likely re-exports
                    # (why else would you alias if not to re-export?)
                    is_likely_reexport = bool(alias.asname)

                    symbols.append(
                        self._create_symbol(
                            name=export_name,
                            member_type=MemberType.IMPORTED,
                            location=SourceLocation(line=node.lineno),
                            provenance=SymbolProvenance.ALIAS_IMPORTED
                            if alias.asname
                            else SymbolProvenance.IMPORTED,
                            is_private=False,
                            original_name=alias.name,
                            original_source=import_path,
                            metadata={
                                "import_type": "from",
                                "is_likely_reexport": is_likely_reexport,
                                "is_stdlib": is_stdlib,
                            },
                        )
                    )

        return symbols

    def _extract_imports(self, tree: ast.Module) -> list[str]:
        """Extract import statements as strings."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_name = f"import {alias.name}"
                    if alias.asname:
                        import_name += f" as {alias.asname}"
                    imports.append(import_name)

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level = "." * node.level  # Relative imports
                for alias in node.names:
                    import_name = f"from {level}{module} import {alias.name}"
                    if alias.asname:
                        import_name += f" as {alias.asname}"
                    imports.append(import_name)

        return imports

    def _is_stdlib_module(self, module_name: str) -> bool:
        """Check if a module is from the Python standard library.

        Uses a simple heuristic: stdlib modules don't contain dots (top-level only).
        This covers common cases like sys, os, pathlib, typing, etc.

        Args:
            module_name: Name of the module to check

        Returns:
            True if likely a stdlib module, False otherwise
        """
        if not module_name:
            return False

        # Common stdlib modules (top-level only)
        common_stdlib = sys.stdlib_module_names

        # Get the top-level module name
        top_level = module_name.split(".")[0]

        # Check if it's a known stdlib module or starts with underscore (internal)
        return top_level in common_stdlib or top_level.startswith("_")

    def _create_symbol(
        self,
        name: str,
        member_type: MemberType,
        location: SourceLocation,
        provenance: SymbolProvenance,
        *,
        is_private: bool,
        original_name: str | None = None,
        original_source: str | None = None,
        docstring: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> DetectedSymbol:
        """Helper to create DetectedSymbol with default values."""
        return DetectedSymbol(
            name=name,
            member_type=member_type,
            location=location,
            provenance=provenance,
            is_private=is_private,
            original_name=original_name,
            original_source=original_source,
            docstring=docstring,
            metadata=metadata or {},
        )


__all__ = ["ASTParser"]
