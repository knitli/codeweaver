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

import contextlib
import logging
import multiprocessing

from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

from codeweaver.engine.chunker.selector import ChunkerSelector


if TYPE_CHECKING:
    from concurrent.futures import Future

    from codeweaver.core.chunks import CodeChunk
    from codeweaver.core.discovery import DiscoveredFile
    from codeweaver.engine.chunker.base import ChunkGovernor
logger = logging.getLogger(__name__)

def _chunk_single_file(file: DiscoveredFile, governor: ChunkGovernor) -> tuple[Path, list[CodeChunk]] | tuple[Path, None]:
    """Chunk a single file using appropriate chunker.

    This function is designed to be called in worker processes/threads.
    It creates a fresh chunker instance to ensure isolation and avoid
    state contamination across files.

    Args:
        file: DiscoveredFile to chunk
        governor: ChunkGovernor configuration for chunking behavior

    Returns:
        Tuple of (file_path, chunks) on success, or (file_path, None) on error.
        The None return indicates an error occurred and was logged.

    Notes:
        - Creates fresh ChunkerSelector and chunker instances
        - Reads file content directly from disk
        - Handles all exceptions internally with logging
        - Never raises exceptions to caller
    """
    try:
        selector = ChunkerSelector(governor)
        chunker = selector.select_for_file(file)
        content = file.path.read_text(encoding='utf-8', errors='ignore')
        chunks = chunker.chunk(content, file=file)
        logger.debug('Chunked %s: %d chunks generated', file.path, len(chunks))
    except Exception:
        logger.exception('Failed to chunk file %s', file.path, extra={'file_path': str(file.path), 'ext_kind': file.ext_kind.value if file.ext_kind else None})
        return (file.path, None)
    else:
        return (file.path, chunks)

def chunk_files_parallel(files: list[DiscoveredFile], governor: ChunkGovernor, *, max_workers: int | None=None, executor_type: str | None=None) -> Iterator[tuple[Path, list[CodeChunk]]]:
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

    Yields:
        Tuples of (file_path, chunks) for successfully chunked files.
        Files that fail to chunk are logged but not yielded.

    Examples:
        Basic usage with defaults:

        >>> from codeweaver.engine.chunker.base import ChunkGovernor
        >>> from codeweaver.core.discovery import DiscoveredFile
        >>> from pathlib import Path
        >>>
        >>> files = [DiscoveredFile.from_path(p) for p in Path("src").rglob("*.py")]
        >>> governor = ChunkGovernor(capabilities=(...))
        >>>
        >>> for file_path, chunks in chunk_files_parallel(files, governor):
        ...     print(f"Processed {file_path}: {len(chunks)} chunks")

        With custom settings:

        >>> for file_path, chunks in chunk_files_parallel(
        ...     files, governor, max_workers=8, executor_type="thread"
        ... ):
        ...     process_chunks(file_path, chunks)

    Notes:
        - Process executor: Better isolation, handles CPU-bound work well
        - Thread executor: Lower overhead, better for I/O-bound operations
        - Errors in individual files don't stop processing of other files
        - Results yielded in completion order (not submission order)
        - Empty file list returns immediately without creating executor
    """
    if not files:
        logger.debug('No files to chunk')
        return
    if max_workers is None:
        if governor.settings and governor.settings.concurrency:
            max_workers = governor.settings.concurrency.max_parallel_files
        else:
            max_workers = 4
    if executor_type is None:
        if governor.settings and governor.settings.concurrency:
            executor_type = governor.settings.concurrency.executor
        else:
            executor_type = 'process'
    if executor_type == 'process':
        cpu_count = multiprocessing.cpu_count()
        max_workers = min(max_workers, cpu_count)
        executor_class = ProcessPoolExecutor
        logger.info('Using ProcessPoolExecutor with %d workers (CPU count: %d)', max_workers, cpu_count)
    else:
        executor_class = ThreadPoolExecutor
        logger.info('Using ThreadPoolExecutor with %d workers', max_workers)
    total_files = len(files)
    processed_count = 0
    error_count = 0
    logger.info('Starting parallel chunking of %d files with %d workers', total_files, max_workers)
    with executor_class(max_workers=max_workers) as executor:
        future_to_file: dict[Future[tuple[Path, list[CodeChunk] | None]], DiscoveredFile] = {executor.submit(_chunk_single_file, file, governor): file for file in files}
        for future in as_completed(future_to_file):
            future_to_file[future]
            with contextlib.suppress(Exception):
                result = future.result()
                file_path, chunks = result
                if chunks is None:
                    error_count += 1
                    processed_count += 1
                    continue
                processed_count += 1
                logger.debug('Completed %d/%d files: %s (%d chunks)', processed_count, total_files, file_path, len(chunks))
                yield (file_path, chunks)
    success_count = processed_count - error_count
    logger.info('Parallel chunking complete: %d/%d files successful, %d errors', success_count, total_files, error_count)

def chunk_files_parallel_dict(files: list[DiscoveredFile], governor: ChunkGovernor, *, max_workers: int | None=None, executor_type: str | None=None) -> dict[Path, list[CodeChunk]]:
    """Chunk multiple files in parallel and return as dictionary.

    Convenience wrapper around chunk_files_parallel that collects all results
    into a dictionary. Useful when you need all results at once rather than
    processing them incrementally.

    Args:
        files: List of DiscoveredFile objects to chunk
        governor: ChunkGovernor providing resource limits and configuration
        max_workers: Maximum number of parallel workers (see chunk_files_parallel)
        executor_type: "process" or "thread" (see chunk_files_parallel)

    Returns:
        Dictionary mapping file paths to their chunks. Files that failed to
        chunk are excluded from the result.

    Examples:
        >>> results = chunk_files_parallel_dict(files, governor, max_workers=8)
        >>> for file_path, chunks in results.items():
        ...     print(f"{file_path}: {len(chunks)} chunks")

    Notes:
        - Loads all results in memory (use chunk_files_parallel for streaming)
        - Only includes successfully chunked files
        - Returns empty dict if no files chunked successfully
    """
    return dict(chunk_files_parallel(files, governor, max_workers=max_workers, executor_type=executor_type))
__all__ = ('chunk_files_parallel', 'chunk_files_parallel_dict')
