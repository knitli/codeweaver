#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Holdout evaluation: how well do universal rules classify a new language?

This script simulates the "just add a grammar" scenario for Thread. For each
holdout language, it strips all language-specific knowledge and attempts to
classify every Thing using ONLY universal rules derived from the other languages.

Classification tiers (highest to lowest priority):
  1. Token purpose  — operator/keyword/literal/punctuation/comment → direct map
  2. Universal exact — thing name classified unanimously in all OTHER languages
  3. Universal majority — thing name classified ≥75% same in OTHER languages
  4. Category mapping — category name → SemanticClass (from _categories.json)
  5. Unclassified — no rule matched

The ground truth is the full classifier output from export-classifications.py.

Metrics reported per holdout language:
  - Coverage: % of things that got any classification
  - Accuracy: % of classified things that match ground truth
  - Tier-weighted accuracy: accuracy weighted by importance rank
  - Per-method breakdown: how many things each rule tier handled
  - Confusion matrix: what gets misclassified and how
"""

from __future__ import annotations

import json
import sys

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


def load_overrides(overrides_dir: Path, lang: str) -> dict[str, str]:
    """Load TOML override file for a language.

    Returns a flat dict mapping thing_name → SemanticClass for all override types:
    [overrides], [token_overrides], and [doc_comment_tokens].
    """
    override_file = overrides_dir / f"{lang}.toml"
    if not override_file.exists():
        return {}

    with override_file.open("rb") as f:
        data = tomllib.load(f)

    result: dict[str, str] = (
        dict(data.get("overrides", {}).items()) | data.get("token_overrides", {}).items()
    ) | {
        name: "documentation_structured"
        for name, val in data.get("doc_comment_tokens", {}).items()
        if val
    }
    return result


# --- Token purpose → SemanticClass mapping ---
# This is the most fundamental rule: if we know a token's purpose, we know its class.
TOKEN_PURPOSE_MAP = {
    "operator": "operation_operator",
    "keyword": "syntax_keyword",
    "literal": "syntax_literal",
    "punctuation": "syntax_punctuation",
    "comment": "syntax_annotation",
    "identifier": "syntax_identifier",
}

# Tier weights for tier-weighted accuracy (rank 1 = most important)
TIER_WEIGHTS = {1: 5.0, 2: 4.0, 3: 3.0, 4: 2.0, 5: 1.0}


def build_universal_rules(
    classifications_dir: Path, holdout_lang: str
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Build universal rules excluding the holdout language.

    Returns:
        (exact_rules, majority_rules, category_rules)
        Each is a dict mapping name/category → SemanticClass variable.
    """
    # Aggregate name → classification across all NON-holdout languages
    name_to_classifications: dict[str, Counter[str]] = defaultdict(Counter)

    for lang_file in sorted(classifications_dir.glob("*.json")):
        if lang_file.name.startswith("_"):
            continue
        lang_key = lang_file.stem
        if lang_key == holdout_lang:
            continue  # exclude holdout

        with lang_file.open("r", encoding="utf-8") as f:
            lang_data = json.load(f)

        for section in ("tokens", "composites"):
            for name, entry in lang_data.get(section, {}).items():
                if cls := entry.get("classification"):
                    name_to_classifications[name][cls] += 1

    # Build exact (unanimous) and majority (≥75%) rules
    exact_rules: dict[str, str] = {}
    majority_rules: dict[str, str] = {}

    for name, cls_counts in name_to_classifications.items():
        total = sum(cls_counts.values())
        top_cls, top_count = cls_counts.most_common(1)[0]
        if top_count == total:
            exact_rules[name] = top_cls
        elif top_count / total >= 0.75:
            majority_rules[name] = top_cls

    # Category mapping (language-independent)
    cat_file = classifications_dir / "_categories.json"
    category_rules: dict[str, str] = {}
    if cat_file.exists():
        with cat_file.open("r", encoding="utf-8") as f:
            category_rules = json.load(f).get("mapping", {})

    return exact_rules, majority_rules, category_rules


