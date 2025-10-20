# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Chunker routing system for selecting appropriate chunking strategies."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import UUID7

from codeweaver._data_structures import CodeChunk, DiscoveredFile, Metadata, Span
from codeweaver._utils import estimate_tokens, uuid7
from codeweaver.services.chunker.registry import source_id_for


if TYPE_CHECKING:
    from codeweaver.services.chunker.base import ChunkGovernor


class EnhancedChunkMicroManager:
    """Enhanced micro manager that uses the existing ChunkMicroManager with langchain integration."""

    def __init__(self, governor: ChunkGovernor) -> None:
        """Initialize the micro manager.

        Args:
            governor: The chunk governor providing limits and configuration
        """

    def chunk_file(self, file: DiscoveredFile, content: str) -> list[CodeChunk]:
        """Chunk a file using the appropriate strategy.

        Args:
            file: The discovered file to chunk
            content: The file content to chunk

        Returns:
            List of CodeChunk objects
        """
        if not content.strip():
            return []

        # Perform final validation and adjustments
        return self._finalize_chunks(chunks)

    def _finalize_chunks(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Perform final validation and micro-adjustments on chunks.

        Steps:
        - Drop empty-content chunks
        - Enforce token budget via metadata trim and, if needed, re-splitting
        """
        non_empty = [c for c in chunks if c.content.strip()]
        return self._enforce_budget_on_chunks(non_empty)

    # Internal helpers to reduce complexity and keep logic testable
    def _effective_limits(self) -> tuple[int, int]:
        safety_margin_pct = 0.1
        effective_limit = int(self.governor.chunk_limit * (1 - safety_margin_pct))
        return effective_limit, self.governor.simple_overlap

    def _enforce_budget_on_chunks(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Ensure all chunks fit within the token budget."""
        effective_limit, _overlap = self._effective_limits()

        # Pass 1: trim metadata if needed, else resplit
        validated: list[CodeChunk] = []
        for chunk in chunks:
            if self._tokens_for_chunk(chunk) <= effective_limit:
                validated.append(chunk)
                continue
            if (chunk.metadata and not chunk.metadata.get("semantic_meta")) or not chunk.metadata:
                no_meta = self._copy_without_metadata(chunk)
                if self._tokens_for_chunk(no_meta) <= effective_limit:
                    validated.append(no_meta)
                    continue
            else:
                # we need to preserve semantic_meta, which is richer than the content
                # we'll try to split and encode them separately
                new_chunk = CodeChunk.model_construct(
                    _fields_set=chunk.model_fields_set,
                    **(
                        chunk.model_dump(mode="python", exclude={"metadata"})
                        | {"metadata": {"name": chunk.metadata.get("name") or "Unnamed chunk"}}
                    ),
                )
                if self._tokens_for_chunk(new_chunk) <= effective_limit:
                    validated.append(new_chunk)
                else:
                    validated.extend(self._resplit_chunk(new_chunk))
                _metadata_chunk = CodeChunk.model_construct(
                    _fields_set=chunk.model_fields_set,
                    **(
                        chunk.model_dump(mode="python", exclude={"content"})
                        | {
                            "content": "<EMPTY> [Metadata only]",
                            "metadata": {
                                "name": f"{chunk.metadata.get('name', 'Unnamed chunk')} (metadata only)"
                            },
                        }
                    ),
                )

                if self._tokens_for_chunk(_metadata_chunk) <= effective_limit:
                    validated.append(_metadata_chunk)
                continue

            validated.extend(self._resplit_chunk(chunk))
        return validated

    def _tokens_for_chunk(self, chunk: CodeChunk) -> int:
        data = chunk.serialize_for_embedding()
        text = (
            data.decode("utf-8", errors="ignore")
            if isinstance(data, bytes | bytearray)
            else str(data)
        )
        return estimate_tokens(text)

    def _copy_without_metadata(self, chunk: CodeChunk) -> CodeChunk:
        return CodeChunk.model_construct(
            content=chunk.content,
            line_range=chunk.line_range,
            file_path=chunk.file_path,
            language=chunk.language,
            source=chunk.source,
            ext_kind=chunk.ext_kind,
            timestamp=chunk.timestamp,
            chunk_id=chunk.chunk_id,
            parent_id=chunk.parent_id,
            metadata=None,
        )

    def _resplit_chunk(self, chunk: CodeChunk) -> list[CodeChunk]:
        """Resplit a chunk using langchain's RecursiveCharacterTextSplitter."""
        effective_limit, overlap = self._effective_limits()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=effective_limit,
            chunk_overlap=overlap,
            length_function=estimate_tokens,
            separators=["\n\n", "\n", ".", "!", "?", ";", " ", ""],
        )
        text_parts = splitter.split_text(chunk.content)
        if len(text_parts) <= 1:
            return [chunk]

        new_chunks: list[CodeChunk] = []
        current_line = chunk.line_range.start
        src_id: UUID7 | None = chunk.parent_id or (
            source_id_for(chunk.file_path) if chunk.file_path else None
        )
        if src_id is None:
            src_id = uuid7()

        for idx, part in enumerate(text_parts):
            if not part.strip():
                continue
            lines = part.count("\n") + 1
            start_line = current_line
            end_line = current_line + lines - 1

            name_base: str | None = None
            if chunk.metadata and (nm := chunk.metadata.get("name")):
                name_base = nm
            elif chunk.file_path:
                name_base = chunk.file_path.name

            meta: Metadata = {
                "chunk_id": chunk.chunk_id if idx == 0 else uuid7(),
                "created_at": datetime.now(UTC).timestamp(),
                "name": f"{name_base}, cont. {idx + 1}" if name_base else None,
                "semantic_meta": chunk.metadata.get("semantic_meta") if chunk.metadata else None,
                "tags": chunk.metadata.get("tags") if chunk.metadata else None,
            }

            new_chunk = CodeChunk.model_construct(
                content=part.rstrip(),
                line_range=Span(start_line, end_line, src_id),
                file_path=chunk.file_path,
                language=chunk.language,
                source=chunk.source,
                ext_kind=chunk.ext_kind,
                parent_id=src_id,
                metadata=meta,
            )
            new_chunks.append(new_chunk)
            current_line = end_line + 1

        return new_chunks

    @property
    def governor(self) -> ChunkGovernor:
        """Get the chunk governor."""
        return self._micro_manager._governor  # type: ignore
