#!/usr/bin/env -S uv run -s
# ///script
# python-version: ">=3.11"
# dependencies: "pydantic"
# ///
# sourcery skip: name-type-suffix, no-complex-if-expressions
"""Analyze grammar structure patterns across all supported languages.

This script extracts and categorizes structural patterns from node_types.json
files to inform the grammar-based classification system design.

SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-License-Identifier: MIT OR Apache-2.0
"""

from __future__ import annotations

import json

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic.dataclasses import dataclass

from codeweaver.core.language import SemanticSearchLanguage


@dataclass
class GrammarStructureStats:
    """Statistics about grammar structure patterns."""

    language: SemanticSearchLanguage
    total_nodes: int = 0
    named_nodes: int = 0
    unnamed_nodes: int = 0

    # Abstract type patterns
    abstract_types: dict[str, list[str]] = Field(default_factory=dict)
    abstract_type_count: int = 0

    # Field patterns
    nodes_with_fields: int = 0
    common_field_names: Counter[str] = Field(default_factory=Counter)
    field_semantic_roles: dict[str, list[str]] = Field(default_factory=lambda: defaultdict(list))

    # Children patterns
    nodes_with_children: int = 0
    nodes_with_both: int = 0  # both fields and children

    # Extra patterns
    extra_nodes: list[str] = Field(default_factory=list)
    extra_node_count: int = 0

    # Root patterns
    root_nodes: list[str] = Field(default_factory=list)

    # Q1: Category references in connections
    field_references: dict[str, set[str]] = Field(default_factory=lambda: defaultdict(set))
    children_references: dict[str, set[str]] = Field(default_factory=lambda: defaultdict(set))
    category_references_in_fields: Counter[str] = Field(default_factory=Counter)
    category_references_in_children: Counter[str] = Field(default_factory=Counter)
    concrete_references_in_fields: Counter[str] = Field(default_factory=Counter)
    concrete_references_in_children: Counter[str] = Field(default_factory=Counter)

    # Q2: Multiple category membership
    concrete_to_categories: dict[str, set[str]] = Field(default_factory=lambda: defaultdict(set))
    multi_category_things: dict[str, list[str]] = Field(default_factory=dict)

    def summary(self) -> str:
        """Generate summary statistics."""
        return f"""
Language: {self.language.value}
{"=" * 60}
Total Nodes: {self.total_nodes}
  Named: {self.named_nodes} ({self.named_nodes / self.total_nodes * 100:.1f}%)
  Unnamed: {self.unnamed_nodes} ({self.unnamed_nodes / self.total_nodes * 100:.1f}%)

Abstract Types: {self.abstract_type_count}
  Top abstract categories: {", ".join(list(self.abstract_types.keys()))}

Structural Patterns:
  Nodes with fields: {self.nodes_with_fields} ({self.nodes_with_fields / self.named_nodes * 100:.1f}% of named)
  Nodes with children: {self.nodes_with_children}
  Nodes with both: {self.nodes_with_both}

Common Field Names (top 10):
  {self._format_counter(self.common_field_names, 10)}

Extra Nodes: {self.extra_node_count}
  Examples: {", ".join(self.extra_nodes[:5])}

Root Nodes: {", ".join(self.root_nodes)}
"""

    def _format_counter(self, counter: Counter[str], limit: int) -> str:
        """Format counter for display."""
        items = counter.most_common(limit)
        return "\n  ".join(f"{name}: {count}" for name, count in items)


