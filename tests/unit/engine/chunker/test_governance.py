"""
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Claude Code

SPDX-License-Identifier: MIT OR Apache-2.0
"""

"""Tests for ResourceGovernor resource limits enforcement."""

import time
from typing import Protocol

import pytest

from codeweaver.engine.chunker.exceptions import ChunkLimitExceededError, ChunkingTimeoutError
from codeweaver.engine.chunker.governance import ResourceGovernor


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

    with pytest.raises(ChunkingTimeoutError, match="exceeded timeout"):
        with ResourceGovernor(settings) as governor:
            time.sleep(1.1)
            governor.check_timeout()


def test_chunk_limit_enforcement():
    """Test that ChunkLimitExceededError is raised at chunk limit."""
    settings = MockPerformanceSettings(max_chunks_per_file=10)

    with pytest.raises(ChunkLimitExceededError, match="Exceeded maximum"):
        with ResourceGovernor(settings) as governor:
            for _ in range(11):
                governor.register_chunk()


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

    try:
        with governor:
            governor.register_chunk()
            assert governor._chunk_count == 1
            raise ValueError("Test error")
    except ValueError:
        pass

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
