# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for response summary generation in response.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from codeweaver.server.agent_api.search.intent import IntentType
from codeweaver.server.agent_api.search.response import generate_summary
from codeweaver.server.agent_api.search.types import CodeMatch


def create_mock_match(file_name: str) -> MagicMock:
    """Helper to create a mock CodeMatch with a nested file.path.name.

    Uses spec=CodeMatch to ensure the mock mirrors the actual interface.
    """
    mock_match = MagicMock(spec=CodeMatch)
    mock_file = MagicMock()
    mock_path = MagicMock()
    mock_path.name = file_name
    mock_file.path = mock_path
    mock_match.file = mock_file
    return mock_match


class TestGenerateSummary:
    """Test suite for generate_summary function."""

    @pytest.mark.unit
    def test_generate_summary_empty_results(self) -> None:
        """Test summary generation when no matches are found."""
        query = "how to do something"
        summary = generate_summary([], IntentType.UNDERSTAND, query)
        assert summary == f"No matches found for query: '{query}'"

    @pytest.mark.unit
    def test_generate_summary_with_results(self) -> None:
        """Test summary generation with search results."""
        mock_match1 = create_mock_match("auth.py")
        mock_match2 = create_mock_match("models.py")

        matches = [mock_match1, mock_match2]
        query = "find auth models"

        summary = generate_summary(matches, IntentType.UNDERSTAND, query)

        assert "Found 2 relevant matches" in summary
        assert "for understand query" in summary
        assert "Top results in: " in summary
        assert "auth.py" in summary
        assert "models.py" in summary

    @pytest.mark.unit
    def test_generate_summary_unique_files_limit(self) -> None:
        """Test that summary only includes up to 3 unique file names from top results."""
        # Create 5 matches with different files
        matches = [create_mock_match(f"file_{i}.py") for i in range(5)]

        summary = generate_summary(matches, IntentType.IMPLEMENT, "test query")

        # Should mention "Found 5 relevant matches"
        assert "Found 5 relevant matches" in summary
        # Should only list first 3 files: file_0.py, file_1.py, file_2.py
        assert "file_0.py" in summary
        assert "file_1.py" in summary
        assert "file_2.py" in summary
        assert "file_3.py" not in summary

    @pytest.mark.unit
    def test_generate_summary_duplicate_files(self) -> None:
        """Test that summary handles duplicate file names gracefully."""
        # 3 matches in the same file
        m1 = create_mock_match("shared.py")
        m2 = create_mock_match("shared.py")
        m3 = create_mock_match("other.py")

        matches = [m1, m2, m3]
        summary = generate_summary(matches, IntentType.DEBUG, "fix bug")

        assert "Found 3 relevant matches" in summary
        # Should only list "shared.py" once and "other.py"
        assert "shared.py" in summary
        assert "other.py" in summary
        # Verify it doesn't look like "shared.py, shared.py, other.py"
        assert summary.count("shared.py") == 1

    @pytest.mark.unit
    def test_generate_summary_truncation(self) -> None:
        """Test that summary is truncated to 1000 characters."""
        # Create a match with an extremely long file name to trigger truncation
        long_name = "a" * 2000
        m = create_mock_match(long_name)

        summary = generate_summary([m], IntentType.OPTIMIZE, "fast")

        # Assert exact maximum length
        assert len(summary) == 1000

        # Verify it starts with the expected prefix
        expected_prefix = "Found 1 relevant matches for optimize query. Top results in: "
        assert summary.startswith(expected_prefix)

        # Verify it ends with the truncated content of the long name
        remaining_length = 1000 - len(expected_prefix)
        expected_suffix = long_name[:remaining_length]
        assert summary.endswith(expected_suffix)
