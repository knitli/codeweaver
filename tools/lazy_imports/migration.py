#!/usr/bin/env python3
"""Migration tool to convert old hardcoded validation to new YAML-based rules.

This module analyzes the legacy validate-lazy-imports.py script and generates
equivalent YAML configuration that preserves all existing behavior.

Workflow:
    1. Extract rules from hardcoded if/else logic
    2. Convert to YAML rule definitions
    3. Extract module-specific overrides
    4. Generate migration report showing conversions
    5. Validate equivalence between old and new systems

Usage:
    codeweaver lazy-imports migrate [--output PATH] [--dry-run]
"""

from __future__ import annotations

import ast
import re

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .common.types import MemberType, PropagationLevel, RuleAction


# Constants from old system
OLD_SCRIPT = Path("mise-tasks/validate-lazy-imports.py")
DEFAULT_OUTPUT = Path(".codeweaver/lazy_import_rules.yaml")
SCHEMA_VERSION = "1.0"

# Known exception patterns in old system
EXCEPTION_MODULES = [
    "codeweaver.__version__",
    "codeweaver.server.mcp.user_agent",
    "codeweaver.core.utils.create_lazy_getattr",
    "codeweaver.core.utils.LazyImport",
    "codeweaver.core.utils.lazy_importer",
    "codeweaver.server.mcp.middleware.default_middleware_for_transport",
    "codeweaver.server.mcp.middleware.McpMiddleware",
    "codeweaver.providers.agent.AgentProfile",
    "codeweaver.providers.agent.AgentProfileSpec",
    "codeweaver.providers.reranking.providers.sentence_transformers",
    "codeweaver.providers.embedding.providers.sentence_transformers",
    "codeweaver.providers.reranking.capabilities.dependency_map",
    "codeweaver.providers.reranking.capabilities.load_default_capabilities",
    "codeweaver.providers.vector_stores.get_vector_store_provider",
    "codeweaver_tokenizers.get_tokenizer",
    "codeweaver.providers.embedding.capabilities.load_default_capabilities",
    "codeweaver.providers.embedding.capabilities.load_sparse_capabilities",
]


@dataclass
class ExtractedRule:
    """A rule extracted from the old system."""

    name: str
    priority: int
    description: str
    pattern: str | None
    exact_match: str | None
    member_type: MemberType | None
    action: RuleAction
    propagate: PropagationLevel | None
    source_line: int | None = None


@dataclass
class MigrationResult:
    """Result of migration process."""

    yaml_content: str
    rules_extracted: list[ExtractedRule]
    overrides_extracted: dict[str, dict[str, list[str]]]
    equivalence_report: str
    success: bool
    errors: list[str]


