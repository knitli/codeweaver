#!/usr/bin/env -S uv run -s
# ///script
# requires-python = ">=3.11"
# dependencies = ["pydantic"]
# ///
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Build language mapping files from tree-sitter node-types.json files."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import cast

from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.categories import SemanticNodeCategory
from codeweaver.semantic.mapper import NodeMapper, get_node_mapper
from codeweaver.semantic.node_type_parser import LanguageNodeType, NodeTypeInfo, NodeTypeParser


type ProjectNodeTypes = Sequence[dict[SemanticSearchLanguage, Sequence[LanguageNodeType]]]
type PatternLanguages = dict[str, list[SemanticSearchLanguage]]
type ConfidenceRow = tuple[str, SemanticNodeCategory, float, int]


def locate_node_types() -> Path:
    """Locate the node_types directory relative to this script."""
    project_root = Path(__file__).parent.parent
    node_types_dir = project_root / "node_types"
    if not node_types_dir.exists():
        raise FileNotFoundError(f"Node types directory not found: {node_types_dir}")
    return node_types_dir


def parse_node_types(
    node_types_dir: Path,
) -> Sequence[Mapping[SemanticSearchLanguage, Sequence[NodeTypeInfo]]]:
    """Parse the node types from the specified directory."""
    parser = NodeTypeParser(node_types_dir=node_types_dir)
    return parser.parse_all_node_types()


def display_common_patterns(common_patterns: PatternLanguages, top: int = 20) -> None:
    """Display the most common node patterns across languages."""
    print("\n=== Most Common Node Types Across Languages ===")

    filtered = {p: langs for p, langs in common_patterns.items() if langs}
    items = sorted(common_patterns.items(), key=lambda kv: len(kv[1]), reverse=True)
    for pattern, languages in items[:top]:
        print(f"{pattern}: {len(languages)} languages")


def analyze_confidence(
    mapper: NodeMapper, common_patterns: PatternLanguages, top: int = 50
) -> tuple[list[ConfidenceRow], list[ConfidenceRow], list[ConfidenceRow]]:
    """Analyze classification confidence for common patterns."""
    high: list[ConfidenceRow] = []
    medium: list[ConfidenceRow] = []
    low: list[ConfidenceRow] = []

    items = list(common_patterns.items())[:top]

    for pattern, languages in items:
        for language in languages:
            conf = mapper.get_classification_confidence(pattern, language)
            cat = mapper.classify_node_type(pattern, language)
            row = (pattern, cat, conf, len(languages))
            if conf >= 0.8:
                high.append(row)
            elif conf >= 0.5:
                medium.append(row)
            else:
                low.append(row)
    return high, medium, low


def print_confidence_rows(title: str, rows: Iterable[ConfidenceRow], limit: int = 10) -> None:
    """Print a table of confidence rows."""
    rows = list(rows)
    print(f"\n{title} ({len(rows)}):")
    for pattern, category, conf, lang_count in rows[:limit]:
        print(f"  {pattern} → {category} (confidence: {conf:.2f}, {lang_count} langs)")


def down_to_node_types(project_root: ProjectNodeTypes) -> dict[SemanticSearchLanguage, set[str]]:
    """Convert project node types to a mapping of language names to their node type names."""
    lang_to_types: dict[SemanticSearchLanguage, set[str]] = {}
    for entry in project_root:
        for lang_name, nodes in entry.items():
            collected: list[str] = []
            if "named" in nodes and isinstance(nodes, dict):
                collected.append(nodes.get("type_name", nodes.get("type", "")))
                if "children" in nodes and (children := nodes.get("children")):
                    collected.extend(
                        child.get("type_name", child.get("type", ""))
                        for child in children
                        if isinstance(child, dict)
                    )
                if "fields" in nodes and (fields := nodes.get("fields")):
                    collected.extend(v for v in fields if isinstance(v, str))
                    if types := [
                        f.get("types")
                        for f in fields
                        if isinstance(f, dict) and "types" in f and f.get("types")
                    ]:
                        for type_list in types:
                            if isinstance(type_list, list):
                                collected.extend(
                                    t.get("type_name", t.get("type", ""))
                                    for t in type_list
                                    if isinstance(t, dict)
                                )
            lang_to_types[lang_name] = set(collected)
    return lang_to_types


