# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Parallel chunking operations for efficient multi-file processing.

This module provides parallel chunking capabilities using ProcessPoolExecutor
or ThreadPoolExecutor based on configuration settings. It enables efficient
processing of large codebases by distributing file chunking across multiple
workers while maintaining error isolation and memory efficiency.

Key Features:
- Process-based or thread-based execution (configurable)
- Independent file processing with error isolation
- Memory-efficient iterator pattern
- Graceful error handling with detailed logging
- Automatic chunker selection per file

Architecture:
- Uses ChunkerSelector for intelligent chunker routing
- Creates fresh chunker instances in each worker
- Yields results as (Path, list[CodeChunk]) tuples
- Logs errors but continues processing remaining files

Performance Considerations:
- Process-based: Better for CPU-bound parsing (default)
- Thread-based: Better for I/O-bound operations
- Memory usage scales with max_workers setting
- Iterator pattern prevents loading all results in memory
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing

from collections.abc import AsyncIterator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

from codeweaver.core.constants import DEFAULT_MAX_CONCURRENT_BATCHES, ZERO
from codeweaver.engine.chunker.delimiter import DelimiterChunker
from codeweaver.engine.chunker.exceptions import ChunkingError
from codeweaver.engine.chunker.selector import ChunkerSelector


if TYPE_CHECKING:
    from codeweaver.core import CodeChunk, DiscoveredFile
    from codeweaver.engine.chunker.base import ChunkGovernor
logger = logging.getLogger(__name__)


def _chunk_single_file(
    file: DiscoveredFile, governor: ChunkGovernor, tokenizer: Any | None = None
) -> tuple[Path, list[CodeChunk] | None]:
    """Chunk a single file using appropriate chunker with graceful fallback.

    This function is designed to be called in worker processes/threads.
    It creates a fresh chunker instance to ensure isolation and avoid
    state contamination across files.

    Args:
        file: DiscoveredFile to chunk
        governor: ChunkGovernor configuration for chunking behavior
        tokenizer: Optional tokenizer for accurate token counting

    Returns:
        Tuple of (file_path, chunks) on success, or (file_path, None) on error.
        The None return indicates an error occurred and was logged.

    Notes:
        - Creates fresh ChunkerSelector and chunker instances
        - Reads file content directly from disk
        - Gracefully falls back to delimiter chunking on parse errors
        - Handles all exceptions internally with logging
        - Never raises exceptions to caller
    """
    try:
        selector = ChunkerSelector(governor, tokenizer)
        chunker = selector.select_for_file(file)
        content = file.absolute_path.read_text(encoding="utf-8", errors="ignore")

        try:
            chunks = chunker.chunk(content, file=file)
        except ChunkingError as e:
            # Graceful fallback to delimiter chunking for parse errors
            # This is expected behavior for malformed files - not an error to report
            logger.debug(
                "Semantic chunking failed for %s, falling back to delimiter: %s",
                file.path,
                type(e).__name__,
                extra={"file_path": str(file.path), "error_type": type(e).__name__},
            )
            # Create delimiter chunker as fallback
            language = (
                file.ext_kind.language.variable
                if file.ext_kind and file.ext_kind.language
                else "unknown"
            )
            fallback_chunker = DelimiterChunker(governor, language=language)

            # Log fallback event for observability
            from codeweaver.engine.chunker import _logging as chunker_logging

            chunker_logging.log_chunking_fallback(
                file_path=file.path,
                from_chunker=chunker,  # ty: ignore[invalid-argument-type]
                to_chunker=fallback_chunker,
                reason="parse_error",
                extra_context={"error_type": type(e).__name__, "error_message": str(e)},
            )

            chunks = fallback_chunker.chunk(content, file=file)

        logger.debug("Chunked %s: %d chunks generated", file.path, len(chunks))
    except Exception:
        # Only log at warning level - these are operational issues, not critical errors
        # The file is simply skipped, server continues normally
        logger.warning(
            "Skipping file %s: chunking failed",
            file.path,
            extra={"file_path": str(file.path), "ext_kind": file.ext_kind or "unknown"},
        )
        # Log full traceback only at debug level
        logger.debug(
            "Full error for %s", file.path, exc_info=True, extra={"file_path": str(file.path)}
        )
        return (file.path, None)
    else:
        return (file.path, chunks)


