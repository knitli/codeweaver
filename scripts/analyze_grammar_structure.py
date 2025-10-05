#!/usr/bin/env python3
"""Analyze grammar structure patterns across all supported languages.

This script extracts and categorizes structural patterns from node_types.json
files to inform the grammar-based classification system design.

SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-License-Identifier: MIT OR Apache-2.0
"""

from __future__ import annotations

import json

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codeweaver.language import SemanticSearchLanguage


@dataclass
class GrammarStructureStats:
    """Statistics about grammar structure patterns."""

    language: SemanticSearchLanguage
    total_nodes: int = 0
    named_nodes: int = 0
    unnamed_nodes: int = 0

    # Abstract type patterns
    abstract_types: dict[str, list[str]] = field(default_factory=dict)
    abstract_type_count: int = 0

    # Field patterns
    nodes_with_fields: int = 0
    common_field_names: Counter[str] = field(default_factory=Counter)
    field_semantic_roles: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    # Children patterns
    nodes_with_children: int = 0
    nodes_with_both: int = 0  # both fields and children

    # Extra patterns
    extra_nodes: list[str] = field(default_factory=list)
    extra_node_count: int = 0

    # Root patterns
    root_nodes: list[str] = field(default_factory=list)

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
            node_types_dir = Path(__file__).parent.parent / "node_types"
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

        return stats

    def _analyze_node(self, node_info: dict[str, Any], stats: GrammarStructureStats) -> None:
        """Analyze a single node type entry."""
        node_type = node_info.get("type", "")
        is_named = node_info.get("named", False)

        if is_named:
            stats.named_nodes += 1
        else:
            stats.unnamed_nodes += 1

        # Check for subtypes (abstract types)
        if "subtypes" in node_info:
            stats.abstract_type_count += 1
            subtypes = [st["type"] for st in node_info.get("subtypes", [])]
            stats.abstract_types[node_type] = subtypes

        # Check for fields
        if "fields" in node_info:
            stats.nodes_with_fields += 1
            fields = node_info["fields"]

            # Count field names
            for field_name in fields:
                stats.common_field_names[field_name] += 1

                if parent_category := self._infer_category_from_node_type(node_type):
                    stats.field_semantic_roles[field_name].append(f"{parent_category}:{node_type}")

        # Check for children
        if "children" in node_info:
            stats.nodes_with_children += 1

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
        }

        for stats in self.stats.values():
            # Abstract type patterns (normalize leading underscore)
            for abstract_type in stats.abstract_types:
                normalized = abstract_type.lstrip("_")
                patterns["common_abstract_types"][normalized] += 1

            # Field name patterns
            patterns["universal_field_names"].update(stats.common_field_names)

            # Extra node patterns
            for extra_node in stats.extra_nodes:
                patterns["common_extra_nodes"][extra_node] += 1

            # Field semantic patterns
            for field_name, contexts in stats.field_semantic_roles.items():
                for context in contexts:
                    category = context.split(":")[0]
                    patterns["field_semantic_patterns"][field_name][category] += 1

        return patterns

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
            "Shows which semantic categories commonly use each field name:",
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
    output_dir = Path(__file__).parent.parent / "claudedocs"
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
