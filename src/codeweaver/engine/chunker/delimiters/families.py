# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Language family classification and delimiter grouping.

This module provides language family definitions and detection logic for grouping
languages with similar delimiter patterns. Families enable code reuse and provide
reasonable defaults for unknown languages.

Example:
    >>> detect_language_family("function foo() { return 42; }")
    <LanguageFamily.C_STYLE: 'c_style'>

    >>> FAMILY_PATTERNS[LanguageFamily.C_STYLE]
    [FUNCTION_PATTERN, CLASS_PATTERN, ...]
"""

from __future__ import annotations

import asyncio

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from pydantic import NonNegativeFloat, NonNegativeInt

from codeweaver.core.types.delimiter import _LANGUAGE_TO_FAMILY, LanguageFamily


if TYPE_CHECKING:
    from codeweaver.core.types.delimiter import DelimiterKind, LanguageFamily
    from codeweaver.engine.chunker.delimiters.patterns import DelimiterPattern


# Language-to-family mapping for known languages -- moved to core.types.delimiter


def defined_languages() -> tuple[str, ...]:
    """Get a list of all languages with defined families.

    Returns:
        List of language names with known family mappings

    Example:
        >>> "python" in defined_languages()
        True

        >>> "unknownlang" in defined_languages()
        False
    """
    return tuple(_LANGUAGE_TO_FAMILY.keys())


# Family delimiter pattern mappings
# Lazy import to avoid circular dependencies
def _get_family_patterns() -> dict[LanguageFamily, list[DelimiterPattern]]:
    """Get family delimiter patterns with lazy import."""
    from codeweaver.engine.chunker.delimiters.patterns import (
        ARRAY_PATTERN,
        BEGIN_END_BLOCK_PATTERN,
        BRACE_BLOCK_PATTERN,
        C_BLOCK_COMMENT_PATTERN,
        CLASS_PATTERN,
        CONDITIONAL_PATTERN,
        CONDITIONAL_TEX_PATTERN,
        CONTEXT_MANAGER_PATTERN,
        DASH_COMMENT_PATTERN,
        DECORATOR_PATTERN,
        DOCSTRING_HASH_PATTERN,
        DOCSTRING_MATLAB_PATTERN,
        DOCSTRING_QUOTE_PATTERN,
        DOCSTRING_RUBY_PATTERN,
        DOCSTRING_SEMICOLON_PATTERN,
        DOCSTRING_SLASH_PATTERN,
        EMPTY_PATTERN,
        ENUM_PATTERN,
        EXTENSION_PATTERN,
        FUNCTION_PATTERN,
        HASH_COMMENT_PATTERN,
        HASKELL_BLOCK_COMMENT_PATTERN,
        HTML_COMMENT_PATTERN,
        IMPL_PATTERN,
        INTERFACE_PATTERN,
        LATEX_ALIGN_PATTERNS,
        LATEX_ARRAY_PATTERNS,
        LATEX_BLOCK_PATTERNS,
        LATEX_ENV_PATTERN,
        LATEX_LITERALS_PATTERNS,
        LATEX_SECTION_PATTERN,
        LATEX_STRING_PATTERN,
        LET_END_BLOCK_PATTERN,
        LISP_BLOCK_COMMENT_PATTERN,
        LOOP_PATTERN,
        ML_BLOCK_COMMENT_PATTERN,
        MODULE_BOUNDARY_PATTERN,
        MODULE_PATTERN,
        NEWLINE_PATTERN,
        PARAGRAPH_PATTERN,
        PERCENT_COMMENT_PATTERN,
        PRAGMA_PATTERN,
        PROPERTY_PATTERN,
        SEMICOLON_COMMENT_PATTERN,
        SLASH_COMMENT_PATTERN,
        STRING_BACKTICK_QUOTE_PATTERN,
        STRING_BYTES_PATTERN,
        STRING_FORMATTED_PATTERN,
        STRING_HASH_PATTERN,
        STRING_QUOTE_PATTERN,
        STRING_RAW_BYTES_PATTERN,
        STRING_RAW_FORMATTED_PATTERN,
        STRING_RAW_PATTERN,
        STRUCT_PATTERN,
        TEMPLATE_ANGLE_PATTERN,
        TEMPLATE_BRACE_PATTERN,
        TEMPLATE_BRACKET_PATTERN,
        TEMPLATE_PERCENT_PATTERN,
        TRY_CATCH_PATTERN,
        TUPLE_PATTERN,
        TYPE_ALIAS_PATTERN,
        WHITESPACE_PATTERN,
    )

    return {
        LanguageFamily.C_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            CLASS_PATTERN,
            STRUCT_PATTERN,
            INTERFACE_PATTERN,
            ENUM_PATTERN,
            TYPE_ALIAS_PATTERN,
            IMPL_PATTERN,
            EXTENSION_PATTERN,
            MODULE_BOUNDARY_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            TRY_CATCH_PATTERN,
            CONTEXT_MANAGER_PATTERN,
            # Commentary
            SLASH_COMMENT_PATTERN,
            C_BLOCK_COMMENT_PATTERN,
            DOCSTRING_SLASH_PATTERN,
            # Structural
            BRACE_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            PRAGMA_PATTERN,
            STRING_QUOTE_PATTERN,
            STRING_RAW_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.PLAIN_TEXT: [
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.PYTHON_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            CLASS_PATTERN,
            TYPE_ALIAS_PATTERN,
            MODULE_BOUNDARY_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            TRY_CATCH_PATTERN,
            CONTEXT_MANAGER_PATTERN,
            # Commentary
            HASH_COMMENT_PATTERN,
            DOCSTRING_QUOTE_PATTERN,
            DOCSTRING_HASH_PATTERN,
            # Structural
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            DECORATOR_PATTERN,
            PROPERTY_PATTERN,
            STRING_QUOTE_PATTERN,
            STRING_RAW_PATTERN,
            STRING_FORMATTED_PATTERN,
            STRING_RAW_FORMATTED_PATTERN,
            STRING_BYTES_PATTERN,
            STRING_RAW_BYTES_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.ML_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            MODULE_PATTERN,
            STRUCT_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            # Commentary
            ML_BLOCK_COMMENT_PATTERN,
            # Structural
            LET_END_BLOCK_PATTERN,
            BEGIN_END_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.LISP_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            MODULE_PATTERN,
            # Commentary
            SEMICOLON_COMMENT_PATTERN,
            DOCSTRING_SEMICOLON_PATTERN,
            LISP_BLOCK_COMMENT_PATTERN,
            # Structural
            TUPLE_PATTERN,  # S-expressions
            ARRAY_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            STRING_HASH_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.MARKUP_STYLE: [
            # Commentary
            HTML_COMMENT_PATTERN,
            # Structural
            TEMPLATE_ANGLE_PATTERN,
            TEMPLATE_BRACE_PATTERN,
            TEMPLATE_BRACKET_PATTERN,
            TEMPLATE_PERCENT_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            STRING_BACKTICK_QUOTE_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.SHELL_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            # Commentary
            HASH_COMMENT_PATTERN,
            # Structural
            BRACE_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            STRING_RAW_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.FUNCTIONAL_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            CLASS_PATTERN,
            MODULE_PATTERN,
            TYPE_ALIAS_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            # Commentary
            DASH_COMMENT_PATTERN,
            HASKELL_BLOCK_COMMENT_PATTERN,
            # Structural
            LET_END_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.LATEX_STYLE: [
            LATEX_SECTION_PATTERN,
            # Control flow
            CONDITIONAL_TEX_PATTERN,
            # Commentary
            PERCENT_COMMENT_PATTERN,
            # Structural
            *LATEX_BLOCK_PATTERNS,
            LATEX_ENV_PATTERN,
            *LATEX_ARRAY_PATTERNS,
            *LATEX_ALIGN_PATTERNS,
            # Data
            BRACE_BLOCK_PATTERN,
            ARRAY_PATTERN,
            # Special
            *LATEX_LITERALS_PATTERNS,
            LATEX_STRING_PATTERN,
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.RUBY_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            CLASS_PATTERN,
            MODULE_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            TRY_CATCH_PATTERN,
            # Commentary
            HASH_COMMENT_PATTERN,
            DOCSTRING_RUBY_PATTERN,
            # Structural
            BEGIN_END_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            STRING_RAW_PATTERN,
            STRING_FORMATTED_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.MATLAB_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            # Commentary
            PERCENT_COMMENT_PATTERN,
            DOCSTRING_MATLAB_PATTERN,
            # Structural
            ARRAY_PATTERN,
            BRACE_BLOCK_PATTERN,
            TUPLE_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.UNKNOWN: [
            # Generic fallback patterns
            PARAGRAPH_PATTERN,
            BRACE_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
    }


# Cache family patterns for performance
_family_patterns_cache: dict[LanguageFamily, list[DelimiterPattern]] | None = None


def get_family_patterns(family: LanguageFamily) -> list[DelimiterPattern]:
    """Get delimiter patterns for a language family.

    Args:
        family: The language family to get patterns for

    Returns:
        List of DelimiterPattern objects for the family

    Example:
        >>> patterns = get_family_patterns(LanguageFamily.C_STYLE)
        >>> len(patterns) > 10
        True
    """
    global _family_patterns_cache
    if _family_patterns_cache is None:
        _family_patterns_cache = _get_family_patterns()
    return _family_patterns_cache.get(family, [])


def _detect_language_family_sync(content: str, min_confidence: int = 3) -> LanguageFamily:
    """Synchronous language family detection used by the async wrapper.

    Chooses the family with the highest weighted score (distinctive pattern matches).
    If the highest match count is less than min_confidence, returns LanguageFamily.UNKNOWN.
    """
    # Reuse the existing characteristic analyzer
    characteristics = detect_family_characteristics(content)

    best_family = LanguageFamily.UNKNOWN
    best_weighted_score = -1.0
    best_matches = -1
    best_pattern_count = 0

    for family, stats in characteristics.items():
        weighted_score = float(stats.get("weighted_score", 0.0))
        matches = int(stats.get("pattern_matches", 0))
        # Use total non-excluded patterns as another tiebreaker
        from codeweaver.engine.chunker.delimiters.kind import DelimiterKind

        excluded_kinds = {
            DelimiterKind.PARAGRAPH,
            DelimiterKind.WHITESPACE,
            DelimiterKind.GENERIC,
            DelimiterKind.UNKNOWN,
        }
        pattern_count = len([
            p for p in get_family_patterns(family) if p.kind not in excluded_kinds
        ])

        confidence = float(stats.get("confidence", 0.0))

        # Primary criterion: weighted score (favors distinctive patterns)
        # Tiebreaker 1: raw match count (more matches better)
        # Tiebreaker 2: more total patterns (more comprehensive family)
        # Tiebreaker 3: confidence (higher % of patterns matched)
        is_better = False
        # Use small tolerance for floating point comparison
        if weighted_score > best_weighted_score + 0.001:
            is_better = True
        elif abs(weighted_score - best_weighted_score) <= 0.001:
            if (
                matches <= best_matches
                and matches == best_matches
                and pattern_count > best_pattern_count
            ) or matches > best_matches:
                is_better = True
            elif matches == best_matches and pattern_count == best_pattern_count:
                # Only then use confidence as final tiebreaker
                best_confidence = (
                    characteristics[best_family].get("confidence", 0.0)
                    if best_family != LanguageFamily.UNKNOWN
                    else 0.0
                )
                if confidence > best_confidence:
                    is_better = True

        if is_better:
            best_weighted_score = weighted_score
            best_matches = matches
            best_pattern_count = pattern_count
            best_family = family

    return LanguageFamily.UNKNOWN if best_matches < min_confidence else best_family


async def detect_language_family(content: str, min_confidence: int = 3) -> LanguageFamily:
    r"""Detect language family from code sample asynchronously.

    Runs in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:
        # Offload the synchronous detection helper to the thread pool.
        return await loop.run_in_executor(
            executor, _detect_language_family_sync, content, min_confidence
        )


