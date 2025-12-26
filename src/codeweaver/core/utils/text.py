# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Text manipulation utilities."""

from __future__ import annotations

import logging
import re
import textwrap
import unicodedata

from typing import Literal, cast

import textcase

from pydantic import NonNegativeFloat, NonNegativeInt

from codeweaver.exceptions import ConfigurationError


logger = logging.getLogger(__name__)


REMOVE_ID = re.compile(r"(?P<trailing_id>(?!^)_id$)|(?P<lone_id>\b_id$|(?<=\b)_id(?=\b))")
"""Matches trailing and lone _id patterns. Only matches _id at the end of a string or surrounded by word boundaries."""

BOUNDARY = re.compile(r"(\W+)")

LOWLY_WORDS = {  # Don't confuse with lowly worms 🪱🎩
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "nor",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "without",
    "vs",
}


def to_lowly_lowercase(word: str) -> str:
    """Ensure insignificant words are lowercase."""
    return word.lower() if word in LOWLY_WORDS else word


def humanize(word: str) -> str:
    """
    Capitalize the first word and turn underscores into spaces and strip a
    trailing ``"_id"``, if any. Creates a nicer looking string.

    Examples:
        >>> humanize("employee_salary")
        'Employee salary'
        >>> humanize("author_id")
        'Author'

    """
    word = REMOVE_ID.sub(lambda m: "ID" if m.group("lone_id") else "", word)
    return to_lowly_lowercase(textcase.sentence(word))


# ===========================================================================
# *                 Formatting Functions for Elements
# ===========================================================================


def format_docstring(docstring: str) -> str:
    """Format a docstring for display."""
    lines = docstring.strip().splitlines()
    return textwrap.dedent("\n".join([to_lowly_lowercase(textcase.title(lines[0])), *lines[1:]]))


def format_snippet_name(name: str) -> str:
    """Format a snippet name for display."""
    return to_lowly_lowercase(textcase.title(humanize(textcase.snake(name.strip()))))


def format_signature(signature: str) -> str:
    """Format a function signature for display."""
    return textcase.title(humanize(textcase.snake(signature.strip())))


def format_descriptor(
    module: str, file_name: str, code_kind: str, snippet_name: str | None = None
) -> str:
    """Format a code descriptor for display."""
    return f"module {module} | file {file_name} | {code_kind} {format_snippet_name(snippet_name) if snippet_name else ''}".strip()


def to_tokens(text: str) -> str:
    """Convert a text string into a list of tokens."""
    tokens = BOUNDARY.split(text)
    tokens = (x for x in tokens if x)
    return " ".join(tokens)


def truncate_text(text: str, max_length: int = 100, ellipsis: str = "...") -> str:
    """
    Truncate text to a maximum length, adding an ellipsis if truncated.

    Args:
        text: The input text to truncate.
        max_length: The maximum allowed length of the text (default: 100).
        ellipsis: The string to append if truncation occurs (default: "...").

    Returns:
        The truncated text if it exceeds max_length, otherwise the original text.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(ellipsis)] + ellipsis


def elapsed_time_to_human_readable(elapsed_seconds: NonNegativeFloat | NonNegativeInt) -> str:
    """Convert elapsed time between start_time and end_time to a human-readable format."""
    minutes, sec = divmod(int(elapsed_seconds), 60)
    hours, min_ = divmod(minutes, 60)
    days, hr = divmod(hours, 24)
    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}d")
    if hr > 0:
        parts.append(f"{hr}h")
    if min_ > 0:
        parts.append(f"{min_}m")
    parts.append(f"{sec}s")
    return " ".join(parts)


# * Constants for unicode sanitization and prompt injection detection

NORMALIZE_FORM = "NFKC"
CONTROL_CHARS = [chr(i) for i in range(0x20) if i not in (9, 10, 13)]
INVISIBLE_CHARS = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", *CONTROL_CHARS)
INVISIBLE_PATTERN = re.compile("|".join(re.escape(c) for c in INVISIBLE_CHARS))
POSSIBLE_PROMPT_INJECTS = (
    r"[<(\|=:]\s*system\s*[>)\|=:]",
    r"[<(\|=:]\s*instruction\s*[>)\|=:]",
    r"\b(?:ignore|disregard|forget|cancel|override|void)\b(?:\s+(?:previous|above|all|prior|earlier|former|before|other|last|everything|this)){0,2}\s*(?:instruct(?:ions?)?|direction(?:s?)?|directive(?:s?)?|command(?:s?)?|request(?:s?)?|order(?:s?)?|message(?:s?)?|prompt(?:s?)?)\b",
)
"""Very basic patterns to catch common prompt injection attempts. Not remotely exhaustive, but useful as a first line of defense.

