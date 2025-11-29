# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Resource estimation utilities for backup vector store activation.

This module provides utilities to estimate memory requirements and system
resources needed for activating the in-memory backup vector store.
"""

from __future__ import annotations

import logging

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import rignore

from pydantic import NonNegativeFloat, NonNegativeInt


if TYPE_CHECKING:
    from codeweaver.engine.indexer.progress import IndexingStats

logger = logging.getLogger(__name__)

# Cache for file count estimates (path -> (count, timestamp))
# Using a bounded cache with LRU-like behavior to prevent unbounded growth
_file_count_cache: dict[Path, tuple[int, datetime]] = {}
_CACHE_EXPIRY = timedelta(minutes=20)  # Cache file counts for 20 minutes
_MAX_CACHE_SIZE = 100  # Maximum number of paths to cache


class MemoryEstimate(NamedTuple):
    """Memory estimation result for backup activation."""

    estimated_bytes: NonNegativeInt
    """Estimated memory required in bytes"""

    available_bytes: NonNegativeInt
    """Available system memory in bytes"""

    required_bytes: NonNegativeInt
    """Required memory with safety buffer in bytes"""

    is_safe: bool
    """Whether it's safe to activate backup"""

    estimated_chunks: NonNegativeInt
    """Estimated number of chunks"""

    zone: str
    """Memory zone: 'green', 'yellow', or 'red'"""

    @property
    def estimated_gb(self) -> NonNegativeFloat:
        """Estimated memory in GB."""
        return self.estimated_bytes / 1e9

    @property
    def available_gb(self) -> NonNegativeFloat:
        """Available memory in GB."""
        return self.available_bytes / 1e9

    @property
    def required_gb(self) -> NonNegativeFloat:
        """Required memory in GB."""
        return self.required_bytes / 1e9


def get_walker() -> rignore.Walker:
    """Get a rignore.Walker instance. Walkers are generators, so we create a new one each time."""
    from codeweaver.config.indexer import DefaultIndexerSettings
    from codeweaver.config.settings import get_settings
    from codeweaver.core.types import Unset

    settings = get_settings()
    index_settings = (
        DefaultIndexerSettings if isinstance(settings.indexer, Unset) else settings.indexer
    )
    import rignore

    return rignore.Walker(**index_settings.to_settings())


def estimate_file_count(project_path: Path | None = None) -> NonNegativeInt:
    """Quickly estimate the number of indexable files in a project.

    OPTIMIZATION: Caches results to avoid repeated file system scans.

    Args:
        project_path: Root path of the project
        max_depth: Maximum directory depth to scan

    Returns:
        Estimated file count
    """
    if project_path is None:
        from codeweaver.common.utils.git import get_project_path
        from codeweaver.config.settings import get_settings
        from codeweaver.core.types import Unset

        settings = get_settings()
        project_path = (
            get_project_path()
            if isinstance(settings.project_path, Unset)
            else settings.project_path
        )

    from codeweaver.common.statistics import get_session_statistics

    if (
        (statistics := get_session_statistics())
        and (index_stats := statistics.index_statistics)
        and (file_count := index_stats.total_file_count) > 0
    ):
        logger.debug("Using indexing statistics for file count: %d files", file_count)
        return file_count
    # Check cache first
    now = datetime.now(UTC)
    if project_path in _file_count_cache:
        cached_count, cache_time = _file_count_cache[project_path]
        if now - cache_time < _CACHE_EXPIRY:
            logger.debug(
                "Using cached file count for %s: %d (age: %.1fs)",
                project_path,
                cached_count,
                (now - cache_time).total_seconds(),
            )
            return cached_count

        # Evict oldest entries if cache is full
        if len(_file_count_cache) >= _MAX_CACHE_SIZE:
            # Remove the oldest entry
            oldest_path = min(_file_count_cache.items(), key=lambda x: x[1][1])[0]
            del _file_count_cache[oldest_path]
            logger.debug("Evicted oldest cache entry for %s", oldest_path)
    try:
        walker = get_walker()
        result = sum(bool(p and p.is_file()) for p in walker)
        # Cache the result
        _file_count_cache[project_path] = (result, now)
        logger.debug("Cached file count estimate for %s: %d files", project_path, result)

    except Exception as e:
        logger.warning("Failed to estimate file count", exc_info=e)
        # Return conservative default
        result = 1000
        # Cache the fallback value to avoid repeated failures
        if len(_file_count_cache) >= _MAX_CACHE_SIZE:
            oldest_path = min(_file_count_cache.items(), key=lambda x: x[1][1])[0]
            del _file_count_cache[oldest_path]
        _file_count_cache[project_path] = (result, now)
    return result


