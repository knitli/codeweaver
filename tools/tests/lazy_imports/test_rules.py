#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Comprehensive test suite for Rule Engine.

Tests cover:
- Core rule matching (exact, pattern, module)
- Priority ordering and lexicographic tiebreaking
- Provenance-based matching (DEFINED_HERE, IMPORTED, ALIAS_IMPORTED)
- Nested criteria (any_of, all_of)
- Rule loading from YAML
- Schema version validation
- Propagation levels
"""

# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
from __future__ import annotations

import tempfile

from pathlib import Path

import pytest
import yaml

from tools.lazy_imports.common.types import (
    DetectedSymbol,
    MemberType,
    PropagationLevel,
    Rule,
    RuleAction,
    RuleMatchCriteria,
    SourceLocation,
    SymbolProvenance,
)
from tools.lazy_imports.export_manager.rules import RuleEngine, SchemaVersionError


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def rule_engine() -> RuleEngine:
    """Create a fresh rule engine for each test."""
    return RuleEngine()


@pytest.fixture
def temp_rule_file():
    """Create a temporary rule file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yield f
    Path(f.name).unlink()


# ============================================================================
# Test Class: Rule Engine Core Functionality
# ============================================================================


class TestRuleEngine:
    """Test suite for rule engine core functionality."""

    def _create_symbol(
        self,
        name: str,
        member_type: MemberType,
        provenance: SymbolProvenance = SymbolProvenance.DEFINED_HERE,
    ) -> DetectedSymbol:
        """Helper to create a DetectedSymbol for testing."""
        return DetectedSymbol(
            name=name,
            member_type=member_type,
            provenance=provenance,
            location=SourceLocation(line=1),
            is_private=name.startswith("_"),
            original_source=None,
            original_name=name,
        )

    # ========================================================================
    # Core Matching Tests
    # ========================================================================

    def test_exact_name_match(self, rule_engine: RuleEngine):
        """Rule with exact name match should include export."""
        rule = Rule(
            name="include-version",
            priority=900,
            description="Include __version__",
            match=RuleMatchCriteria(name_exact="__version__"),
            action=RuleAction.INCLUDE,
        )
        rule_engine.add_rule(rule)

        symbol = self._create_symbol("__version__", MemberType.VARIABLE)
        result = rule_engine.evaluate(symbol, "codeweaver.core")

        assert result.action == RuleAction.INCLUDE
        assert result.reason.startswith("Matched rule: include-version")

    def test_pattern_match(self, rule_engine: RuleEngine):
        """Rule with regex pattern should match correctly."""
        rule = Rule(
            name="include-get-functions",
            priority=800,
            description="Include get_ functions",
            match=RuleMatchCriteria(name_pattern=r"^get_"),
            action=RuleAction.INCLUDE,
        )
        rule_engine.add_rule(rule)

        symbol = self._create_symbol("get_config", MemberType.FUNCTION)
        result = rule_engine.evaluate(symbol, "codeweaver.core")

        assert result.action == RuleAction.INCLUDE
        assert result.reason.startswith("Matched rule: include-get-functions")

    def test_pattern_no_match(self, rule_engine: RuleEngine):
        """Pattern that doesn't match should not trigger."""
        rule = Rule(
            name="include-get-functions",
            priority=800,
            description="Include get_ functions",
            match=RuleMatchCriteria(name_pattern=r"^get_"),
            action=RuleAction.INCLUDE,
        )
        rule_engine.add_rule(rule)

        symbol = self._create_symbol("set_config", MemberType.FUNCTION)
        result = rule_engine.evaluate(symbol, "codeweaver.core")

        assert result.action == RuleAction.NO_DECISION

    def test_no_matching_rule(self, rule_engine: RuleEngine):
        """When no rule matches, should return NO_DECISION."""
        rule = Rule(
            name="specific-rule",
            priority=500,
            description="Only matches 'specific'",
            match=RuleMatchCriteria(name_exact="specific"),
            action=RuleAction.INCLUDE,
        )
        rule_engine.add_rule(rule)

        symbol = self._create_symbol("something", MemberType.CLASS)
        result = rule_engine.evaluate(symbol, "module")

        assert result.action == RuleAction.NO_DECISION

    def test_module_pattern_match(self, rule_engine: RuleEngine):
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
        rule_engine.add_rule(rule)

        symbol = self._create_symbol("MyType", MemberType.CLASS)
        result = rule_engine.evaluate(symbol, "codeweaver.core.types")

        assert result.action == RuleAction.INCLUDE
        assert result.propagation == PropagationLevel.PARENT

    def test_module_pattern_no_match(self, rule_engine: RuleEngine):
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
        rule_engine.add_rule(rule)

        symbol = self._create_symbol("MyClass", MemberType.CLASS)
        result = rule_engine.evaluate(symbol, "codeweaver.core.utils")

        assert result.action == RuleAction.NO_DECISION

    # ========================================================================
    # Filtering Tests
    # ========================================================================

    def test_member_type_filter(self, rule_engine: RuleEngine):
        """Rule should filter by member type."""
        rule = Rule(
            name="classes-only",
            priority=600,
            description="Include classes only",
            match=RuleMatchCriteria(name_pattern=".*", member_type=MemberType.CLASS),
            action=RuleAction.INCLUDE,
        )
        rule_engine.add_rule(rule)

        # Class should match
        symbol_class = self._create_symbol("MyClass", MemberType.CLASS)
        result_class = rule_engine.evaluate(symbol_class, "module")
        assert result_class.action == RuleAction.INCLUDE

        # Function should not match
        symbol_func = self._create_symbol("my_function", MemberType.FUNCTION)
        result_func = rule_engine.evaluate(symbol_func, "module")
        assert result_func.action == RuleAction.NO_DECISION

    def test_exclude_private_members(self, rule_engine: RuleEngine):
        """Exclude rule should work for private members."""
        rule = Rule(
            name="exclude-private",
            priority=900,
            description="Exclude private members",
            match=RuleMatchCriteria(name_pattern=r"^_"),
            action=RuleAction.EXCLUDE,
        )
        rule_engine.add_rule(rule)

        symbol = self._create_symbol("_private_func", MemberType.FUNCTION)
        result = rule_engine.evaluate(symbol, "module")

        assert result.action == RuleAction.EXCLUDE

    # ========================================================================
    # Priority & Ordering Tests
    # ========================================================================

    def test_priority_ordering(self, rule_engine: RuleEngine):
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
        for rule in rules:
            rule_engine.add_rule(rule)

        symbol = self._create_symbol("__version__", MemberType.VARIABLE)
        result = rule_engine.evaluate(symbol, "any.module")

        assert result.action == RuleAction.INCLUDE
        assert result.priority == 900

    def test_lexicographic_tiebreak(self, rule_engine: RuleEngine):
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
        # Add in reverse alphabetical order to test sorting
        rule_engine.add_rule(rules[0])
        rule_engine.add_rule(rules[1])

        symbol = self._create_symbol("test", MemberType.CLASS)
        result = rule_engine.evaluate(symbol, "module")

        assert result.action == RuleAction.INCLUDE
        assert "aaa-include" in result.reason

    # ========================================================================
    # Provenance Matching Tests
    # ========================================================================

    def test_match_defined_here_provenance(self, rule_engine: RuleEngine, temp_rule_file) -> None:
        """Test matching symbols with DEFINED_HERE provenance."""
        rule_yaml = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "ExportDefinedSymbols",
                    "priority": 700,
                    "match": {"provenance": "defined_here"},
                    "action": "include",
                    "propagate": "parent",
                }
            ],
        }

        temp_rule_file.write(yaml.dump(rule_yaml))
        temp_rule_file.flush()
        rule_engine.load_rules([Path(temp_rule_file.name)])

        # Test with DEFINED_HERE symbol
        defined_symbol = DetectedSymbol(
            name="MyClass",
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=10),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source=None,
            original_name=None,
        )

        decision = rule_engine.evaluate(defined_symbol, "test.module")
        assert decision.action == RuleAction.INCLUDE
        assert decision.reason == "Matched rule: ExportDefinedSymbols"

        # Test with IMPORTED symbol (should not match)
        imported_symbol = DetectedSymbol(
            name="ImportedClass",
            provenance=SymbolProvenance.IMPORTED,
            location=SourceLocation(line=1),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source="other.module",
            original_name="ImportedClass",
        )

        decision = rule_engine.evaluate(imported_symbol, "test.module")
        assert decision.action == RuleAction.NO_DECISION

    def test_match_imported_provenance(self, rule_engine: RuleEngine, temp_rule_file) -> None:
        """Test matching symbols with IMPORTED provenance."""
        rule_yaml = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "ExcludeRegularImports",
                    "priority": 500,
                    "match": {"provenance": "imported"},
                    "action": "exclude",
                }
            ],
        }

        temp_rule_file.write(yaml.dump(rule_yaml))
        temp_rule_file.flush()
        rule_engine.load_rules([Path(temp_rule_file.name)])

        # Test with IMPORTED symbol
        imported_symbol = DetectedSymbol(
            name="something",
            provenance=SymbolProvenance.IMPORTED,
            location=SourceLocation(line=1),
            member_type=MemberType.IMPORTED,
            is_private=False,
            original_source="other.module",
            original_name="something",
        )

        decision = rule_engine.evaluate(imported_symbol, "test.module")
        assert decision.action == RuleAction.EXCLUDE

    def test_match_alias_imported_provenance(self, rule_engine: RuleEngine, temp_rule_file) -> None:
        """Test matching symbols with ALIAS_IMPORTED provenance (re-exports)."""
        rule_yaml = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "ExportAliasedImports",
                    "priority": 600,
                    "match": {"provenance": "alias_imported"},
                    "action": "include",
                    "propagate": "parent",
                }
            ],
        }

        temp_rule_file.write(yaml.dump(rule_yaml))
        temp_rule_file.flush()
        rule_engine.load_rules([Path(temp_rule_file.name)])

        # Test with ALIAS_IMPORTED symbol
        aliased_symbol = DetectedSymbol(
            name="PublicAPI",
            provenance=SymbolProvenance.ALIAS_IMPORTED,
            location=SourceLocation(line=1),
            member_type=MemberType.IMPORTED,
            is_private=False,
            original_source="internal.module",
            original_name="InternalAPI",
        )

        decision = rule_engine.evaluate(aliased_symbol, "test.module")
        assert decision.action == RuleAction.INCLUDE
        assert decision.reason == "Matched rule: ExportAliasedImports"

        # Test with regular IMPORTED (should not match)
        regular_import = DetectedSymbol(
            name="RegularImport",
            provenance=SymbolProvenance.IMPORTED,
            location=SourceLocation(line=2),
            member_type=MemberType.IMPORTED,
            is_private=False,
            original_source="other.module",
            original_name="RegularImport",
        )

        decision = rule_engine.evaluate(regular_import, "test.module")
        assert decision.action == RuleAction.NO_DECISION

    def test_provenance_with_all_of(self, rule_engine: RuleEngine, temp_rule_file) -> None:
        """Test provenance matching combined with other criteria using all_of."""
        rule_yaml = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "ExportDefinedClasses",
                    "priority": 700,
                    "match": {"all_of": [{"member_type": "class"}, {"provenance": "defined_here"}]},
                    "action": "include",
                    "propagate": "parent",
                }
            ],
        }

        temp_rule_file.write(yaml.dump(rule_yaml))
        temp_rule_file.flush()
        rule_engine.load_rules([Path(temp_rule_file.name)])

        # Test with matching symbol (class + defined_here)
        matching_symbol = DetectedSymbol(
            name="MyClass",
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=10),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source=None,
            original_name=None,
        )

        decision = rule_engine.evaluate(matching_symbol, "test.module")
        assert decision.action == RuleAction.INCLUDE

        # Test with non-matching symbol (function + defined_here)
        non_matching_symbol = DetectedSymbol(
            name="my_function",
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=15),
            member_type=MemberType.FUNCTION,
            is_private=False,
            original_source=None,
            original_name=None,
        )

        decision = rule_engine.evaluate(non_matching_symbol, "test.module")
        assert decision.action == RuleAction.NO_DECISION

        # Test with non-matching symbol (class + imported)
        imported_class = DetectedSymbol(
            name="ImportedClass",
            provenance=SymbolProvenance.IMPORTED,
            location=SourceLocation(line=1),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source="other.module",
            original_name="ImportedClass",
        )

        decision = rule_engine.evaluate(imported_class, "test.module")
        assert decision.action == RuleAction.NO_DECISION

    def test_provenance_with_any_of(self, rule_engine: RuleEngine, temp_rule_file) -> None:
        """Test provenance matching in any_of conditions."""
        rule_yaml = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "ExportDefinedOrAliased",
                    "priority": 650,
                    "match": {
                        "any_of": [{"provenance": "defined_here"}, {"provenance": "alias_imported"}]
                    },
                    "action": "include",
                    "propagate": "parent",
                }
            ],
        }

        temp_rule_file.write(yaml.dump(rule_yaml))
        temp_rule_file.flush()
        rule_engine.load_rules([Path(temp_rule_file.name)])

        # Test with DEFINED_HERE (should match)
        defined_symbol = DetectedSymbol(
            name="MyClass",
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=10),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source=None,
            original_name=None,
        )

        decision = rule_engine.evaluate(defined_symbol, "test.module")
        assert decision.action == RuleAction.INCLUDE

        # Test with ALIAS_IMPORTED (should match)
        aliased_symbol = DetectedSymbol(
            name="PublicAPI",
            provenance=SymbolProvenance.ALIAS_IMPORTED,
            location=SourceLocation(line=1),
            member_type=MemberType.IMPORTED,
            is_private=False,
            original_source="internal.module",
            original_name="InternalAPI",
        )

        decision = rule_engine.evaluate(aliased_symbol, "test.module")
        assert decision.action == RuleAction.INCLUDE

        # Test with IMPORTED (should not match)
        imported_symbol = DetectedSymbol(
            name="RegularImport",
            provenance=SymbolProvenance.IMPORTED,
            location=SourceLocation(line=2),
            member_type=MemberType.IMPORTED,
            is_private=False,
            original_source="other.module",
            original_name="RegularImport",
        )

        decision = rule_engine.evaluate(imported_symbol, "test.module")
        assert decision.action == RuleAction.NO_DECISION

    def test_provenance_priority_order(self, rule_engine: RuleEngine, temp_rule_file) -> None:
        """Test that provenance rules follow priority order correctly."""
        rule_yaml = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "ExcludeAllImports",
                    "priority": 500,
                    "match": {
                        "any_of": [{"provenance": "imported"}, {"provenance": "alias_imported"}]
                    },
                    "action": "exclude",
                },
                {
                    "name": "IncludeAliasedImports",
                    "priority": 600,  # Higher priority
                    "match": {"provenance": "alias_imported"},
                    "action": "include",
                    "propagate": "parent",
                },
            ],
        }

        temp_rule_file.write(yaml.dump(rule_yaml))
        temp_rule_file.flush()
        rule_engine.load_rules([Path(temp_rule_file.name)])

        # Test with ALIAS_IMPORTED - higher priority rule should win
        aliased_symbol = DetectedSymbol(
            name="PublicAPI",
            provenance=SymbolProvenance.ALIAS_IMPORTED,
            location=SourceLocation(line=1),
            member_type=MemberType.IMPORTED,
            is_private=False,
            original_source="internal.module",
            original_name="InternalAPI",
        )

        decision = rule_engine.evaluate(aliased_symbol, "test.module")
        assert decision.action == RuleAction.INCLUDE
        assert decision.reason == "Matched rule: IncludeAliasedImports"
        assert decision.priority == 600

    def test_no_provenance_criteria_matches_all(
        self, rule_engine: RuleEngine, temp_rule_file
    ) -> None:
        """Test that rules without provenance criteria match all provenances."""
        rule_yaml = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "ExportAllClasses",
                    "priority": 700,
                    "match": {"member_type": "class"},
                    "action": "include",
                    "propagate": "parent",
                }
            ],
        }

        temp_rule_file.write(yaml.dump(rule_yaml))
        temp_rule_file.flush()
        rule_engine.load_rules([Path(temp_rule_file.name)])

        # Test with DEFINED_HERE class
        defined_class = DetectedSymbol(
            name="DefinedClass",
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=10),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source=None,
            original_name=None,
        )

        decision = rule_engine.evaluate(defined_class, "test.module")
        assert decision.action == RuleAction.INCLUDE

        # Test with IMPORTED class
        imported_class = DetectedSymbol(
            name="ImportedClass",
            provenance=SymbolProvenance.IMPORTED,
            location=SourceLocation(line=1),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source="other.module",
            original_name="ImportedClass",
        )

        decision = rule_engine.evaluate(imported_class, "test.module")
        assert decision.action == RuleAction.INCLUDE

        # Test with ALIAS_IMPORTED class
        aliased_class = DetectedSymbol(
            name="AliasedClass",
            provenance=SymbolProvenance.ALIAS_IMPORTED,
            location=SourceLocation(line=2),
            member_type=MemberType.CLASS,
            is_private=False,
            original_source="other.module",
            original_name="OriginalClass",
        )

        decision = rule_engine.evaluate(aliased_class, "test.module")
        assert decision.action == RuleAction.INCLUDE

    # ========================================================================
    # Propagation Tests
    # ========================================================================

    def test_propagation_default(self, rule_engine: RuleEngine):
        """Default propagation when not specified."""
        rule = Rule(
            name="include-all",
            priority=500,
            description="Include all",
            match=RuleMatchCriteria(name_pattern=".*"),
            action=RuleAction.INCLUDE,
            # No propagate specified
        )
        rule_engine.add_rule(rule)

        symbol = self._create_symbol("something", MemberType.CLASS)
        result = rule_engine.evaluate(symbol, "module")

        assert result.action == RuleAction.INCLUDE
        assert result.propagation is None or result.propagation == PropagationLevel.PARENT

    def test_propagation_root(self, rule_engine: RuleEngine):
        """ROOT propagation level."""
        rule = Rule(
            name="version-to-root",
            priority=950,
            description="Version to root",
            match=RuleMatchCriteria(name_exact="__version__"),
            action=RuleAction.INCLUDE,
            propagate=PropagationLevel.ROOT,
        )
        rule_engine.add_rule(rule)

        symbol = self._create_symbol("__version__", MemberType.VARIABLE)
        result = rule_engine.evaluate(symbol, "deep.nested.module")

        assert result.action == RuleAction.INCLUDE
        assert result.propagation == PropagationLevel.ROOT


