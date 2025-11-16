#!/usr/bin/env -S uv run -s
# ///script
# requires-python = ">=3.11"
# dependencies = ["rich"]
# ///
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Compare manually-defined delimiters with pattern-generated ones.

This script helps validate that the pattern-based generation produces
equivalent or better DelimiterPattern sets compared to manual definitions.
"""

from __future__ import annotations

import sys

from pathlib import Path

from rich.console import Console
from rich.table import Table


# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from codeweaver.engine.chunker.delimiters.custom import get_custom_patterns
from codeweaver.engine.chunker.delimiters.families import LanguageFamily, get_family_patterns
from codeweaver.engine.chunker.delimiters.kind import DelimiterKind
from codeweaver.engine.chunker.delimiters.patterns import (
    DelimiterDict,
    DelimiterPattern,
    expand_pattern,
)


def delimiter_dict_to_delimiter(d: DelimiterDict) -> DelimiterPattern:
    """Convert DelimiterDict to DelimiterPattern NamedTuple."""
    return DelimiterPattern(
        starts=[d["start"]],
        ends=[d["end"]],
        kind=d.get("kind", DelimiterKind.UNKNOWN),
        nestable=d.get("nestable", False),
        priority_override=d.get("priority_override", 50),
        inclusive=d.get("inclusive", False),
        take_whole_lines=d.get("take_whole_lines", False),
    )


def generate_language_delimiters(language: str) -> tuple[DelimiterPattern, ...]:
    """Generate delimiters for a language (copied from generate_delimiters.py)."""
    # Auto-detect family
    family = LanguageFamily.from_known_language(language)

    # Get family + custom patterns
    family_patterns = get_family_patterns(family)
    lang_custom = get_custom_patterns(language)
    all_patterns = family_patterns + lang_custom

    # Expand patterns
    delimiter_dicts: list[DelimiterDict] = []
    for pattern in all_patterns:
        delimiter_dicts.extend(expand_pattern(pattern))

    # Deduplicate
    seen: dict[tuple[str, str], DelimiterDict] = {}
    for delim in delimiter_dicts:
        key = (delim["start"], delim["end"])
        if key not in seen or delim.get("priority_override", 50) > seen[key].get(
            "priority_override", 50
        ):
            seen[key] = delim

    # Convert and sort
    delimiters = [delimiter_dict_to_delimiter(d) for d in seen.values()]
    return tuple(sorted(delimiters, key=lambda d: d.priority_override or 50, reverse=True))


console = Console()


def compare_delimiter_counts(language: str) -> tuple[int, int, int]:
    """Compare DelimiterPattern counts for a language.

    Returns:
        Tuple of (manual_count, generated_count, delta)
    """
    # Get manual delimiters
    manual = DELIMITERS.get(language, ())  # noqa: F821
    manual_count = len(manual)

    # Generate new delimiters
    generated = generate_language_delimiters(language)
    generated_count = len(generated)

    delta = generated_count - manual_count

    return manual_count, generated_count, delta


def compare_delimiter_sets(language: str) -> dict[str, list[tuple[str, str]]]:
    """Compare DelimiterPattern sets to find differences.

    Returns:
        Dictionary with keys:
        - "only_manual": Delimiters only in manual set
        - "only_generated": Delimiters only in generated set
        - "common": Delimiters in both sets
    """
    # Get manual delimiters
    manual = DELIMITERS.get(language, ())  # noqa: F821
    manual_pairs = {(d.start, d.end) for d in manual}

    # Generate new delimiters
    generated = generate_language_delimiters(language)
    generated_pairs = {(d.start, d.end) for d in generated}

    return {
        "only_manual": sorted(manual_pairs - generated_pairs),
        "only_generated": sorted(generated_pairs - manual_pairs),
        "common": sorted(manual_pairs & generated_pairs),
    }


def print_summary_statistics(
    manual_languages: list[str], improvements: int, regressions: int
) -> None:
    """Print summary statistics for DelimiterPattern comparison.

    Args:
        manual_languages: List of manually-defined languages.
        improvements: Number of languages with more generated delimiters.
        regressions: Number of languages with fewer generated delimiters.

    Side Effects:
        Prints summary statistics to the console.
    """
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Languages with [green]more[/green] delimiters: {improvements}")
    console.print(f"  Languages with [red]fewer[/red] delimiters: {regressions}")
    console.print(
        f"  Languages with [dim]same[/dim] count: {len(manual_languages) - improvements - regressions}"
    )


def print_detailed_differences(manual_languages: list[str]) -> None:
    """Print detailed differences between manual and generated DelimiterPattern sets.

    Args:
        manual_languages: List of manually-defined languages.

    Side Effects:
        Prints detailed differences to the console.
    """
    console.print("\n[bold cyan]Detailed Differences:[/bold cyan]\n")
    for lang in manual_languages:
        diff = compare_delimiter_sets(lang)
        if diff["only_manual"] or diff["only_generated"]:
            console.print(f"\n[bold yellow]{lang}:[/bold yellow]")
            if diff["only_manual"]:
                console.print(f"  [red]Only in manual ({len(diff['only_manual'])}):[/red]")
                for start, end in diff["only_manual"][:5]:
                    console.print(f"    ({start!r}, {end!r})")
                if len(diff["only_manual"]) > 5:
                    console.print(f"    ... and {len(diff['only_manual']) - 5} more")
            if diff["only_generated"]:
                console.print(
                    f"  [green]Only in generated ({len(diff['only_generated'])}):[/green]"
                )
                for start, end in diff["only_generated"][:5]:
                    console.print(f"    ({start!r}, {end!r})")
                if len(diff["only_generated"]) > 5:
                    console.print(f"    ... and {len(diff['only_generated']) - 5} more")
            console.print(f"  [dim]Common: {len(diff['common'])} delimiters[/dim]")


def main() -> None:
    """
    Compare manually-defined and pattern-generated delimiters for all languages.

    This function prints a summary table comparing the count of manual and generated
    delimiters for each language, displays summary statistics, and shows detailed
    differences for languages where the sets differ. Output is printed to the console.

    Side Effects:
        Prints tables and summaries to the console.
    """
    manual_languages = sorted(DELIMITERS.keys())  # noqa: F821

    console.print(
        f"\n[bold cyan]Comparing {len(manual_languages)} manually-defined languages[/bold cyan]\n"
    )

    table = Table(title="DelimiterPattern Count Comparison")
    table.add_column("Language", style="cyan")
    table.add_column("Manual", justify="right", style="yellow")
    table.add_column("Generated", justify="right", style="green")
    table.add_column("Delta", justify="right")

    total_manual = 0
    total_generated = 0
    improvements = 0
    regressions = 0

    for lang in manual_languages:
        manual_count, generated_count, delta = compare_delimiter_counts(lang)
        total_manual += manual_count
        total_generated += generated_count
        if delta > 0:
            improvements += 1
            formatted_delta = f"[green]+{delta}[/green]"
        elif delta < 0:
            regressions += 1
            formatted_delta = f"[red]{delta}[/red]"
        else:
            formatted_delta = "[dim]0[/dim]"
        table.add_row(lang, str(manual_count), str(generated_count), formatted_delta)

    table.add_section()
    total_delta = total_generated - total_manual
    delta_color = "green" if total_delta > 0 else "red" if total_delta < 0 else "dim"
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_manual}[/bold]",
        f"[bold]{total_generated}[/bold]",
        f"[bold {delta_color}]{total_delta:+d}[/bold {delta_color}]",
    )

    console.print(table)
    print_summary_statistics(manual_languages, improvements, regressions)
    print_detailed_differences(manual_languages)


if __name__ == "__main__":
    main()