def analyze_language_specific(
    mapper: NodeMapper, node_types: ProjectNodeTypes, targets: Iterable[SemanticSearchLanguage]
) -> None:
    """Analyze language-specific node types."""
    print("\n=== Language-Specific Analysis ===")
    nodes = down_to_node_types(node_types)
    for target in targets:
        if target in nodes and (flattened_nodes := sorted(nodes[target])):
            print(f"\n{str(target).upper()}:")
            for node_type in flattened_nodes:
                category = mapper.classify_node_type(node_type, target)
                confidence = mapper.get_classification_confidence(node_type, target)
                print(f"  {node_type} → {category} (confidence: {confidence:.2f})")


def compute_statistics(
    parser: NodeTypeParser, mapper: NodeMapper, common_patterns: PatternLanguages
) -> None:
    """Compute and display statistics about node types."""
    print("\n=== Statistics ===")
    total_node_types = len(parser.get_all_node_types())
    print(f"Total unique node types across all languages: {total_node_types}")

    distribution: dict[SemanticNodeCategory, int] = {}
    for pattern, languages in common_patterns.items():
        for language in languages:
            cat = mapper.classify_node_type(pattern, language)
            distribution[cat] = distribution.get(cat, 0) + 1

    print("\nSemantic category distribution:")
    for category, count in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count} node types")


def suggest_overrides(
    mapper: NodeMapper, node_types: ProjectNodeTypes, threshold: float = 0.3, top_n: int = 5
) -> None:
    """Suggest manual overrides for low-confidence classifications."""
    print("\n=== Suggested Manual Overrides ===")
    print("The following node types have low classification confidence and may need manual review:")

    overrides_by_language: dict[str, dict[str, SemanticNodeCategory]] = {}
    nodes = down_to_node_types(node_types)
    for lang_name, node_type in nodes.items():
        node_type_names = getattr(node_type, "node_type", {}).keys()
        for node_type in node_type_names:
            conf = mapper.get_classification_confidence(node_type, lang_name)
            if conf < threshold:
                cat = mapper.classify_node_type(node_type, lang_name)
                overrides_by_language.setdefault(lang_name, {})[node_type] = cat

    for lang_name, overrides in overrides_by_language.items():
        if not overrides:
            continue
        print(f"\n{lang_name}:")
        for node_type, category in list(overrides.items())[:top_n]:
            print(f"  '{node_type}': SemanticNodeCategory.{category.name}")


def analyze_node_types_and_generate_mappings() -> None:
    """Main function to analyze node types and generate mappings."""
    try:
        node_types_dir = locate_node_types()
    except FileNotFoundError as exc:
        print(exc)
        return

    try:
        parser = NodeTypeParser(node_types_dir=node_types_dir)
        node_types: ProjectNodeTypes = cast(ProjectNodeTypes, parser.parse_all_node_types())
    except Exception as exc:
        print(f"Failed to parse node_types: {exc}")
        return

    print(f"Found {len(node_types)} languages with grammar files")

    common_patterns = parser.find_common_patterns()
    display_common_patterns(common_patterns, top=20)

    mapper = get_node_mapper()

    high, medium, low = analyze_confidence(mapper, common_patterns, top=25)
    print_confidence_rows("High confidence classifications", high)
    print_confidence_rows("Medium confidence classifications", medium)
    print_confidence_rows("Low confidence classifications", low)

    analyze_language_specific(
        mapper,
        node_types,
        [
            SemanticSearchLanguage.PYTHON,
            SemanticSearchLanguage.JAVASCRIPT,
            SemanticSearchLanguage.TYPESCRIPT,
            SemanticSearchLanguage.RUST,
            SemanticSearchLanguage.GO,
        ],
    )
    compute_statistics(parser, mapper, common_patterns)
    suggest_overrides(mapper, node_types, threshold=0.3, top_n=5)


if __name__ == "__main__":
    analyze_node_types_and_generate_mappings()
