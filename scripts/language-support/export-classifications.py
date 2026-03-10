#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Export CodeWeaver's semantic classifications as declarative JSON data.

This script loads the full grammar + classifier pipeline, classifies every
Thing in every supported language, and exports the results as structured
JSON files suitable for use as a declarative classification ruleset.

The output is designed to be:
1. Human-readable and auditable (every classification is one entry)
2. Portable to Rust/Thread (no Python-specific serialization)
3. A ground truth for holdout evaluation experiments
4. The seed for a declarative rules file that replaces the 7-stage classifier

Output structure:
  classifications/
    _meta.json              — schema version, generation metadata
    _universal_rules.json   — cross-language classification rules
    _scoring.json           — ImportanceScores and AgentTask profiles
    _categories.json        — category-to-SemanticClass mapping
    python.json             — per-language classification results
    rust.json
    ...
"""

from __future__ import annotations

import contextlib
import json
import sys
import time

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


AGENT_TASKS = {
    "debug": {
        "discovery": 0.2,
        "comprehension": 0.3,
        "modification": 0.1,
        "debugging": 0.35,
        "documentation": 0.05,
    },
    "default": {
        "discovery": 0.05,
        "comprehension": 0.05,
        "modification": 0.05,
        "debugging": 0.05,
        "documentation": 0.05,
    },
    "document": {
        "discovery": 0.2,
        "comprehension": 0.2,
        "modification": 0.1,
        "debugging": 0.05,
        "documentation": 0.45,
    },
    "implement": {
        "discovery": 0.3,
        "comprehension": 0.3,
        "modification": 0.2,
        "debugging": 0.1,
        "documentation": 0.1,
    },
    "local_edit": {
        "discovery": 0.4,
        "comprehension": 0.3,
        "modification": 0.2,
        "debugging": 0.05,
        "documentation": 0.05,
    },
    "refactor": {
        "discovery": 0.15,
        "comprehension": 0.25,
        "modification": 0.45,
        "debugging": 0.1,
        "documentation": 0.05,
    },
    "review": {
        "discovery": 0.25,
        "comprehension": 0.35,
        "modification": 0.15,
        "debugging": 0.15,
        "documentation": 0.1,
    },
    "search": {
        "discovery": 0.5,
        "comprehension": 0.2,
        "modification": 0.15,
        "debugging": 0.1,
        "documentation": 0.05,
    },
    "test": {
        "discovery": 0.5,
        "comprehension": 0.2,
        "modification": 0.2,
        "debugging": 0.4,
        "documentation": 0.1,
    },
}


def main() -> int:
    """Export all classifications as declarative JSON."""
    repo_root = Path(__file__).parent.parent.parent
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    output_dir = repo_root / "src" / "codeweaver" / "semantic" / "data" / "classifications"
    output_dir.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    print("Loading semantic package...")

    from codeweaver.core import SemanticSearchLanguage
    from codeweaver.semantic.classifications import ImportanceRank, SemanticClass
    from codeweaver.semantic.classifier import GrammarBasedClassifier
    from codeweaver.semantic.grammar import get_grammar

    # --- Initialize ---
    # We rely on get_grammar() which loads from the pickle cache automatically.
    # No need to call parse_all_nodes() — that triggers circular initialization.
    classifier = GrammarBasedClassifier()

    # Collect stats
    total_things = 0
    total_classified = 0
    total_confident = 0
    tier_distribution: Counter[str] = Counter()
    method_distribution: Counter[str] = Counter()
    unclassified_things: list[dict[str, str]] = []

    # =================================================================
    # 1. Export per-language classification results
    # =================================================================
    print("\nClassifying all Things across all languages...")

    for lang in SemanticSearchLanguage:
        lang_key = lang.variable  # e.g. "python", "rust"
        print(f"  {lang.as_title}...", end=" ", flush=True)

        try:
            grammar = get_grammar(lang)
        except Exception as e:
            print(f"SKIP ({e})")
            continue

        lang_data: dict[str, Any] = {
            "language": lang_key,
            "stats": {},
            "tokens": {},
            "composites": {},
            "categories": {},
        }

        lang_classified = 0
        lang_total = 0

        # --- Tokens ---
        for token in sorted(grammar.tokens, key=lambda t: str(t.name)):
            lang_total += 1
            total_things += 1
            entry: dict[str, Any] = {
                "kind": "token",
                "name": str(token.name),
                "purpose": token.purpose.variable,
                "is_explicit_rule": token.is_explicit_rule,
                "can_be_anywhere": token.can_be_anywhere or False,
                "categories": sorted(str(c) for c in token.category_names)
                if token.category_names
                else [],
            }

            result = classifier.classify_thing(token.name, lang)
            if result:
                lang_classified += 1
                total_classified += 1
                entry["classification"] = result.classification.variable
                entry["rank"] = result.rank.value
                entry["confidence"] = round(result.confidence, 4)
                entry["method"] = result.classification_method.variable
                entry["evidence"] = [e.variable for e in result.evidence]
                if result.is_confident:
                    total_confident += 1
                tier_distribution[f"tier_{result.rank.value}"] += 1
                method_distribution[result.classification_method.variable] += 1
                if result.alternate_classifications:
                    entry["alternates"] = {
                        sc.variable: [e.variable for e in evs]
                        for sc, evs in result.alternate_classifications.items()
                    }
            else:
                entry["classification"] = None
                unclassified_things.append({
                    "language": lang_key,
                    "name": str(token.name),
                    "kind": "token",
                })

            lang_data["tokens"][str(token.name)] = entry

        # --- CompositeThings ---
        for comp in sorted(grammar.composite_things, key=lambda t: str(t.name)):
            lang_total += 1
            total_things += 1
            entry = {
                "kind": "composite",
                "name": str(comp.name),
                "is_explicit_rule": comp.is_explicit_rule,
                "is_file": comp.is_file or False,
                "can_be_anywhere": comp.can_be_anywhere or False,
                "categories": sorted(str(c) for c in comp.category_names)
                if comp.category_names
                else [],
            }

            # Capture connection roles (the key signal for role-based inference)
            with contextlib.suppress(Exception):
                roles = sorted(str(conn.role) for conn in comp.direct_connections)
                if roles:
                    entry["roles"] = roles

            with contextlib.suppress(Exception):
                if comp.positional_connections:
                    pos_targets = sorted(
                        str(t) for t in comp.positional_connections.target_thing_names
                    )
                    if pos_targets:
                        entry["positional_targets"] = pos_targets
                        entry["positional_constraints"] = (
                            comp.positional_connections.constraints.variable
                            if comp.positional_connections.constraints
                            else None
                        )
            result = classifier.classify_thing(comp.name, lang)
            if result:
                lang_classified += 1
                total_classified += 1
                entry["classification"] = result.classification.variable
                entry["rank"] = result.rank.value
                entry["confidence"] = round(result.confidence, 4)
                entry["method"] = result.classification_method.variable
                entry["evidence"] = [e.variable for e in result.evidence]
                if result.is_confident:
                    total_confident += 1
                tier_distribution[f"tier_{result.rank.value}"] += 1
                method_distribution[result.classification_method.variable] += 1
                if result.alternate_classifications:
                    entry["alternates"] = {
                        sc.variable: [e.variable for e in evs]
                        for sc, evs in result.alternate_classifications.items()
                    }
            else:
                entry["classification"] = None
                unclassified_things.append({
                    "language": lang_key,
                    "name": str(comp.name),
                    "kind": "composite",
                })

            lang_data["composites"][str(comp.name)] = entry

        # --- Categories ---
        for cat in sorted(grammar.categories, key=lambda c: str(c.name)):
            lang_data["categories"][str(cat.name)] = {
                "name": str(cat.name),
                "members": sorted(str(m) for m in cat.member_thing_names),
            }

        # --- Language stats ---
        lang_data["stats"] = {
            "total_things": lang_total,
            "classified": lang_classified,
            "coverage_pct": round(lang_classified / lang_total * 100, 1) if lang_total else 0,
            "token_count": len(lang_data["tokens"]),
            "composite_count": len(lang_data["composites"]),
            "category_count": len(lang_data["categories"]),
        }

        print(f"{lang_classified}/{lang_total} classified ({lang_data['stats']['coverage_pct']}%)")

        # Write per-language file
        lang_file = output_dir / f"{lang_key}.json"
        with lang_file.open("w", encoding="utf-8") as f:
            json.dump(lang_data, f, indent=2, ensure_ascii=False)

    # =================================================================
    # 2. Export universal category→SemanticClass mapping
    # =================================================================
    print("\nExporting category mapping...")

    cat_map = classifier._classification_map
    categories_data = {
        "description": "Mapping from grammar Category names to SemanticClass values. Derived from empirical analysis of 25 languages.",
        "mapping": {
            str(cat_name): sc.variable
            for cat_name, sc in sorted(cat_map.items(), key=lambda x: str(x[0]))
        },
    }
    with (output_dir / "_categories.json").open("w", encoding="utf-8") as f:
        json.dump(categories_data, f, indent=2, ensure_ascii=False)

    # =================================================================
    # 3. Export scoring profiles
    # =================================================================
    print("Exporting scoring profiles...")

    scoring_data: dict[str, Any] = {
        "description": "ImportanceScores per SemanticClass and AgentTask weight profiles.",
        "semantic_classes": {},
        "agent_tasks": {},
        "importance_ranks": {},
    }

    for sc in SemanticClass:
        with contextlib.suppress(Exception):
            tc = sc.category
            scoring_data["semantic_classes"][sc.variable] = {
                "description": tc.description,
                "rank": tc.rank.value,
                "rank_name": tc.rank.name,
                "importance_scores": {
                    "discovery": tc.importance_scores.discovery,
                    "comprehension": tc.importance_scores.comprehension,
                    "modification": tc.importance_scores.modification,
                    "debugging": tc.importance_scores.debugging,
                    "documentation": tc.importance_scores.documentation,
                },
                "examples": list(tc.examples),
            }

    for rank in ImportanceRank:
        scoring_data["importance_ranks"][rank.name] = {
            "value": rank.value,
            "classifications": [sc.variable for sc in rank.semantic_classifications],
        }
    for task, profile in AGENT_TASKS.items():
        scoring_data["agent_tasks"][task] = {
            "profile": {
                "discovery": profile["discovery"],
                "comprehension": profile["comprehension"],
                "modification": profile["modification"],
                "debugging": profile["debugging"],
                "documentation": profile["documentation"],
            },
        }

    with (output_dir / "_scoring.json").open("w", encoding="utf-8") as f:
        json.dump(scoring_data, f, indent=2, ensure_ascii=False)

    # =================================================================
    # 4. Build universal rules summary
    # =================================================================
    print("Building universal rules summary...")

    # Aggregate: for each thing name, what SemanticClass does it get across languages?
    name_to_classifications: dict[str, Counter[str]] = defaultdict(Counter)
    name_to_method: dict[str, Counter[str]] = defaultdict(Counter)

    for lang_file in sorted(output_dir.glob("*.json")):
        if lang_file.name.startswith("_"):
            continue
        with lang_file.open("r", encoding="utf-8") as f:
            lang_data = json.load(f)
        for section in ("tokens", "composites"):
            for name, entry in lang_data.get(section, {}).items():
                if cls := entry.get("classification"):
                    name_to_classifications[name][cls] += 1
                    if method := entry.get("method"):
                        name_to_method[name][method] += 1

    # Find things that are classified the same way in ALL languages they appear in
    universal_exact: dict[str, str] = {}
    universal_majority: dict[str, dict[str, Any]] = {}

    for name, cls_counts in sorted(name_to_classifications.items()):
        total = sum(cls_counts.values())
        top_cls, top_count = cls_counts.most_common(1)[0]
        if top_count == total:
            # unanimous across all languages
            universal_exact[name] = top_cls
        elif top_count / total >= 0.75:
            # 75%+ agreement
            universal_majority[name] = {
                "classification": top_cls,
                "agreement": round(top_count / total * 100, 1),
                "total_languages": total,
                "distribution": dict(cls_counts.most_common()),
            }

    universal_data: dict[str, Any] = {
        "description": "Cross-language classification patterns. 'exact' means unanimous across all languages a thing appears in. 'majority' means 75%+ agreement.",
        "exact_match_count": len(universal_exact),
        "majority_match_count": len(universal_majority),
        "exact": universal_exact,
        "majority": universal_majority,
    }

    with (output_dir / "_universal_rules.json").open("w", encoding="utf-8") as f:
        json.dump(universal_data, f, indent=2, ensure_ascii=False)

    # =================================================================
    # 5. Meta file
    # =================================================================
    elapsed = time.monotonic() - start

    meta = {
        "schema_version": "1.0.0",
        "generated_by": "export-classifications.py",
        "generation_time_seconds": round(elapsed, 2),
        "total_things": total_things,
        "total_classified": total_classified,
        "total_confident": total_confident,
        "coverage_pct": round(total_classified / total_things * 100, 1) if total_things else 0,
        "confident_pct": round(total_confident / total_things * 100, 1) if total_things else 0,
        "tier_distribution": dict(sorted(tier_distribution.items())),
        "method_distribution": dict(sorted(method_distribution.items())),
        "unclassified_count": len(unclassified_things),
        "languages": [lang.variable for lang in SemanticSearchLanguage],
        "semantic_classes": [sc.variable for sc in SemanticClass],
    }

    with (output_dir / "_meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # Write unclassified things for analysis
    if unclassified_things:
        with (output_dir / "_unclassified.json").open("w", encoding="utf-8") as f:
            json.dump(unclassified_things, f, indent=2, ensure_ascii=False)

    # =================================================================
    # Summary
    # =================================================================
    print(f"\n{'=' * 60}")
    print(f"Export complete in {elapsed:.1f}s")
    print(f"  Total Things:      {total_things:,}")
    print(f"  Classified:        {total_classified:,} ({meta['coverage_pct']}%)")
    print(f"  High confidence:   {total_confident:,} ({meta['confident_pct']}%)")
    print(f"  Unclassified:      {len(unclassified_things):,}")
    print(
        f"  Universal exact:   {len(universal_exact):,} thing names classified same in all languages",
    )
    print(f"  Universal 75%+:    {len(universal_majority):,} thing names with majority agreement")
    print("\n  Tier distribution:")
    for tier, count in sorted(tier_distribution.items()):
        print(f"    {tier}: {count:,}")
    print("\n  Method distribution:")
    for method, count in sorted(method_distribution.items(), key=lambda x: -x[1]):
        print(f"    {method}: {count:,}")
    print(f"\n  Output: {output_dir}")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
