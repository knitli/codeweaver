"""Rule engine for export decision making.

This module implements the priority-based rule system for determining which
exports should be included and how they should propagate through the package
hierarchy.
"""

from __future__ import annotations

import re

from pathlib import Path
from typing import Protocol

import yaml

from tools.lazy_imports.common.types import (
    MemberType,
    PropagationLevel,
    Rule,
    RuleAction,
    RuleEvaluationResult,
    RuleMatch,
    RuleMatchCriteria,
)


class RuleEngineProtocol(Protocol):
    """Interface for rule evaluation."""

    def evaluate(self, name: str, module: str, member_type: MemberType) -> RuleEvaluationResult:
        """Evaluate rules for an export candidate."""
        ...

    def load_rules(self, rule_files: list[Path]) -> None:
        """Load rules from files."""
        ...

    def validate_rules(self) -> list[str]:
        """Validate all loaded rules."""
        ...

    def get_rule_by_name(self, name: str) -> Rule | None:
        """Get a specific rule."""
        ...


class RuleEngine:
    """Registry and evaluator for all rules.

    The rule engine implements a priority-based system for deciding whether
    exports should be included and how far they should propagate. Rules are
    evaluated in priority order (highest first), and the first matching rule
    determines the action.

    Conflict resolution:
    - Higher priority always wins
    - Same priority: alphabetically first rule name wins
    """

    def __init__(self):
        """Initialize rule engine with empty rule set and no overrides."""
        self.rules: list[Rule] = []
        self.overrides: dict[str, dict[str, list[str]]] = {"include": {}, "exclude": {}}
        self._compiled_patterns: dict[str, re.Pattern] = {}

    def add_rule(self, rule: Rule) -> None:
        """Add a rule and maintain priority order.

        Rules are sorted by:
        1. Priority (descending - higher priority first)
        2. Name (ascending - alphabetically first wins ties)
        """
        self.rules.append(rule)
        self.rules.sort(key=lambda r: (-r.priority, r.name))

    def set_overrides(self, overrides: dict[str, dict[str, list[str]]]) -> None:
        """Set manual overrides (highest priority)."""
        self.overrides = overrides

    def evaluate(self, name: str, module: str, member_type: MemberType) -> RuleEvaluationResult:
        """Evaluate all rules for a given export.

        Returns:
            RuleEvaluationResult with action, matched rule, and propagation level
        """
        if module in self.overrides["include"] and name in self.overrides["include"][module]:
            return RuleEvaluationResult(
                action=RuleAction.INCLUDE,
                matched_rule=RuleMatch(
                    rule_name="manual-include-override",
                    priority=9999,
                    action=RuleAction.INCLUDE,
                    propagation=PropagationLevel.ROOT,
                    reason=f"Manual override: {module}.{name} included",
                ),
                propagation=PropagationLevel.ROOT,
                all_matches=[],
            )
        if module in self.overrides["exclude"] and name in self.overrides["exclude"][module]:
            return RuleEvaluationResult(
                action=RuleAction.EXCLUDE,
                matched_rule=RuleMatch(
                    rule_name="manual-exclude-override",
                    priority=9999,
                    action=RuleAction.EXCLUDE,
                    propagation=PropagationLevel.NONE,
                    reason=f"Manual override: {module}.{name} excluded",
                ),
                propagation=PropagationLevel.NONE,
                all_matches=[],
            )
        all_matches: list[RuleMatch] = []
        for rule in self.rules:
            if self._matches_rule(name, module, member_type, rule):
                match = RuleMatch(
                    rule_name=rule.name,
                    priority=rule.priority,
                    action=rule.action,
                    propagation=rule.propagate,
                    reason=self._get_match_reason(name, module, member_type, rule),
                )
                all_matches.append(match)
                return RuleEvaluationResult(
                    action=rule.action,
                    matched_rule=match,
                    propagation=rule.propagate,
                    all_matches=all_matches,
                )
        return RuleEvaluationResult(
            action=RuleAction.INCLUDE,
            matched_rule=None,
            propagation=PropagationLevel.NONE,
            all_matches=[],
        )

    def _matches_rule(self, name: str, module: str, member_type: MemberType, rule: Rule) -> bool:
        """Check if a rule matches the given export."""
        return self._matches_criteria(name, module, member_type, rule.match)

    def _matches_criteria(
        self, name: str, module: str, member_type: MemberType, criteria: RuleMatchCriteria
    ) -> bool:
        """Check if match criteria are satisfied."""
        if criteria.any_of:
            return any(
                self._matches_criteria(name, module, member_type, sub_criteria)
                for sub_criteria in criteria.any_of
            )
        if criteria.all_of:
            return all(
                self._matches_criteria(name, module, member_type, sub_criteria)
                for sub_criteria in criteria.all_of
            )
        if criteria.name_exact and name != criteria.name_exact:
            return False
        if criteria.name_pattern:
            pattern = self._get_compiled_pattern(criteria.name_pattern)
            if not pattern.match(name):
                return False
        if criteria.module_exact and module != criteria.module_exact:
            return False
        if criteria.module_pattern:
            pattern = self._get_compiled_pattern(criteria.module_pattern)
            if not pattern.match(module):
                return False
        return not (criteria.member_type and member_type != criteria.member_type)

    def _get_compiled_pattern(self, pattern_str: str) -> re.Pattern:
        """Get or compile a regex pattern (with caching)."""
        if pattern_str not in self._compiled_patterns:
            try:
                self._compiled_patterns[pattern_str] = re.compile(pattern_str)
            except re.error as e:
                raise ValueError(
                    f"Invalid regex pattern: {pattern_str!r}\nError: {e}\nPosition: {(e.pos if hasattr(e, 'pos') else 'unknown')}"
                ) from e
        return self._compiled_patterns[pattern_str]

    def _get_match_reason(self, name: str, module: str, member_type: MemberType, rule: Rule) -> str:
        """Generate human-readable reason for rule match."""
        reasons = []
        if rule.match.name_exact:
            reasons.append(f"name == {rule.match.name_exact!r}")
        if rule.match.name_pattern:
            reasons.append(f"name matches {rule.match.name_pattern!r}")
        if rule.match.module_exact:
            reasons.append(f"module == {rule.match.module_exact!r}")
        if rule.match.module_pattern:
            reasons.append(f"module matches {rule.match.module_pattern!r}")
        if rule.match.member_type:
            reasons.append(f"type == {rule.match.member_type.value}")
        return " AND ".join(reasons) if reasons else "always matches"

    def load_rules(self, rule_files: list[Path]) -> None:
        """Load rules from YAML files.

        Args:
            rule_files: List of YAML files containing rule definitions

        Raises:
            FileNotFoundError: If a rule file doesn't exist
            yaml.YAMLError: If YAML syntax is invalid
            ValueError: If rule schema is invalid
        """
        for rule_file in rule_files:
            if not rule_file.exists():
                raise FileNotFoundError(
                    f"Rule file not found: {rule_file}\nSuggestions:\n- Create the file: touch {rule_file}\n- Remove reference from config\n- Check file path spelling"
                )
            with rule_file.open() as f:
                try:
                    data = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    raise ValueError(
                        f"❌ Error loading rules from {rule_file}\n\nInvalid YAML syntax:\n{e}\n\nSuggestions:\n- Check for missing quotes, colons, or indentation\n- Validate YAML at: https://www.yamllint.com/\n- Restore from backup: {rule_file}.bak"
                    ) from e
            schema_version = data.get("schema_version", "1.0")
            if schema_version not in ("1.0", "1.1"):
                raise ValueError(
                    f"❌ Error: Unsupported schema version\n\nFile: {rule_file}\nSchema version: {schema_version!r}\nSupported versions: 1.0, 1.1\n\nSuggestions:\n- Upgrade codeweaver to support this schema\n- Migrate config to supported version\n- Use migration tool: mise run lazy-imports migrate-config"
                )
            for rule_data in data.get("rules", []):
                rule = self._parse_rule(rule_data, rule_file)
                self.add_rule(rule)

    def _parse_rule(self, rule_data: dict, source_file: Path) -> Rule:
        """Parse a rule from YAML data.

        Args:
            rule_data: Rule dictionary from YAML
            source_file: Source file path for error messages

        Returns:
            Parsed Rule object

        Raises:
            ValueError: If rule data is invalid
        """
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
                any_of=[RuleMatchCriteria(**sub_match) for sub_match in match_data["any_of"]]
                if "any_of" in match_data
                else None,
                all_of=[RuleMatchCriteria(**sub_match) for sub_match in match_data["all_of"]]
                if "all_of" in match_data
                else None,
            )
            if match.name_pattern:
                self._get_compiled_pattern(match.name_pattern)
            if match.module_pattern:
                self._get_compiled_pattern(match.module_pattern)
            action = RuleAction(rule_data["action"])
            propagate = None
            if "propagate" in rule_data:
                propagate = PropagationLevel(rule_data["propagate"])
        except (KeyError, ValueError, TypeError) as e:
            raise ValueError(
                f"❌ Error in rule definition\n\nFile: {source_file}\nRule: {rule_data.get('name', 'unnamed')}\nError: {e}\n\nCheck rule schema and ensure all required fields are present."
            ) from e
        else:
            return Rule(
                name=rule_data["name"],
                priority=rule_data.get("priority", 500),
                description=rule_data.get("description", ""),
                match=match,
                action=action,
                propagate=propagate,
            )

    def validate_rules(self) -> list[str]:
        """Validate all loaded rules.

        Returns:
            List of validation errors (empty if all rules valid)
        """
        errors = []
        rule_names = [r.name for r in self.rules]
        duplicates = [name for name in rule_names if rule_names.count(name) > 1]
        if duplicates:
            errors.append(f"Duplicate rule names found: {', '.join(set(duplicates))}")
        errors.extend(
            f"Rule {rule.name!r} has invalid priority: {rule.priority} (must be 0-1000)"
            for rule in self.rules
            if not 0 <= rule.priority <= 1000
        )
        return errors

    def get_rule_by_name(self, name: str) -> Rule | None:
        """Get a specific rule by name."""
        return next((rule for rule in self.rules if rule.name == name), None)

    def get_all_rules(self) -> list[Rule]:
        """Get all loaded rules in priority order."""
        return self.rules.copy()
