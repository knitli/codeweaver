# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Test type alias detection for both Python 3.12+ and pre-3.12 styles."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.lazy_imports.analysis.ast_parser import ASTParser
from tools.lazy_imports.common.types import MemberType


@pytest.fixture
def parser() -> ASTParser:
    """Create AST parser."""
    return ASTParser()


def create_temp_file(content: str, tmp_path: Path) -> Path:
    """Create a temporary Python file."""
    file_path = tmp_path / "test_module.py"
    file_path.write_text(content)
    return file_path


class TestPython312TypeAliases:
    """Test Python 3.12+ type alias style (type X = Y)."""

    def test_simple_type_alias(self, parser: ASTParser, tmp_path: Path) -> None:
        """Detect simple Python 3.12+ type alias."""
        content = """
type MyType = dict[str, Any]
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        # Find MyType
        my_type = [e for e in result.symbols if e.name == "MyType"]
        assert len(my_type) == 1
        assert my_type[0].member_type == MemberType.TYPE_ALIAS
        assert my_type[0].metadata["style"] == "python3.12+"

    def test_multiple_type_aliases(self, parser: ASTParser, tmp_path: Path) -> None:
        """Detect multiple Python 3.12+ type aliases."""
        content = """
type MyType = dict[str, Any]
type Config = dict[str, str | int]
type ResultType = tuple[bool, str]
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        # Find all type aliases
        aliases = [e for e in result.symbols if e.member_type == MemberType.TYPE_ALIAS]
        assert len(aliases) == 3
        assert {a.name for a in aliases} == {"MyType", "Config", "ResultType"}
        assert all(a.metadata["style"] == "python3.12+" for a in aliases)

    def test_generic_type_alias(self, parser: ASTParser, tmp_path: Path) -> None:
        """Detect generic type alias with type parameters."""
        content = """
type GenericType[T] = list[T]
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        # Find GenericType
        generic = [e for e in result.symbols if e.name == "GenericType"]
        assert len(generic) == 1
        assert generic[0].member_type == MemberType.TYPE_ALIAS
        assert generic[0].metadata["style"] == "python3.12+"

    def test_multi_param_generic_type_alias(self, parser: ASTParser, tmp_path: Path) -> None:
        """Detect generic type alias with multiple type parameters."""
        content = """
type MultiParam[K, V] = dict[K, V]
type ComplexGeneric[T, U, V] = tuple[T, U, V]
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        # Find both generic type aliases
        aliases = [e for e in result.symbols if e.member_type == MemberType.TYPE_ALIAS]
        assert len(aliases) == 2
        assert {a.name for a in aliases} == {"MultiParam", "ComplexGeneric"}

    def test_complex_type_alias(self, parser: ASTParser, tmp_path: Path) -> None:
        """Detect complex type alias with nested types."""
        content = """
type ComplexType = Callable[[int, str], bool]
type NestedType = dict[str, list[tuple[int, str]]]
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        # Find both complex aliases
        aliases = [e for e in result.symbols if e.member_type == MemberType.TYPE_ALIAS]
        assert len(aliases) == 2
        assert {a.name for a in aliases} == {"ComplexType", "NestedType"}


class TestPrePython312TypeAliases:
    """Test pre-Python 3.12 type alias style (X: TypeAlias = Y)."""

    def test_type_alias_annotation(self, parser: ASTParser, tmp_path: Path) -> None:
        """TypeAlias annotation should be detected."""
        content = """
from typing import TypeAlias

MyType: TypeAlias = int | str
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        # Find MyType
        my_type = [e for e in result.symbols if e.name == "MyType"]
        assert len(my_type) == 1
        assert my_type[0].member_type == MemberType.TYPE_ALIAS
        assert my_type[0].metadata["style"] == "pre-python3.12"

    def test_typing_type_alias(self, parser: ASTParser, tmp_path: Path) -> None:
        """typing.TypeAlias should be detected."""
        content = """
import typing

MyType: typing.TypeAlias = list[int]
Config: typing.TypeAlias = dict[str, Any]
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        # Find both type aliases
        aliases = [e for e in result.symbols if e.member_type == MemberType.TYPE_ALIAS]
        assert len(aliases) == 2
        assert {a.name for a in aliases} == {"MyType", "Config"}
        assert all(a.metadata["style"] == "pre-python3.12" for a in aliases)

    def test_multiple_pre_312_aliases(self, parser: ASTParser, tmp_path: Path) -> None:
        """Detect multiple pre-3.12 type aliases."""
        content = """
from typing import TypeAlias

PathLike: TypeAlias = str | Path
ConfigDict: TypeAlias = dict[str, Any]
ResultTuple: TypeAlias = tuple[bool, str, int]
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        # Find all type aliases
        aliases = [e for e in result.symbols if e.member_type == MemberType.TYPE_ALIAS]
        assert len(aliases) == 3
        assert {a.name for a in aliases} == {"PathLike", "ConfigDict", "ResultTuple"}