def _get_excluded_kinds() -> set[DelimiterKind]:
    """Get delimiter kinds to exclude from family detection."""
    from codeweaver.engine.chunker.delimiters.kind import DelimiterKind

    return {
        DelimiterKind.PARAGRAPH,
        DelimiterKind.WHITESPACE,
        DelimiterKind.GENERIC,
        DelimiterKind.UNKNOWN,
    }


def _calculate_specificity_weight(pattern_length: int) -> float:
    """Calculate specificity weight based on pattern length.

    Args:
        pattern_length: Length of the pattern string

    Returns:
        Weight between 0.05 and 0.8 based on pattern reliability
    """
    # Single chars are very unreliable
    if pattern_length == 1:
        return 0.05
    # 2-char patterns are good ({{, //, etc.)
    if pattern_length == 2:
        return 0.5
    # 3-char patterns are reliable (def, end, etc.)
    if pattern_length == 3:
        return 0.7
    # 4-char patterns are quite reliable
    return 0.8 if pattern_length == 4 else 0.6


type PatternKey = tuple[DelimiterKind, tuple[str, ...]]


def _build_pattern_family_counts(
    excluded_kinds: set[DelimiterKind],
) -> tuple[dict[PatternKey, NonNegativeInt], dict[LanguageFamily, list[DelimiterPattern]]]:
    """Build pattern distinctiveness counts and family pattern mappings.

    Args:
        excluded_kinds: Set of DelimiterKind to exclude

    Returns:
        Tuple of (pattern_family_counts, family_patterns_map)
    """
    pattern_family_counts: dict[PatternKey, NonNegativeInt] = {}
    family_patterns_map: dict[LanguageFamily, list[DelimiterPattern]] = {}

    for family in LanguageFamily:
        if family == LanguageFamily.UNKNOWN:
            continue
        patterns = get_family_patterns(family)
        family_patterns_map[family] = patterns
        for pattern in patterns:
            if pattern.kind in excluded_kinds:
                continue
            pattern_key = (pattern.kind, tuple(sorted(pattern.starts)))
            pattern_family_counts[pattern_key] = pattern_family_counts.get(pattern_key, 0) + 1

    return pattern_family_counts, family_patterns_map


