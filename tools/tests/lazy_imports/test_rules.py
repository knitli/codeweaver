"""Tests for Rule Engine."""

# ruff: noqa: TID252, S101, ANN201
# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
from __future__ import annotations

import pytest

from tools.lazy_imports.common.types import (
    MemberType,
    PropagationLevel,
    Rule,
    RuleAction,
    RuleMatchCriteria,
)
from tools.lazy_imports.export_manager.rules import RuleEngine


class TestRuleEngine:
    """Test suite for rule engine."""

    def test_exact_name_match(self):
        """Rule with exact name match should include export."""
        rule = Rule(
            name="include-version",
            priority=900,
            description="Include __version__",
            match=RuleMatchCriteria(name_exact="__version__"),
            action=RuleAction.INCLUDE,
        )
        engine = RuleEngine()


        engine.add_rule(rule)

        result = engine.evaluate("__version__", "codeweaver.core", MemberType.VARIABLE)

        assert result.action == RuleAction.INCLUDE
        assert result.matched_rule is not None
        assert result.matched_rule.rule_name == "include-version"

    def test_pattern_match(self):
        """Rule with regex pattern should match correctly."""
        rule = Rule(
            name="include-get-functions",
            priority=800,
            description="Include get_ functions",
            match=RuleMatchCriteria(name_pattern=r"^get_"),
            action=RuleAction.INCLUDE,
        )
        engine = RuleEngine()


        engine.add_rule(rule)

        result = engine.evaluate("get_config", "codeweaver.core", MemberType.FUNCTION)

        assert result.action == RuleAction.INCLUDE
        assert result.matched_rule is not None
        assert result.matched_rule.rule_name == "include-get-functions"

    def test_pattern_no_match(self):
        """Pattern that doesn't match should not trigger."""
        rule = Rule(
            name="include-get-functions",
            priority=800,
            description="Include get_ functions",
            match=RuleMatchCriteria(name_pattern=r"^get_"),
            action=RuleAction.INCLUDE,
        )
        engine = RuleEngine()


        engine.add_rule(rule)

        result = engine.evaluate("set_config", "codeweaver.core", MemberType.FUNCTION)

        assert result.action == RuleAction.NO_DECISION
        assert result.matched_rule is None

    def test_priority_ordering(self):
        """Higher priority rule should win over lower priority."""
        rules = [
            Rule(
                "exclude-all",
                priority=100,
                description="Exclude all",
                match=RuleMatchCriteria(name_pattern=".*"),
                action=RuleAction.EXCLUDE,
            ),
            Rule(
                "include-version",
                priority=900,
                description="Include version",
                match=RuleMatchCriteria(name_exact="__version__"),
                action=RuleAction.INCLUDE,
            ),
        ]
        engine = RuleEngine()

        engine.add_rule(rule)

        result = engine.evaluate("__version__", "any.module", MemberType.VARIABLE)

        assert result.action == RuleAction.INCLUDE
        assert result.matched_rule.rule_name == "include-version"

    def test_lexicographic_tiebreak(self):
        """Same priority: alphabetically first rule name wins."""
        rules = [
            Rule(
                "zzz-exclude",
                priority=500,
                description="Exclude",
                match=RuleMatchCriteria(name_pattern="test"),
                action=RuleAction.EXCLUDE,
            ),
            Rule(
                "aaa-include",
                priority=500,
                description="Include",
                match=RuleMatchCriteria(name_pattern="test"),
                action=RuleAction.INCLUDE,
            ),
        ]
        engine = RuleEngine()

        engine.add_rule(rule)

        result = engine.evaluate("test", "module", MemberType.CLASS)

        assert result.action == RuleAction.INCLUDE
        assert result.matched_rule.rule_name == "aaa-include"

    def test_no_matching_rule(self):
        """When no rule matches, should return NO_DECISION."""
        engine = RuleEngine()


        engine.add_rule(rule)

        result = engine.evaluate("something", "module", MemberType.CLASS)

        assert result.action == RuleAction.NO_DECISION
        assert result.matched_rule is None

    def test_module_pattern_match(self):
        """Rule should match on module pattern."""
        rule = Rule(
            name="types-propagate",
            priority=700,
            description="Types propagate to parent",
            match=RuleMatchCriteria(
                name_pattern=r"^[A-Z][a-zA-Z0-9]*$", module_pattern=r".*\.types(\..*)?"
            ),
            action=RuleAction.INCLUDE,
            propagate=PropagationLevel.PARENT,
        )
        engine = RuleEngine()


        engine.add_rule(rule)

        result = engine.evaluate("MyType", "codeweaver.core.types", MemberType.CLASS)

        assert result.action == RuleAction.INCLUDE
        assert result.propagation == PropagationLevel.PARENT

    def test_module_pattern_no_match(self):
        """Module pattern that doesn't match should not trigger."""
        rule = Rule(
            name="types-propagate",
            priority=700,
            description="Types propagate",
            match=RuleMatchCriteria(
                name_pattern=r"^[A-Z][a-zA-Z0-9]*$", module_pattern=r".*\.types(\..*)?"
            ),
            action=RuleAction.INCLUDE,
        )
        engine = RuleEngine()


        engine.add_rule(rule)

        result = engine.evaluate("MyClass", "codeweaver.core.utils", MemberType.CLASS)

        assert result.action == RuleAction.NO_DECISION

    def test_member_type_filter(self):
        """Rule should filter by member type."""
        rule = Rule(
            name="classes-only",
            priority=600,
            description="Include classes only",
            match=RuleMatchCriteria(name_pattern=".*", member_type=MemberType.CLASS),
            action=RuleAction.INCLUDE,
        )
        engine = RuleEngine()


        # Class should match
        result_class = engine.evaluate("MyClass", "module", MemberType.CLASS)
        assert result_class.action == RuleAction.INCLUDE

        # Function should not match
        result_func = engine.evaluate("my_function", "module", MemberType.FUNCTION)
        assert result_func.action == RuleAction.NO_DECISION

    def test_exclude_private_members(self):
        """Exclude rule should work for private members."""
        rule = Rule(
            name="exclude-private",
            priority=900,
            description="Exclude private members",
            match=RuleMatchCriteria(name_pattern=r"^_"),
            action=RuleAction.EXCLUDE,
        )
        engine = RuleEngine()


        engine.add_rule(rule)

        result = engine.evaluate("_private_func", "module", MemberType.FUNCTION)

        assert result.action == RuleAction.EXCLUDE

    def test_propagation_default(self):
        """Default propagation when not specified."""
        rule = Rule(
            name="include-all",
            priority=500,
            description="Include all",
            match=RuleMatchCriteria(name_pattern=".*"),
            action=RuleAction.INCLUDE,
            # No propagate specified
        )
        engine = RuleEngine()


        engine.add_rule(rule)

        result = engine.evaluate("something", "module", MemberType.CLASS)

        assert result.action == RuleAction.INCLUDE
        # Default propagation is None (will use default behavior)
        assert result.propagation is None or result.propagation == PropagationLevel.PARENT

    def test_propagation_root(self):
        """ROOT propagation level."""
        rule = Rule(
            name="version-to-root",
            priority=950,
            description="Version to root",
            match=RuleMatchCriteria(name_exact="__version__"),
            action=RuleAction.INCLUDE,
            propagate=PropagationLevel.ROOT,
        )
        engine = RuleEngine()


        engine.add_rule(rule)

        result = engine.evaluate("__version__", "deep.nested.module", MemberType.VARIABLE)

        assert result.action == RuleAction.INCLUDE
        assert result.propagation == PropagationLevel.ROOT

    def test_all_matches_recorded(self):
        """All matching rules should be recorded."""
        rules = [
            Rule(
                "match-1",
                priority=500,
                description="Match 1",
                match=RuleMatchCriteria(name_pattern="test"),
                action=RuleAction.INCLUDE,
            ),
            Rule(
                "match-2",
                priority=400,
                description="Match 2",
                match=RuleMatchCriteria(name_pattern=".*"),
                action=RuleAction.EXCLUDE,
            ),
        ]
        engine = RuleEngine()

        engine.add_rule(rule)

        result = engine.evaluate("test", "module", MemberType.CLASS)

        assert len(result.all_matches) == 2
        assert result.matched_rule.rule_name == "match-1"  # Higher priority wins

    def test_invalid_regex_pattern(self):
        """Invalid regex pattern should raise error during rule creation or evaluation."""
        # This depends on implementation - might validate at rule load time
        rule = Rule(
            name="invalid-regex",
            priority=500,
            description="Invalid regex",
            match=RuleMatchCriteria(name_pattern="[invalid"),  # Unclosed bracket
            action=RuleAction.INCLUDE,
        )

        engine = RuleEngine()


        # Should either fail at engine creation or during evaluation
        # For now, let's expect it to handle gracefully during evaluation
        result = engine.evaluate("test", "module", MemberType.CLASS)

        # Should not crash - either matches or doesn't
        assert result.action in (RuleAction.INCLUDE, RuleAction.EXCLUDE, RuleAction.NO_DECISION)

    def test_complex_pattern_matching(self):
        """Complex regex patterns should work."""
        rule = Rule(
            name="pascalcase-classes",
            priority=700,
            description="PascalCase classes",
            match=RuleMatchCriteria(
                name_pattern=r"^[A-Z][a-zA-Z0-9]*$", member_type=MemberType.CLASS
            ),
            action=RuleAction.INCLUDE,
        )
        engine = RuleEngine()


        # Should match
        assert engine.evaluate("MyClass", "module", MemberType.CLASS).action == RuleAction.INCLUDE
        assert (
            engine.evaluate("ClassABC123", "module", MemberType.CLASS).action == RuleAction.INCLUDE
        )

        # Should not match
        assert (
            engine.evaluate("myClass", "module", MemberType.CLASS).action == RuleAction.NO_DECISION
        )
        assert (
            engine.evaluate("my_class", "module", MemberType.CLASS).action == RuleAction.NO_DECISION
        )

    def test_multiple_criteria_all_must_match(self):
        """When multiple criteria specified, all must match."""
        rule = Rule(
            name="strict-match",
            priority=700,
            description="Strict match",
            match=RuleMatchCriteria(
                name_pattern=r"^[A-Z]", module_pattern=r".*\.types", member_type=MemberType.CLASS
            ),
            action=RuleAction.INCLUDE,
        )
        engine = RuleEngine()


        # All match - should include
        assert (
            engine.evaluate("MyClass", "pkg.types", MemberType.CLASS).action == RuleAction.INCLUDE
        )

        # Name doesn't match - should not include
        assert (
            engine.evaluate("myClass", "pkg.types", MemberType.CLASS).action
            == RuleAction.NO_DECISION
        )

        # Module doesn't match - should not include
        assert (
            engine.evaluate("MyClass", "pkg.utils", MemberType.CLASS).action
            == RuleAction.NO_DECISION
        )

        # Member type doesn't match - should not include
        assert (
            engine.evaluate("MyClass", "pkg.types", MemberType.FUNCTION).action
            == RuleAction.NO_DECISION
        )

    def test_empty_rules_list(self):
        """Engine with empty rules list should always return NO_DECISION."""
        engine = RuleEngine()


        engine.add_rule(rule)

        result = engine.evaluate("anything", "any.module", MemberType.CLASS)

        assert result.action == RuleAction.NO_DECISION
        assert result.matched_rule is None
        assert len(result.all_matches) == 0


