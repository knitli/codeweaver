#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Generate TOML override files from holdout evaluation misclassification data.

Reads _holdout_evaluation.json and creates per-language TOML override files
for any language that doesn't already have one (or all languages with --all).

The generated overrides correct misclassifications found during holdout
evaluation, where universal rules alone fail to classify things correctly.

Override sections:
  [overrides]          - Composite things: name = "expected_class"
  [token_overrides]    - Token things: name = "expected_class"
  [doc_comment_tokens] - Tokens with expected "documentation_structured": name = true
"""

from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "src" / "codeweaver" / "semantic" / "data" / "classifications"
OVERRIDES_DIR = DATA_DIR / "overrides"
EVAL_FILE = DATA_DIR / "_holdout_evaluation.json"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TIER_NAMES: dict[int, str] = {
    1: "Primary Definitions",
    2: "Boundaries",
    3: "Control Flow",
    4: "Operations",
    5: "Syntax",
}

METHOD_DISPLAY: dict[str, str] = {
    "universal_exact": "universal",
    "universal_majority": "universal",
    "category": "category",
    "token_purpose": "token_purpose",
}

# For token_purpose, shorten the predicted semantic class to its purpose name.
# e.g. "syntax_keyword" -> "keyword", "syntax_annotation" -> "annotation"
TOKEN_PURPOSE_SHORT: dict[str, str] = {
    "syntax_keyword": "keyword",
    "syntax_literal": "literal",
    "syntax_annotation": "annotation",
    "syntax_punctuation": "punctuation",
    "syntax_identifier": "identifier",
    "operation_operator": "operator",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def format_method_comment(method: str, predicted: str | None) -> str | None:
    """Build the inline comment showing what the wrong prediction was.

    Returns None when there is no predicted value (unclassified) or the method
    is not in our display mapping.
    """
    if predicted is None:
        return None
    display_method = METHOD_DISPLAY.get(method)
    if display_method is None:
        return None
    if method == "token_purpose":
        short = TOKEN_PURPOSE_SHORT.get(predicted, predicted)
        return f"# {display_method} says {short}"
    return f"# {display_method} says {predicted}"


def compute_expected_accuracy(entry: dict) -> float:
    """Compute the expected accuracy if all misclassifications were overridden.

    After overrides, all previously misclassified + unclassified things become
    correct, so expected = (correct + incorrect + unclassified) / total * 100.
    But gt_unclassified things remain unclassifiable.
    """
    total = entry["total_things"]
    gt_unclassified = entry.get("gt_unclassified", 0)
    classifiable = total - gt_unclassified
    return 100.0 if classifiable == 0 else round(classifiable / total * 100, 0)


def format_accuracy_label(pct: float) -> str:
    """Format expected accuracy like '~99%' or '~100%'."""
    rounded = int(pct)
    return f"~{rounded}%"


def needs_quoting(name: str) -> bool:
    """Check if a TOML key needs quoting (contains non-alphanumeric/underscore)."""
    return not all(c.isalnum() or c == "_" for c in name)


def toml_key(name: str) -> str:
    """Format a name as a TOML key, quoting if necessary."""
    return f'"{name}"' if needs_quoting(name) else name


def generate_toml(lang_entry: dict) -> str | None:
    """Generate TOML override content for a single language.

    Returns None if the language has zero misclassifications.
    """
    language = lang_entry["language"]
    misclassifications = lang_entry.get("misclassifications", [])

    if not misclassifications:
        return None

    # Partition misclassifications into sections
    composites: list[dict] = []
    tokens: list[dict] = []
    doc_comments: list[dict] = []

    for m in misclassifications:
        kind = m["kind"]
        expected = m["expected"]

        if kind == "token" and expected == "documentation_structured":
            doc_comments.append(m)
        elif kind == "token":
            tokens.append(m)
        else:
            composites.append(m)

    # Sort each group: by rank ascending, then alphabetically within same rank
    def sort_key(m: dict) -> tuple[int, str]:
        return (m["rank"], m["name"].lower())

    composites.sort(key=sort_key)
    tokens.sort(key=sort_key)
    doc_comments.sort(key=sort_key)

    # Count unclassified vs misclassified
    n_unclassified = sum(m["predicted"] is None for m in misclassifications)
    n_misclassified = len(misclassifications) - n_unclassified

    # Compute baseline and expected accuracy
    baseline_pct = lang_entry["overall_accuracy_pct"]
    expected_pct = compute_expected_accuracy(lang_entry)
    expected_label = format_accuracy_label(expected_pct)

    # Determine column alignment widths
    # The = sign aligns to the longest key + 1 space across ALL sections
    all_names = [toml_key(m["name"]) for m in {*composites, *tokens, *doc_comments}]

    if not all_names:
        return None

    max_key_len = max(len(n) for n in all_names)
    # Pad to at least the longest key + 1 space before =
    key_width = max_key_len + 1

    # For comment alignment, find the longest value string in each section
    # Values are like "definition_callable" (max ~24 chars) or true (4 chars)
    # Comments should align after the value
    def max_value_len(entries: list[dict], *, is_doc: bool = False) -> int:
        if not entries:
            return 0
        if is_doc:
            return len("true")
        return max(len(f'"{m["expected"]}"') for m in entries)

    composite_val_width = max_value_len(composites)
    token_val_width = max_value_len(tokens)

    # Build the TOML content
    lines: list[str] = []

    # Header
    lines.append(f"# {language.capitalize()} language classification overrides")
    lines.append(
        f"# Holdout evaluation: {baseline_pct}% overall"
        f" \u2192 expected {expected_label} with overrides"
    )
    lines.append(
        f"# {len(misclassifications)} items to override"
        f" ({n_unclassified} unclassified + {n_misclassified} misclassified)"
    )

    # [overrides] section
    if composites:
        lines.append("")
        lines.append("[overrides]")
        _emit_entries(lines, composites, key_width, composite_val_width, is_doc=False)

    # [token_overrides] section
    if tokens:
        lines.append("")
        lines.append("[token_overrides]")
        _emit_entries(lines, tokens, key_width, token_val_width, is_doc=False)

    # [doc_comment_tokens] section
    if doc_comments:
        lines.append("")
        lines.append("[doc_comment_tokens]")
        _emit_doc_entries(lines, doc_comments, key_width)

    lines.append("")  # trailing newline
    return "\n".join(lines)


def _emit_entries(
    lines: list[str], entries: list[dict], key_width: int, val_width: int, *, is_doc: bool
) -> None:
    """Emit sorted, tier-grouped TOML entries with aligned columns."""
    current_tier: int | None = None

    for m in entries:
        rank = m["rank"]
        if rank != current_tier:
            current_tier = rank
            tier_label = TIER_NAMES.get(rank, f"Tier {rank}")
            lines.append(f"# --- Tier {rank}: {tier_label} ---")

        key = toml_key(m["name"])
        value = f'"{m["expected"]}"'

        # Build the base assignment: key + padding + = + space + value
        padded_key = key.ljust(key_width)
        base = f"{padded_key}= {value}"

        if comment := format_method_comment(m["method"], m["predicted"]):
            # Pad value to align comments
            padded_value = value.ljust(val_width)
            base = f"{padded_key}= {padded_value}"
            line = f"{base}   {comment}"
        else:
            line = base

        lines.append(line)


def _emit_doc_entries(lines: list[str], entries: list[dict], key_width: int) -> None:
    """Emit doc_comment_tokens entries."""
    for m in entries:
        key = toml_key(m["name"])
        padded_key = key.ljust(key_width)
        lines.append(f"{padded_key}= true")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:  # sourcery skip: low-code-quality
    parser = argparse.ArgumentParser(
        description="Generate TOML override files from holdout evaluation data."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Regenerate ALL languages, even those with existing overrides.",
    )
    parser.add_argument(
        "--lang", nargs="+", metavar="LANG", help="Generate overrides for specific languages only."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be generated without writing files.",
    )
    args = parser.parse_args()

    # Load evaluation data
    if not EVAL_FILE.exists():
        print(f"Error: evaluation file not found: {EVAL_FILE}", file=sys.stderr)
        sys.exit(1)

    with EVAL_FILE.open() as f:
        eval_data = json.load(f)

    baseline_entries = eval_data.get("baseline", [])
    if not baseline_entries:
        print("Error: no baseline entries found in evaluation data.", file=sys.stderr)
        sys.exit(1)

    # Determine which languages already have override files
    existing_overrides = {p.stem for p in OVERRIDES_DIR.glob("*.toml") if p.stem != "SPEC"}

    # Filter languages to process
    if args.lang:
        requested = set(args.lang)
        entries_to_process = [e for e in baseline_entries if e["language"] in requested]
        if missing := requested - {e["language"] for e in entries_to_process}:
            print(
                f"Warning: languages not found in evaluation data: {', '.join(sorted(missing))}",
                file=sys.stderr,
            )
    elif args.all:
        entries_to_process = baseline_entries
    else:
        # Default: only languages WITHOUT existing overrides
        entries_to_process = [
            e for e in baseline_entries if e["language"] not in existing_overrides
        ]

    if not entries_to_process:
        print("No languages to process.")
        return

    # Process each language
    generated: list[str] = []
    skipped_zero: list[str] = []
    skipped_exists: list[str] = []

    for entry in entries_to_process:
        lang = entry["language"]
        misclassifications = entry.get("misclassifications", [])

        # Skip languages with 0 misclassifications
        if not misclassifications:
            skipped_zero.append(lang)
            continue

        # Skip existing overrides unless --all or --lang
        if not args.all and not args.lang and lang in existing_overrides:
            skipped_exists.append(lang)
            continue

        toml_content = generate_toml(entry)
        if toml_content is None:
            skipped_zero.append(lang)
            continue

        output_path = OVERRIDES_DIR / f"{lang}.toml"

        if args.dry_run:
            print(f"\n{'=' * 60}")
            print(f"Would write: {output_path}")
            print(f"{'=' * 60}")
            print(toml_content)
        else:
            output_path.write_text(toml_content, encoding="utf-8")

        generated.append(lang)

    # Summary
    print(f"\n{'=' * 60}")
    print("Override Generation Summary")
    print(f"{'=' * 60}")
    if generated:
        action = "Would generate" if args.dry_run else "Generated"
        print(f"  {action}: {len(generated)} files")
        for lang in sorted(generated):
            print(f"    - {lang}.toml")
    if skipped_zero:
        print(f"  Skipped (0 misclassifications): {', '.join(sorted(skipped_zero))}")
    if skipped_exists:
        print(f"  Skipped (already exists): {', '.join(sorted(skipped_exists))}")
    if not generated and not skipped_zero and not skipped_exists:
        print("  Nothing to do.")
    print()


if __name__ == "__main__":
    main()
