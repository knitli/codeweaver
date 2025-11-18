# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for resource estimation utilities."""

import sys

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codeweaver.engine.resource_estimation import (
    MemoryEstimate,
    estimate_backup_memory_requirements,
    estimate_file_count,
)


class MockIndexingStats:
    """Mock indexing stats for testing."""

    def __init__(self, chunks_created: int = 0, files_discovered: int = 0):
        self.chunks_created = chunks_created
        self.files_discovered = files_discovered


class TestEstimateFileCount:
    """Tests for estimate_file_count function."""

    def test_estimates_file_count_in_directory(self, tmp_path: Path):
        """Test file count estimation on a real directory."""
        # Create some test files
        (tmp_path / "file1.py").touch()
        (tmp_path / "file2.py").touch()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file3.py").touch()

        count = estimate_file_count(tmp_path)
        assert count >= 3  # At least the 3 files we created

    def test_handles_empty_directory(self, tmp_path: Path):
        """Test estimation on empty directory."""
        count = estimate_file_count(tmp_path)
        assert count >= 0

    def test_handles_missing_directory(self):
        """Test estimation on non-existent directory."""
        count = estimate_file_count(Path("/nonexistent/directory"))
        assert count == 1000  # Default fallback


class TestEstimateBackupMemoryRequirements:
    """Tests for estimate_backup_memory_requirements function."""

    @pytest.mark.skipif("psutil" not in sys.modules, reason="psutil not available")
    def test_estimates_from_stats_with_chunks(self):
        """Test memory estimation using stats with chunks created."""
        stats = MockIndexingStats(chunks_created=10000)

        estimate = estimate_backup_memory_requirements(stats=stats)  # ty:ignore[invalid-argument-type]

        assert isinstance(estimate, MemoryEstimate)
        assert estimate.estimated_chunks == 10000
        assert estimate.estimated_bytes == 10000 * 5000  # 5KB per chunk
        assert estimate.zone == "green"  # <100K chunks

    @pytest.mark.skipif("psutil" not in sys.modules, reason="psutil not available")
    def test_estimates_from_stats_with_files(self):
        """Test memory estimation using stats with files discovered."""
        stats = MockIndexingStats(files_discovered=1000)

        estimate = estimate_backup_memory_requirements(stats=stats)  # ty:ignore[invalid-argument-type]

        assert estimate.estimated_chunks == 10000  # 1000 files * 10 chunks/file
        assert estimate.zone == "green"

    @pytest.mark.skipif("psutil" not in sys.modules, reason="psutil not available")
    @pytest.mark.parametrize("filenames", [[f"file{i}.py" for i in range(10)]])
    def test_estimates_from_project_path(self, tmp_path: Path, filenames):
        """Test memory estimation using project path."""
        # Create some files
        # sourcery skip: no-loop-in-tests
        for filename in filenames:
            (tmp_path / filename).touch()

        estimate = estimate_backup_memory_requirements(project_path=tmp_path)

        assert estimate.estimated_chunks > 0
        assert estimate.estimated_bytes > 0

    @pytest.mark.skipif("psutil" not in sys.modules, reason="psutil not available")
    def test_yellow_zone_for_large_projects(self):
        """Test yellow zone classification for medium-sized projects."""
        stats = MockIndexingStats(chunks_created=250000)  # 250K chunks

        estimate = estimate_backup_memory_requirements(stats=stats)  # ty:ignore[invalid-argument-type]

        assert estimate.zone == "yellow"
        assert 100_000 < estimate.estimated_chunks < 500_000

    @pytest.mark.skipif("psutil" not in sys.modules, reason="psutil not available")
    def test_red_zone_for_very_large_projects(self):
        """Test red zone classification for very large projects."""
        stats = MockIndexingStats(chunks_created=600000)  # 600K chunks

        estimate = estimate_backup_memory_requirements(stats=stats)  # ty:ignore[invalid-argument-type]

        assert estimate.zone == "red"
        assert estimate.estimated_chunks >= 500_000

    @pytest.mark.skipif("psutil" not in sys.modules, reason="psutil not available")
    def test_safety_check_with_sufficient_memory(self):
        """Test is_safe is True when sufficient memory available."""
        stats = MockIndexingStats(chunks_created=10000)  # Small project

        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = MagicMock(available=10_000_000_000)  # 10GB available

            estimate = estimate_backup_memory_requirements(stats=stats)  # ty:ignore[invalid-argument-type]

            assert estimate.is_safe is True
            assert estimate.available_bytes == 10_000_000_000

    @pytest.mark.skipif("psutil" not in sys.modules, reason="psutil not available")
    def test_safety_check_with_insufficient_memory(self):
        """Test is_safe is False when insufficient memory available."""
        stats = MockIndexingStats(chunks_created=200000)  # Large project

        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = MagicMock(available=500_000_000)  # Only 500MB available

            estimate = estimate_backup_memory_requirements(stats=stats)  # ty:ignore[invalid-argument-type]

            assert estimate.is_safe is False

    def test_fallback_when_psutil_not_available(self):
        """Test graceful fallback when psutil is not installed."""
        stats = MockIndexingStats(chunks_created=10000)

        with patch.dict("sys.modules", {"psutil": None}):
            estimate = estimate_backup_memory_requirements(stats=stats)  # ty:ignore[invalid-argument-type]

            # Should return safe default
            assert estimate.is_safe is True
            assert estimate.estimated_chunks == 100_000  # Default fallback


class TestMemoryEstimate:
    """Tests for MemoryEstimate namedtuple."""

    def test_gb_properties(self):
        """Test GB conversion properties."""
        estimate = MemoryEstimate(
            estimated_bytes=1_000_000_000,  # 1GB
            available_bytes=4_000_000_000,  # 4GB
            required_bytes=2_500_000_000,  # 2.5GB
            is_safe=True,
            estimated_chunks=100000,
            zone="green",
        )

        assert estimate.estimated_gb == pytest.approx(1.0, rel=0.01)
        assert estimate.available_gb == pytest.approx(4.0, rel=0.01)
        assert estimate.required_gb == pytest.approx(2.5, rel=0.01)
