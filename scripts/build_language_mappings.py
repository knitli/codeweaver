#!/usr/bin/env -S uv run

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# ///script
# requires-python = ">=3.11"
# dependencies = ["pydantic"]
# ///
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0# python
"""Build language mapping files from tree-sitter node-types.json files."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.categories import SemanticNodeCategory
from codeweaver.semantic.mapper import NodeMapper, get_node_mapper
from codeweaver.semantic.node_type_parser import LanguageNodeType, NodeTypeParser


type ProjectNodeTypes = dict[SemanticSearchLanguage, LanguageNodeType]
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
) -> Sequence[Mapping[SemanticSearchLanguage, LanguageNodeType]]:
    """Parse the node types from the specified directory."""
    parser = NodeTypeParser(node_types_dir=node_types_dir)
    return parser.parse_all_node_types()


def display_common_patterns(common_patterns: PatternLanguages, top: int = 20) -> None:
    """Display the most common node patterns across languages."""
    print("\n=== Most Common Node Types Across Languages ===")
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


def analyze_language_specific(
    mapper: NodeMapper, node_types: ProjectNodeTypes, targets: Iterable[SemanticSearchLanguage]
) -> None:
    """Analyze language-specific node types."""
    print("\n=== Language-Specific Analysis ===")
    for lang_name in targets:
        grammar = node_types.get(lang_name)
        if not grammar:
            continue
        print(f"\n{lang_name.upper()}:")
        node_type_names = list(getattr(grammar, "node_types", {}).keys())[:20]
        for node_type in node_type_names:
            category = mapper.classify_node_type(node_type, lang_name)
            confidence = mapper.get_classification_confidence(node_type, lang_name)
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
    for lang_name, grammar in node_types.items():
        node_type_names = getattr(grammar, "node_types", {}).keys()
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
        node_types = parser.parse_all_node_types()
    except Exception as exc:
        print(f"Failed to parse node_types: {exc}")
        return

    print(f"Found {len(node_types)} languages with grammar files")

    common_patterns = parser.find_common_patterns()
    display_common_patterns(common_patterns, top=20)

    mapper = get_node_mapper()

    high, medium, low = analyze_confidence(mapper, common_patterns, top=50)
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
