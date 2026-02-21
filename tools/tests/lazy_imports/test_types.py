# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for common types and data structures."""

# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
from __future__ import annotations

import pytest

from tools.lazy_imports.common.types import (
    DetectedSymbol,
    ExportDecision,
    ExportManifest,
    LazyExport,
    MemberType,
    PropagationLevel,
    Rule,
    RuleAction,
    RuleMatchCriteria,
    SourceLocation,
    SymbolProvenance,
    ValidationError,
)


class TestMemberType:
    """Test MemberType enum."""

    def test_member_type_values(self):
        """Member types have expected values."""
        assert MemberType.CLASS == "class"
        assert MemberType.FUNCTION == "function"
        assert MemberType.VARIABLE == "variable"

    def test_member_type_equality(self):
        """Member type comparison works."""
        assert MemberType.CLASS == MemberType.CLASS
        assert MemberType.CLASS != MemberType.FUNCTION


class TestPropagationLevel:
    """Test PropagationLevel enum."""

    def test_propagation_levels(self):
        """Propagation levels have expected values."""
        assert PropagationLevel.NONE == "none"
        assert PropagationLevel.PARENT == "parent"
        assert PropagationLevel.ROOT == "root"

    def test_propagation_ordering(self):
        """Propagation levels can be compared."""
        # String comparison
        assert PropagationLevel.NONE.value < PropagationLevel.PARENT.value


class TestRuleAction:
    """Test RuleAction enum."""

    def test_rule_actions(self):
        """Rule actions have expected values."""
        assert RuleAction.INCLUDE == "include"
        assert RuleAction.EXCLUDE == "exclude"
        assert RuleAction.NO_DECISION == "no_decision"


class TestDetectedSymbol:
    """Test DetectedSymbol dataclass."""

    def test_symbol_creation(self):
        """Can create detected symbol."""
        symbol = DetectedSymbol(
            name="MyClass",
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=10, column=4),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source=None,
            original_name=None,
        )

        assert symbol.name == "MyClass"
        assert symbol.member_type == MemberType.CLASS
        assert symbol.location.line == 10
        assert symbol.provenance == SymbolProvenance.DEFINED_HERE

    def test_symbol_defaults(self):
        """Test default values."""
        symbol = DetectedSymbol(
            name="func",
            provenance=SymbolProvenance.IMPORTED,
            location=SourceLocation(line=1),
            member_type=MemberType.FUNCTION,
            is_private=True,
            original_source="other.module",
            original_name="other_func",
        )

        assert symbol.docstring is None
        assert symbol.metadata == {}
        assert symbol.location.column is None


class TestExportDecision:
    """Test ExportDecision dataclass."""

    def test_decision_creation(self):
        """Can create export decision."""
        symbol = DetectedSymbol(
            name="MyClass",
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=10),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source=None,
            original_name=None,
        )

        decision = ExportDecision(
            module_path="test.module",
            action=RuleAction.INCLUDE,
            export_name="MyClass",
            propagation=PropagationLevel.PARENT,
            priority=100,
            reason="Test rule",
            source_symbol=symbol,
        )

        assert decision.module_path == "test.module"
        assert decision.action == RuleAction.INCLUDE
        assert decision.source_symbol == symbol


class TestExportManifest:
    """Test ExportManifest dataclass."""

    def test_manifest_creation(self):
        """Can create export manifest."""
        own = [
            LazyExport(
                public_name="Own", target_module="test", target_object="Own", is_type_only=False
            )
        ]

        propagated = [
            LazyExport(
                public_name="Propagated",
                target_module="test.child",
                target_object="Propagated",
                is_type_only=False,
            )
        ]

        manifest = ExportManifest(
            module_path="test",
            own_exports=own,
            propagated_exports=propagated,
            all_exports=own + propagated,
        )

        assert manifest.module_path == "test"
        assert len(manifest.own_exports) == 1
        assert len(manifest.propagated_exports) == 1
        assert len(manifest.all_exports) == 2

    def test_export_names_sorted(self):
        """Export names are sorted alphabetically."""
        exports = [
            LazyExport(
                public_name="Zebra", target_module="test", target_object="Zebra", is_type_only=False
            ),
            LazyExport(
                public_name="Apple", target_module="test", target_object="Apple", is_type_only=False
            ),
        ]

        manifest = ExportManifest(
            module_path="test", own_exports=exports, propagated_exports=[], all_exports=exports
        )

        assert manifest.export_names == ["Apple", "Zebra"]


class TestRule:
    """Test Rule dataclass."""

    def test_rule_creation(self):
        """Can create rule."""
        rule = Rule(
            name="test-rule",
            priority=500,
            description="Test rule",
            match=RuleMatchCriteria(name_exact="test"),
            action=RuleAction.INCLUDE,
        )

        assert rule.name == "test-rule"
        assert rule.priority == 500
        assert rule.action == RuleAction.INCLUDE

    def test_rule_priority_validation(self):
        """Rule priority must be 0-1000."""
        # Valid priorities
        Rule(
            name="low",
            priority=0,
            description="Low priority",
            match=RuleMatchCriteria(),
            action=RuleAction.INCLUDE,
        )

        Rule(
            name="high",
            priority=1000,
            description="High priority",
            match=RuleMatchCriteria(),
            action=RuleAction.INCLUDE,
        )

        # Invalid priority (too high)
        with pytest.raises(ValueError, match="Priority must be 0-1000"):
            Rule(
                name="invalid",
                priority=1500,
                description="Invalid",
                match=RuleMatchCriteria(),
                action=RuleAction.INCLUDE,
            )

        # Invalid priority (negative)
        with pytest.raises(ValueError, match="Priority must be 0-1000"):
            Rule(
                name="invalid",
                priority=-100,
                description="Invalid",
                match=RuleMatchCriteria(),
                action=RuleAction.INCLUDE,
            )

    def test_rule_name_required(self):
        """Rule name is required."""
        with pytest.raises(ValueError, match="Rule name required"):
            Rule(
                name="",
                priority=500,
                description="Test",
                match=RuleMatchCriteria(),
                action=RuleAction.INCLUDE,
            )


class TestRuleMatchCriteria:
    """Test RuleMatchCriteria dataclass."""

    def test_match_criteria_all_none(self):
        """Match criteria with all None is valid."""
        criteria = RuleMatchCriteria()

        assert criteria.name_exact is None
        assert criteria.name_pattern is None
        assert criteria.module_exact is None

    def test_match_criteria_with_values(self):
        """Match criteria with specific values."""
        criteria = RuleMatchCriteria(
            name_exact="MyClass", module_pattern=r".*\.types", member_type=MemberType.CLASS
        )

        assert criteria.name_exact == "MyClass"
        assert criteria.module_pattern == r".*\.types"
        assert criteria.member_type == MemberType.CLASS


class TestValidationError:
    """Test ValidationError dataclass."""

    def test_validation_error_creation(self):
        """Can create validation error."""
        from pathlib import Path

        error = ValidationError(
            file=Path("test.py"),
            line=10,
            message="Import not found",
            suggestion="Check module path",
            code="BROKEN_IMPORT",
        )

        assert error.file == Path("test.py")
        assert error.line == 10
        assert error.message == "Import not found"
        assert error.code == "BROKEN_IMPORT"

    def test_validation_error_optional_fields(self):
        """Validation error has optional fields."""
        from pathlib import Path

        error = ValidationError(
            file=Path("test.py"),
            line=None,
            message="General error",
            suggestion=None,
            code="GENERAL_ERROR",
        )

        assert error.line is None
        assert error.suggestion is None
