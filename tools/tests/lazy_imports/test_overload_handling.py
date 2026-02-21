#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for @overload decorator handling."""

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

    # Add basic rules
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

    # Exclude private members
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
def parser():
    """Create AST parser."""
    return ASTParser()


def create_temp_file(content: str) -> Path:
    """Create temporary Python file with content."""
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)  # noqa: SIM115
    temp_file.write(content)
    temp_file.close()
    return Path(temp_file.name)


class TestOverloadDetection:
    """Test @overload decorator detection."""

    def test_detect_overload_decorator(self, parser) -> None:
        """Parser should detect @overload decorator."""
        content = '''
from typing import overload

@overload
def process(x: int) -> int: ...

@overload
def process(x: str) -> str: ...

def process(x: int | str) -> int | str:
    """Process values."""
    return x
'''
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "mymodule")

            # Should find ONE export named "process" (not 3)
            functions = [e for e in result.symbols if e.member_type == MemberType.FUNCTION]
            process_funcs = [f for f in functions if f.name == "process"]

            assert len(process_funcs) == 1  # Only one export
            export = process_funcs[0]
            assert export.metadata["is_overloaded"] is True
            assert export.metadata["overload_count"] == 2
            assert export.metadata["has_implementation"] is True
        finally:
            file_path.unlink()

    def test_overload_with_typing_prefix(self, parser) -> None:
        """Handle typing.overload prefix."""
        content = """
import typing

@typing.overload
def func(x: int) -> int: ...

@typing.overload
def func(x: str) -> str: ...

def func(x):
    return x
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "mymodule")

            funcs = [e for e in result.symbols if e.name == "func"]
            assert len(funcs) == 1
            assert funcs[0].metadata["is_overloaded"] is True
        finally:
            file_path.unlink()

    def test_overload_without_implementation(self, parser) -> None:
        """Handle @overload without implementation."""
        content = """
from typing import overload

@overload
def func(x: int) -> int: ...

@overload
def func(x: str) -> str: ...

# Missing actual implementation!
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "mymodule")

            funcs = [e for e in result.symbols if e.name == "func"]
            assert len(funcs) == 1
            assert funcs[0].metadata["is_overloaded"] is True
            assert funcs[0].metadata["has_implementation"] is False  # No impl found
        finally:
            file_path.unlink()

    def test_async_overload(self, parser) -> None:
        """Handle @overload with async functions."""
        content = '''
from typing import overload

@overload
async def fetch(url: str) -> str: ...

@overload
async def fetch(url: str, timeout: int) -> str: ...

async def fetch(url: str, timeout: int | None = None) -> str:
    """Fetch content."""
    return "content"
'''
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "mymodule")

            funcs = [e for e in result.symbols if e.name == "fetch"]
            assert len(funcs) == 1
            assert funcs[0].metadata["is_overloaded"] is True
            assert funcs[0].metadata["overload_count"] == 2
        finally:
            file_path.unlink()