# ============================================================================
# Test Class: Rule Loading
# ============================================================================


class TestRuleLoading:
    """Test suite for rule loading and validation."""

    def test_load_from_dict_list(self, rule_engine: RuleEngine, temp_rule_file):
        """Should load rules from YAML dict structure."""
        rules_data = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "test-rule",
                    "priority": 500,
                    "description": "Test rule",
                    "match": {"name_pattern": "^test_"},
                    "action": "include",
                }
            ],
        }

        temp_rule_file.write(yaml.dump(rules_data))
        temp_rule_file.flush()
        temp_path = Path(temp_rule_file.name)

        rule_engine.load_rules([temp_path])

        symbol = DetectedSymbol(
            name="test_func",
            member_type=MemberType.FUNCTION,
            provenance=SymbolProvenance.DEFINED_HERE,
            location=SourceLocation(line=1),
            is_private=False,
            original_source=None,
            original_name="test_func",
        )
        result = rule_engine.evaluate(symbol, "module")
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

    def test_load_rule_with_provenance(self, rule_engine: RuleEngine, temp_rule_file) -> None:
        """Test loading a rule with provenance from YAML."""
        rule_yaml = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "TestRule",
                    "priority": 600,
                    "match": {"provenance": "alias_imported"},
                    "action": "include",
                }
            ],
        }

        temp_rule_file.write(yaml.dump(rule_yaml))
        temp_rule_file.flush()
        rule_engine.load_rules([Path(temp_rule_file.name)])

        assert len(rule_engine.rules) == 1
        rule = rule_engine.rules[0]
        assert rule.name == "TestRule"
        assert rule.match.provenance == SymbolProvenance.ALIAS_IMPORTED

    def test_invalid_provenance_value(self, rule_engine: RuleEngine, temp_rule_file) -> None:
        """Test that invalid provenance values raise an error."""
        rule_yaml = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "TestRule",
                    "priority": 600,
                    "match": {"provenance": "invalid_provenance"},
                    "action": "include",
                }
            ],
        }

        temp_rule_file.write(yaml.dump(rule_yaml))
        temp_rule_file.flush()

        with pytest.raises(ValueError, match="Error in rule definition"):
            rule_engine.load_rules([Path(temp_rule_file.name)])

    def test_nested_provenance_in_any_of(self, rule_engine: RuleEngine, temp_rule_file) -> None:
        """Test loading rules with provenance in nested any_of conditions."""
        rule_yaml = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "TestRule",
                    "priority": 650,
                    "match": {
                        "any_of": [{"provenance": "defined_here"}, {"provenance": "alias_imported"}]
                    },
                    "action": "include",
                }
            ],
        }

        temp_rule_file.write(yaml.dump(rule_yaml))
        temp_rule_file.flush()
        rule_engine.load_rules([Path(temp_rule_file.name)])

        assert len(rule_engine.rules) == 1
        rule = rule_engine.rules[0]
        assert rule.match.any_of is not None
        assert len(rule.match.any_of) == 2
        assert rule.match.any_of[0].provenance == SymbolProvenance.DEFINED_HERE
        assert rule.match.any_of[1].provenance == SymbolProvenance.ALIAS_IMPORTED