def _get_backup_profile():
    """Get the backup configuration profile."""
    from codeweaver.config.profiles import get_profile

    return get_profile("backup", "local")


def estimate_backup_memory_requirements(
    project_path: Path | None = None, stats: IndexingStats | None = None
) -> MemoryEstimate:
    """Estimate memory needed for in-memory backup vector store.

    This function estimates the memory requirements based on the number of
    chunks that will be stored in the backup. It uses either provided
    indexing statistics or performs a quick file scan to estimate.

    The current backup profile uses an in-memory Qdrant vector store,
    with very lightweight models for embeddings. Dense embeddings are quantized to uint8, and sparse to float16.

    Memory estimation:
    - Chunks on backup models are about 450 tokens each, or ~2KB of text.
    - Per-chunk overhead: add 1KB for metadata and indexing overhead.
    - Dense embedding: 384 dimensions x 1 byte = ~384 bytes
    - Sparse embedding: ~100 non-zero dimensions x 2 bytes = ~200... let's call it 300 bytes
    - Total per-chunk: ~4KB rounded up from 3.5KB because 🤷‍♂️

    Safety zones:
    - Green (<125K chunks, ~500MB): Always safe
    - Yellow (125K-625K chunks, ~500MB-2.5GB): Check available memory
    - Red (>625K chunks, >2.5GB): Warn user, require confirmation

    Args:
        project_path: Path to the project (for file count estimation)
        stats: Optional indexing statistics with actual chunk counts

    Returns:
        MemoryEstimate with all memory calculations and safety assessment
    """
    try:
        import psutil
    except ImportError:
        return _estimate_memory_fallback()
    # Estimate number of chunks
    if stats and stats.chunks_created > 0:
        estimated_chunks = stats.chunks_created
    elif stats and stats.files_discovered > 0:
        chunks_per_file = 3250 / 450  # Average tokens per file divided by tokens per chunk
        estimated_chunks = int(stats.files_discovered * chunks_per_file)
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
        "Memory estimation: %d chunks, %.2fGB estimated, %.2fGB available, %.2fGB required, zone=%s, safe=%s",
        estimated_chunks,
        estimated_memory / 1e9,
        available_memory / 1e9,
        required_memory / 1e9,
        zone,
        is_safe,
    )

    return MemoryEstimate(
        estimated_bytes=estimated_memory,
        available_bytes=available_memory,
        required_bytes=required_memory,
        is_safe=is_safe,
        estimated_chunks=estimated_chunks,
        zone=zone,
    )


def _estimate_memory_fallback():
    """Fallback memory estimation when psutil is not available."""
    logger.warning("psutil not available, cannot estimate memory")
    # we'll estimate by file count
    from codeweaver.config.indexer import DefaultIndexerSettings
    from codeweaver.config.settings import get_settings
    from codeweaver.core.types import Unset

    settings = get_settings()
    index_settings = (
        DefaultIndexerSettings if isinstance(settings.indexer, Unset) else settings.indexer
    )
    import rignore

    walker = rignore.Walker(**index_settings.to_settings())
    file_count = len([p for p in walker if p and p.is_file()])
    tokens_per_file = (
        3250  # This is the average for codeweaver over its 770 files with recognized extensions
    )
    chunks_per_file = tokens_per_file / 450  # 450 tokens per chunk
    # Return safe default to avoid blocking
    chunks = int(file_count * chunks_per_file)
    est_bytes = int(chunks * 4000)
    return MemoryEstimate(
        estimated_bytes=est_bytes,
        available_bytes=4_000_000_000,
        required_bytes=est_bytes + 500_000_000,
        is_safe=est_bytes < 3_500_000_000,
        estimated_chunks=chunks,
        zone="green",
    )


__all__ = ["MemoryEstimate", "estimate_backup_memory_requirements", "estimate_file_count"]
