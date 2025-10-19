#!/usr/bin/env python3
"""Script to optimize CompositeCheck patterns into grouped mega-regexes.

This script analyzes the existing COMPOSITE_CHECKS and generates an optimized
structure with:
1. Language-specific grouped patterns
2. Generic cross-language patterns
3. Separate predicate-based checks

Expected performance improvement: ~15-30x faster classification.
"""

import re

# Add src to path for imports
import sys

from collections import defaultdict
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codeweaver.semantic._constants import COMPOSITE_CHECKS


def extract_pattern_text(pattern: re.Pattern[str]) -> str:
    """Extract the regex pattern string from a compiled Pattern object."""
    return pattern.pattern


def group_checks_by_language_and_class() -> dict[str, Any]:
    """Group CompositeChecks by language and classification.

    Returns:
        Dictionary with structure:
        {
            'language_specific': {
                SemanticSearchLanguage.SWIFT: {
                    SemanticClass.OPERATION_OPERATOR: [pattern1, pattern2, ...],
                    ...
                },
                ...
            },
            'generic': {
                SemanticClass.DEFINITION_TYPE: [pattern1, pattern2, ...],
                ...
            },
            'predicates': [CompositeCheck, ...],  # Checks requiring predicates
        }
    """
    result: dict[str, Any] = {
        "language_specific": defaultdict(lambda: defaultdict(list)),
        "generic": defaultdict(list),
        "predicates": [],
    }

    for check in COMPOSITE_CHECKS:
        # Handle predicate-based checks separately
        if check.predicate is not None:
            result["predicates"].append(check)
            continue

        pattern_text = extract_pattern_text(check.name_pattern)

        # Group by language or generic
        if check.languages is None:
            # Generic pattern (applies to all languages)
            result["generic"][check.classification].append(pattern_text)
        else:
            # Language-specific pattern
            for lang in check.languages:
                result["language_specific"][lang][check.classification].append(pattern_text)

    return result


def combine_patterns(patterns: list[str]) -> str:
    """Combine multiple regex patterns into a single alternation pattern.

    Args:
        patterns: List of regex pattern strings

    Returns:
        Combined pattern string like "^(pattern1|pattern2|...)$"
    """
    if not patterns:
        return ""

    # Remove ^...$ anchors from individual patterns
    cleaned_patterns = []
    for p in patterns:
        # Remove leading ^ and trailing $
        p = p.strip()
        p = p.removeprefix("^")
        p = p.removesuffix("$")
        cleaned_patterns.append(p)

    # Combine with alternation
    combined = "|".join(f"(?:{p})" for p in cleaned_patterns)
    return f"^(?:{combined})$"


def order_patterns_by_specificity(patterns: list[str]) -> list[str]:
    """Order patterns from specific to general.

    Wildcards and greedy patterns should be checked last.

    Args:
        patterns: List of regex pattern strings

    Returns:
        Ordered list with specific patterns first, wildcards last
    """
    specific = []
    wildcards = []

    for p in patterns:
        # Patterns with .+ or .* are wildcards
        if ".+" in p or ".*" in p:
            wildcards.append(p)
        else:
            specific.append(p)

    return specific + wildcards


