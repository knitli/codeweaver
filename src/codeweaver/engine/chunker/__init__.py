# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Chunker services for embeddings and vector storage."""

from __future__ import annotations

from codeweaver.engine.chunker.base import ChunkGovernor
from codeweaver.engine.chunker.delimiter import DelimiterChunker
from codeweaver.engine.chunker.delimiter_model import Boundary, Delimiter, DelimiterMatch
from codeweaver.engine.chunker.delimiters import (
    DelimiterPattern,
    LanguageFamily,
    detect_language_family,
    expand_pattern,
)
from codeweaver.engine.chunker.exceptions import (
    ASTDepthExceededError,
    BinaryFileError,
    ChunkingError,
    ChunkingTimeoutError,
    ChunkLimitExceededError,
    OversizedChunkError,
    ParseError,
)
from codeweaver.engine.chunker.governance import ResourceGovernor
from codeweaver.engine.chunker.registry import (
    SourceIdRegistry,
    clear_store,
    get_store,
    source_id_for,
)
from codeweaver.engine.chunker.parallel import chunk_files_parallel, chunk_files_parallel_dict
from codeweaver.engine.chunker.selector import ChunkerSelector, GracefulChunker
from codeweaver.engine.chunker.semantic import SemanticChunker


__all__ = (
    "ASTDepthExceededError",
    "BinaryFileError",
    "Boundary",
    "ChunkGovernor",
    "ChunkLimitExceededError",
    "ChunkerSelector",
    "ChunkingError",
    "ChunkingTimeoutError",
    "Delimiter",
    "DelimiterChunker",
    "DelimiterMatch",
    "DelimiterPattern",
    "GracefulChunker",
    "LanguageFamily",
    "OversizedChunkError",
    "ParseError",
    "ResourceGovernor",
    "SemanticChunker",
    "SourceIdRegistry",
    "chunk_files_parallel",
    "chunk_files_parallel_dict",
    "clear_store",
    "detect_language_family",
    "expand_pattern",
    "get_store",
    "source_id_for",
)