# ============================================================================
# Test Class: Schema Versioning
# ============================================================================


class TestSchemaVersioning:
    """Test suite for schema version validation."""

    def test_missing_schema_version_raises_error(self, rule_engine: RuleEngine, temp_rule_file):
        """Missing schema_version should raise SchemaVersionError."""
        rules_data = {
            "rules": [
                {
                    "name": "test-rule",
                    "priority": 500,
                    "description": "Test rule",
                    "match": {"name_pattern": "^test_"},
                    "action": "include",
                }
            ]
        }

        temp_rule_file.write(yaml.dump(rules_data))
        temp_rule_file.flush()
        temp_path = Path(temp_rule_file.name)

        with pytest.raises(SchemaVersionError) as exc_info:
            rule_engine.load_rules([temp_path])

        error_msg = str(exc_info.value)
        assert "Missing schema_version" in error_msg

    def test_unsupported_version_raises_error_with_helpful_message(
        self, rule_engine: RuleEngine, temp_rule_file
    ):
        """Unsupported version (e.g., '2.0') should raise with helpful message."""
        rules_data = {"schema_version": "2.0", "rules": []}

        temp_rule_file.write(yaml.dump(rules_data))
        temp_rule_file.flush()
        temp_path = Path(temp_rule_file.name)

        with pytest.raises(SchemaVersionError) as exc_info:
            rule_engine.load_rules([temp_path])

        error_msg = str(exc_info.value)
        assert "Unsupported schema version 2.0" in error_msg