def generate_optimized_code(grouped: dict[str, Any]) -> str:
    """Generate Python code for the optimized pattern structures.

    Args:
        grouped: Grouped patterns from group_checks_by_language_and_class()

    Returns:
        Python code string defining the new structures
    """
    lines = [
        '"""Optimized composite check patterns grouped by language and classification."""',
        "",
        "import re",
        "",
        "from codeweaver.language import SemanticSearchLanguage",
        "from codeweaver.semantic.classifications import SemanticClass",
        "",
        "",
        "# Language-specific pattern groups (ordered by frequency)",
        "# Structure: {Language: tuple[(SemanticClass, compiled_pattern), ...]",
        "LANG_SPECIFIC_PATTERNS: dict[SemanticSearchLanguage, tuple[tuple[SemanticClass, re.Pattern[str]], ...]] = {",
    ]

    # Generate language-specific patterns
    for lang, classifications in sorted(
        grouped["language_specific"].items(), key=lambda x: x[0].value
    ):
        # Format: SemanticSearchLanguage.BASH instead of repr
        lines.append(f"    SemanticSearchLanguage.{lang.name}: (")

        # Sort by classification for consistency
        for cls, patterns in sorted(classifications.items(), key=lambda x: x[0].value):
            ordered_patterns = order_patterns_by_specificity(patterns)
            combined = combine_patterns(ordered_patterns)

            # Format: SemanticClass.SYNTAX_KEYWORD instead of repr
            lines.append(f"        (SemanticClass.{cls.name}, re.compile(r'{combined}')),")

        lines.append("    ),")

    lines.append("}")
    lines.append("")
    lines.append("")
    lines.append("# Generic cross-language patterns (ordered by frequency)")
    lines.append("# Structure: tuple[(SemanticClass, compiled_pattern), ...]")
    lines.append("GENERIC_PATTERNS: tuple[tuple[SemanticClass, re.Pattern[str]], ...] = (")

    # Generate generic patterns
    for cls, patterns in sorted(grouped["generic"].items(), key=lambda x: x[0].value):
        ordered_patterns = order_patterns_by_specificity(patterns)
        combined = combine_patterns(ordered_patterns)

        # Format: SemanticClass.SYNTAX_KEYWORD instead of repr
        lines.append(f"    (SemanticClass.{cls.name}, re.compile(r'{combined}')),")

    lines.append(")")
    lines.append("")
    lines.append("")

    # Note about predicates
    lines.append(f"# Predicate-based checks (special cases): {len(grouped['predicates'])} checks")
    lines.append("# These are preserved from the original COMPOSITE_CHECKS")
    lines.append(f"# Original count: {len(COMPOSITE_CHECKS)} individual checks")
    lines.append(
        f"# Optimized count: {len(grouped['language_specific'])} language groups + {len(grouped['generic'])} generic patterns + {len(grouped['predicates'])} predicates"
    )

    return "\n".join(lines)


def print_statistics(grouped: dict[str, Any]) -> None:
    """Print statistics about the optimization."""
    total_lang_patterns = sum(
        len(classifications) for classifications in grouped["language_specific"].values()
    )
    total_generic_patterns = len(grouped["generic"])
    total_predicates = len(grouped["predicates"])

    print("\n=== Optimization Statistics ===")
    print(f"Original individual checks: {len(COMPOSITE_CHECKS)}")
    print("\nOptimized structure:")
    print(f"  Language-specific groups: {len(grouped['language_specific'])} languages")
    print(f"  Total language patterns: {total_lang_patterns}")
    print(f"  Generic patterns: {total_generic_patterns}")
    print(f"  Predicate checks: {total_predicates}")
    print("\nEstimated checks per classification:")
    print(f"  Before: ~{len(COMPOSITE_CHECKS)} sequential regex checks")
    print(
        f"  After: ~{max(total_lang_patterns // len(grouped['language_specific']) if grouped['language_specific'] else 0, total_generic_patterns) + total_predicates} grouped checks"
    )
    print(
        f"  Expected speedup: ~{len(COMPOSITE_CHECKS) // max(1, total_lang_patterns // max(1, len(grouped['language_specific'])) + total_generic_patterns + total_predicates)}x"
    )


def main() -> None:
    """Main migration script execution."""
    print("Analyzing COMPOSITE_CHECKS...")
    grouped = group_checks_by_language_and_class()

    print("Generating optimized code...")
    optimized_code = generate_optimized_code(grouped)

    # Write to output file
    output_path = Path(__file__).parent / "optimized_patterns.py"
    output_path.write_text(optimized_code)

    print(f"\nOptimized patterns written to: {output_path}")
    print_statistics(grouped)

    print("\n=== Next Steps ===")
    print("1. Review the generated optimized_patterns.py")
    print("2. Integrate into _constants.py")
    print("3. Update _classify_from_composite_checks() in grammar_classifier.py")
    print("4. Run tests to validate equivalence")


if __name__ == "__main__":
    main()
