# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Chunking service for processing files into code chunks."""

from __future__ import annotations

import asyncio
import logging

from pathlib import Path
from typing import TYPE_CHECKING

from codeweaver.core import SemanticSearchLanguage
from codeweaver.core.constants import PARALLEL_CHUNKING_THRESHOLD
from codeweaver.engine.chunker import ChunkerSelector, chunk_files_parallel
from codeweaver.engine.chunker.delimiter import DelimiterChunker
from codeweaver.engine.chunker.exceptions import ChunkingError, FileTooLargeError


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from codeweaver_tokenizers.base import Tokenizer

    from codeweaver.core import CodeChunk, DiscoveredFile
    from codeweaver.engine.chunker.base import ChunkGovernor
    from codeweaver.engine.config import ChunkerSettings


logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for chunking discovered files with parallel processing support."""

    def __init__(
        self, governor: ChunkGovernor, tokenizer: Tokenizer, settings: ChunkerSettings
    ) -> None:
        """Initialize chunking service with required dependencies."""
        self.governor = governor
        self.tokenizer = tokenizer
        self.settings = settings
        self._selector = ChunkerSelector(governor, tokenizer)

    async def chunk_files(
        self,
        files: list[DiscoveredFile],
        *,
        max_workers: int | None = None,
        executor_type: str | None = None,
        force_parallel: bool = False,
        source_chunks: dict[Path, list[CodeChunk]] | None = None,
    ) -> AsyncIterator[tuple[Path, list[CodeChunk]]]:
        """Chunk multiple files with optional parallel processing."""
        if not files:
            return

        # Normal chunking logic
        if force_parallel or (len(files) >= PARALLEL_CHUNKING_THRESHOLD):
            async for result in chunk_files_parallel(
                files,
                self.governor,
                max_workers=max_workers,
                executor_type=executor_type,
                tokenizer=self.tokenizer,
            ):
                yield result
        else:
            async for result in self._chunk_sequential(files):
                yield result

    async def _chunk_sequential(
        self, files: list[DiscoveredFile]
    ) -> AsyncIterator[tuple[Path, list[CodeChunk]]]:
        """Sequential chunking with fallback."""
        for file in files:
            try:
                chunker = self._selector.select_for_file(file)
                # Offload blocking I/O to a thread
                content = await asyncio.to_thread(file.absolute_path.read_text, "utf-8", "ignore")

                try:
                    chunks = chunker.chunk(content, file=file)
                except ChunkingError:
                    language = (
                        file.ext_category.language.variable
                        if isinstance(file.ext_category, SemanticSearchLanguage)
                        else str(file.ext_category.language)
                    )
                    fallback_chunker = DelimiterChunker(self.governor, language=language)
                    chunks = fallback_chunker.chunk(content, file=file)

                yield (file.path, chunks)
            except FileTooLargeError as e:
                logger.info(
                    "Skipping oversized file: %s (%s)",
                    file.path,
                    e,
                    extra={"file_size_mb": e.file_size_mb, "max_size_mb": e.max_size_mb},
                )
            except Exception:
                logger.warning("Skipping file %s: chunking failed", file.path, exc_info=True)

    async def chunk_file(self, file: DiscoveredFile) -> list[CodeChunk]:
        """Chunk a single file."""
        async for _, chunks in self._chunk_sequential([file]):
            return chunks
        return []


__all__ = ("ChunkingService",)