class TestNonOverloadDuplicates:
    """Test handling of duplicate functions without @overload."""

    def test_non_overload_duplicates_warning(self, parser, caplog) -> None:
        """Warn about duplicates without @overload."""
        content = """
def func():
    pass

def func():  # Duplicate without @overload - suspicious
    pass
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "mymodule")

            # Should still export (not crash)
            funcs = [e for e in result.symbols if e.name == "func"]
            assert len(funcs) == 1

            # Should log warning
            assert any("without @overload" in record.message for record in caplog.records)
        finally:
            file_path.unlink()


class TestDocstringExtraction:
    """Test docstring extraction for overloaded functions."""

    def test_docstring_from_implementation(self, parser) -> None:
        """Docstring should come from implementation, not overloads."""
        content = '''
from typing import overload

@overload
def process(x: int) -> int: ...

@overload
def process(x: str) -> str: ...

def process(x: int | str) -> int | str:
    """Process any value.

    This is the real docstring.
    """
    return x
'''
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "mymodule")

            funcs = [e for e in result.symbols if e.name == "process"]
            assert len(funcs) == 1
            assert funcs[0].docstring.startswith("Process any value")
        finally:
            file_path.unlink()


class TestRealWorldOverloads:
    """Test with real overloaded functions from codeweaver."""

    def test_real_codeweaver_overloads(self, parser) -> None:
        """Test with actual overloaded functions from codeweaver."""
        # Use the real file from codeweaver
        real_file = Path("src/codeweaver/engine/chunker/delimiters/patterns.py")

        if not real_file.exists():
            pytest.skip("Real file not found")

        result = parser.parse_file(real_file, "codeweaver.engine.chunker.delimiters.patterns")

        # Should find kind_from_delimiter_tuple as overloaded
        funcs = [e for e in result.symbols if e.name == "kind_from_delimiter_tuple"]
        assert len(funcs) == 1  # Only one export despite multiple definitions
        func = funcs[0]
        assert func.metadata.get("is_overloaded") is True
        assert func.metadata.get("overload_count") == 2

    def test_real_middleware_overloads(self, parser) -> None:
        """Test with middleware statistics overloads."""
        real_file = Path("src/codeweaver/server/mcp/middleware/statistics.py")

        if not real_file.exists():
            pytest.skip("Real file not found")

        result = parser.parse_file(real_file, "codeweaver.server.mcp.middleware.statistics")

        # Should find _time_operation as overloaded
        funcs = [e for e in result.symbols if e.name == "_time_operation"]
        if funcs:  # May be filtered as private
            func = funcs[0]
            assert func.metadata.get("is_overloaded") is True
            # Has many overloads (6+)
            assert func.metadata.get("overload_count", 0) >= 6


class TestMixedOverloadAndRegular:
    """Test files with both overloaded and regular functions."""

    def test_mixed_functions(self, parser) -> None:
        """Handle mix of overloaded and regular functions."""
        content = '''
from typing import overload

def regular_func():
    """Regular function."""
    pass

@overload
def overloaded(x: int) -> int: ...

@overload
def overloaded(x: str) -> str: ...

def overloaded(x):
    """Overloaded function."""
    return x

def another_regular():
    """Another regular."""
    pass
'''
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "mymodule")

            functions = {e.name: e for e in result.symbols if e.member_type == MemberType.FUNCTION}

            assert len(functions) == 3

            # Regular functions should NOT be marked as overloaded
            assert functions["regular_func"].metadata.get("is_overloaded", False) is False
            assert functions["another_regular"].metadata.get("is_overloaded", False) is False

            # Overloaded function should be marked
            assert functions["overloaded"].metadata["is_overloaded"] is True
        finally:
            file_path.unlink()


class TestLineNumbers:
    """Test line number reporting for overloaded functions."""

    def test_line_number_is_first_definition(self, parser) -> None:
        """Line number should be from first definition (first @overload)."""
        content = """# Line 1
# Line 2

from typing import overload  # Line 4

@overload  # Line 6
def func(x: int) -> int: ...

@overload  # Line 9
def func(x: str) -> str: ...

def func(x):  # Line 12
    return x
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "mymodule")

            funcs = [e for e in result.symbols if e.name == "func"]
            assert len(funcs) == 1
            # Line number should be from first @overload (line 7: def func...)
            assert funcs[0].location.line == 7
        finally:
            file_path.unlink()


class TestEdgeCases:
    """Test edge cases for overload handling."""

    def test_single_overload_with_implementation(self, parser) -> None:
        """Handle edge case of single @overload with implementation."""
        content = """
from typing import overload

@overload
def func(x: int) -> int: ...

def func(x):
    return x
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "mymodule")

            funcs = [e for e in result.symbols if e.name == "func"]
            assert len(funcs) == 1
            assert funcs[0].metadata["is_overloaded"] is True
            assert funcs[0].metadata["overload_count"] == 1
        finally:
            file_path.unlink()

    def test_many_overloads(self, parser) -> None:
        """Handle many overload signatures."""
        content = """
from typing import overload

@overload
def func(x: int) -> int: ...

@overload
def func(x: str) -> str: ...

@overload
def func(x: float) -> float: ...

@overload
def func(x: list) -> list: ...

@overload
def func(x: dict) -> dict: ...

def func(x):
    return x
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "mymodule")

            funcs = [e for e in result.symbols if e.name == "func"]
            assert len(funcs) == 1
            assert funcs[0].metadata["overload_count"] == 5
        finally:
            file_path.unlink()