async def chunk_files_parallel(
    files: list[DiscoveredFile],
    governor: ChunkGovernor,
    *,
    max_workers: int | None = None,
    executor_type: str | None = None,
    tokenizer: Any | None = None,
) -> AsyncIterator[tuple[Path, list[CodeChunk]]]:
    """Chunk multiple files in parallel using process or thread pool.

    Distributes file chunking across multiple workers for efficient processing
    of large codebases. Uses an iterator pattern to yield results as they
    complete, preventing memory exhaustion from loading all chunks at once.

    Args:
        files: List of DiscoveredFile objects to chunk
        governor: ChunkGovernor providing resource limits and configuration
        max_workers: Maximum number of parallel workers. If None, uses settings
            from governor or defaults to CPU count. For process executor, limited
            to available CPUs. For thread executor, can exceed CPU count.
        executor_type: Type of executor to use - "process" or "thread" or None.
            If None, uses settings from governor or defaults to "process".
            Process-based is better for CPU-bound parsing, thread-based for I/O.
        tokenizer: Optional tokenizer for accurate token counting

    Yields:
        Tuples of (file_path, chunks) for successfully chunked files.
        Files that fail to chunk are logged but not yielded.
    """
    if not files:
        logger.debug("No files to chunk")
        return

    if max_workers is None:
        if governor.settings and governor.settings.concurrency:
            max_workers = governor.settings.concurrency.max_parallel_files
        else:
            max_workers = DEFAULT_MAX_CONCURRENT_BATCHES

    if executor_type is None:
        if governor.settings and governor.settings.concurrency:
            executor_type = governor.settings.concurrency.executor
        else:
            executor_type = "process"

    if executor_type == "process":
        try:
            current_method = multiprocessing.get_start_method(allow_none=True)
            if current_method != "spawn":
                multiprocessing.set_start_method("spawn", force=True)
                logger.debug("Set multiprocessing start method to 'spawn'")
        except RuntimeError:
            logger.debug("Multiprocessing start method already configured")

        cpu_count = multiprocessing.cpu_count()
        max_workers = min(max_workers, cpu_count)
        executor_class = ProcessPoolExecutor
        logger.info(
            "Using ProcessPoolExecutor with %d workers (CPU count: %d)", max_workers, cpu_count
        )
    else:
        executor_class = ThreadPoolExecutor
        logger.info("Using ThreadPoolExecutor with %d workers", max_workers)

    total_files = len(files)
    processed_count = ZERO
    error_count = ZERO
    logger.info("Starting parallel chunking of %d files with %d workers", total_files, max_workers)

    loop = asyncio.get_running_loop()

    with executor_class(max_workers=max_workers) as executor:
        # Bounded task submission using a semaphore to prevent unbounded Future creation
        # We allow a small buffer (max_workers * 2) to keep the pool saturated
        semaphore = asyncio.Semaphore(max_workers * 2)

        async def _run_task(file_obj: DiscoveredFile) -> tuple[Path, list[CodeChunk] | None]:
            async with semaphore:
                return await loop.run_in_executor(
                    executor, _chunk_single_file, file_obj, governor, tokenizer
                )

        # Submit tasks through the bounded runner
        futures = [_run_task(file) for file in files]

        # Use asyncio.as_completed to avoid blocking the event loop
        for future in asyncio.as_completed(futures):
            try:
                result = await future
                file_path, chunks = result
                processed_count += 1

                if chunks is None:
                    error_count += 1
                    continue

                logger.debug(
                    "Completed %d/%d files: %s (%d chunks)",
                    processed_count,
                    total_files,
                    file_path,
                    len(chunks),
                )
                yield (file_path, chunks)
            except Exception:
                processed_count += 1
                error_count += 1
                logger.warning("Unexpected error in parallel chunking task", exc_info=True)

    success_count = processed_count - error_count
    logger.info(
        "Parallel chunking complete: %d/%d files successful, %d errors",
        success_count,
        total_files,
        error_count,
    )


async def chunk_files_parallel_dict(
    files: list[DiscoveredFile],
    governor: ChunkGovernor,
    *,
    max_workers: int | None = None,
    executor_type: str | None = None,
) -> dict[Path, list[CodeChunk]]:
    """Chunk multiple files in parallel and return as dictionary."""
    return {
        k: v
        async for k, v in chunk_files_parallel(
            files, governor, max_workers=max_workers, executor_type=executor_type
        )
    }


__all__ = ("chunk_files_parallel", "chunk_files_parallel_dict")
