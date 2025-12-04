# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Privacy utilities for telemetry."""

from __future__ import annotations

import re

from typing import NamedTuple


class IntifyingPatterns(NamedTuple):
    """Patterns for identifying identifiable information."""

    email: re.Pattern
    ip_address: re.Pattern
    ipv6_address: re.Pattern
    mac_address: re.Pattern
    root_file_path: re.Pattern
    username: re.Pattern
    api_key: re.Pattern
    company_name: re.Pattern
    name: re.Pattern


PATTERNS = IntifyingPatterns(
    # Email addresses - more comprehensive pattern
    email=re.compile(
        r"\b[A-Za-z0-9]([A-Za-z0-9._%-]*[A-Za-z0-9])?@[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}\b"
    ),
    # IPv4 addresses - validates proper ranges
    ip_address=re.compile(
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    ),
    # IPv6 addresses
    ipv6_address=re.compile(
        r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|"
        r"\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b|"
        r"\b(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}\b|"
        r"\b::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}\b"
    ),
    # MAC addresses
    mac_address=re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"),
    # File paths - Windows and Unix home directories, includes more variations
    root_file_path=re.compile(
        r"(?:/home/[A-Za-z0-9._-]+(?:/[^\s]*)?)|"
        r"(?:/Users/[A-Za-z0-9._-]+(?:/[^\s]*)?)|"
        r"(?:[A-Za-z]:\\Users\\[A-Za-z0-9._-]+(?:\\[^\s]*)?)|"
        r"(?:~[A-Za-z0-9._-]*(?:/[^\s]*)?)"
    ),
    # Usernames in paths or @mentions
    username=re.compile(
        r"(?:@[A-Za-z0-9._-]{3,})|" r"(?:(?:user|username|usr)[:=]\s*[A-Za-z0-9._-]{3,})"
    ),
    # API keys and tokens (common patterns)
    api_key=re.compile(
        r"(?:api[_-]?key|token|secret|password|passwd|pwd)[:=]\s*['\"]?([A-Za-z0-9+/=_-]{20,})['\"]?",
        re.IGNORECASE,
    ),
    # Company names - expanded list
    company_name=re.compile(
        r"\b[A-Z][A-Za-z0-9&\s]+\s+(?:Inc\.?|LLC|LLP|Corp\.?|Corporation|PBC|Ltd\.?|Limited|"
        r"GmbH|S\.A\.?|AG|N\.V\.?|Partners?|Group|Holdings?|Company|Co\.?|"
        r"Technologies|Tech|Systems|Solutions|Services)\b"
    ),
    # Personal names - matches exactly 2-3 capitalized words (e.g., "John Doe" or "Mary Jane Smith")
    # Each word must start with capital letter followed by lowercase letters
    name=re.compile(r"\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b"),
)


def find_identifiable_info(data: str) -> list[str]:
    """Find identifiable information in the given data string.

    Args:
        data (str): The data string to analyze.

    Returns:
        list[str]: A list of identifiable information found in the data.
    """
    found_info = []

    # Search for each pattern type
    for pattern in PATTERNS:
        if matches := pattern.findall(data):
            found_info.extend(matches)

    return found_info


def redact_identifiable_info(data: str) -> str:
    """Redact identifiable information from the given data string.

    Replaces identified patterns with generic placeholders while maintaining
    string structure. This is a best-effort approach for privacy protection.

    Args:
        data (str): The data string to redact.

    Returns:
        str: The data string with identifiable information redacted.
    """
    # Order matters: redact most specific patterns first to avoid partial matches

    # Redact API keys and tokens
    data = PATTERNS.api_key.sub(r"\1[API_KEY]", data)

    # Redact email addresses
    data = PATTERNS.email.sub("[EMAIL]", data)

    # Redact MAC addresses
    data = PATTERNS.mac_address.sub("[MAC_ADDRESS]", data)

    # Redact IPv6 addresses (before IPv4 to avoid partial matches)
    data = PATTERNS.ipv6_address.sub("[IPV6_ADDRESS]", data)

    # Redact IPv4 addresses
    data = PATTERNS.ip_address.sub("[IP_ADDRESS]", data)

    # Redact file paths (home directories)
    data = PATTERNS.root_file_path.sub("[USER_PATH]", data)

    # Redact usernames
    data = PATTERNS.username.sub("[USERNAME]", data)

    # Redact company names
    data = PATTERNS.company_name.sub("[COMPANY]", data)

    # Redact personal names (do this last as it's the most general pattern)
    return PATTERNS.name.sub("[NAME]", data)


__all__ = ("find_identifiable_info", "redact_identifiable_info")
