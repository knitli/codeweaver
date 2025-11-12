# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Text normalization and safety utilities."""

from __future__ import annotations

import logging
import re
import unicodedata

from functools import cache
from typing import Literal, cast

from codeweaver.core.types.aliases import FileExt, FileExtensionT, LiteralStringT
from codeweaver.exceptions import ConfigurationError


# ===========================================================================
# *               Text Normalization/Safety Utilities
# ===========================================================================
# by default, we do basic NFKC normalization and strip known invisible/control chars
# this is to avoid issues with fullwidth chars, zero-width spaces, etc.
# We plan to add more advanced sanitization options in the future, which users can opt into.
# TODO: Add Rebuff.ai integration, and/or other advanced sanitization options. Probably as middleware.

NORMALIZE_FORM = "NFKC"

CONTROL_CHARS = [chr(i) for i in range(0x20) if i not in (9, 10, 13)]
INVISIBLE_CHARS = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", *CONTROL_CHARS)

INVISIBLE_PATTERN = re.compile("|".join(re.escape(c) for c in INVISIBLE_CHARS))

POSSIBLE_PROMPT_INJECTS = (
    r"[<\(\|=:]\s*system\s*[>\)\|=:]",
    r"[<\(\|=:]\s*instruction\s*[>\)\|=:]",
    r"\b(?:ignore|disregard|forget|cancel|override|void)\b(?:\s+(?:previous|above|all|prior|earlier|former|before|other|last|everything|this)){0,2}\s*(?:instruct(?:ions?)?|direction(?:s?)?|directive(?:s?)?|command(?:s?)?|request(?:s?)?|order(?:s?)?|message(?:s?)?|prompt(?:s?)?)\b",
)

INJECT_PATTERN = re.compile("|".join(POSSIBLE_PROMPT_INJECTS), re.IGNORECASE)

logger = logging.getLogger(__name__)

# Basic regex safety heuristics for user-supplied patterns
MAX_REGEX_PATTERN_LENGTH = 8192
# Very simple heuristic to flag obviously dangerous nested quantifiers that are common in ReDoS patterns,
# e.g., (.+)+, (\w+)*, (a|aa)+, etc. This is not exhaustive but catches many foot-guns.
_NESTED_QUANTIFIER_RE = re.compile(
    r"(?:\([^)]*\)|\[[^\]]*\]|\\.|.)(?:\+|\*|\{[^}]*\})\s*(?:\+|\*|\{[^}]*\})"
)


def sanitize_unicode(
    text: str | bytes | bytearray,
    normalize_form: Literal["NFC", "NFKC", "NFD", "NFKD"] = NORMALIZE_FORM,
) -> str:
    """Sanitize unicode text by normalizing and removing invisible/control characters.

    TODO: Need to add a mechanism to override or customize the injection patterns.
    """
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


@cache
def normalize_ext(ext: FileExtensionT | str) -> FileExtensionT:
    """Normalize a file extension to a standard format. Cached because of hot/repetitive use."""
    ext = str(ext)
    return (
        FileExt(cast(LiteralStringT, ext.lower().strip()))
        if ext.startswith(".")
        else FileExt(cast(LiteralStringT, f".{ext.lower().strip()}"))
    )


def _walk_pattern(s: str) -> str:
    r"""Normalize a user-supplied regex pattern string. Helper for `validate_regex_pattern`.

    - Preserves whitespace exactly (no strip).
    - Doubles unknown escapes so they are treated literally (e.g. "\y" -> "\\y")
      instead of raising "bad escape" at compile time.
    - Protects against a lone trailing backslash by doubling it.
    This aims to accept inputs written as if they were r-strings while remaining robust to
    config/env string parsing that may have processed standard escapes like "\n".
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
    - For strings, applies normalization via `walk_pattern`, basic length and nested-quantifier checks,
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


__all__ = ("normalize_ext", "sanitize_unicode", "validate_regex_pattern")
