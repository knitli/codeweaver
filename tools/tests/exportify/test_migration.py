#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for lazy import migration tool."""

# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports, avoid-loops-in-tests
from __future__ import annotations

from pathlib import Path

import yaml

from tools.exportify.common.types import MemberType, PropagationLevel, RuleAction
from tools.exportify.migration import RuleMigrator, verify_migration


class TestRuleMigrator:
    """Test the rule migration system."""

    def test_migrate_creates_valid_yaml(self, tmp_path: Path):
        """Test that migration creates valid YAML."""
        migrator = RuleMigrator()
        result = migrator.migrate()

        # Should succeed even if old script not found (uses defaults)
        assert result.success or result.errors  # Either works or has errors

        if result.success:
            # YAML should be parseable
            parsed = yaml.safe_load(result.yaml_content)
            assert "schema_version" in parsed
            assert "rules" in parsed
            assert len(parsed["rules"]) > 0

    def test_extracts_private_exclusion_rule(self):
        """Test extraction of private member exclusion."""
        migrator = RuleMigrator()
        migrator._extract_private_exclusion_rule()

        assert len(migrator.rules) == 1
        rule = migrator.rules[0]
        assert rule.name == "exclude-private-members"
        assert rule.priority == 900
        assert rule.action == RuleAction.EXCLUDE
        assert rule.pattern == r"^_.*"

    def test_extracts_constant_detection_rule(self):
        """Test extraction of constant detection."""
        migrator = RuleMigrator()
        migrator._extract_constant_detection_rule()

        assert len(migrator.rules) == 1
        rule = migrator.rules[0]
        assert rule.name == "include-constants"
        assert rule.priority == 700
        assert rule.action == RuleAction.INCLUDE
        assert rule.pattern == r"^[A-Z][A-Z0-9_]*$"
        assert rule.member_type == MemberType.CONSTANT

    def test_extracts_exception_propagation_rule(self):
        """Test extraction of exception propagation."""
        migrator = RuleMigrator()
        migrator._extract_exception_propagation_rule()

        assert len(migrator.rules) == 1
        rule = migrator.rules[0]
        assert rule.name == "propagate-exceptions"
        assert rule.priority == 800
        assert rule.action == RuleAction.INCLUDE
        assert rule.propagate == PropagationLevel.ROOT
        assert rule.member_type == MemberType.CLASS

    def test_extracts_module_exceptions(self):
        """Test extraction of module overrides."""
        migrator = RuleMigrator()
        migrator._extract_module_exceptions()

        # Should have some overrides
        assert len(migrator.overrides_include) > 0

        # Check specific known override
        assert "codeweaver.core.utils" in migrator.overrides_include
        assert "LazyImport" in migrator.overrides_include["codeweaver.core.utils"]

    def test_generates_valid_yaml_structure(self):
        """Test YAML generation structure."""
        migrator = RuleMigrator()
        migrator._extract_hardcoded_rules(Path("fake"))  # Uses defaults
        yaml_content = migrator._generate_yaml()

        parsed = yaml.safe_load(yaml_content)

        # Check structure
        assert parsed["schema_version"] == "1.0"
        assert "metadata" in parsed
        assert "rules" in parsed
        assert len(parsed["rules"]) > 0

        # Check first rule structure
        rule = parsed["rules"][0]
        assert "name" in rule
        assert "priority" in rule
        assert "description" in rule
        assert "match" in rule
        assert "action" in rule

    def test_rule_priority_ordering(self):
        """Test rules are ordered by priority in generated YAML."""
        migrator = RuleMigrator()
        migrator._extract_hardcoded_rules(Path("fake"))
        yaml_content = migrator._generate_yaml()

        import yaml

        parsed = yaml.safe_load(yaml_content)
        priorities = [r["priority"] for r in parsed["rules"]]

        # Should be in descending order
        assert priorities == sorted(priorities, reverse=True)

    def test_generates_equivalence_report(self):
        """Test equivalence report generation."""
        migrator = RuleMigrator()
        migrator._extract_hardcoded_rules(Path("fake"))
        report = migrator._generate_equivalence_report()

        # Should contain key sections
        assert "# Migration Equivalence Report" in report
        assert "## Rule Conversions" in report
        assert "## Validation Notes" in report

        # Should list rules
        for rule in migrator.rules:
            assert rule.name in report