class GrammarStructureAnalyzer:
    """Analyze grammar structure patterns across all languages."""

    def __init__(self, node_types_dir: Path | None = None) -> None:
        """Initialize analyzer with node types directory."""
        if node_types_dir is None:
            # Default to project structure
            node_types_dir = Path(__file__).parent.parent.parent / "node_types"
        self.node_types_dir = node_types_dir
        self.stats: dict[SemanticSearchLanguage, GrammarStructureStats] = {}
        # Map from enum values to actual file names
        self.file_name_map = self._build_file_name_map()

    def _build_file_name_map(self) -> dict[str, str]:
        """Build mapping from enum values to actual filenames."""
        # Scan directory for actual files
        file_map = {}
        if not self.node_types_dir.exists():
            return file_map

        for json_file in self.node_types_dir.glob("*-node-types.json"):
            if json_file.name.endswith("license"):
                continue
            # Extract language from filename (e.g., "python-node-types.json" -> "python")
            lang_name = json_file.stem.replace("-node-types", "")
            semantic_language = SemanticSearchLanguage.from_string(lang_name)
            file_map[semantic_language.variable] = json_file.name

        return file_map

    def analyze_all_languages(self) -> dict[SemanticSearchLanguage, GrammarStructureStats]:
        """Analyze grammar structure for all supported languages."""
        print("Analyzing grammar structures for all supported languages...")
        print("=" * 60)

        for language in SemanticSearchLanguage:
            try:
                stats = self.analyze_language(language)
                self.stats[language] = stats
                print(
                    f"✓ {language.as_title}: {stats.total_nodes} nodes, {stats.abstract_type_count} abstract types"
                )
            except Exception as e:
                print(f"✗ {language.as_title}: {e}")

        return self.stats

    def analyze_language(self, language: SemanticSearchLanguage) -> GrammarStructureStats:
        """Analyze grammar structure for a specific language."""
        stats = GrammarStructureStats(language=language)

        # Load node types for this language
        file_name = self.file_name_map.get(language.value)
        if not file_name:
            raise FileNotFoundError(f"No node types file found for language: {language.value}")

        node_types_file = self.node_types_dir / file_name
        if not node_types_file.exists():
            raise FileNotFoundError(f"Node types file not found: {node_types_file}")

        with node_types_file.open() as f:
            node_types: list[dict[str, Any]] = json.load(f)

        stats.total_nodes = len(node_types)

        for node_info in node_types:
            self._analyze_node(node_info, stats)

        # Post-process: Classify references and identify multi-category Things
        self._classify_connection_references(stats)
        self._identify_multi_category_things(stats)

        return stats

    def _analyze_node(self, node_info: dict[str, Any], stats: GrammarStructureStats) -> None:
        """Analyze a single node type entry."""
        node_type = node_info.get("type", "")
        is_named = node_info.get("named", False)

        if is_named:
            stats.named_nodes += 1
        else:
            stats.unnamed_nodes += 1

        # Check for subtypes (abstract types / Categories)
        if "subtypes" in node_info:
            stats.abstract_type_count += 1
            subtypes = [st["type"] for st in node_info.get("subtypes", [])]
            stats.abstract_types[node_type] = subtypes

            # Q2: Track which concrete types belong to which categories
            for subtype in subtypes:
                stats.concrete_to_categories[subtype].add(node_type)

        # Check for fields (Direct connections)
        if "fields" in node_info:
            stats.nodes_with_fields += 1
            fields = node_info["fields"]

            # Count Field names
            for field_name, field_info in fields.items():
                stats.common_field_names[field_name] += 1

                if parent_category := self._infer_category_from_node_type(node_type):
                    stats.field_semantic_roles[field_name].append(f"{parent_category}:{node_type}")

                # Q1: Track what types are referenced in fields
                if "types" in field_info:
                    for type_ref in field_info["types"]:
                        if ref_type := type_ref.get("type", ""):
                            stats.field_references[node_type].add(ref_type)

        # Check for children (Positional connections)
        if "children" in node_info:
            stats.nodes_with_children += 1

            # Q1: Track what types are referenced in children
            children_info = node_info["children"]
            if "types" in children_info:
                for type_ref in children_info["types"]:
                    if ref_type := type_ref.get("type", ""):
                        stats.children_references[node_type].add(ref_type)

            # Check for both fields and children
            if "fields" in node_info:
                stats.nodes_with_both += 1

        # Check for extra
        if node_info.get("extra", False):
            stats.extra_node_count += 1
            stats.extra_nodes.append(node_type)

        # Check for root
        if node_info.get("root", False):
            stats.root_nodes.append(node_type)

    def _classify_connection_references(self, stats: GrammarStructureStats) -> None:
        """Classify connection references as Category or Concrete Thing references.

        Answers Q1: Can connections reference Categories or only concrete Things?
        """
        abstract_types = set(stats.abstract_types.keys())

        # Analyze Field references
        for target_types in stats.field_references.values():
            for target_type in target_types:
                if target_type in abstract_types:
                    stats.category_references_in_fields[target_type] += 1
                else:
                    stats.concrete_references_in_fields[target_type] += 1

        # Analyze children references
        for target_types in stats.children_references.values():
            for target_type in target_types:
                if target_type in abstract_types:
                    stats.category_references_in_children[target_type] += 1
                else:
                    stats.concrete_references_in_children[target_type] += 1

    def _identify_multi_category_things(self, stats: GrammarStructureStats) -> None:
        """Identify Things that belong to multiple Categories.

        Answers Q2: Can a Thing belong to multiple Categories?
        """
        for concrete_type, categories in stats.concrete_to_categories.items():
            if len(categories) > 1:
                stats.multi_category_things[concrete_type] = sorted(categories)

    def _infer_category_from_node_type(self, node_type: str) -> str | None:
        """Infer semantic category from node type name."""
        # Common patterns in node type names
        if any(x in node_type for x in ["function", "method", "procedure", "lambda"]):
            return "callable"
        if any(x in node_type for x in ["class", "struct", "interface", "trait", "type"]):
            return "type_def"
        if any(x in node_type for x in ["import", "export", "module", "package"]):
            return "boundary"
        if any(x in node_type for x in ["if", "while", "for", "switch", "match"]):
            return "control_flow"
        if any(x in node_type for x in ["call", "binary", "unary", "assignment"]):
            return "operation"
        return None

    def find_cross_language_patterns(self) -> dict[str, Any]:
        """Find common patterns across all languages."""
        patterns = {
            "common_abstract_types": Counter(),
            "universal_field_names": Counter(),
            "common_extra_nodes": Counter(),
            "field_semantic_patterns": defaultdict(Counter),
            # Q1 patterns
            "category_refs_in_fields": Counter(),
            "category_refs_in_children": Counter(),
            "concrete_refs_in_fields": Counter(),
            "concrete_refs_in_children": Counter(),
            # Q2 patterns
            "all_multi_category_things": defaultdict(set),
        }

        for stats in self.stats.values():
            # Abstract type patterns (normalize leading underscore)
            for abstract_type in stats.abstract_types:
                normalized = abstract_type.lstrip("_")
                patterns["common_abstract_types"][normalized] += 1  # type: ignore

            # Field name patterns
            patterns["universal_field_names"].update(stats.common_field_names)  # type: ignore

            # Extra node patterns
            for extra_node in stats.extra_nodes:
                patterns["common_extra_nodes"][extra_node] += 1  # type: ignore

            # Field semantic patterns
            for field_name, contexts in stats.field_semantic_roles.items():
                for context in contexts:
                    category = context.split(":")[0]
                    patterns["field_semantic_patterns"][field_name][category] += 1  # type: ignore

            # Q1: Aggregate category and concrete references
            patterns["category_refs_in_fields"].update(stats.category_references_in_fields)  # type: ignore
            patterns["category_refs_in_children"].update(stats.category_references_in_children)  # type: ignore
            patterns["concrete_refs_in_fields"].update(stats.concrete_references_in_fields)  # type: ignore
            patterns["concrete_refs_in_children"].update(stats.concrete_references_in_children)  # type: ignore

            # Q2: Aggregate multi-category Things
            for thing, categories in stats.multi_category_things.items():
                patterns["all_multi_category_things"][thing].update(categories)  # type: ignore

        return patterns

    def analyze_category_references(self) -> dict[str, Any]:
        """Analyze Q1: Category vs Concrete references in connections.

        Returns detailed statistics about what types of references appear in
        fields (Direct connections) and children (Positional connections).
        """
        total_category_in_fields = 0
        total_concrete_in_fields = 0
        total_category_in_children = 0
        total_concrete_in_children = 0

        # Language-specific examples
        examples_fields_category: list[tuple[str, str, str]] = []  # (language, source, target)
        examples_fields_concrete: list[tuple[str, str, str]] = []
        examples_children_category: list[tuple[str, str, str]] = []
        examples_children_concrete: list[tuple[str, str, str]] = []

        for lang, stats in self.stats.items():
            abstract_types = set(stats.abstract_types.keys())

            # Count references
            total_category_in_fields += sum(stats.category_references_in_fields.values())
            total_concrete_in_fields += sum(stats.concrete_references_in_fields.values())
            total_category_in_children += sum(stats.category_references_in_children.values())
            total_concrete_in_children += sum(stats.concrete_references_in_children.values())

            # Collect examples (limit to first 3 per type per language)
            field_cat_count = 0
            field_conc_count = 0
            for source, targets in stats.field_references.items():
                for target in targets:
                    if target in abstract_types and field_cat_count < 3:
                        examples_fields_category.append((lang.value, source, target))
                        field_cat_count += 1
                    elif target not in abstract_types and field_conc_count < 3:
                        examples_fields_concrete.append((lang.value, source, target))
                        field_conc_count += 1

            child_cat_count = 0
            child_conc_count = 0
            for source, targets in stats.children_references.items():
                for target in targets:
                    if target in abstract_types and child_cat_count < 3:
                        examples_children_category.append((lang.value, source, target))
                        child_cat_count += 1
                    elif target not in abstract_types and child_conc_count < 3:
                        examples_children_concrete.append((lang.value, source, target))
                        child_conc_count += 1

        return {
            "field_category_count": total_category_in_fields,
            "field_concrete_count": total_concrete_in_fields,
            "children_category_count": total_category_in_children,
            "children_concrete_count": total_concrete_in_children,
            "examples_fields_category": examples_fields_category[:20],
            "examples_fields_concrete": examples_fields_concrete[:20],
            "examples_children_category": examples_children_category[:20],
            "examples_children_concrete": examples_children_concrete[:20],
        }

    def analyze_multi_category_membership(self) -> dict[str, Any]:
        """Analyze Q2: Things belonging to multiple Categories.

        Returns statistics about how common it is for a Thing to belong to
        multiple Categories across all languages.
        """
        all_things_with_categories: dict[str, int] = Counter()
        things_in_multiple: list[tuple[str, str, list[str]]] = []  # (language, thing, categories)

        for lang, stats in self.stats.items():
            # Count all Things that have any category membership
            for thing, categories in stats.concrete_to_categories.items():
                all_things_with_categories[thing] = len(categories)

                # Track multi-category Things
                if len(categories) > 1:
                    things_in_multiple.append((lang.value, thing, sorted(categories)))

        # Statistics
        total_things_with_categories = len(all_things_with_categories)
        total_multi_category = sum(count > 1 for count in all_things_with_categories.values())
        max_categories = (
            max(all_things_with_categories.values()) if all_things_with_categories else 0
        )

        return {
            "total_things_with_categories": total_things_with_categories,
            "total_multi_category": total_multi_category,
            "percentage_multi": (
                (total_multi_category / total_things_with_categories * 100)
                if total_things_with_categories
                else 0
            ),
            "max_categories_per_thing": max_categories,
            "examples": things_in_multiple[:30],  # First 30 examples
            "distribution": Counter(all_things_with_categories.values()),
        }

    def generate_report(self, output_file: Path | None = None) -> str:
        """Generate comprehensive analysis report."""
        report_lines = ["# Grammar Structure Analysis Report", "", "## Per-Language Statistics", ""]

        # Individual language stats
        for language in sorted(self.stats.keys(), key=lambda x: x.value):
            stats = self.stats[language]
            report_lines.append(stats.summary())

        # Cross-language patterns
        patterns = self.find_cross_language_patterns()

        report_lines.extend([
            "",
            "## Cross-Language Patterns",
            "",
            "### Common Abstract Types (appears in multiple languages)",
        ])

        for abstract_type, count in patterns["common_abstract_types"].items():
            percentage = count / len(self.stats) * 100
            report_lines.append(
                f"  {abstract_type}: {count}/{len(self.stats)} languages ({percentage:.1f}%)"
            )

        report_lines.extend(["", "### Universal Field Names"])

        report_lines.extend(
            f"  {field_name}: {count} total occurrences"
            for field_name, count in patterns["universal_field_names"].items()
        )
        report_lines.extend([
            "",
            "### Field Semantic Patterns",
            "",
            "Shows which semantic categories commonly use each Field name:",
            "",
        ])

        for field_name, category_counts in sorted(
            patterns["field_semantic_patterns"].items(),
            key=lambda x: sum(x[1].values()),
            reverse=True,
        ):
            total = sum(category_counts.values())
            categories = ", ".join(f"{cat}({count})" for cat, count in category_counts.items())
            report_lines.append(f"  {field_name} [{total} uses]: {categories}")

        # Q1 Analysis: Category References
        report_lines.extend([
            "",
            "## Q1: Category vs Concrete References in Connections",
            "",
            "Analysis of whether connections (fields/children) reference Categories (abstract types)",
            "or only concrete Things.",
            "",
        ])

        q1_analysis = self.analyze_category_references()

        report_lines.extend([
            "### Direct Connections (fields)",
            f"  Category references: {q1_analysis['field_category_count']}",
            f"  Concrete references: {q1_analysis['field_concrete_count']}",
            f"  Percentage Category: {q1_analysis['field_category_count'] / (q1_analysis['field_category_count'] + q1_analysis['field_concrete_count']) * 100:.1f}%",
            "",
            "Examples of Category references in fields:",
        ])

        report_lines.extend(
            f"  - {lang}: {source} → {target} (Category)"
            for lang, source, target in q1_analysis["examples_fields_category"][:10]
        )
        report_lines.extend(["", "Examples of Concrete references in fields:"])

        report_lines.extend(
            f"  - {lang}: {source} → {target} (Concrete)"
            for lang, source, target in q1_analysis["examples_fields_concrete"][:10]
        )
        report_lines.extend([
            "",
            "### Positional Connections (children)",
            f"  Category references: {q1_analysis['children_category_count']}",
            f"  Concrete references: {q1_analysis['children_concrete_count']}",
            f"  Percentage Category: {q1_analysis['children_category_count'] / (q1_analysis['children_category_count'] + q1_analysis['children_concrete_count']) * 100:.1f}%"
            if (q1_analysis["children_category_count"] + q1_analysis["children_concrete_count"]) > 0
            else "  Percentage Category: N/A",
            "",
            "Examples of Category references in children:",
        ])

        report_lines.extend(
            f"  - {lang}: {source} → {target} (Category)"
            for lang, source, target in q1_analysis["examples_children_category"][:10]
        )
        report_lines.extend(["", "Examples of Concrete references in children:"])

        report_lines.extend(
            f"  - {lang}: {source} → {target} (Concrete)"
            for lang, source, target in q1_analysis["examples_children_concrete"][:10]
        )
        # Q2 Analysis: Multi-Category Membership
        report_lines.extend([
            "",
            "## Q2: Things with Multiple Category Membership",
            "",
            "Analysis of whether concrete Things can belong to multiple Categories",
            "(i.e., appear in multiple abstract types' subtypes lists).",
            "",
        ])

        q2_analysis = self.analyze_multi_category_membership()

        report_lines.extend([
            f"Total Things with category membership: {q2_analysis['total_things_with_categories']}",
            f"Things belonging to multiple Categories: {q2_analysis['total_multi_category']}",
            f"Percentage multi-category: {q2_analysis['percentage_multi']:.1f}%",
            f"Maximum categories per Thing: {q2_analysis['max_categories_per_thing']}",
            "",
            "Distribution of category membership:",
        ])

        report_lines.extend(
            f"  {num_cats} category/categories: {count} Things"
            for num_cats, count in sorted(q2_analysis["distribution"].items())
        )
        report_lines.extend(["", "Examples of Things with multiple Category membership:"])

        for lang, thing, categories in q2_analysis["examples"][:20]:
            cats_str = ", ".join(categories)
            report_lines.append(f"  - {lang}: {thing} → [{cats_str}]")

        report_lines.extend([
            "",
            "## Conclusions",
            "",
            "### Q1: Category References",
            "**Answer: YES** - Connections CAN reference Categories (abstract types).",
            f"- Fields reference Categories in {q1_analysis['field_category_count']} cases",
            f"- Children reference Categories in {q1_analysis['children_category_count']} cases",
            "- This is a common pattern used for polymorphic type constraints",
            "",
            "### Q2: Multiple Category Membership",
            f"**Answer: YES** - Things CAN belong to multiple Categories, but it's {('uncommon' if q2_analysis['percentage_multi'] < 20 else 'common')}.",
            f"- Only {q2_analysis['percentage_multi']:.1f}% of Things belong to multiple Categories",
            f"- Maximum observed: {q2_analysis['max_categories_per_thing']} categories for a single Thing",
            "- This typically occurs for nodes that serve multiple grammatical roles",
        ])

        report = "\n".join(report_lines)

        if output_file:
            output_file.write_text(report)  # type: ignore
            print(f"\nReport written to: {output_file}")

        return report


def main() -> None:
    """Run grammar structure analysis."""
    analyzer = GrammarStructureAnalyzer()
    _stats = analyzer.analyze_all_languages()

    # Generate report
    output_dir = Path(__file__).parent.parent.parent / "claudedocs"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "grammar_structure_analysis.md"

    _report = analyzer.generate_report(output_file)  # type: ignore

    # Print summary
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"Total languages analyzed: {len(analyzer.stats)}")
    print(f"Report saved to: {output_file}")


if __name__ == "__main__":
    main()
