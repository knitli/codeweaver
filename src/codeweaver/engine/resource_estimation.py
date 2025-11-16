"""Resource estimation utilities for backup vector store activation.

This module provides utilities to estimate memory requirements and system
resources needed for activating the in-memory backup vector store.
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple


if TYPE_CHECKING:
    from codeweaver.engine.indexer.indexer import IndexingStats

logger = logging.getLogger(__name__)


class MemoryEstimate(NamedTuple):
    """Memory estimation result for backup activation."""

    estimated_bytes: int
    """Estimated memory required in bytes"""

    available_bytes: int
    """Available system memory in bytes"""

    required_bytes: int
    """Required memory with safety buffer in bytes"""

    is_safe: bool
    """Whether it's safe to activate backup"""

    estimated_chunks: int
    """Estimated number of chunks"""

    zone: str
    """Memory zone: 'green', 'yellow', or 'red'"""

    @property
    def estimated_gb(self) -> float:
        """Estimated memory in GB."""
        return self.estimated_bytes / 1e9

    @property
    def available_gb(self) -> float:
        """Available memory in GB."""
        return self.available_bytes / 1e9

    @property
    def required_gb(self) -> float:
        """Required memory in GB."""
        return self.required_bytes / 1e9


def estimate_file_count(project_path: Path, max_depth: int = 5) -> int:
    """Quickly estimate the number of indexable files in a project.

    Args:
        project_path: Root path of the project
        max_depth: Maximum directory depth to scan

    Returns:
        Estimated file count
    """
    try:
        # Check if path exists
        if not project_path.exists():
            logger.warning(f"Project path does not exist: {project_path}")
            return 1000  # Conservative default

        # Quick estimation by sampling directories
        total_files = 0
        scanned_dirs = 0
        max_scan = 100  # Scan at most 100 directories

        for item in project_path.rglob("*"):
            if scanned_dirs >= max_scan:
                break

            if item.is_file():
                total_files += 1
            elif item.is_dir():
                scanned_dirs += 1

        # Extrapolate if we hit the scan limit
        if scanned_dirs >= max_scan:
            # Conservative multiplier
            total_files = int(total_files * 1.5)

        # If we found very few files, return at least default
        if total_files < 10:
            return 1000

        return total_files

    except Exception as e:
        logger.warning(f"Failed to estimate file count: {e}")
        # Return conservative default
        return 1000


def estimate_backup_memory_requirements(
    project_path: Path | None = None,
    stats: IndexingStats | None = None,
) -> MemoryEstimate:
    """Estimate memory needed for in-memory backup vector store.

    This function estimates the memory requirements based on the number of
    chunks that will be stored in the backup. It uses either provided
    indexing statistics or performs a quick file scan to estimate.

    Memory estimation:
    - Per-chunk overhead: ~5KB (text content + embeddings + metadata)
    - Dense embedding: 768 dimensions × 4 bytes = 3,072 bytes
    - Sparse embedding: ~1KB average
    - Text content: ~500 bytes average
    - Metadata: ~500 bytes
    - Total per chunk: ~5KB

    Safety zones:
    - Green (<100K chunks, ~500MB): Always safe
    - Yellow (100K-500K chunks, 500MB-2.5GB): Check available memory
    - Red (>500K chunks, >2.5GB): Warn user, require confirmation

    Args:
        project_path: Path to the project (for file count estimation)
        stats: Optional indexing statistics with actual chunk counts

    Returns:
        MemoryEstimate with all memory calculations and safety assessment
    """
    try:
        import psutil
    except ImportError:
        logger.warning("psutil not available, cannot estimate memory")
        # Return safe default to avoid blocking
        return MemoryEstimate(
            estimated_bytes=500_000_000,  # 500MB
            available_bytes=4_000_000_000,  # 4GB assumed
            required_bytes=1_500_000_000,  # 1.5GB
            is_safe=True,
            estimated_chunks=100_000,
            zone="green",
        )

    # Estimate number of chunks
    if stats and stats.chunks_created > 0:
        estimated_chunks = stats.chunks_created
    elif stats and stats.files_discovered > 0:
        # Conservative estimate: 10 chunks per file
        estimated_chunks = stats.files_discovered * 10
    elif project_path:
        file_count = estimate_file_count(project_path)
        # Conservative estimate: 10 chunks per file
        estimated_chunks = file_count * 10
    else:
        # Default conservative estimate
        estimated_chunks = 10_000

    # Per-chunk memory: ~5KB (text + embeddings + metadata + overhead)
    bytes_per_chunk = 5000
    estimated_memory = estimated_chunks * bytes_per_chunk

    # System memory check
    mem_info = psutil.virtual_memory()
    available_memory = mem_info.available

    # Safety buffer: require 2x estimated + 500MB buffer
    # This ensures we don't consume all available memory
    required_memory = (estimated_memory * 2) + 500_000_000

    # Determine safety zone
    if estimated_chunks < 100_000:
        zone = "green"
    elif estimated_chunks < 500_000:
        zone = "yellow"
    else:
        zone = "red"

    # Final safety check
    is_safe = available_memory > required_memory

    logger.debug(
        f"Memory estimation: {estimated_chunks:,} chunks, "
        f"{estimated_memory/1e9:.2f}GB estimated, "
        f"{available_memory/1e9:.2f}GB available, "
        f"{required_memory/1e9:.2f}GB required, "
        f"zone={zone}, safe={is_safe}"
    )

    return MemoryEstimate(
        estimated_bytes=estimated_memory,
        available_bytes=available_memory,
        required_bytes=required_memory,
        is_safe=is_safe,
        estimated_chunks=estimated_chunks,
        zone=zone,
    )


__all__ = [
    "MemoryEstimate",
    "estimate_backup_memory_requirements",
    "estimate_file_count",
]
