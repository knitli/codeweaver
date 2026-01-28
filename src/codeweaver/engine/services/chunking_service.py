# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Chunking service for processing files into code chunks."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import TYPE_CHECKING

from codeweaver.engine.chunker import ChunkerSelector, chunk_files_parallel
from codeweaver.engine.chunker.delimiter import DelimiterChunker
from codeweaver.engine.chunker.exceptions import ChunkingError


if TYPE_CHECKING:
    from collections.abc import Iterator

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

    def chunk_files(
        self,
        files: list[DiscoveredFile],
        *,
        max_workers: int | None = None,
        executor_type: str | None = None,
        force_parallel: bool = False,
        source_chunks: dict[Path, list[CodeChunk]] | None = None,
    ) -> Iterator[tuple[Path, list[CodeChunk]]]:
        """Chunk multiple files with optional smart reuse for backup scenarios."""
        if not files:
            return

        # If backup and source chunks provided, attempt smart reuse
        if source_chunks and self._is_backup_service():
            yield from self._chunk_with_reuse(files, source_chunks)
            return

        # Normal chunking logic
        if force_parallel or (
            self.settings.enable_parallel and len(files) >= self.settings.parallel_threshold
        ):
            yield from chunk_files_parallel(
                files,
                self.governor,
                max_workers=max_workers,
                executor_type=executor_type,
                tokenizer=self.tokenizer,
            )
        else:
            yield from self._chunk_sequential(files)

    def _chunk_with_reuse(
        self, files: list[DiscoveredFile], source_chunks: dict[Path, list[CodeChunk]]
    ) -> Iterator[tuple[Path, list[CodeChunk]]]:
        """Smart reuse logic for backup scenarios."""
        for file in files:
            chunks = source_chunks.get(file.path)
            if self._can_reuse_chunks(chunks):
                logger.debug("Reusing chunks for %s", file.path)
                yield (file.path, chunks)  # type: ignore
            else:
                yield from self._chunk_sequential([file])

    def can_reuse_chunks(self, chunks: list[CodeChunk] | None) -> bool:
        """Check if existing chunks fit in backup model context (public API)."""
        return self._can_reuse_chunks(chunks)

    def _can_reuse_chunks(self, chunks: list[CodeChunk] | None) -> bool:
        """Check if existing chunks fit in backup model context."""
        if not chunks:
            return False

        max_tokens = self.governor.max_chunk_tokens
        return all(self.tokenizer.count_tokens(chunk.content) <= max_tokens for chunk in chunks)

    def _chunk_sequential(
        self, files: list[DiscoveredFile]
    ) -> Iterator[tuple[Path, list[CodeChunk]]]:
        """Sequential chunking with fallback."""
        for file in files:
            try:
                chunker = self._selector.select_for_file(file)
                content = file.absolute_path.read_text(encoding="utf-8", errors="ignore")

                try:
                    chunks = chunker.chunk(content, file=file)
                except ChunkingError:
                    language = (
                        file.ext_kind.language.variable
                        if file.ext_kind and file.ext_kind.language
                        else "unknown"
                    )
                    fallback_chunker = DelimiterChunker(self.governor, language=language)
                    chunks = fallback_chunker.chunk(content, file=file)

                yield (file.path, chunks)
            except Exception:
                logger.warning("Skipping file %s: chunking failed", file.path, exc_info=True)

    def chunk_file(self, file: DiscoveredFile) -> list[CodeChunk]:
        """Chunk a single file."""
        return next(iter(self._chunk_sequential([file])))[1]


__all__ = ("ChunkingService",)