def classify_thing_universal(
    entry: dict[str, Any],
    exact_rules: dict[str, str],
    majority_rules: dict[str, str],
    category_rules: dict[str, str],
    overrides: dict[str, str] | None = None,
) -> tuple[str | None, str]:
    """Classify a single thing using universal rules only.

    Returns:
        (predicted_class, method_used)
    """
    name = entry["name"]
    kind = entry["kind"]

    # 0. Language-specific override (highest priority)
    if overrides and name in overrides:
        return overrides[name], "override"

    # 1. File thing — always classified
    if kind == "composite" and entry.get("is_file"):
        return "file_thing", "file_detection"

    # 2. Token purpose (most reliable for tokens)
    if kind == "token":
        purpose = entry.get("purpose")
        if purpose and purpose in TOKEN_PURPOSE_MAP:
            return TOKEN_PURPOSE_MAP[purpose], "token_purpose"

    # 3. Universal exact match (name seen in all other languages with same class)
    if name in exact_rules:
        return exact_rules[name], "universal_exact"

    # 4. Universal majority match (name seen in 75%+ of other languages)
    if name in majority_rules:
        return majority_rules[name], "universal_majority"

    # 5. Category-based inference
    categories = entry.get("categories", [])
    for cat in categories:
        if cat in category_rules:
            return category_rules[cat], "category"

    # 6. Simple name heuristics (things any reasonable system would catch)
    name_lower = name.lower()
    if "comment" in name_lower:
        if "line" in name_lower:
            return "syntax_annotation", "name_heuristic"
        if "block" in name_lower or "doc" in name_lower:
            return "documentation_structured", "name_heuristic"
        return "syntax_annotation", "name_heuristic"

    return None, "unclassified"


