"""
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Claude Code

SPDX-License-Identifier: MIT OR Apache-2.0
"""

import contextlib


"""Tests for ResourceGovernor resource limits enforcement."""

from typing import Protocol
from unittest.mock import patch

import pytest

from codeweaver.engine.chunker.exceptions import ChunkingTimeoutError, ChunkLimitExceededError
from codeweaver.engine.chunker.governance import ResourceGovernor


pytestmark = [pytest.mark.unit]


class PerformanceSettings(Protocol):
    """Minimal protocol for testing."""

    chunk_timeout_seconds: int
    max_chunks_per_file: int


class MockPerformanceSettings:
    """Mock settings for testing."""

    def __init__(self, chunk_timeout_seconds: int = 30, max_chunks_per_file: int = 5000):
        self.chunk_timeout_seconds = chunk_timeout_seconds
        self.max_chunks_per_file = max_chunks_per_file


def test_timeout_enforcement():
    """Test that ChunkingTimeoutError is raised when timeout is exceeded."""
    settings = MockPerformanceSettings(chunk_timeout_seconds=1)

    with patch("codeweaver.engine.chunker.governance.time") as mock_time:
        # Set up time progression: 0.0 at __enter__, 1.5 at check_timeout()
        mock_time.time.side_effect = [0.0, 1.5]

        with pytest.raises(ChunkingTimeoutError, match="exceeded timeout"):
            with ResourceGovernor(settings) as governor:
                governor.check_timeout()


def test_chunk_limit_enforcement():
    """Test that ChunkLimitExceededError is raised at chunk limit."""
    settings = MockPerformanceSettings(max_chunks_per_file=10)

    with pytest.raises(ChunkLimitExceededError, match="Exceeded maximum"):
        with ResourceGovernor(settings) as governor:
            # Register 11 chunks to exceed the limit of 10
            governor.register_chunk()  # 1
            governor.register_chunk()  # 2
            governor.register_chunk()  # 3
            governor.register_chunk()  # 4
            governor.register_chunk()  # 5
            governor.register_chunk()  # 6
            governor.register_chunk()  # 7
            governor.register_chunk()  # 8
            governor.register_chunk()  # 9
            governor.register_chunk()  # 10
            governor.register_chunk()  # 11 - should raise


def test_governor_context_manager_success():
    """Test context manager initializes and cleans up on success."""
    settings = MockPerformanceSettings()

    governor = ResourceGovernor(settings)
    assert governor._start_time is None
    assert governor._chunk_count == 0

    with governor:
        assert governor._start_time is not None
        assert governor._chunk_count == 0
        governor.register_chunk()
        assert governor._chunk_count == 1

    # Verify cleanup
    assert governor._start_time is None
    assert governor._chunk_count == 0


def test_governor_context_manager_error():
    """Test context manager cleans up even on error."""
    settings = MockPerformanceSettings()
    governor = ResourceGovernor(settings)

    with contextlib.suppress(ValueError):
        with governor:
            governor.register_chunk()
            assert governor._chunk_count == 1
            raise ValueError("Test error")
    # Verify cleanup even after error
    assert governor._start_time is None
    assert governor._chunk_count == 0


def test_register_chunk_increments_and_checks():
    """Test that register_chunk increments counter and performs checks."""
    settings = MockPerformanceSettings(max_chunks_per_file=5)

    with ResourceGovernor(settings) as governor:
        governor.register_chunk()
        assert governor._chunk_count == 1

        governor.register_chunk()
        assert governor._chunk_count == 2

        # Should not raise yet
        governor.register_chunk()
        governor.register_chunk()
        governor.register_chunk()
        assert governor._chunk_count == 5

        # Next one should raise
        with pytest.raises(ChunkLimitExceededError):
            governor.register_chunk()