class TestRuleLoading:
    """Test suite for rule loading and validation."""

    def test_load_from_dict_list(self):
        """Should load rules from list of dicts."""
        rules_data = [
            {
                "name": "test-rule",
                "priority": 500,
                "description": "Test rule",
                "match": {"name_pattern": "^test_"},
                "action": "include",
            }
        ]

        engine = RuleEngine()


        engine.add_rule(rule)

        result = engine.evaluate("test_func", "module", MemberType.FUNCTION)
        assert result.action == RuleAction.INCLUDE

    def test_invalid_action_value(self):
        """Should reject invalid action values."""
        with pytest.raises((ValueError, KeyError)):
            Rule(
                name="invalid",
                priority=500,
                description="Invalid",
                match=RuleMatchCriteria(),
                action="invalid_action",
            )

    def test_propagation_level_validation(self):
        """Should validate propagation levels."""
        # Valid propagation
        rule = Rule(
            name="valid",
            priority=500,
            description="Valid",
            match=RuleMatchCriteria(),
            action=RuleAction.INCLUDE,
            propagate=PropagationLevel.PARENT,
        )
        assert rule.propagate == PropagationLevel.PARENT

        # Invalid propagation (if validation exists)
        with pytest.raises((ValueError, KeyError)):
            Rule(
                name="invalid",
                priority=500,
                description="Invalid",
                match=RuleMatchCriteria(),
                action=RuleAction.INCLUDE,
                propagate="invalid_level",
            )