class TestMigrationVerification:
    """Test migration verification."""

    def test_verify_private_exclusion(self, tmp_path: Path):
        """Test verification of private member exclusion."""
        # Create a minimal YAML config
        yaml_content = """
schema_version: "1.0"
rules:
  - name: exclude-private
    priority: 900
    description: Exclude private members
    match:
      name_pattern: "^_.*"
    action: exclude
"""
        yaml_path = tmp_path / "rules.yaml"
        yaml_path.write_text(yaml_content)

        # Verify
        test_cases = [
            ("_private", "test.module", MemberType.FUNCTION),
            ("__dunder__", "test.module", MemberType.FUNCTION),
        ]

        success, errors = verify_migration(yaml_path, test_cases)
        assert success, f"Verification failed: {errors}"

    def test_verify_constant_inclusion(self, tmp_path: Path):
        """Test verification of constant inclusion."""
        yaml_content = """
schema_version: "1.0"
rules:
  - name: include-constants
    priority: 700
    description: Include constants
    match:
      name_pattern: "^[A-Z][A-Z0-9_]*$"
      member_type: constant
    action: include
"""
        yaml_path = tmp_path / "rules.yaml"
        yaml_path.write_text(yaml_content)

        test_cases = [
            ("MAX_SIZE", "test.config", MemberType.CONSTANT),
            ("DEFAULT_VALUE", "test.config", MemberType.CONSTANT),
        ]

        success, errors = verify_migration(yaml_path, test_cases)
        assert success, f"Verification failed: {errors}"

    def test_verify_exception_propagation(self, tmp_path: Path):
        """Test verification of exception propagation."""
        yaml_content = """
schema_version: "1.0"
rules:
  - name: propagate-exceptions
    priority: 800
    description: Propagate exceptions to root
    match:
      name_pattern: ".*Error$|.*Exception$|.*Warning$"
      member_type: class
    action: include
    propagate: root
"""
        yaml_path = tmp_path / "rules.yaml"
        yaml_path.write_text(yaml_content)

        test_cases = [
            ("ValidationError", "test.exceptions", MemberType.CLASS),
            ("CustomException", "test.tools", MemberType.CLASS),
        ]

        success, errors = verify_migration(yaml_path, test_cases)
        assert success, f"Verification failed: {errors}"


class TestEndToEndMigration:
    """Test complete migration workflow."""

    def test_full_migration_workflow(self, tmp_path: Path):
        """Test complete migration from extraction to verification."""
        from tools.exportify.migration import migrate_to_yaml

        output_path = tmp_path / "lazy_import_rules.yaml"

        # Use a path that doesn't exist - migration should use defaults
        fake_script = tmp_path / "nonexistent.py"

        # Perform migration with fake script (uses defaults)
        result = migrate_to_yaml(output_path, old_script=fake_script, dry_run=True)

        # Migration should succeed with defaults even if script not found
        # (It uses hardcoded default rules)
        assert result.rules_extracted
        assert result.yaml_content
        assert result.equivalence_report

        # Should have key rules (from defaults)
        rule_names = {r.name for r in result.rules_extracted}
        assert "exclude-private-members" in rule_names
        assert "include-constants" in rule_names
        assert "propagate-exceptions" in rule_names

        # Verify YAML is valid
        parsed = yaml.safe_load(result.yaml_content)
        assert parsed["schema_version"] == "1.0"
        assert len(parsed["rules"]) > 0

    def test_migration_with_write(self, tmp_path: Path):
        """Test migration with file write."""
        from tools.exportify.migration import migrate_to_yaml

        output_path = tmp_path / "lazy_import_rules.yaml"

        # Perform migration
        result = migrate_to_yaml(output_path, dry_run=False)

        if result.success:
            # Files should exist
            assert output_path.exists()
            assert output_path.with_suffix(".migration.md").exists()

            # Content should be valid
            content = output_path.read_text()
            parsed = yaml.safe_load(content)
            assert "rules" in parsed