def _calculate_family_score(
    content: str,
    patterns: list[DelimiterPattern],
    pattern_family_counts: dict[PatternKey, NonNegativeInt],
    excluded_kinds: set[DelimiterKind],
) -> tuple[NonNegativeInt, NonNegativeFloat]:
    """Calculate matches and weighted score for a family's patterns.

    Args:
        content: Code content to analyze
        patterns: List of delimiter patterns for the family
        pattern_family_counts: Mapping of pattern keys to family counts
        excluded_kinds: Set of DelimiterKind to exclude

    Returns:
        Tuple of (match_count, weighted_score)
    """
    matches = 0
    weighted_score = 0.0

    for pattern in patterns:
        if pattern.kind in excluded_kinds:
            continue

        pattern_key = (pattern.kind, tuple(sorted(pattern.starts)))
        for start in pattern.starts:
            if start and start in content:
                matches += 1
                # Weight by distinctiveness: 1/count (rare patterns worth more)
                distinctiveness_weight = 1.0 / pattern_family_counts.get(pattern_key, 1)
                # Weight by specificity based on pattern length
                specificity_weight = _calculate_specificity_weight(len(start))
                weight = distinctiveness_weight * specificity_weight
                weighted_score += weight
                break

    return matches, weighted_score


def detect_family_characteristics(content: str) -> dict[LanguageFamily, dict[str, int | float]]:
    """Analyze family characteristics in code sample.

    Provides detailed scoring breakdown for all families, useful for
    debugging classifier performance or understanding mixed-language files.

    Args:
        content: Code sample to analyze

    Returns:
        Dictionary mapping families to their characteristics:
        - pattern_matches: Number of delimiter patterns found
        - confidence: Normalized confidence score (0.0-1.0)
        - weighted_score: Score weighted by pattern distinctiveness

    Example:
        >>> chars = detect_family_characteristics("function foo() { }")
        >>> chars[LanguageFamily.C_STYLE]["pattern_matches"]
        4
    """
    excluded_kinds = _get_excluded_kinds()
    pattern_family_counts, family_patterns_map = _build_pattern_family_counts(excluded_kinds)

    results: dict[LanguageFamily, dict[str, int | float]] = {}

    for family in LanguageFamily:
        if family == LanguageFamily.UNKNOWN:
            continue

        patterns = family_patterns_map[family]
        matches, weighted_score = _calculate_family_score(
            content, patterns, pattern_family_counts, excluded_kinds
        )

        # Calculate confidence as percentage of patterns matched
        total_patterns = len(patterns)
        confidence = matches / total_patterns if total_patterns > 0 else 0.0

        results[family] = {
            "pattern_matches": matches,
            "confidence": confidence,
            "weighted_score": weighted_score,
        }

    return results


__all__ = (
    "LanguageFamily",
    "defined_languages",
    "detect_family_characteristics",
    "detect_language_family",
    "get_family_patterns",
)