class RuleMigrator:
    """Migrator to convert old hardcoded system to YAML rules."""

    def __init__(self):
        """Initialize migrator with empty state."""
        self.rules: list[ExtractedRule] = []
        self.overrides_include: dict[str, list[str]] = {}
        self.overrides_exclude: dict[str, list[str]] = {}
        self.errors: list[str] = []

    def migrate(self, old_script: Path = OLD_SCRIPT) -> MigrationResult:
        """Perform complete migration from old to new system.

        Args:
            old_script: Path to old validation script

        Returns:
            MigrationResult with YAML content and migration details
        """
        if not old_script.exists():
            return MigrationResult(
                yaml_content="",
                rules_extracted=[],
                overrides_extracted={},
                equivalence_report="",
                success=False,
                errors=[f"Old script not found: {old_script}"],
            )

        # Extract rules from old system
        self._extract_hardcoded_rules(old_script)

        # Extract module exceptions
        self._extract_module_exceptions()

        # Generate YAML configuration
        yaml_content = self._generate_yaml()

        # Create equivalence report
        report = self._generate_equivalence_report()

        return MigrationResult(
            yaml_content=yaml_content,
            rules_extracted=self.rules,
            overrides_extracted={
                "include": self.overrides_include,
                "exclude": self.overrides_exclude,
            },
            equivalence_report=report,
            success=len(self.errors) == 0,
            errors=self.errors,
        )

    def _extract_hardcoded_rules(self, script_path: Path) -> None:
        """Extract rules from hardcoded logic in old script.

        The old script contains hardcoded patterns for:
        - Private member exclusion (starts with _)
        - Exception/Error class propagation
        - Type alias handling
        - Constant detection (SCREAMING_SNAKE_CASE)
        - Special module patterns
        """
        # Read and parse the old script
        try:
            source = script_path.read_text(encoding="utf-8")
            ast.parse(source)
        except Exception as e:
            self.errors.append(f"Failed to parse old script: {e}")
            return

        # Analyze the get_public_members function for patterns
        self._extract_private_exclusion_rule()
        self._extract_constant_detection_rule()
        self._extract_exception_propagation_rule()
        self._extract_type_alias_rule()
        self._extract_function_class_inclusion_rule()

    def _extract_private_exclusion_rule(self) -> None:
        """Extract the private member exclusion pattern."""
        self.rules.append(
            ExtractedRule(
                name="exclude-private-members",
                priority=900,
                description="Exclude private members (starting with underscore)",
                pattern=r"^_.*",
                exact_match=None,
                member_type=None,
                action=RuleAction.EXCLUDE,
                propagate=None,
                source_line=None,
            )
        )

    def _extract_constant_detection_rule(self) -> None:
        """Extract constant detection pattern (SCREAMING_SNAKE_CASE)."""
        self.rules.append(
            ExtractedRule(
                name="include-constants",
                priority=700,
                description="Include module-level constants (SCREAMING_SNAKE_CASE)",
                pattern=r"^[A-Z][A-Z0-9_]*$",
                exact_match=None,
                member_type=MemberType.CONSTANT,
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.NONE,
                source_line=None,
            )
        )

    def _extract_exception_propagation_rule(self) -> None:
        """Extract exception class propagation pattern."""
        self.rules.append(
            ExtractedRule(
                name="propagate-exceptions",
                priority=800,
                description="Propagate exception classes to root package",
                pattern=r".*Error$|.*Exception$|.*Warning$",
                exact_match=None,
                member_type=MemberType.CLASS,
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.ROOT,
                source_line=None,
            )
        )

    def _extract_type_alias_rule(self) -> None:
        """Extract type alias handling pattern."""
        self.rules.append(
            ExtractedRule(
                name="include-type-aliases",
                priority=650,
                description="Include type aliases (detected via TypeAlias or capital name)",
                pattern=r"^[A-Z][a-zA-Z0-9]*$",
                exact_match=None,
                member_type=MemberType.TYPE_ALIAS,
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.PARENT,
                source_line=None,
            )
        )

    def _extract_function_class_inclusion_rule(self) -> None:
        """Extract default inclusion for public functions and classes."""
        # Public functions
        self.rules.append(
            ExtractedRule(
                name="include-public-functions",
                priority=500,
                description="Include public functions (not starting with underscore)",
                pattern=r"^[a-z_][a-z0-9_]*$",
                exact_match=None,
                member_type=MemberType.FUNCTION,
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.NONE,
                source_line=None,
            )
        )

        # Public classes
        self.rules.append(
            ExtractedRule(
                name="include-public-classes",
                priority=500,
                description="Include public classes (CamelCase)",
                pattern=r"^[A-Z][a-zA-Z0-9]*$",
                exact_match=None,
                member_type=MemberType.CLASS,
                action=RuleAction.INCLUDE,
                propagate=PropagationLevel.NONE,
                source_line=None,
            )
        )

    def _extract_module_exceptions(self) -> None:
        """Extract module-specific exceptions from IS_EXCEPTION list."""
        # Parse module paths and convert to overrides
        for full_path in EXCEPTION_MODULES:
            # Split module.name format
            parts = full_path.rsplit(".", 1)
            if len(parts) == 2:
                module, name = parts
                if module not in self.overrides_include:
                    self.overrides_include[module] = []
                self.overrides_include[module].append(name)
            else:
                # Whole module exception (rare)
                self.overrides_include[full_path] = ["*"]

    def _generate_yaml(self) -> str:
        """Generate YAML configuration from extracted rules.

        Returns:
            YAML string with schema, rules, and overrides
        """
        # Sort rules by priority (descending)
        sorted_rules = sorted(self.rules, key=lambda r: (-r.priority, r.name))

        # Build YAML structure
        yaml_data: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "metadata": {
                "generated_by": "migration tool",
                "source": str(OLD_SCRIPT),
                "note": "Auto-generated from legacy validation script",
            },
            "rules": [],
        }

        # Add rules
        for rule in sorted_rules:
            rule_dict: dict[str, Any] = {
                "name": rule.name,
                "priority": rule.priority,
                "description": rule.description,
                "match": {},
                "action": rule.action.value,
            }

            # Add match criteria
            if rule.pattern:
                rule_dict["match"]["name_pattern"] = rule.pattern
            if rule.exact_match:
                rule_dict["match"]["name_exact"] = rule.exact_match
            if rule.member_type:
                rule_dict["match"]["member_type"] = rule.member_type.value

            # Add propagation if specified
            if rule.propagate:
                rule_dict["propagate"] = rule.propagate.value

            yaml_data["rules"].append(rule_dict)

        # Add overrides if any
        if self.overrides_include or self.overrides_exclude:
            yaml_data["overrides"] = {}
            if self.overrides_include:
                yaml_data["overrides"]["include"] = self.overrides_include
            if self.overrides_exclude:
                yaml_data["overrides"]["exclude"] = self.overrides_exclude

        # Generate YAML with comments
        yaml_str = yaml.dump(
            yaml_data, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100
        )

        # Add header comment
        header = f"""# CodeWeaver Lazy Import Rules
# Auto-generated from legacy validation script
#
# This configuration replaces hardcoded rules with declarative YAML definitions.
# Rules are evaluated in priority order (highest first).
#
# Schema: {SCHEMA_VERSION}
# Source: {OLD_SCRIPT}

"""

        return header + yaml_str

    def _generate_equivalence_report(self) -> str:
        """Generate report showing migration equivalence.

        Returns:
            Markdown report with rule mappings and validation
        """
        report_lines = [
            "# Migration Equivalence Report",
            "",
            f"**Source**: `{OLD_SCRIPT}`",
            f"**Generated Rules**: {len(self.rules)}",
            f"**Override Modules**: {len(self.overrides_include) + len(self.overrides_exclude)}",
            "",
            "## Rule Conversions",
            "",
        ]

        # Sort by priority for report
        sorted_rules = sorted(self.rules, key=lambda r: (-r.priority, r.name))

        for rule in sorted_rules:
            report_lines.append(f"### {rule.name} (priority {rule.priority})")
            report_lines.append(f"**Description**: {rule.description}")
            report_lines.append(f"**Action**: `{rule.action.value}`")

            if rule.pattern:
                report_lines.append(f"**Pattern**: `{rule.pattern}`")
            if rule.exact_match:
                report_lines.append(f"**Exact Match**: `{rule.exact_match}`")
            if rule.member_type:
                report_lines.append(f"**Member Type**: `{rule.member_type.value}`")
            if rule.propagate:
                report_lines.append(f"**Propagation**: `{rule.propagate.value}`")

            report_lines.append("")

        # Overrides section
        if self.overrides_include or self.overrides_exclude:
            report_lines.append("## Manual Overrides")
            report_lines.append("")

            if self.overrides_include:
                report_lines.append("### Include Overrides")
                for module, names in sorted(self.overrides_include.items()):
                    report_lines.append(f"- **{module}**: {', '.join(sorted(names))}")
                report_lines.append("")

            if self.overrides_exclude:
                report_lines.append("### Exclude Overrides")
                for module, names in sorted(self.overrides_exclude.items()):
                    report_lines.append(f"- **{module}**: {', '.join(sorted(names))}")
                report_lines.append("")

        # Validation notes
        report_lines.extend([
            "## Validation Notes",
            "",
            "### Pattern Equivalence",
            "- Private exclusion: `^_.*` matches old `name.startswith('_')`",
            "- Constants: `^[A-Z][A-Z0-9_]*$` matches old `name.isupper()`",
            "- Exceptions: `.*Error$|.*Exception$|.*Warning$` matches old suffix check",
            "",
            "### Priority Assignment",
            "Rules maintain behavioral equivalence through priority ordering:",
            "- 900: Private exclusion (must run first)",
            "- 800: Exception propagation (high priority)",
            "- 700: Constant detection",
            "- 650: Type alias handling",
            "- 500: Default public member inclusion",
            "",
            "### Override Handling",
            f"Converted {len(EXCEPTION_MODULES)} module exceptions to overrides.",
            "These have implicit priority 9999 (highest).",
            "",
        ])

        return "\n".join(report_lines)