class TestMixedTypeAliasStyles:
    """Test files with both Python 3.12+ and pre-3.12 type alias styles."""

    def test_mixed_styles(self, parser: ASTParser, tmp_path: Path) -> None:
        """Handle both styles in same file."""
        content = """
from typing import TypeAlias

# Pre-3.12 style
OldStyle: TypeAlias = dict[str, Any]
ConfigType: TypeAlias = dict[str, str | int]

# Python 3.12+ style
type NewStyle = dict[str, Any]
type ModernType = list[int]
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        # Find all type aliases
        aliases = [e for e in result.symbols if e.member_type == MemberType.TYPE_ALIAS]
        assert len(aliases) == 4
        assert {a.name for a in aliases} == {"OldStyle", "ConfigType", "NewStyle", "ModernType"}

        # Check styles
        old_style = [a for a in aliases if "Old" in a.name or "Config" in a.name]
        new_style = [a for a in aliases if "New" in a.name or "Modern" in a.name]

        assert all(a.metadata["style"] == "pre-python3.12" for a in old_style)
        assert all(a.metadata["style"] == "python3.12+" for a in new_style)

    def test_mixed_with_other_symbols(self, parser: ASTParser, tmp_path: Path) -> None:
        """Type aliases should coexist with other symbol types."""
        content = """
from typing import TypeAlias

# Type aliases
OldAlias: TypeAlias = str | int
type NewAlias = list[str]

# Classes
class MyClass:
    pass

# Functions
def my_function() -> None:
    pass

# Constants
MAX_SIZE = 100

# Variables
config: dict = {}
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        # Check all types are detected
        types = {e.name: e.member_type for e in result.symbols}

        assert types.get("OldAlias") == MemberType.TYPE_ALIAS
        assert types.get("NewAlias") == MemberType.TYPE_ALIAS
        assert types.get("MyClass") == MemberType.CLASS
        assert types.get("my_function") == MemberType.FUNCTION
        assert types.get("MAX_SIZE") == MemberType.CONSTANT
        assert types.get("config") == MemberType.VARIABLE


class TestRealCodeweaverFiles:
    """Test with actual type aliases from codeweaver codebase."""

    @pytest.mark.skipif(
        not Path("src/codeweaver/engine/dependencies.py").exists(),
        reason="Codeweaver source not available",
    )
    def test_real_dependencies_file(self, parser: ASTParser) -> None:
        """Test with real dependencies.py file."""
        real_file = Path("src/codeweaver/engine/dependencies.py")
        result = parser.parse_file(real_file, "codeweaver.engine.dependencies")

        # Should detect Python 3.12+ type aliases
        aliases = [e for e in result.symbols if e.member_type == MemberType.TYPE_ALIAS]

        # Verify we found some aliases
        assert len(aliases) > 0

        # Check they're all Python 3.12+ style
        assert all(a.metadata.get("style") == "python3.12+" for a in aliases)

        # Check for specific known aliases
        alias_names = {a.name for a in aliases}
        assert "IndexerSettingsDep" in alias_names or len(aliases) > 5

    @pytest.mark.skipif(
        not Path("src/codeweaver/core/types/aliases.py").exists(),
        reason="Type aliases file not available",
    )
    def test_real_type_aliases_file(self, parser: ASTParser) -> None:
        """Test with real type aliases file if it exists."""
        real_file = Path("src/codeweaver/core/types/aliases.py")
        result = parser.parse_file(real_file, "codeweaver.core.types.aliases")

        # Should detect type aliases
        aliases = [e for e in result.symbols if e.member_type == MemberType.TYPE_ALIAS]
        assert len(aliases) > 0


class TestTypeAliasEdgeCases:
    """Test edge cases and error scenarios."""

    def test_empty_file(self, parser: ASTParser, tmp_path: Path) -> None:
        """Empty file should have no type aliases."""
        content = ""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        aliases = [e for e in result.symbols if e.member_type == MemberType.TYPE_ALIAS]
        assert len(aliases) == 0

    def test_type_alias_with_comment(self, parser: ASTParser, tmp_path: Path) -> None:
        """Type aliases with comments should be detected."""
        content = """
# This is a type alias
type MyType = dict[str, Any]

# Another one
from typing import TypeAlias
ConfigType: TypeAlias = dict[str, str]  # Inline comment
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        aliases = [e for e in result.symbols if e.member_type == MemberType.TYPE_ALIAS]
        assert len(aliases) == 2

    def test_type_alias_in_type_checking_block(self, parser: ASTParser, tmp_path: Path) -> None:
        """Type aliases in TYPE_CHECKING blocks should be detected."""
        content = """
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    # These should NOT be detected (inside if block, not top-level)
    LocalAlias: TypeAlias = dict[str, Any]

# This should be detected (top-level)
type GlobalAlias = list[str]
"""
        file_path = create_temp_file(content, tmp_path)
        result = parser.parse_file(file_path, "test.module")

        # Only top-level type aliases should be detected
        aliases = [e for e in result.symbols if e.member_type == MemberType.TYPE_ALIAS]

        # Should only find GlobalAlias (LocalAlias is inside if block)
        assert len(aliases) == 1
        assert aliases[0].name == "GlobalAlias"
