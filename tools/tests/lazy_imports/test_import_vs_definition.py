#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for differentiating module definitions vs imports.

This module tests edge case #3: Properly differentiating between symbols
defined in a module and symbols imported into it, with special handling
for `as` imports (aliased imports).

Rules:
- Module-defined symbols: Export based on rules
- Regular imports: Generally don't export (unless rules say so)
- `as` imports: Generally SHOULD export (explicit public API intent)
"""

import tempfile

from pathlib import Path

import pytest

from tools.lazy_imports.analysis.ast_parser import ASTParser
from tools.lazy_imports.common.types import (
    MemberType,
    PropagationLevel,
    Rule,
    RuleAction,
    RuleMatchCriteria,
    SymbolProvenance,
)
from tools.lazy_imports.export_manager.rules import RuleEngine


@pytest.fixture
def rule_engine():
    """Create rule engine with default and aliased import rules."""
    engine = RuleEngine()

    # Rule 1: Include all defined symbols by default
    engine.add_rule(
        Rule(
            name="default-include-defined",
            priority=0,
            description="Include all defined symbols by default",
            match=RuleMatchCriteria(name_pattern=".*"),
            action=RuleAction.INCLUDE,
            propagate=PropagationLevel.PARENT,
        )
    )

    # Rule 2: Exclude private members (higher priority)
    engine.add_rule(
        Rule(
            name="exclude-private",
            priority=100,
            description="Exclude private members",
            match=RuleMatchCriteria(name_pattern=r"^_.*"),
            action=RuleAction.EXCLUDE,
            propagate=None,
        )
    )

    # Rule 3: Exclude non-aliased imports (higher priority)
    engine.add_rule(
        Rule(
            name="exclude-non-aliased-imports",
            priority=50,
            description="Exclude imports without aliases",
            match=RuleMatchCriteria(member_type=MemberType.IMPORTED),
            action=RuleAction.EXCLUDE,
            propagate=None,
        )
    )

    return engine


@pytest.fixture
def rule_engine_with_aliased():
    """Create rule engine that exports aliased imports."""
    engine = RuleEngine()

    # Rule 1: Export aliased imports (highest priority for imports)
    engine.add_rule(
        Rule(
            name="export-aliased-imports",
            priority=100,
            description="Always export imports with 'as' aliases",
            match=RuleMatchCriteria(member_type=MemberType.IMPORTED),
            action=RuleAction.INCLUDE,
            propagate=PropagationLevel.PARENT,
        )
    )

    # Rule 2: Include all defined symbols by default
    engine.add_rule(
        Rule(
            name="default-include-defined",
            priority=0,
            description="Include all defined symbols by default",
            match=RuleMatchCriteria(name_pattern=".*"),
            action=RuleAction.INCLUDE,
            propagate=PropagationLevel.PARENT,
        )
    )

    # Rule 3: Exclude private members (higher priority)
    engine.add_rule(
        Rule(
            name="exclude-private",
            priority=200,
            description="Exclude private members",
            match=RuleMatchCriteria(name_pattern=r"^_.*"),
            action=RuleAction.EXCLUDE,
            propagate=None,
        )
    )

    return engine


@pytest.fixture
def parser():
    """Create AST parser."""
    return ASTParser()


@pytest.fixture
def parser_aliased():
    """Create AST parser."""
    return ASTParser()


def create_temp_file(content: str) -> Path:
    """Create temporary Python file with content."""
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)  # noqa: SIM115
    temp_file.write(content)
    temp_file.close()
    return Path(temp_file.name)


class TestDefinedVsImported:
    """Test differentiation between defined and imported symbols."""

    def test_mark_defined_symbols(self, parser) -> None:
        """Parser should mark defined symbols with is_defined_here=True."""
        content = """
class MyClass:
    pass

def my_function():
    pass

MY_VAR = 42
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # All should be marked as defined
            for export in result.symbols:
                assert export.provenance == SymbolProvenance.DEFINED_HERE

        finally:
            file_path.unlink()

    def test_mark_imported_symbols(self, parser_aliased) -> None:
        """Parser should mark imported symbols with is_defined_here=False."""
        content = """
from .models import User
import sys
"""
        file_path = create_temp_file(content)
        try:
            result = parser_aliased.parse_file(file_path, "test.module")

            # All should be marked as imported
            imported = [e for e in result.symbols if e.member_type == MemberType.IMPORTED]
            assert len(imported) == 2

            for export in imported:
                assert export.provenance != SymbolProvenance.DEFINED_HERE

        finally:
            file_path.unlink()

    def test_differentiate_defined_vs_imported(self, parser_aliased) -> None:
        """Parser should differentiate between defined and imported symbols."""
        content = """
from .models import User  # Imported
import sys  # Imported

class MyClass:  # Defined
    pass

def my_function():  # Defined
    pass

MY_VAR = 42  # Defined
"""
        file_path = create_temp_file(content)
        try:
            result = parser_aliased.parse_file(file_path, "test.module")

            # Check metadata
            defined = [e for e in result.symbols if e.provenance == SymbolProvenance.DEFINED_HERE]
            imported = [e for e in result.symbols if e.provenance != SymbolProvenance.DEFINED_HERE]

            assert len(defined) == 3  # MyClass, my_function, MY_VAR
            assert len(imported) == 2  # User, sys

            # Verify names
            defined_names = {e.name for e in defined}
            assert defined_names == {"MyClass", "my_function", "MY_VAR"}

            imported_names = {e.name for e in imported}
            assert imported_names == {"User", "sys"}

        finally:
            file_path.unlink()


