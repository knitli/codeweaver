"""Tests for common types and data structures."""

# ruff: noqa: TID252, S101, ANN201
# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
from __future__ import annotations

import pytest

from tools.lazy_imports.common.types import (
    ExportManifest,
    ExportNode,
    MemberType,
    PropagationLevel,
    Rule,
    RuleAction,
    RuleMatchCriteria,
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


class TestExportNode:
    """Test ExportNode dataclass."""

    def test_export_node_creation(self):
        """Can create export node."""
        from pathlib import Path

        node = ExportNode(
            name="MyClass",
            module="test.module",
            member_type=MemberType.CLASS,
            propagation=PropagationLevel.PARENT,
            source_file=Path("test/module.py"),
            line_number=10,
            defined_in="test.module",
        )

        assert node.name == "MyClass"
        assert node.module == "test.module"
        assert node.member_type == MemberType.CLASS
        assert node.propagation == PropagationLevel.PARENT

    def test_export_node_is_hashable(self):
        """Export nodes are hashable for use in sets."""
        from pathlib import Path

        node1 = ExportNode(
            name="MyClass",
            module="test.module",
            member_type=MemberType.CLASS,
            propagation=PropagationLevel.PARENT,
            source_file=Path("test/module.py"),
            line_number=10,
            defined_in="test.module",
        )

        node2 = ExportNode(
            name="MyClass",
            module="test.module",
            member_type=MemberType.CLASS,
            propagation=PropagationLevel.PARENT,
            source_file=Path("test/module.py"),
            line_number=10,
            defined_in="test.module",
        )

        # Can use in sets
        nodes = {node1, node2}
        assert len(nodes) == 1  # Same content = same hash

    def test_export_node_default_fields(self):
        """Export node has default values for optional fields."""
        from pathlib import Path

        node = ExportNode(
            name="func",
            module="test",
            member_type=MemberType.FUNCTION,
            propagation=PropagationLevel.NONE,
            source_file=Path("test.py"),
            line_number=1,
            defined_in="test",
        )

        assert node.docstring is None
        assert node.propagates_to == set()
        assert node.dependencies == set()


class TestExportManifest:
    """Test ExportManifest dataclass."""

    def test_manifest_creation(self):
        """Can create export manifest."""
        from pathlib import Path

        own = [
            ExportNode(
                name="Own",
                module="test",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("test.py"),
                line_number=1,
                defined_in="test",
            )
        ]

        propagated = [
            ExportNode(
                name="Propagated",
                module="test.child",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("test/child.py"),
                line_number=1,
                defined_in="test.child",
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
        from pathlib import Path

        exports = [
            ExportNode(
                name="Zebra",
                module="test",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("test.py"),
                line_number=1,
                defined_in="test",
            ),
            ExportNode(
                name="Apple",
                module="test",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("test.py"),
                line_number=2,
                defined_in="test",
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