def evaluate_holdout(
    classifications_dir: Path, holdout_lang: str, *, use_overrides: bool = False
) -> dict[str, Any]:  # sourcery skip: low-code-quality
    """Run holdout evaluation for a single language."""

    # Load ground truth
    gt_file = classifications_dir / f"{holdout_lang}.json"
    if not gt_file.exists():
        return {"error": f"No ground truth file for {holdout_lang}"}

    with gt_file.open("r", encoding="utf-8") as f:
        gt_data = json.load(f)

    # Build universal rules excluding this language
    exact_rules, majority_rules, category_rules = build_universal_rules(
        classifications_dir, holdout_lang
    )

    # Load overrides if requested
    overrides: dict[str, str] | None = None
    if use_overrides:
        overrides_dir = classifications_dir / "overrides"
        overrides = load_overrides(overrides_dir, holdout_lang)

    # Classify every thing
    method_counts: Counter[str] = Counter()
    correct = 0
    incorrect = 0
    unclassified = 0
    gt_unclassified = 0
    tier_correct: Counter[int] = Counter()
    tier_total: Counter[int] = Counter()
    confusion: list[dict[str, str]] = []

    for section in ("tokens", "composites"):
        for name, entry in gt_data.get(section, {}).items():
            gt_class = entry.get("classification")
            gt_rank = entry.get("rank")

            if gt_class is None:
                gt_unclassified += 1
                continue

            predicted, method = classify_thing_universal(
                entry, exact_rules, majority_rules, category_rules, overrides
            )
            method_counts[method] += 1

            if predicted is None:
                unclassified += 1
                confusion.append({
                    "name": name,
                    "kind": entry["kind"],
                    "expected": gt_class,
                    "predicted": None,
                    "method": method,
                    "rank": gt_rank,
                })
            elif predicted == gt_class:
                correct += 1
                if gt_rank:
                    tier_correct[gt_rank] += 1
                    tier_total[gt_rank] += 1
            else:
                incorrect += 1
                if gt_rank:
                    tier_total[gt_rank] += 1
                confusion.append({
                    "name": name,
                    "kind": entry["kind"],
                    "expected": gt_class,
                    "predicted": predicted,
                    "method": method,
                    "rank": gt_rank,
                })

    total_classifiable = correct + incorrect + unclassified
    classified = correct + incorrect
    coverage = classified / total_classifiable * 100 if total_classifiable else 0
    accuracy = correct / classified * 100 if classified else 0
    overall_accuracy = correct / total_classifiable * 100 if total_classifiable else 0

    # Tier-weighted accuracy
    weighted_correct = sum(tier_correct[r] * TIER_WEIGHTS.get(r, 1) for r in tier_correct)
    weighted_total = sum(tier_total[r] * TIER_WEIGHTS.get(r, 1) for r in tier_total)
    tier_weighted_accuracy = weighted_correct / weighted_total * 100 if weighted_total else 0

    return {
        "language": holdout_lang,
        "total_things": total_classifiable,
        "gt_unclassified": gt_unclassified,
        "has_overrides": use_overrides and bool(overrides),
        "override_count": len(overrides) if overrides else 0,
        "universal_rules_available": {
            "exact": len(exact_rules),
            "majority": len(majority_rules),
            "category": len(category_rules),
        },
        "coverage_pct": round(coverage, 1),
        "accuracy_pct": round(accuracy, 1),
        "overall_accuracy_pct": round(overall_accuracy, 1),
        "tier_weighted_accuracy_pct": round(tier_weighted_accuracy, 1),
        "correct": correct,
        "incorrect": incorrect,
        "unclassified": unclassified,
        "method_distribution": dict(method_counts.most_common()),
        "per_tier_accuracy": {
            f"tier_{r}": {
                "correct": tier_correct[r],
                "total": tier_total[r],
                "accuracy_pct": round(tier_correct[r] / tier_total[r] * 100, 1)
                if tier_total[r]
                else 0,
            }
            for r in sorted(set(tier_correct.keys()) | set(tier_total.keys()))
        },
        "misclassifications": sorted(confusion, key=lambda x: (x.get("rank") or 99, x["name"])),
    }


def print_summary_table(
    label: str, results: list[dict[str, Any]]
) -> tuple[float, float, float, float]:
    """Print a summary table and return averages."""
    w = max(12, max((len(r["language"]) for r in results), default=12) + 2)
    print(
        f"\n  {'Language':<{w}s}  {'Coverage':>8s}  {'Accuracy':>8s}  {'Overall':>8s}  {'Tier-Wtd':>8s}  {'Uncls':>5s}  {'Wrong':>5s}"
    )
    print(f"  {'─' * w}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 5}  {'─' * 5}")
    for r in results:
        ovr = f" (+{r['override_count']})" if r.get("override_count") else ""
        print(
            f"  {r['language']:<{w}s}  {r['coverage_pct']:>7.1f}%  {r['accuracy_pct']:>7.1f}%  "
            f"{r['overall_accuracy_pct']:>7.1f}%  {r['tier_weighted_accuracy_pct']:>7.1f}%  "
            f"{r['unclassified']:>5d}  {r['incorrect']:>5d}{ovr}"
        )

    avg_cov = sum(r["coverage_pct"] for r in results) / len(results)
    avg_acc = sum(r["accuracy_pct"] for r in results) / len(results)
    avg_ovr = sum(r["overall_accuracy_pct"] for r in results) / len(results)
    avg_tier = sum(r["tier_weighted_accuracy_pct"] for r in results) / len(results)
    print(f"  {'─' * w}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 5}  {'─' * 5}")
    print(
        f"  {'AVERAGE':<{w}s}  {avg_cov:>7.1f}%  {avg_acc:>7.1f}%  "
        f"{avg_ovr:>7.1f}%  {avg_tier:>7.1f}%"
    )
    return avg_cov, avg_acc, avg_ovr, avg_tier