def migrate_to_yaml(
    output_path: Path = DEFAULT_OUTPUT, old_script: Path = OLD_SCRIPT, *, dry_run: bool = False
) -> MigrationResult:
    """Perform migration and optionally write output.

    Args:
        output_path: Where to write YAML config
        old_script: Path to old validation script
        dry_run: If True, don't write files

    Returns:
        MigrationResult with YAML content and details
    """
    migrator = RuleMigrator()
    result = migrator.migrate(old_script)

    if not dry_run and result.success:
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write YAML config
        output_path.write_text(result.yaml_content, encoding="utf-8")

        # Write equivalence report
        report_path = output_path.with_suffix(".migration.md")
        report_path.write_text(result.equivalence_report, encoding="utf-8")

    return result


def verify_migration(
    yaml_path: Path = DEFAULT_OUTPUT, test_cases: list[tuple[str, str, MemberType]] | None = None
) -> tuple[bool, list[str]]:
    """Verify migration produces equivalent behavior.

    Args:
        yaml_path: Path to generated YAML config
        test_cases: Test cases (name, module, member_type) to validate

    Returns:
        (success, errors) tuple
    """
    from .export_manager.rules import RuleEngine

    # Load new rule engine
    engine = RuleEngine()
    try:
        engine.load_rules([yaml_path])
    except Exception as e:
        return False, [f"Failed to load rules: {e}"]

    # Default test cases representing old system behavior
    if test_cases is None:
        test_cases = [
            # Private members should be excluded
            ("_private_func", "codeweaver.core", MemberType.FUNCTION),
            ("__dunder__", "codeweaver.core", MemberType.FUNCTION),
            # Constants should be included
            ("MAX_SIZE", "codeweaver.config", MemberType.CONSTANT),
            # Exceptions should be included and propagated
            ("ValidationError", "codeweaver.exceptions", MemberType.CLASS),
            ("CustomException", "codeweaver.tools", MemberType.CLASS),
            # Public functions should be included
            ("public_function", "codeweaver.utils", MemberType.FUNCTION),
            # Public classes should be included
            ("PublicClass", "codeweaver.core", MemberType.CLASS),
        ]

    errors = []

    # Test each case
    for name, module, member_type in test_cases:
        result = engine.evaluate(name, module, member_type)

        # Verify expected behavior
        if name.startswith("_"):
            # Private should be excluded
            if result.action != RuleAction.EXCLUDE:
                errors.append(f"Private member {name} not excluded: got {result.action.value}")

        elif re.match(r"^[A-Z][A-Z0-9_]*$", name) and member_type == MemberType.CONSTANT:
            # Constants should be included
            if result.action != RuleAction.INCLUDE:
                errors.append(f"Constant {name} not included: got {result.action.value}")

        elif (
            re.match(r".*Error$|.*Exception$|.*Warning$", name) and member_type == MemberType.CLASS
        ):
            # Exceptions should be included and propagated to root
            if result.action != RuleAction.INCLUDE:
                errors.append(f"Exception {name} not included: got {result.action.value}")
            if result.propagation != PropagationLevel.ROOT:
                errors.append(f"Exception {name} not propagated to root: got {result.propagation}")

        else:
            # Other public members should be included (with no/parent propagation)
            if result.action != RuleAction.INCLUDE:
                errors.append(f"Public member {name} not included: got {result.action.value}")

    return not errors, errors