Also likes to catch itself when codeweaver scans this file.
"""
INJECT_PATTERN = re.compile("|".join(POSSIBLE_PROMPT_INJECTS), re.IGNORECASE)


def sanitize_unicode(
    text: str | bytes | bytearray,
    normalize_form: Literal["NFC", "NFKC", "NFD", "NFKD"] = NORMALIZE_FORM,
) -> str:
    """Sanitize unicode text by normalizing and removing invisible/control characters."""
    if isinstance(text, bytes | bytearray):
        text = text.decode("utf-8", errors="ignore")
    if not text.strip():
        return ""

    text = unicodedata.normalize(normalize_form, cast(str, text))
    filtered = INVISIBLE_PATTERN.sub("", text)

    matches = list(INJECT_PATTERN.finditer(filtered))
    for match in reversed(matches):
        start, end = match.span()
        logger.warning("Possible prompt injection detected and neutralized: %s", match.group(0))
        replacement = "[[ POSSIBLE PROMPT INJECTION REMOVED ]]"
        filtered = filtered[:start] + replacement + filtered[end:]

    return filtered.strip()


# * Regex pattern validation and resolution utilities

# Basic regex safety heuristics for user-supplied patterns
MAX_REGEX_PATTERN_LENGTH = 8192

# Very simple heuristic to flag obviously dangerous nested quantifiers that are common in ReDoS patterns,
# e.g., (.+)+, (\w+)*, (a|aa)+, etc. This is not exhaustive but catches many foot-guns.
_NESTED_QUANTIFIER_RE = re.compile(
    r"(?:\([^)]*\)|\[[^\]]*\]|\\.|.)(?:\+|\*|\{[^}]*\})\s*(?:\+|\*|\{[^}]*\})"
)


def _walk_pattern(s: str) -> str:
    r"""Normalize a user-supplied regex pattern string. Helper for `validate_regex_pattern`.

    - Preserves whitespace exactly (no strip).
    - Doubles unknown escapes so they are treated literally (e.g. "\y" -> "\\y")
      instead of raising "bad escape" at compile time.
    - Protects against a lone trailing backslash by doubling it.
    This aims to accept inputs written as if they were r-strings while remaining robust to
    config/env string parsing that may have processed standard escapes like "\n".  Should we just throw an error and let the user figure it out? Possibly, but one thing I really hate is trying to decode how to write a regex that gets parsed through multiple layers of string processing. Let's call it paying it forward for user convenience.
    """
    if not isinstance(s, str):  # just being defensive
        raise TypeError("Pattern must be a string.")

    out: list[str] = []
    i = 0
    n = len(s)

    # First character after a backslash that we consider valid in Python's `re` syntax or as an escaped metachar.
    legal_next = set("AbBdDsSwWZzGAfnrtvxuUN0123456789") | set(".*+?^$|()[]{}\\")

    while i < n:
        ch = s[i]
        if ch == "\\":
            # If pattern ends with a single backslash, double it so compile won't fail.
            if i == n - 1:
                out.append("\\\\")
                i += 1
                continue
            nxt = s[i + 1]
            if nxt in legal_next:
                # Keep known/valid escapes and escaped metacharacters as-is.
                out.append("\\")
            else:
                # Unknown escape — make it literal by doubling the backslash.
                out.append("\\\\")
            out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1

    return "".join(out)


def validate_regex_pattern(value: re.Pattern[str] | str | None) -> re.Pattern[str] | None:
    """Validate and compile a regex pattern from config/env.

    - Accepts compiled patterns as-is.
    - For strings, applies normalization via `_walk_pattern`, basic length and nested-quantifier checks,
      then compiles. Raises `ConfigurationError` on invalid/unsafe patterns.
    """
    if value is None:
        return None
    if isinstance(value, re.Pattern):
        return value

    if len(value) > MAX_REGEX_PATTERN_LENGTH:
        raise ConfigurationError(
            f"Regex pattern is too long (max {MAX_REGEX_PATTERN_LENGTH} characters)."
        )

    normalized = _walk_pattern(value)

    # Heuristic check for patterns likely to cause catastrophic backtracking
    if _NESTED_QUANTIFIER_RE.search(normalized):
        raise ConfigurationError(
            "Pattern contains nested quantifiers (e.g., (.+)+), which can cause excessive backtracking. Please simplify the pattern."
        )

    # Optional sanity check on number of groups (very large numbers are often accidental or risky)
    try:
        open_groups = sum(
            c == "(" and (i == 0 or normalized[i - 1] != "\\") for i, c in enumerate(normalized)
        )
    except Exception:
        logging.getLogger(__name__).debug(
            "Failed to count groups in regex safety check", exc_info=True
        )
    else:
        if open_groups > 100:
            raise ConfigurationError("Pattern uses too many capturing/non-capturing groups (>100).")

    try:
        return re.compile(normalized)
    except re.error as e:
        raise ConfigurationError(f"Invalid regex pattern: {e.args[0]}") from e


__all__ = (
    "elapsed_time_to_human_readable",
    "format_descriptor",
    "format_docstring",
    "format_signature",
    "format_snippet_name",
    "humanize",
    "sanitize_unicode",
    "to_lowly_lowercase",
    "to_tokens",
    "truncate_text",
    "validate_regex_pattern",
)
