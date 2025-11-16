#!/usr/bin/env -S uv run -s
# ///script
# requires-python = ">=3.11"
# dependencies = ["rich"]
# ///
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Generate language delimiter definitions from patterns.

This script uses the pattern-based delimiter system to generate concrete
delimiter definitions for each supported language. It combines family patterns
with language-specific customizations.

Usage:
    python scripts/generate_delimiters.py [--output OUTPUT_FILE] [--language LANG]

TODO: I'm fairly sure we aren't using this anymore, and instead we construct them dynamically
      at runtime. Consider removing this script if confirmed.
"""

from __future__ import annotations

import argparse
import sys

from pathlib import Path
from typing import TYPE_CHECKING, cast

from rich.console import Console


# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from codeweaver.engine.chunker.delimiters import LanguageFamily, expand_pattern
from codeweaver.engine.chunker.delimiters.custom import get_custom_patterns
from codeweaver.engine.chunker.delimiters.families import get_family_patterns
from codeweaver.engine.chunker.delimiters.kind import DelimiterKind
from codeweaver.engine.chunker.delimiters.patterns import (
    DelimiterDict,
    DelimiterPattern,
    kind_from_delimiter_tuple,
)


if TYPE_CHECKING:
    from codeweaver.engine.chunker.delimiters.patterns import DelimiterPattern


console = Console(markup=True, emoji=True)


def delimiter_dict_to_delimiter(d: DelimiterDict) -> DelimiterPattern:
    """Convert DelimiterDict to DelimiterPattern NamedTuple."""
    return DelimiterPattern(
        starts=d["start"],
        ends=d["end"],
        kind=d.get("kind", DelimiterKind.UNKNOWN),
        nestable=d.get("nestable", False),
        priority_override=d.get("priority", 20),
        inclusive=d.get("inclusive", False),
        take_whole_lines=d.get("take_whole_lines", False),
    )


def generate_language_delimiters(
    language: str,
    family: LanguageFamily | None = None,
    custom_patterns: list[DelimiterPattern] | None = None,
    *,
    include_custom: bool = True,
) -> tuple[DelimiterPattern, ...]:
    """Generate delimiters for a language.

    Args:
        language: Language name (e.g., "python", "javascript")
        family: Language family (auto-detected if None)
        custom_patterns: Additional language-specific patterns (overrides auto-detected)
        include_custom: Whether to include language-specific custom patterns

    Returns:
        Tuple of DelimiterPattern objects sorted by priority (descending)
    """
    # Auto-detect family if not provided
    if family is None:
        family = LanguageFamily.from_known_language(language)

    # Get family patterns
    family_patterns = get_family_patterns(family)

    # Get custom patterns
    if custom_patterns is not None:
        lang_custom = custom_patterns
    elif include_custom:
        lang_custom = get_custom_patterns(language)
    else:
        lang_custom = []

    # Combine with custom patterns
    all_patterns = family_patterns + lang_custom

    # Expand all patterns to concrete delimiters
    delimiter_dicts: list[DelimiterDict] = []
    for pattern in all_patterns:
        delimiter_dicts.extend(expand_pattern(pattern))

    # Deduplicate by (start, end) pair, keeping highest priority
    seen: dict[tuple[str, str], DelimiterDict] = {}
    for delim in delimiter_dicts:
        key = (delim["start"], delim["end"])
        if key not in seen or delim.get("priority", 10) > seen[key].get("priority", 20):
            seen[key] = delim

    # Convert to DelimiterPattern objects and sort by priority
    delimiters = [delimiter_dict_to_delimiter(d) for d in seen.values()]
    sorted_delimiters = sorted(delimiters, key=lambda d: d.priority_override or 20, reverse=True)

    return tuple(sorted_delimiters)


def format_delimiter_definition(language: str, delimiters: tuple[DelimiterPattern, ...]) -> str:
    """Format delimiter tuple as Python code for _constants.py.

    Args:
        language: Language name
        delimiters: Tuple of DelimiterPattern objects

    Returns:
        Formatted Python code string
    """
    lines = [f'    "{language}": (']

    for delim in delimiters:
        if not delim.kind:
            delim = DelimiterPattern(
                starts=delim.starts,
                ends=delim.ends,
                kind=kind_from_delimiter_tuple(delim.starts, delim.ends),
                nestable=delim.nestable,
                priority_override=delim.priority_override,
                inclusive=delim.inclusive,
                take_whole_lines=delim.take_whole_lines,
            )
        lines.extend((
            "        DelimiterPattern(",
            f'            starts="{delim.starts}",',
            f'            ends="{delim.ends}",',
            f"            kind=DelimiterKind.{cast(DelimiterKind, delim.kind).name.upper()},",
            f"            nestable={delim.nestable},",
            f"            priority_override={delim.priority_override},",
            f"            inclusive={delim.inclusive},",
            f"            take_whole_lines={delim.take_whole_lines},",
            "        ),",
        ))
    lines.append("    ),")

    return "\n".join(lines)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate language delimiter definitions")
    parser.add_argument(
        "--output", "-o", type=Path, help="Output file (prints to stdout if not specified)"
    )
    parser.add_argument("--language", "-l", help="Generate for specific language only")
    parser.add_argument(
        "--list-families",
        action="store_true",
        help="List all language families and their languages",
    )

    args = parser.parse_args()

    if args.list_families:
        console.print("[bold cyan]Language Families:[/bold cyan]")
        console.print("=" * 80)
        for family in LanguageFamily:
            if family == LanguageFamily.UNKNOWN:
                continue
            console.print(f"\n[cyan]{family.value.upper()}:[/cyan]")
            # Would need to iterate through language mappings
            # For now, just show family names
        return

    # Generate for specific language or all
    if args.language:
        delimiters = generate_language_delimiters(args.language)
        output = format_delimiter_definition(args.language, delimiters)
        if args.output:
            args.output.write_text(output)
            console.print(
                f"[bold green]Generated delimiters for {args.language} → {args.output}[/bold green]"
            )
        else:
            console.print(output)
    else:
        _print_outcome()


def _print_outcome() -> None:
    """Generate and print delimiter definitions for all languages."""
    # Generate for all languages from the family mapping
    from codeweaver.engine.chunker.delimiters.families import _LANGUAGE_TO_FAMILY

    languages = sorted(_LANGUAGE_TO_FAMILY.keys())

    console.print("[bold cyan]# Generated delimiter definitions from pattern system[/bold cyan]")
    console.print("[bold cyan]# Generated by scripts/generate_delimiters.py[/bold cyan]")
    console.print("[bold cyan]#[/bold cyan]")
    console.print(f"[bold cyan]# Languages: {len(languages)}[/bold cyan]")
    console.print(
        "[bold cyan]# DO NOT EDIT - regenerate using: uv run python scripts/generate_delimiters.py[/bold cyan]"
    )
    console.print()
    console.print(
        "DELIMITERS: MappingProxyType[LiteralStringT, tuple[DelimiterPattern, ...]] = MappingProxyType({"
    )

    for i, lang in enumerate(languages):
        delimiters = generate_language_delimiters(lang)
        output = format_delimiter_definition(lang, delimiters)
        if i < len(languages) - 1:
            console.print(output)
        else:
            # Last item - no trailing comma on closing paren
            console.print(output.rstrip(","))

    console.print("})")
    console.print()
    console.print(f"# Total languages: {len(languages)}")
    console.print(
        f"# Total delimiter definitions: {sum(len(generate_language_delimiters(lang)) for lang in languages)}"
    )


if __name__ == "__main__":
    main()