class TestAliasedImports:
    """Test detection and handling of aliased imports."""

    def test_detect_aliased_imports(self, parser_aliased) -> None:
        """Aliased imports should be marked with is_aliased=True."""
        content = """
from .models import User as UserModel  # Aliased
from .models import Post  # Not aliased
import sys  # Not aliased
import numpy as np  # Aliased
"""
        file_path = create_temp_file(content)
        try:
            result = parser_aliased.parse_file(file_path, "test.module")

            # Check aliases detected
            aliased = [e for e in result.symbols if e.provenance == SymbolProvenance.ALIAS_IMPORTED]
            not_aliased = [
                e for e in result.symbols if e.provenance != SymbolProvenance.ALIAS_IMPORTED
            ]

            assert len(aliased) == 2  # UserModel, np
            assert len(not_aliased) == 2  # Post, sys

            # Verify aliased names use the alias
            aliased_names = {e.name for e in aliased}
            assert aliased_names == {"UserModel", "np"}

            # Verify original names stored in metadata
            for export in aliased:
                assert export.original_name is not None
                if export.name == "UserModel":
                    assert export.original_name == "User"
                elif export.name == "np":
                    assert export.original_name == "numpy"

        finally:
            file_path.unlink()

    def test_detect_aliased_imports_marked(self, parser_aliased) -> None:
        """Aliased imports should be detected and marked."""
        content = """
from .models import User as UserModel  # Aliased
from .models import Post  # Not aliased
"""
        file_path = create_temp_file(content)
        try:
            result = parser_aliased.parse_file(file_path, "test.module")

            # Both should be in symbols
            symbol_names = {e.name for e in result.symbols}
            assert "UserModel" in symbol_names
            assert "Post" in symbol_names

            # Verify aliased flag
            for export in result.symbols:
                if export.name == "UserModel":
                    assert export.provenance == SymbolProvenance.ALIAS_IMPORTED
                elif export.name == "Post":
                    assert export.provenance == SymbolProvenance.IMPORTED

        finally:
            file_path.unlink()

    def test_detect_non_aliased_imports(self, parser) -> None:
        """Non-aliased imports should be detected but marked appropriately."""
        content = """
from .models import User  # Not aliased
import sys  # Not aliased

class MyClass:  # Defined
    pass
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Check detection
            symbol_names = {e.name for e in result.symbols}
            assert "MyClass" in symbol_names
            assert "User" in symbol_names
            assert "sys" in symbol_names

            # Verify metadata
            for s in result.symbols:
                if s.name in ("User", "sys"):
                    assert s.member_type == MemberType.IMPORTED
                    assert s.provenance == SymbolProvenance.IMPORTED

        finally:
            file_path.unlink()


class TestComplexImportScenarios:
    """Test complex import scenarios."""

    def test_module_import_vs_from_import(self, parser_aliased) -> None:
        """Distinguish 'import sys' from 'from typing import Any'."""
        content = """
import sys  # Module import
from typing import Any  # From import
"""
        file_path = create_temp_file(content)
        try:
            result = parser_aliased.parse_file(file_path, "test.module")

            # Both should be marked as imported
            assert len(result.symbols) == 2

            # Check import_type metadata
            for export in result.symbols:
                assert export.member_type == MemberType.IMPORTED
                if export.name == "sys":
                    assert export.metadata["import_type"] == "module"
                    assert export.original_source is None
                elif export.name == "Any":
                    assert export.metadata["import_type"] == "from"
                    assert export.original_source == "typing"

        finally:
            file_path.unlink()

    def test_complex_aliasing(self, parser_aliased) -> None:
        """Handle complex import scenarios with mixed aliases."""
        content = """
from .models import (
    User as UserModel,  # Aliased
    Post,  # Not aliased
    Comment as CommentType,  # Aliased
)
"""
        file_path = create_temp_file(content)
        try:
            result = parser_aliased.parse_file(file_path, "test.module")

            # All 3 should be exported
            assert len(result.symbols) == 3

            # 2 aliased, 1 not
            aliased = [e for e in result.symbols if e.provenance == SymbolProvenance.ALIAS_IMPORTED]
            not_aliased = [
                e for e in result.symbols if e.provenance != SymbolProvenance.ALIAS_IMPORTED
            ]

            assert len(aliased) == 2
            assert len(not_aliased) == 1

            # Verify aliased names
            aliased_names = {e.name for e in aliased}
            assert aliased_names == {"UserModel", "CommentType"}

            # Verify non-aliased name
            assert not_aliased[0].name == "Post"

        finally:
            file_path.unlink()

    def test_relative_imports_with_aliases(self, parser_aliased) -> None:
        """Handle relative imports with aliases."""
        content = """
