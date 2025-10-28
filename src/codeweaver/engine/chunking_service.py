# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Chunking service for processing files into code chunks.

This service bridges file discovery and chunk storage, providing both
sequential and parallel chunking capabilities with intelligent fallback.
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import TYPE_CHECKING

from codeweaver.core.chunks import CodeChunk
from codeweaver.engine.chunker import ChunkerSelector, ChunkGovernor, chunk_files_parallel


if TYPE_CHECKING:
    from collections.abc import Iterator

    from codeweaver.core.discovery import DiscoveredFile


logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for chunking discovered files with parallel processing support.

    This service provides a unified interface for chunking files, with automatic
    fallback from parallel to sequential processing when appropriate.

    Examples:
        Basic usage with parallel processing:

        >>> from codeweaver.providers.embedding.capabilities.base import (
        ...     EmbeddingModelCapabilities,
        ... )
        >>> capabilities = EmbeddingModelCapabilities(context_window=8192)
        >>> governor = ChunkGovernor(capabilities=(capabilities,))
        >>> service = ChunkingService(governor)
        >>>
        >>> # Chunk files in parallel
        >>> for file_path, chunks in service.chunk_files(discovered_files):
        ...     print(f"Chunked {file_path}: {len(chunks)} chunks")

        Using settings for configuration:

        >>> from codeweaver.config.chunker import ChunkerSettings, ConcurrencySettings
        >>> settings = ChunkerSettings(
        ...     concurrency=ConcurrencySettings(max_parallel_files=8, executor="thread")
        ... )
        >>> governor = ChunkGovernor(capabilities=(capabilities,), settings=settings)
        >>> service = ChunkingService(governor)
    """

    def __init__(
        self, governor: ChunkGovernor, *, enable_parallel: bool = True, parallel_threshold: int = 3
    ) -> None:
        """Initialize the chunking service.

        Args:
            governor: ChunkGovernor providing resource limits and configuration
            enable_parallel: Whether to use parallel processing (default: True)
            parallel_threshold: Minimum number of files to trigger parallel processing
        """
        self.governor = governor
        self.enable_parallel = enable_parallel
        self.parallel_threshold = parallel_threshold
        self._selector = ChunkerSelector(governor)

    def chunk_files(
        self,
        files: list[DiscoveredFile],
        *,
        max_workers: int | None = None,
        executor_type: str | None = None,
        force_parallel: bool = False,
    ) -> Iterator[tuple[Path, list[CodeChunk]]]:
        """Chunk multiple files with automatic parallel/sequential selection.

        Automatically chooses between parallel and sequential processing based on
        file count and configuration. Uses parallel processing for file counts
        above the threshold, sequential otherwise.

        Args:
            files: List of DiscoveredFile objects to chunk
            max_workers: Maximum number of parallel workers (optional)
            executor_type: "process" or "thread" or None for settings default
            force_parallel: Force parallel processing regardless of file count

        Yields:
            Tuples of (file_path, chunks) for successfully chunked files

        Notes:
            - Files with errors are logged but not yielded
            - Parallel processing used when len(files) >= parallel_threshold
            - Sequential processing used for small batches to reduce overhead
        """
        if not files:
            logger.debug("No files to chunk")
            return

        if force_parallel or (self.enable_parallel and len(files) >= self.parallel_threshold):
            logger.info(
                "Chunking %d files in parallel (threshold: %d)", len(files), self.parallel_threshold
            )
            yield from chunk_files_parallel(
                files, self.governor, max_workers=max_workers, executor_type=executor_type
            )
        else:
            logger.info("Chunking %d files sequentially", len(files))
            yield from self._chunk_sequential(files)

    def _chunk_sequential(
        self, files: list[DiscoveredFile]
    ) -> Iterator[tuple[Path, list[CodeChunk]]]:
        """Chunk files sequentially (non-parallel).

        Useful for small batches where parallel overhead isn't justified.

        Args:
            files: List of DiscoveredFile objects to chunk

        Yields:
            Tuples of (file_path, chunks) for successfully chunked files
        """
        for file in files:
            try:
                # Select appropriate chunker
                chunker = self._selector.select_for_file(file)

                # Read file content
                content = file.path.read_text(encoding="utf-8", errors="ignore")

                # Chunk the file
                chunks = chunker.chunk(content, file=file)

                logger.debug("Chunked %s: %d chunks generated", file.path, len(chunks))

                yield (file.path, chunks)

            except Exception:
                logger.exception(
                    "Failed to chunk file %s",
                    file.path,
                    extra={
                        "file_path": str(file.path),
                        "ext_kind": file.ext_kind.value if file.ext_kind else None,  # type: ignore
                    },  # type: ignore
                )
                # Continue processing other files

    def chunk_file(self, file: DiscoveredFile) -> list[CodeChunk]:
        """Chunk a single file.

        Convenience method for chunking a single file without iteration.

        Args:
            file: DiscoveredFile to chunk

        Returns:
            List of CodeChunk objects

        Raises:
            Exception: If chunking fails
        """
        chunker = self._selector.select_for_file(file)
        content = file.path.read_text(encoding="utf-8", errors="ignore")
        return chunker.chunk(content, file=file)

    def chunk_content(self, content: str, file: DiscoveredFile | None = None) -> list[CodeChunk]:
        """Chunk string content directly.

        Args:
            content: String content to chunk
            file: Optional DiscoveredFile for metadata

        Returns:
            List of CodeChunk objects

        Raises:
            Exception: If chunking fails
        """
        if file:
            chunker = self._selector.select_for_file(file)
        else:
            # Use a default chunker when no file context available
            from codeweaver.engine.chunker import DelimiterChunker

            chunker = DelimiterChunker(self.governor)

        return chunker.chunk(content, file=file)


__all__ = ("ChunkingService",)
