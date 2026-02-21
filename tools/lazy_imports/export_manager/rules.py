# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Rule engine for export decision making.

This module implements the priority-based rule system for determining which
exports should be included and how they should propagate through the package
hierarchy.
"""

from __future__ import annotations

import re

from pathlib import Path

import yaml

from tools.lazy_imports.common.types import (
    DetectedSymbol,
    ExportDecision,
    MemberType,
    PropagationLevel,
    Rule,
    RuleAction,
    RuleMatchCriteria,
    SymbolProvenance,
)


# Schema version constants
CURRENT_SCHEMA_VERSION = "1.0"
SUPPORTED_VERSIONS = ["1.0"]


class SchemaVersionError(Exception):
    """Schema version mismatch or unsupported."""


class RuleEngine:
    """Registry and evaluator for all rules.

    The rule engine implements a priority-based system for deciding whether
    exports should be included and how far they should propagate. Rules are
    evaluated in priority order (highest first), and the first matching rule
    determines the action.
    """

    def __init__(self):
        """Initialize rule engine with empty rule set and no overrides."""
        self.rules: list[Rule] = []
        self.overrides: dict[str, dict[str, list[str]]] = {"include": {}, "exclude": {}}
        self._compiled_patterns: dict[str, re.Pattern] = {}

    def add_rule(self, rule: Rule) -> None:
        """Add a rule and maintain priority order."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: (-r.priority, r.name))

    def set_overrides(self, overrides: dict[str, dict[str, list[str]]]) -> None:
        """Set manual overrides (highest priority)."""
        self.overrides = overrides

    def evaluate(self, symbol: DetectedSymbol, module_path: str) -> ExportDecision:
        """Evaluate rules for a given export candidate.

        Args:
            symbol: The detected symbol to evaluate.
            module_path: The full dotted path of the module where the symbol is found.

        Returns:
            ExportDecision: The final decision on whether to export and how.
        """
        name = symbol.name

        # Check overrides first
        if (
            module_path in self.overrides["include"]
            and name in self.overrides["include"][module_path]
        ):
            return ExportDecision(
                module_path=module_path,
                action=RuleAction.INCLUDE,
                export_name=name,
                propagation=PropagationLevel.ROOT,  # Default to ROOT for manual includes
                priority=9999,
                reason=f"Manual override: {module_path}.{name} included",
                source_symbol=symbol,
            )

        if (
            module_path in self.overrides["exclude"]
            and name in self.overrides["exclude"][module_path]
        ):
            return ExportDecision(
                module_path=module_path,
                action=RuleAction.EXCLUDE,
                export_name=name,
                propagation=PropagationLevel.NONE,
                priority=9999,
                reason=f"Manual override: {module_path}.{name} excluded",
                source_symbol=symbol,
            )

        # Evaluate rules
        for rule in self.rules:
            if self._matches_rule(symbol, module_path, rule):
                return ExportDecision(
                    module_path=module_path,
                    action=rule.action,
                    export_name=name,
                    propagation=rule.propagate or PropagationLevel.PARENT,
                    priority=rule.priority,
                    reason=self._get_match_reason(symbol, module_path, rule),
                    source_symbol=symbol,
                )

        # No decision (default deny/ignore)
        return ExportDecision(
            module_path=module_path,
            action=RuleAction.NO_DECISION,
            export_name=name,
            propagation=PropagationLevel.NONE,
            priority=0,
            reason="No rule matched",
            source_symbol=symbol,
        )

    def _matches_rule(self, symbol: DetectedSymbol, module_path: str, rule: Rule) -> bool:
        """Check if a rule matches the given export."""
        return self._matches_criteria(symbol, module_path, rule.match)

    def _matches_criteria(
        self, symbol: DetectedSymbol, module_path: str, criteria: RuleMatchCriteria
    ) -> bool:
        """Check if match criteria are satisfied."""
        if criteria.any_of:
            return any(self._matches_criteria(symbol, module_path, sub) for sub in criteria.any_of)
        if criteria.all_of:
            return all(self._matches_criteria(symbol, module_path, sub) for sub in criteria.all_of)

        if criteria.name_exact and symbol.name != criteria.name_exact:
            return False

        if criteria.name_pattern:
            pattern = self._get_compiled_pattern(criteria.name_pattern)
            if not pattern.match(symbol.name):
                return False

        if criteria.module_exact and module_path != criteria.module_exact:
            return False

        if criteria.module_pattern:
            pattern = self._get_compiled_pattern(criteria.module_pattern)
            if not pattern.match(module_path):
                return False

        if criteria.member_type and symbol.member_type != criteria.member_type:
            return False

        return not (criteria.provenance and symbol.provenance != criteria.provenance)

    def _get_compiled_pattern(self, pattern_str: str) -> re.Pattern:
        """Get or compile a regex pattern (with caching)."""
        if pattern_str not in self._compiled_patterns:
            try:
                self._compiled_patterns[pattern_str] = re.compile(pattern_str)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {pattern_str!r}") from e
        return self._compiled_patterns[pattern_str]

    def _get_match_reason(self, symbol: DetectedSymbol, module_path: str, rule: Rule) -> str:
        """Generate human-readable reason for rule match."""
        return f"Matched rule: {rule.name}"

    def load_rules(self, rule_files: list[Path]) -> None:
        """Load rules from YAML files."""
        for rule_file in rule_files:
            if not rule_file.exists():
                raise FileNotFoundError(f"Rule file not found: {rule_file}")

            with rule_file.open() as f:
                try:
                    data = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML in {rule_file}: {e}") from e

            if "schema_version" not in data:
                raise SchemaVersionError(f"Missing schema_version in {rule_file}")

            version = data["schema_version"]
            if version not in SUPPORTED_VERSIONS:
                raise SchemaVersionError(f"Unsupported schema version {version}")

            if version != CURRENT_SCHEMA_VERSION:
                data = self._migrate_schema(data, from_version=version)

            for rule_data in data.get("rules", []):
                self.add_rule(self._parse_rule(rule_data, rule_file))

    def _migrate_schema(self, data: dict, from_version: str) -> dict:
        """Migrate config - placeholder."""
        return data

    def _parse_rule(self, rule_data: dict, source_file: Path) -> Rule:
        """Parse a rule from YAML data."""
        try:
            match_data = rule_data.get("match", {})
            match = RuleMatchCriteria(
                name_exact=match_data.get("name_exact"),
                name_pattern=match_data.get("name_pattern"),
                module_exact=match_data.get("module_exact"),
                module_pattern=match_data.get("module_pattern"),
                member_type=MemberType(match_data["member_type"])
                if "member_type" in match_data
                else None,
                provenance=SymbolProvenance(match_data["provenance"])
                if "provenance" in match_data
                else None,
                any_of=[self._parse_criteria(sub) for sub in match_data.get("any_of", [])] or None,
                all_of=[self._parse_criteria(sub) for sub in match_data.get("all_of", [])] or None,
            )

            # Pre-compile patterns
            if match.name_pattern:
                self._get_compiled_pattern(match.name_pattern)
            if match.module_pattern:
                self._get_compiled_pattern(match.module_pattern)

            return Rule(
                name=rule_data["name"],
                priority=rule_data.get("priority", 500),
                description=rule_data.get("description", ""),
                match=match,
                action=RuleAction(rule_data["action"]),
                propagate=PropagationLevel(rule_data["propagate"])
                if "propagate" in rule_data
                else None,
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Error in rule definition in {source_file}: {e}") from e

    def _parse_criteria(self, data: dict) -> RuleMatchCriteria:
        """Helper to parse nested criteria."""
        return RuleMatchCriteria(
            name_exact=data.get("name_exact"),
            name_pattern=data.get("name_pattern"),
            module_exact=data.get("module_exact"),
            module_pattern=data.get("module_pattern"),
            member_type=MemberType(data["member_type"]) if "member_type" in data else None,
            provenance=SymbolProvenance(data["provenance"]) if "provenance" in data else None,
            any_of=[self._parse_criteria(sub) for sub in data.get("any_of", [])] or None,
            all_of=[self._parse_criteria(sub) for sub in data.get("all_of", [])] or None,
        )

    def validate_rules(self) -> list[str]:
        """Validate all loaded rules."""
        return []
        # (Validation logic similar to before)