def main() -> int:  # sourcery skip: low-code-quality
    """Run holdout evaluation across selected languages.

    Usage:
        holdout-evaluation.py             # Run on 8 holdout languages (default)
        holdout-evaluation.py --all       # Run on ALL languages with classification data
        holdout-evaluation.py --lang X Y  # Run on specific language(s)
    """
    import argparse

    parser = argparse.ArgumentParser(description="Holdout evaluation for language classifications")
    parser.add_argument(
        "--all", action="store_true", help="Evaluate ALL languages (not just holdout set)"
    )
    parser.add_argument("--lang", nargs="+", help="Evaluate specific language(s)")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent.parent
    classifications_dir = repo_root / "src" / "codeweaver" / "semantic" / "data" / "classifications"

    if not classifications_dir.exists():
        print("ERROR: Classifications directory not found. Run export-classifications.py first.")
        return 1

    # Discover all available languages from JSON files
    all_languages = sorted(
        f.stem for f in classifications_dir.glob("*.json") if not f.name.startswith("_")
    )

    if args.lang:
        holdout_languages = [lang for lang in args.lang if lang in all_languages]
        if not holdout_languages:
            print(f"ERROR: None of {args.lang} found. Available: {all_languages}")
            return 1
    elif args.all:
        holdout_languages = all_languages
    else:
        # Default: 8 holdout languages
        holdout_languages = [
            "go",  # C-family, 100% coverage, relatively clean grammar
            "rust",  # Unique syntax, 100% coverage, rich type system
            "kotlin",  # JVM, 94.5% coverage, has unclassified items
            "elixir",  # Functional, 100% coverage, very different paradigm
            "ruby",  # Dynamic, 99.6% coverage, DSL-heavy
            "hcl",  # Natural holdout — added after classifier was built
            "swift",  # Apple ecosystem, 99.7% coverage, protocol-oriented
            "scala",  # Multi-paradigm, 99.6% coverage, complex type system
        ]

    # Check which languages have override files
    overrides_dir = classifications_dir / "overrides"
    has_any_overrides = overrides_dir.exists() and any(overrides_dir.glob("*.toml"))

    # =====================================================================
    # Phase 1: Universal rules only (no overrides)
    # =====================================================================
    print("=" * 72)
    _display_phase_intro(
        "PHASE 1: Universal Rules Only",
        "Simulates 'just add a grammar' — no language-specific patterns.",
    )
    print("Ground truth: full CodeWeaver classifier output.")
    print()

    baseline_results: list[dict[str, Any]] = []

    for lang in holdout_languages:
        result = evaluate_holdout(classifications_dir, lang, use_overrides=False)
        if "error" in result:
            print(f"  {lang}: {result['error']}")
            continue
        baseline_results.append(result)
        print(
            f"  {lang:<14s}  overall={result['overall_accuracy_pct']:5.1f}%  "
            f"({result['correct']}/{result['total_things']} correct, "
            f"{result['unclassified']} uncls, {result['incorrect']} wrong)"
        )

    _display_phase_intro("\n", "PHASE 1 SUMMARY")
    avg_b = print_summary_table("Baseline", baseline_results)

    # Save baseline results
    output_file = classifications_dir / "_holdout_evaluation.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(baseline_results, f, indent=2, ensure_ascii=False)

    # =====================================================================
    # Phase 2: Universal rules + TOML overrides
    # =====================================================================
    override_results: list[dict[str, Any]] = []

    if has_any_overrides:
        print(f"\n\n{'=' * 72}")
        _display_phase_intro(
            "PHASE 2: Universal Rules + TOML Overrides",
            "Same universal rules, plus per-language TOML override files.",
        )
        print(f"Override directory: {overrides_dir}")
        print()

        for lang in holdout_languages:
            result = evaluate_holdout(classifications_dir, lang, use_overrides=True)
            if "error" in result:
                continue
            override_results.append(result)
            ovr_count = result["override_count"]
            marker = f" [{ovr_count} overrides]" if ovr_count else " [no overrides]"
            print(
                f"  {lang:<14s}  overall={result['overall_accuracy_pct']:5.1f}%  "
                f"({result['correct']}/{result['total_things']} correct, "
                f"{result['unclassified']} uncls, {result['incorrect']} wrong)"
                f"{marker}"
            )

        _display_phase_intro("\n", "PHASE 2 SUMMARY")
        avg_o = print_summary_table("With Overrides", override_results)

        # Save combined results
        combined = {"baseline": baseline_results, "with_overrides": override_results}
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(combined, f, indent=2, ensure_ascii=False)

        _display_phase_intro("\n\n", "COMPARISON: Baseline vs With Overrides")
        w = max(12, max((len(r["language"]) for r in baseline_results), default=12) + 2)
        print(
            f"\n  {'Language':<{w}s}  {'Baseline':>8s}  {'Override':>8s}  {'Delta':>7s}  {'Override Lines':>14s}"
        )
        print(f"  {'─' * w}  {'─' * 8}  {'─' * 8}  {'─' * 7}  {'─' * 14}")

        for b, o in zip(baseline_results, override_results, strict=False):
            if b["language"] != o["language"]:
                continue
            delta = o["overall_accuracy_pct"] - b["overall_accuracy_pct"]
            sign = "+" if delta >= 0 else ""
            ovr_count = o["override_count"]
            print(
                f"  {b['language']:<{w}s}  {b['overall_accuracy_pct']:>7.1f}%  "
                f"{o['overall_accuracy_pct']:>7.1f}%  {sign}{delta:>5.1f}%  "
                f"{ovr_count:>14d}"
            )

        delta_overall = avg_o[2] - avg_b[2]
        print(f"  {'─' * w}  {'─' * 8}  {'─' * 8}  {'─' * 7}  {'─' * 14}")
        print(f"  {'AVERAGE':<{w}s}  {avg_b[2]:>7.1f}%  {avg_o[2]:>7.1f}%  +{delta_overall:>5.1f}%")

    # =====================================================================
    # Assessment
    # =====================================================================
    final_results = override_results or baseline_results
    final_avg = avg_o if override_results else avg_b

    _display_phase_intro("\n", "ASSESSMENT: 'Just Add a Grammar' Viability")
    targets_met = sum(r["coverage_pct"] >= 75 and r["accuracy_pct"] >= 80 for r in final_results)
    print("\n  Target: >= 75% coverage AND >= 80% accuracy")
    print(f"  Languages meeting target: {targets_met}/{len(final_results)}")

    print(f"\n  Baseline (universal only):   {avg_b[2]:.1f}% overall accuracy")
    if override_results:
        print(f"  With TOML overrides:         {avg_o[2]:.1f}% overall accuracy")
        total_overrides = sum(r["override_count"] for r in override_results)
        langs_with_overrides = sum(r["override_count"] > 0 for r in override_results)
        print(
            f"  Override cost:               {total_overrides} lines across {langs_with_overrides} files"
        )

    if final_avg[2] >= 95:
        print(f"\n  VERDICT: Overrides bring accuracy to production quality ({final_avg[2]:.1f}%).")
        print("  The universal-rules + small-TOML-override model is validated.")
    elif final_avg[2] >= 80:
        print("\n  VERDICT: Strong support for the declarative classification model.")
    elif final_avg[2] >= 65:
        print("\n  VERDICT: Moderate support. Additional rule types may be needed.")
    else:
        print("\n  VERDICT: Insufficient. The override model needs redesign.")

    print(f"\n  Detailed results saved to: {output_file}")
    print()
    return 0


def _display_phase_intro(break_or_title: str, phase_intro_message: str):
    print(break_or_title)
    print("=" * 72)
    print()
    print(phase_intro_message)
    print(f"{'=' * 72}")


if __name__ == "__main__":
    sys.exit(main())
