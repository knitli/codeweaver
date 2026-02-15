#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for AST parser."""

import hashlib
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
)
from tools.lazy_imports.export_manager.rules import RuleEngine


@pytest.fixture
def rule_engine():
    """Create a basic rule engine for testing."""
    engine = RuleEngine()

    # Add basic rules using proper Rule objects
    # Rule 1: Include everything by default with parent propagation
    engine.add_rule(
        Rule(
            name="default-include",
            priority=0,
            description="Include all exports by default",
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

    return engine


@pytest.fixture
def parser(rule_engine):
    """Create AST parser with rule engine."""
    return ASTParser(rule_engine)


def create_temp_file(content: str) -> Path:
    """Create temporary Python file with content."""
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)  # noqa: SIM115
    temp_file.write(content)
    temp_file.close()
    return Path(temp_file.name)


class TestClassExtraction:
    """Test class extraction."""

    def test_simple_class(self, parser) -> None:
        """Extract simple class."""
        content = '''
class MyClass:
    """A simple class."""
    pass
'''
        file_path = create_temp_file(content)
        try:
            self._parse_file(parser, file_path)
        finally:
            file_path.unlink()

    def _parse_file(self, parser, file_path):
        result = parser.parse_file(file_path, "test.module")

        assert len(result.exports) == 1
        export = result.exports[0]
        assert export.name == "MyClass"
        assert export.member_type == MemberType.CLASS
        assert export.docstring == "A simple class."
        assert export.line_number == 2

    def test_multiple_classes(self, parser) -> None:
        """Extract multiple classes."""
        content = '''
class First:
    pass

class Second:
    """Second class."""
    pass

class Third:
    pass
'''
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert len(result.exports) == 3
            names = [e.name for e in result.exports]
            assert names == ["First", "Second", "Third"]
        finally:
            file_path.unlink()

    def test_nested_class_not_extracted(self, parser) -> None:
        """Nested classes should not be extracted."""
        content = """
class Outer:
    class Inner:
        pass
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Only Outer should be extracted
            assert len(result.exports) == 1
            assert result.exports[0].name == "Outer"
        finally:
            file_path.unlink()


class TestFunctionExtraction:
    """Test function extraction."""

    def test_simple_function(self, parser) -> None:
        """Extract simple function."""
        content = '''
def my_function():
    """Does something."""
    pass
'''
        file_path = create_temp_file(content)
        try:
            self._extract_function(parser, file_path)
        finally:
            file_path.unlink()

    def _extract_function(self, parser, file_path):
        result = parser.parse_file(file_path, "test.module")

        assert len(result.exports) == 1
        export = result.exports[0]
        assert export.name == "my_function"
        assert export.member_type == MemberType.FUNCTION
        assert export.docstring == "Does something."

    def test_async_function(self, parser) -> None:
        """Extract async function."""
        content = '''
async def async_function():
    """Async operation."""
    pass
'''
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert len(result.exports) == 1
            export = result.exports[0]
            assert export.name == "async_function"
            assert export.member_type == MemberType.FUNCTION
        finally:
            file_path.unlink()

    def test_method_not_extracted(self, parser) -> None:
        """Methods inside classes should not be extracted."""
        content = """
class MyClass:
    def my_method(self):
        pass
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Only class, not method
            assert len(result.exports) == 1
            assert result.exports[0].name == "MyClass"
        finally:
            file_path.unlink()


class TestVariableExtraction:
    """Test variable extraction."""

    def test_annotated_variable(self, parser) -> None:
        """Extract annotated variable."""
        content = """
my_var: int = 42
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert len(result.exports) == 1
            export = result.exports[0]
            assert export.name == "my_var"
            assert export.member_type == MemberType.VARIABLE
        finally:
            file_path.unlink()

    def test_regular_variable(self, parser) -> None:
        """Extract regular variable."""
        content = """
my_var = "value"
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert len(result.exports) == 1
            export = result.exports[0]
            assert export.name == "my_var"
            assert export.member_type == MemberType.VARIABLE
        finally:
            file_path.unlink()


class TestConstantDetection:
    """Test constant detection."""

    def test_screaming_snake_case_constant(self, parser) -> None:
        """SCREAMING_SNAKE_CASE should be detected as constant."""
        content = """
MAX_SIZE = 100
API_KEY = "secret"
RETRY_COUNT = 3
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert len(result.exports) == 3
            for export in result.exports:
                assert export.member_type == MemberType.CONSTANT
        finally:
            file_path.unlink()

    def test_regular_variable_not_constant(self, parser) -> None:
        """Regular variable should not be constant."""
        content = """
max_size = 100
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert len(result.exports) == 1
            assert result.exports[0].member_type == MemberType.VARIABLE
        finally:
            file_path.unlink()


class TestTypeAliasDetection:
    """Test type alias detection."""

    def test_type_alias_annotation(self, parser) -> None:
        """TypeAlias annotation should be detected."""
        content = """
from typing import TypeAlias

MyType: TypeAlias = int | str
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Find MyType (imports are also extracted)
            my_type = [e for e in result.exports if e.name == "MyType"]
            assert len(my_type) == 1
            assert my_type[0].member_type == MemberType.TYPE_ALIAS
        finally:
            file_path.unlink()

    def test_typing_type_alias(self, parser) -> None:
        """typing.TypeAlias should be detected."""
        content = """
import typing

MyType: typing.TypeAlias = list[int]
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            my_type = [e for e in result.exports if e.name == "MyType"]
            assert len(my_type) == 1
            assert my_type[0].member_type == MemberType.TYPE_ALIAS
        finally:
            file_path.unlink()


class TestDocstringExtraction:
    """Test docstring extraction."""

    def test_class_docstring(self, parser) -> None:
        """Extract class docstring."""
        content = '''
class MyClass:
    """This is a docstring.

    With multiple lines.
    """
    pass
'''
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert result.exports[0].docstring.startswith("This is a docstring")
        finally:
            file_path.unlink()

    def test_function_docstring(self, parser) -> None:
        """Extract function docstring."""
        content = '''
def my_func():
    """Function docstring."""
    pass
'''
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert result.exports[0].docstring == "Function docstring."
        finally:
            file_path.unlink()

    def test_no_docstring(self, parser) -> None:
        """Handle missing docstring."""
        content = """
class NoDoc:
    pass
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert result.exports[0].docstring is None
        finally:
            file_path.unlink()


class TestLineNumbers:
    """Test line number accuracy."""

    def test_accurate_line_numbers(self, parser) -> None:
        """Line numbers should be accurate."""
        content = """# Comment
# Another comment

class First:
    pass

def second():
    pass

THIRD = 42
"""
        file_path = create_temp_file(content)
        try:
            self._extracted_from_test_accurate_line_numbers_16(parser, file_path)
        finally:
            file_path.unlink()

    # TODO Rename this here and in `test_accurate_line_numbers`
    def _extracted_from_test_accurate_line_numbers_16(self, parser, file_path):
        result = parser.parse_file(file_path, "test.module")

        # First class is on line 4
        first = next(e for e in result.exports if e.name == "First")
        assert first.line_number == 4

        # second function is on line 7
        second = next(e for e in result.exports if e.name == "second")
        assert second.line_number == 7

        # THIRD constant is on line 10
        third = next(e for e in result.exports if e.name == "THIRD")
        assert third.line_number == 10


class TestSyntaxErrorHandling:
    """Test syntax error handling."""

    def test_syntax_error_returns_empty(self, parser) -> None:
        """Syntax errors should return empty result."""
        content = """
def broken(
    # Missing closing paren
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert len(result.exports) == 0
            assert result.file_hash  # Should still have hash
        finally:
            file_path.unlink()


class TestEmptyFileHandling:
    """Test empty file handling."""

    def test_empty_file(self, parser) -> None:
        """Empty file should return empty result."""
        content = ""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert len(result.exports) == 0
            assert result.file_hash
        finally:
            file_path.unlink()

    def test_comments_only(self, parser) -> None:
        """File with only comments should return empty."""
        content = """# Just comments
# Nothing else
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert len(result.exports) == 0
        finally:
            file_path.unlink()


class TestImportExtraction:
    """Test import extraction."""

    def test_regular_import(self, parser) -> None:
        """Extract regular imports."""
        self._check_import_extraction(
            """
import os
import sys
""",
            parser,
            "import os",
            "import sys",
        )

    def test_from_import(self, parser) -> None:
        """Extract from imports."""
        self._check_import_extraction(
            """
from pathlib import Path
from typing import Any
""",
            parser,
            "from pathlib import Path",
            "from typing import Any",
        )

    def test_relative_import(self, parser) -> None:
        """Extract relative imports."""
        self._check_import_extraction(
            """
from . import module
from ..package import something
""",
            parser,
            "from . import module",
            "from ..package import something",
        )

    def test_import_alias(self, parser) -> None:
        """Extract import aliases."""
        self._check_import_extraction(
            """
import numpy as np
from pathlib import Path as P
""",
            parser,
            "import numpy as np",
            "from pathlib import Path as P",
        )

    def _check_import_extraction(self, arg0, parser, arg2, arg3):
        content = arg0
        file_path = create_temp_file(content)
        try:
            self._validate_args_present(parser, file_path, arg2, arg3)
        finally:
            file_path.unlink()

    def _validate_args_present(self, parser, file_path, arg2, arg3):
        result = parser.parse_file(file_path, "test.module")
        assert arg2 in result.imports
        assert arg3 in result.imports


class TestRuleEngineIntegration:
    """Test rule engine integration."""

    def test_include_action(self, parser) -> None:
        """INCLUDE action should include symbol."""
        content = """
class PublicClass:
    pass
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert len(result.exports) == 1
            assert result.exports[0].name == "PublicClass"
        finally:
            file_path.unlink()

    def test_exclude_action(self, parser) -> None:
        """EXCLUDE action should exclude symbol."""
        content = """
class _PrivateClass:
    pass

class PublicClass:
    pass
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Only PublicClass should be included
            assert len(result.exports) == 1
            assert result.exports[0].name == "PublicClass"
        finally:
            file_path.unlink()

    def test_propagation_level_assignment(self, rule_engine) -> None:
        """Propagation level should be assigned by rules."""
        # Add custom rule for specific propagation
        rule_engine.add_rule(
            Rule(
                name="special-class-root",
                priority=200,
                description="Propagate SpecialClass to root",
                match=RuleMatchCriteria(name_exact="SpecialClass"),
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.ROOT,
            )
        )

        parser = ASTParser(rule_engine)
        content = """
class SpecialClass:
    pass
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert result.exports[0].propagation == PropagationLevel.ROOT
        finally:
            file_path.unlink()


class TestMixedSymbols:
    """Test files with multiple symbol types."""

    def test_mixed_symbols(self, parser) -> None:
        """Extract mixed symbol types."""
        content = """
MAX_SIZE = 100

class MyClass:
    pass

def my_function():
    pass

my_var: str = "value"
"""
        file_path = create_temp_file(content)
        try:
            self._test_symbols(parser, file_path)
        finally:
            file_path.unlink()

    def _test_symbols(self, parser, file_path):
        result = parser.parse_file(file_path, "test.module")

        assert len(result.exports) == 4

        # Check types
        types = {e.name: e.member_type for e in result.exports}
        assert types["MAX_SIZE"] == MemberType.CONSTANT
        assert types["MyClass"] == MemberType.CLASS
        assert types["my_function"] == MemberType.FUNCTION
        assert types["my_var"] == MemberType.VARIABLE


class TestFileHash:
    """Test file hash calculation."""

    def test_file_hash_sha256(self, parser) -> None:
        """File hash should be SHA-256."""
        content = "class Test:\n    pass\n"
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            expected_hash = hashlib.sha256(content.encode()).hexdigest()
            assert result.file_hash == expected_hash
        finally:
            file_path.unlink()

    def test_different_content_different_hash(self, parser) -> None:
        """Different content should have different hash."""
        content1 = "class Test1:\n    pass\n"
        content2 = "class Test2:\n    pass\n"

        file1 = create_temp_file(content1)
        file2 = create_temp_file(content2)
        try:
            result1 = parser.parse_file(file1, "test.module1")
            result2 = parser.parse_file(file2, "test.module2")

            assert result1.file_hash != result2.file_hash
        finally:
            file1.unlink()
            file2.unlink()


class TestMetadata:
    """Test analysis result metadata."""

    def test_timestamp_generation(self, parser) -> None:
        """Timestamp should be generated."""
        content = "class Test:\n    pass\n"
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert result.analysis_timestamp > 0
        finally:
            file_path.unlink()

    def test_schema_version(self, parser) -> None:
        """Schema version should be set."""
        content = "class Test:\n    pass\n"
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            assert result.schema_version == "1.0"
        finally:
            file_path.unlink()


class TestCacheCompatibility:
    """Test cache compatibility."""

    def test_analysis_result_format(self, parser) -> None:
        """AnalysisResult should be cache-compatible."""
        content = '''
class MyClass:
    """Test class."""
    pass
'''
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Should have all required fields
            assert hasattr(result, "exports")
            assert hasattr(result, "imports")
            assert hasattr(result, "file_hash")
            assert hasattr(result, "analysis_timestamp")
            assert hasattr(result, "schema_version")

            # ExportNode should have required fields
            export = result.exports[0]
            assert hasattr(export, "name")
            assert hasattr(export, "module")
            assert hasattr(export, "member_type")
            assert hasattr(export, "propagation")
            assert hasattr(export, "source_file")
            assert hasattr(export, "line_number")
            assert hasattr(export, "defined_in")
        finally:
            file_path.unlink()


class TestRealWorldFile:
    """Test parsing complex real-world file."""

    def test_complex_file(self, parser) -> None:
        """Parse complex file with multiple constructs."""
        content = '''
"""Module docstring."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Iterator

# Constants
MAX_RETRIES = 3
API_URL = "https://api.example.com"

# Type aliases
PathLike: TypeAlias = str | Path

# Variables
_private_var = "hidden"
public_var: int = 42


class BaseClass:
    """Base class."""

    def method(self):
        """Should not be extracted."""
        pass


class DerivedClass(BaseClass):
    """Derived class with nested class."""

    class Nested:
        """Should not be extracted."""
        pass


def sync_function() -> None:
    """Synchronous function."""
    pass


async def async_function() -> None:
    """Asynchronous function."""
    pass


def _private_function():
    """Should be excluded."""
    pass
'''
        file_path = create_temp_file(content)
        try:
            self._test_extracted_exports(parser, file_path)
        finally:
            file_path.unlink()

    def _test_extracted_exports(self, parser, file_path):
        result = parser.parse_file(file_path, "test.complex")

        # Check exports
        export_names = {e.name for e in result.exports}

        # Should include
        assert "MAX_RETRIES" in export_names
        assert "API_URL" in export_names
        assert "PathLike" in export_names
        assert "public_var" in export_names
        assert "BaseClass" in export_names
        assert "DerivedClass" in export_names
        assert "sync_function" in export_names
        assert "async_function" in export_names

        # Should exclude
        assert "_private_var" not in export_names
        assert "_private_function" not in export_names
        assert "Nested" not in export_names
        assert "method" not in export_names

        # Check imports
        assert len(result.imports) > 0
        assert "import os" in result.imports
        assert "from pathlib import Path" in result.imports

        # Check types
        types = {e.name: e.member_type for e in result.exports}
        assert types["MAX_RETRIES"] == MemberType.CONSTANT
        assert types["PathLike"] == MemberType.TYPE_ALIAS
        assert types["public_var"] == MemberType.VARIABLE
        assert types["BaseClass"] == MemberType.CLASS
        assert types["sync_function"] == MemberType.FUNCTION