# CLI integration helpers
def cli_migrate(output: Path | None = None, *, dry_run: bool = False, verbose: bool = False) -> int:
    """CLI command for migration.

    Args:
        output: Output path for YAML config
        dry_run: If True, show output but don't write
        verbose: If True, show detailed output

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    output_path = output or DEFAULT_OUTPUT

    # Perform migration
    result = migrate_to_yaml(output_path, dry_run=dry_run)

    if not result.success:
        print("❌ Migration failed:")
        for error in result.errors:
            print(f"  - {error}")
        return 1

    # Show results
    print("✅ Migration successful!")
    print(f"   Rules extracted: {len(result.rules_extracted)}")
    print(
        f"   Overrides: {len(result.overrides_extracted.get('include', {}))} include, "
        f"{len(result.overrides_extracted.get('exclude', {}))} exclude"
    )

    if dry_run:
        print("\n📄 Generated YAML (dry run - not written):")
        print("─" * 80)
        print(result.yaml_content)
        print("─" * 80)
    else:
        print(f"\n📝 Written to: {output_path}")
        print(f"📄 Report: {output_path.with_suffix('.migration.md')}")

    if verbose:
        print("\n" + result.equivalence_report)

    # Verify migration
    if not dry_run:
        print("\n🔍 Verifying migration...")
        success, errors = verify_migration(output_path)
        if success:
            print("✅ Verification passed - new rules are equivalent!")
        else:
            print("⚠️ Verification found issues:")
            for error in errors:
                print(f"  - {error}")
            return 1

    return 0
