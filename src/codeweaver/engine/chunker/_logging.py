# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Structured logging utilities for chunker system.

Provides consistent structured logging format for chunking events as specified in
architecture spec §9.3:
- Success events: chunking_completed
- Error events: chunking_failed
- Edge case events: chunking_edge_case
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Any

from codeweaver.engine.chunker.delimiter import DelimiterChunker
from codeweaver.engine.chunker.semantic import SemanticChunker


type Chunker = SemanticChunker | DelimiterChunker

logger = logging.getLogger(__name__)


def get_name(chunker: Chunker) -> str:
    """Get the name of the chunker type.

    Args:
        chunker: The chunker instance

    Returns:
        The name of the chunker type as a string
    """
    return "SEMANTIC" if isinstance(chunker, SemanticChunker) else "DELIMITER"


def log_chunking_completed(
    *,
    file_path: Path,
    chunker_type: Chunker,
    chunk_count: int,
    duration_ms: float,
    file_size_bytes: int,
    language: str,
    extra_context: dict[str, Any] | None = None,
) -> None:
    """Log successful chunking completion.

    Args:
        file_path: Path to the file that was chunked
        chunker_type: Type of chunker used (SEMANTIC or DELIMITER)
        chunk_count: Number of chunks produced
        duration_ms: Time taken to chunk in milliseconds
        file_size_bytes: Size of the source file in bytes
        language: Programming language of the file
        extra_context: Additional context to include in the log
    """
    extra = {
        "event": "chunking_completed",
        "file_path": str(file_path),
        "chunker_type": get_name(chunker_type),
        "chunk_count": chunk_count,
        "duration_ms": duration_ms,
        "file_size_bytes": file_size_bytes,
        "language": language,
        "chunks_per_second": chunk_count / (duration_ms / 1000) if duration_ms > 0 else 0,
    }

    if extra_context:
        extra |= extra_context

    logger.info("Chunking completed successfully", extra=extra)


def log_chunking_failed(
    *,
    file_path: Path,
    chunker_type: Chunker,
    error_type: str,
    error_message: str,
    fallback_triggered: bool = False,
    extra_context: dict[str, Any] | None = None,
) -> None:
    """Log chunking failure.

    Args:
        file_path: Path to the file that failed to chunk
        chunker_type: Type of chunker that failed
        error_type: Type/class of the error
        error_message: Error message text
        fallback_triggered: Whether fallback strategy was triggered
        extra_context: Additional context to include in the log
    """
    extra = {
        "event": "chunking_failed",
        "file_path": str(file_path),
        "chunker_type": get_name(chunker_type),
        "error_type": error_type,
        "error_message": error_message,
        "fallback_triggered": fallback_triggered,
    }

    if extra_context:
        extra |= extra_context

    logger.error("Chunking failed", extra=extra)


def log_chunking_edge_case(
    *,
    file_path: Path,
    edge_case_type: str,
    chunk_count: int = 0,
    extra_context: dict[str, Any] | None = None,
) -> None:
    """Log edge case handling during chunking.

    Args:
        file_path: Path to the file with edge case
        edge_case_type: Type of edge case (empty_file, whitespace_only, single_line, binary_file)
        chunk_count: Number of chunks produced (usually 0 or 1)
        extra_context: Additional context to include in the log
    """
    extra = {
        "event": "chunking_edge_case",
        "file_path": str(file_path),
        "edge_case_type": edge_case_type,
        "chunk_count": chunk_count,
    }

    if extra_context:
        extra |= extra_context

    logger.debug("Edge case handled during chunking", extra=extra)


def log_chunking_fallback(
    *,
    file_path: Path,
    from_chunker: Chunker,
    to_chunker: Chunker,
    reason: str,
    extra_context: dict[str, Any] | None = None,
) -> None:
    """Log chunker fallback event.

    Args:
        file_path: Path to the file requiring fallback
        from_chunker: Original chunker that failed
        to_chunker: Fallback chunker being used
        reason: Reason for fallback (e.g., "parse_error", "oversized_chunk")
        extra_context: Additional context to include in the log
    """
    extra = {
        "event": "chunking_fallback",
        "file_path": str(file_path),
        "from_chunker": get_name(from_chunker),
        "to_chunker": get_name(to_chunker),
        "reason": reason,
    }

    if extra_context:
        extra |= extra_context

    logger.warning("Chunker fallback triggered", extra=extra)


def log_chunking_performance_warning(
    *,
    file_path: Path,
    chunker_type: Chunker,
    duration_ms: float,
    threshold_ms: float,
    extra_context: dict[str, Any] | None = None,
) -> None:
    """Log performance warning for slow chunking operations.

    Args:
        file_path: Path to the file that was slow to chunk
        chunker_type: Type of chunker used
        duration_ms: Actual time taken in milliseconds
        threshold_ms: Expected/threshold time in milliseconds
        extra_context: Additional context to include in the log
    """
    extra = {
        "event": "chunking_performance_warning",
        "file_path": str(file_path),
        "chunker_type": get_name(chunker_type),
        "duration_ms": duration_ms,
        "threshold_ms": threshold_ms,
        "slowdown_factor": duration_ms / threshold_ms if threshold_ms > 0 else 0,
    }

    if extra_context:
        extra |= extra_context

    logger.warning("Chunking operation slower than expected", extra=extra)


def log_chunking_resource_limit(
    *,
    file_path: Path,
    limit_type: str,
    limit_value: float,
    actual_value: float,
    extra_context: dict[str, Any] | None = None,
) -> None:
    """Log resource limit violation during chunking.

    Args:
        file_path: Path to the file that violated limits
        limit_type: Type of limit (timeout, chunk_count, ast_depth, memory)
        limit_value: Configured limit value
        actual_value: Actual value that exceeded the limit
        extra_context: Additional context to include in the log
    """
    extra = {
        "event": "chunking_resource_limit",
        "file_path": str(file_path),
        "limit_type": limit_type,
        "limit_value": limit_value,
        "actual_value": actual_value,
        "excess_percentage": ((actual_value - limit_value) / limit_value * 100)
        if limit_value > 0
        else 0,
    }

    if extra_context:
        extra |= extra_context

    logger.error("Resource limit exceeded during chunking", extra=extra)


def log_chunking_deduplication(
    *,
    file_path: Path,
    total_chunks: int,
    duplicate_chunks: int,
    unique_chunks: int,
    extra_context: dict[str, Any] | None = None,
) -> None:
    """Log chunk deduplication statistics.

    Args:
        file_path: Path to the file that was deduplicated
        total_chunks: Total chunks before deduplication
        duplicate_chunks: Number of duplicate chunks removed
        unique_chunks: Number of unique chunks retained
        extra_context: Additional context to include in the log
    """
    extra = {
        "event": "chunking_deduplication",
        "file_path": str(file_path),
        "total_chunks": total_chunks,
        "duplicate_chunks": duplicate_chunks,
        "unique_chunks": unique_chunks,
        "dedup_rate_percentage": (duplicate_chunks / total_chunks * 100) if total_chunks > 0 else 0,
    }

    if extra_context:
        extra |= extra_context

    logger.debug("Chunk deduplication completed", extra=extra)
