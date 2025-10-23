"""Text normalization and safety utilities."""

import logging
import re
import unicodedata

from functools import cache
from typing import Literal


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

    text = unicodedata.normalize(normalize_form, text)
    filtered = INVISIBLE_PATTERN.sub("", text)

    matches = list(INJECT_PATTERN.finditer(filtered))
    for match in reversed(matches):
        start, end = match.span()
        logger.warning("Possible prompt injection detected and neutralized: %s", match.group(0))
        replacement = "[[ POSSIBLE PROMPT INJECTION REMOVED ]]"
        filtered = filtered[:start] + replacement + filtered[end:]

    return filtered.strip()


@cache
def normalize_ext(ext: str) -> str:
    """Normalize a file extension to a standard format. Cached because of hot/repetitive use."""
    return ext.lower().strip() if ext.startswith(".") else f".{ext.lower().strip()}"


__all__ = ("normalize_ext", "sanitize_unicode")
