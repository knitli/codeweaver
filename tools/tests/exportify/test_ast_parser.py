#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for AST parser."""

import hashlib
import tempfile

from pathlib import Path

import pytest

from tools.exportify.analysis.ast_parser import ASTParser
from tools.exportify.common.types import MemberType, SymbolProvenance


@pytest.fixture
def parser():
    """Create AST parser."""
    return ASTParser()


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
            result = parser.parse_file(file_path, "test.module")

            assert len(result.symbols) == 1
            symbol = result.symbols[0]
            assert symbol.name == "MyClass"
            assert symbol.member_type == MemberType.CLASS
            assert symbol.docstring == "A simple class."
            assert symbol.location.line == 2
            assert symbol.provenance == SymbolProvenance.DEFINED_HERE
        finally:
            file_path.unlink()

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

            assert len(result.symbols) == 3
            names = [e.name for e in result.symbols]
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
            assert len(result.symbols) == 1
            assert result.symbols[0].name == "Outer"
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
            result = parser.parse_file(file_path, "test.module")
            assert len(result.symbols) == 1
            symbol = result.symbols[0]
            assert symbol.name == "my_function"
            assert symbol.member_type == MemberType.FUNCTION
            assert symbol.docstring == "Does something."
        finally:
            file_path.unlink()

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

            assert len(result.symbols) == 1
            symbol = result.symbols[0]
            assert symbol.name == "async_function"
            assert symbol.member_type == MemberType.FUNCTION
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
            assert len(result.symbols) == 1
            assert result.symbols[0].name == "MyClass"
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

            assert len(result.symbols) == 1
            symbol = result.symbols[0]
            assert symbol.name == "my_var"
            assert symbol.member_type == MemberType.VARIABLE
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

            assert len(result.symbols) == 1
            symbol = result.symbols[0]
            assert symbol.name == "my_var"
            assert symbol.member_type == MemberType.VARIABLE
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

            assert len(result.symbols) == 3
            for symbol in result.symbols:
                assert symbol.member_type == MemberType.CONSTANT
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

            assert len(result.symbols) == 1
            assert result.symbols[0].member_type == MemberType.VARIABLE
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
            my_type = [e for e in result.symbols if e.name == "MyType"]
            assert len(my_type) == 1
            assert my_type[0].member_type == MemberType.TYPE_ALIAS
            assert my_type[0].metadata.get("style") == "pre-python3.12"
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

            my_type = [e for e in result.symbols if e.name == "MyType"]
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

            assert result.symbols[0].docstring.startswith("This is a docstring")
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

            assert result.symbols[0].docstring == "Function docstring."
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

            assert result.symbols[0].docstring is None
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
            result = parser.parse_file(file_path, "test.module")

            # First class is on line 4
            first = next(e for e in result.symbols if e.name == "First")
            assert first.location.line == 4

            # second function is on line 7
            second = next(e for e in result.symbols if e.name == "second")
            assert second.location.line == 7

            # THIRD constant is on line 10
            third = next(e for e in result.symbols if e.name == "THIRD")
            assert third.location.line == 10
        finally:
            file_path.unlink()


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

            assert len(result.symbols) == 0
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

            assert len(result.symbols) == 0
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

            assert len(result.symbols) == 0
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
            result = parser.parse_file(file_path, "test.module")

            assert len(result.symbols) == 4

            # Check types
            types = {e.name: e.member_type for e in result.symbols}
            assert types["MAX_SIZE"] == MemberType.CONSTANT
            assert types["MyClass"] == MemberType.CLASS
            assert types["my_function"] == MemberType.FUNCTION
            assert types["my_var"] == MemberType.VARIABLE
        finally:
            file_path.unlink()


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
