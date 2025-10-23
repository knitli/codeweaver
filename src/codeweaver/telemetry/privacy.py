# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Privacy filtering for telemetry events.

Ensures no PII or sensitive information is sent in telemetry events.
Implements strict filtering based on CodeWeaver's privacy principles.

Privacy Guarantees:
- No query content or search terms
- No code snippets or file contents
- No file paths or repository names
- No user identifiers (usernames, emails, IPs)
- No individual query timing (could fingerprint)
- Only aggregated, anonymized statistics
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PrivacyFilter:
    """
    Filters telemetry events to ensure privacy compliance.

    Validates that events contain only aggregated, anonymized data
    and no personally identifiable or proprietary information.
    """

    # Keys that should NEVER appear in telemetry events
    DISALLOWED_KEYS = frozenset({
        # Query/content related
        "query",
        "search",
        "term",
        "terms",
        "content",
        "code",
        "snippet",
        "text",
        # Path/file related
        "path",
        "file",
        "filename",
        "filepath",
        "dir",
        "directory",
        "folder",
        # Repository related
        "repository",
        "repo",
        "project",
        # User identification
        "user",
        "username",
        "email",
        "name",
        "id",
        "identifier",
        "ip",
        "host",
        "hostname",
        # Individual timing (could fingerprint)
        "query_time",
        "individual_time",
        "request_time",
    })

    # Keys that are allowed (for validation)
    ALLOWED_KEYS = frozenset({
        # Event metadata
        "event",
        "timestamp",
        "properties",
        # Session-level aggregates
        "session_duration_minutes",
        "total_searches",
        "successful_searches",
        "failed_searches",
        "success_rate",
        # Timing aggregates only
        "timing",
        "avg_response_ms",
        "median_response_ms",
        "p95_response_ms",
        "min_response_ms",
        "max_response_ms",
        # Token statistics
        "tokens",
        "total_generated",
        "total_delivered",
        "total_saved",
        "context_reduction_pct",
        "estimated_cost_savings_usd",
        # Anonymized distributions
        "languages",
        "semantic_frequencies",
        "category_usage",
        "usage_frequencies",
        # Comparison data
        "comparison_type",
        "improvement",
        "baseline",
        "codeweaver",
        "improvement_percentage",
        "estimated_files",
        "estimated_lines",
        "estimated_tokens",
        "estimated_cost_usd",
        "files_returned",
        "lines_returned",
        "tokens_delivered",
        "actual_cost_usd",
        "files_reduction_pct",
        "lines_reduction_pct",
        "tokens_reduction_pct",
        "cost_savings_pct",
        "approach",
        # Semantic analysis
        "period",
        "total_chunks_analyzed",
        "alignment_with_scores",
        "correlation",
        "note",
    })

    def __init__(self, *, strict_mode: bool = True):
        """
        Initialize privacy filter.

        Args:
            strict_mode: If True, reject any unknown keys as potentially sensitive
        """
        self.strict_mode = strict_mode

    def validate_event(self, event: dict[str, Any]) -> bool:
        """
        Validate that an event passes privacy requirements.

        Args:
            event: Event dictionary to validate

        Returns:
            True if event is safe to send, False otherwise
        """
        try:
            # Check for disallowed keys
            if self._contains_disallowed_keys(event):
                logger.warning("Event contains disallowed keys, rejecting for privacy")
                return False

            # In strict mode, check all keys are known
            if self.strict_mode and not self._all_keys_allowed(event):
                logger.warning("Event contains unknown keys in strict mode, rejecting")
                return False

            # Check for string values that might contain sensitive data
            if self._contains_suspicious_strings(event):
                logger.warning("Event contains suspicious string values, rejecting")
                return False

            return True

        except Exception as e:
            logger.exception("Error validating event privacy: %s", e)
            # Fail closed - reject on error
            return False

    def filter_event(self, properties: dict[str, Any]) -> dict[str, Any]:
        """
        Filter event properties to remove any sensitive data.

        Args:
            properties: Event properties dictionary

        Returns:
            Filtered properties dictionary
        """
        filtered = {}

        for key, value in properties.items():
            # Skip disallowed keys
            if key.lower() in self.DISALLOWED_KEYS:
                logger.debug("Filtering disallowed key: %s", key)
                continue

            # Recursively filter nested dictionaries
            if isinstance(value, dict):
                filtered[key] = self.filter_event(value)
            # Filter lists of dictionaries
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                filtered[key] = [self.filter_event(item) for item in value]
            # Keep safe primitive values
            elif isinstance(value, (int, float, bool, type(None))):
                filtered[key] = value
            # Filter strings more carefully
            elif isinstance(value, str):
                # Very short strings are likely safe (like language names)
                # Longer strings need more validation
                if len(value) < 50 and not self._looks_like_path_or_code(value):
                    filtered[key] = value
                else:
                    logger.debug("Filtering potentially sensitive string value for key: %s", key)
            else:
                logger.debug("Filtering unknown value type for key: %s", key)

        return filtered

    def _contains_disallowed_keys(self, data: Any, path: str = "") -> bool:
        """Check if data contains any disallowed keys."""
        if isinstance(data, dict):
            for key, value in data.items():
                # Check key itself
                if key.lower() in self.DISALLOWED_KEYS:
                    logger.debug("Found disallowed key: %s at path: %s", key, path)
                    return True
                # Recursively check nested structures
                new_path = f"{path}.{key}" if path else key
                if self._contains_disallowed_keys(value, new_path):
                    return True
        elif isinstance(data, (list, tuple)):
            for i, item in enumerate(data):
                if self._contains_disallowed_keys(item, f"{path}[{i}]"):
                    return True

        return False

    def _all_keys_allowed(self, data: Any, path: str = "") -> bool:
        """Check if all keys in data are in allowed list (strict mode)."""
        if isinstance(data, dict):
            for key, value in data.items():
                # Special case: allow any keys in language/semantic frequency dicts
                # since these are just counts by category
                if path.endswith(("languages", "semantic_frequencies", "category_usage")):
                    return True

                # Check if key is allowed
                if key not in self.ALLOWED_KEYS:
                    logger.debug("Unknown key in strict mode: %s at path: %s", key, path)
                    return False

                # Recursively check nested structures
                new_path = f"{path}.{key}" if path else key
                if not self._all_keys_allowed(value, new_path):
                    return False

        elif isinstance(data, (list, tuple)):
            for i, item in enumerate(data):
                if not self._all_keys_allowed(item, f"{path}[{i}]"):
                    return False

        return True

    def _contains_suspicious_strings(self, data: Any) -> bool:
        """Check if data contains strings that look like paths, code, or queries."""
        if isinstance(data, str):
            return self._looks_like_path_or_code(data)
        elif isinstance(data, dict):
            return any(self._contains_suspicious_strings(v) for v in data.values())
        elif isinstance(data, (list, tuple)):
            return any(self._contains_suspicious_strings(item) for item in data)
        return False

    @staticmethod
    def _looks_like_path_or_code(value: str) -> bool:
        """
        Check if a string looks like a file path or code snippet.

        Args:
            value: String to check

        Returns:
            True if string looks suspicious, False if safe
        """
        # Paths typically have slashes or backslashes
        if "/" in value or "\\" in value:
            return True

        # Paths often have file extensions
        if "." in value and len(value.split(".")[-1]) < 5:
            # Might be a file extension
            return True

        # Code often has special characters
        suspicious_chars = {"{", "}", "[", "]", "(", ")", ";", "=", ":"}
        if any(char in value for char in suspicious_chars):
            return True

        # Very long strings are suspicious
        if len(value) > 100:
            return True

        return False


__all__ = ("PrivacyFilter",)