from . import module as mod
from ..package import something as sm
from ...root import util
"""
        file_path = create_temp_file(content)
        try:
            result = parser_aliased.parse_file(file_path, "test.module")

            assert len(result.symbols) == 3

            # Check relative import paths
            for export in result.symbols:
                assert export.member_type == MemberType.IMPORTED
                if export.name == "mod":
                    assert export.original_source == "."
                    assert export.provenance == SymbolProvenance.ALIAS_IMPORTED
                elif export.name == "sm":
                    assert export.original_source == "..package"
                    assert export.provenance == SymbolProvenance.ALIAS_IMPORTED
                elif export.name == "util":
                    assert export.original_source == "...root"
                    assert export.provenance == SymbolProvenance.IMPORTED

        finally:
            file_path.unlink()


class TestMixedDefinitionsAndImports:
    """Test files with both definitions and imports."""

    def test_mixed_defined_and_imported(self, parser_aliased) -> None:
        """Handle files with both defined and imported symbols."""
        content = """
from .models import User as UserModel  # Aliased import
from .utils import helper  # Non-aliased import
import sys  # Module import

class MyClass:  # Defined class
    pass

CONSTANT = 42  # Defined constant

def my_function():  # Defined function
    pass
"""
        file_path = create_temp_file(content)
        try:
            result = parser_aliased.parse_file(file_path, "test.module")

            # Categorize exports
            defined = [e for e in result.symbols if e.provenance == SymbolProvenance.DEFINED_HERE]
            imported = [e for e in result.symbols if e.provenance != SymbolProvenance.DEFINED_HERE]

            # Check counts
            assert len(defined) == 3  # MyClass, CONSTANT, my_function
            assert len(imported) == 3  # UserModel, helper, sys

            # Verify defined names
            defined_names = {e.name for e in defined}
            assert defined_names == {"MyClass", "CONSTANT", "my_function"}

            # Verify imported names
            imported_names = {e.name for e in imported}
            assert imported_names == {"UserModel", "helper", "sys"}

            # Verify member types
            for export in defined:
                assert export.member_type in {
                    MemberType.CLASS,
                    MemberType.CONSTANT,
                    MemberType.FUNCTION,
                }

            for export in imported:
                assert export.member_type == MemberType.IMPORTED

        finally:
            file_path.unlink()

    def test_detect_all_symbols_including_private(self, parser_aliased) -> None:
        """Verify all symbols are detected including private ones."""
        content = """
from .database import User as UserModel
from .utils import helper
import sys

class MyClass:
    pass

CONSTANT = 42

_private_var = "hidden"
"""
        file_path = create_temp_file(content)
        try:
            result = parser_aliased.parse_file(file_path, "test.module")

            symbol_names = {e.name for e in result.symbols}
            expected = {"UserModel", "helper", "sys", "MyClass", "CONSTANT", "_private_var"}
            # ASTParser captures everything
            assert symbol_names == expected

            # Verify _private_var is marked private
            private_vars = [s for s in result.symbols if s.name == "_private_var"]
            assert len(private_vars) == 1
            assert private_vars[0].is_private is True

        finally:
            file_path.unlink()


class TestImportMetadata:
    """Test import metadata fields."""

    def test_import_metadata_fields(self, parser_aliased) -> None:
        """Verify all expected metadata fields are present."""
        content = """
from .models import User as UserModel
import sys
"""
        file_path = create_temp_file(content)
        try:
            result = parser_aliased.parse_file(file_path, "test.module")

            for export in result.symbols:
                # All imports should have these fields
                assert export.original_name is not None
                # original_source can be None for module imports
                assert "import_type" in export.metadata

                # Verify values
                assert export.provenance != SymbolProvenance.DEFINED_HERE

                if export.name == "UserModel":
                    assert export.provenance == SymbolProvenance.ALIAS_IMPORTED
                    assert export.original_name == "User"
                    assert export.original_source == ".models"
                    assert export.metadata["import_type"] == "from"
                elif export.name == "sys":
                    assert export.provenance == SymbolProvenance.IMPORTED
                    assert export.original_name == "sys"
                    assert export.original_source is None
                    assert export.metadata["import_type"] == "module"

        finally:
            file_path.unlink()

    def test_defined_symbol_metadata_fields(self, parser) -> None:
        """Verify defined symbols have correct metadata."""
        content = """
class MyClass:
    pass
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            export = result.symbols[0]
            assert export.provenance == SymbolProvenance.DEFINED_HERE

        finally:
            file_path.unlink()


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_imports_still_extracted_as_strings(self, parser) -> None:
        """Ensure imports are still available as strings for backward compatibility."""
        content = """
import os
from pathlib import Path
from .models import User as UserModel
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Check that imports list still exists
            assert hasattr(result, "imports")
            assert isinstance(result.imports, list)

            # Verify import strings
            assert "import os" in result.imports
            assert "from pathlib import Path" in result.imports
            assert "from .models import User as UserModel" in result.imports

        finally:
            file_path.unlink()
