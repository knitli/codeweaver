# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Chunker services for embeddings and vector storage."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.engine.chunker._logging import (
        get_name,
        log_chunking_completed,
        log_chunking_deduplication,
        log_chunking_edge_case,
        log_chunking_failed,
        log_chunking_fallback,
        log_chunking_performance_warning,
        log_chunking_resource_limit,
    )
    from codeweaver.engine.chunker.base import (
        ACCEPTABLE_OVERAGE_RATIO,
        FLOOR_RATIO,
        MIN_FLOOR,
        MIN_VIABLE_CHUNK,
        RETRIEVAL_OPTIMAL,
        SAFETY_MARGIN,
        SMALL_MODEL_RATIO,
        TRANSITION_POINT,
        AdaptiveChunkBehavior,
        BaseChunker,
        ChunkGovernor,
    )
    from codeweaver.engine.chunker.delimiter import (
        CHARS_PER_TOKEN,
        MIN_LINES_FOR_PARAGRAPH_SPLIT,
        PERFORMANCE_THRESHOLD_MS,
        SLIDING_WINDOW_OVERLAP,
        BinaryFileError,
        ChunkingError,
        ChunkLimitExceededError,
        DelimiterChunker,
        ParseError,
        StringParseState,
    )
    from codeweaver.engine.chunker.delimiter_model import Boundary, Delimiter, DelimiterMatch
    from codeweaver.engine.chunker.delimiters import MappingProxyType
    from codeweaver.engine.chunker.delimiters.custom import SettingsDep
    from codeweaver.engine.chunker.delimiters.families import (
        PatternKey,
        detect_family_characteristics,
        detect_language_family,
        get_family_patterns,
    )
    from codeweaver.engine.chunker.delimiters.patterns import expand_pattern
    from codeweaver.engine.chunker.exceptions import (
        Any,
        ASTDepthExceededError,
        ChunkingTimeoutError,
        CodeWeaverError,
        OversizedChunkError,
    )
    from codeweaver.engine.chunker.governance import ResourceGovernor
    from codeweaver.engine.chunker.parallel import chunk_files_parallel, chunk_files_parallel_dict
    from codeweaver.engine.chunker.registry import ONE_MEGABYTE, SourceIdRegistry
    from codeweaver.engine.chunker.selector import ChunkerSelector, GracefulChunker
    from codeweaver.engine.chunker.semantic import SemanticChunker, StatisticsDep

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ACCEPTABLE_OVERAGE_RATIO": (__spec__.parent, "base"),
    "CHARS_PER_TOKEN": (__spec__.parent, "delimiter"),
    "FLOOR_RATIO": (__spec__.parent, "base"),
    "MIN_FLOOR": (__spec__.parent, "base"),
    "MIN_LINES_FOR_PARAGRAPH_SPLIT": (__spec__.parent, "delimiter"),
    "MIN_VIABLE_CHUNK": (__spec__.parent, "base"),
    "ONE_MEGABYTE": (__spec__.parent, "registry"),
    "PERFORMANCE_THRESHOLD_MS": (__spec__.parent, "delimiter"),
    "RETRIEVAL_OPTIMAL": (__spec__.parent, "base"),
    "SAFETY_MARGIN": (__spec__.parent, "base"),
    "SLIDING_WINDOW_OVERLAP": (__spec__.parent, "delimiter"),
    "SMALL_MODEL_RATIO": (__spec__.parent, "base"),
    "TRANSITION_POINT": (__spec__.parent, "base"),
    "AdaptiveChunkBehavior": (__spec__.parent, "base"),
    "Any": (__spec__.parent, "exceptions"),
    "BaseChunker": (__spec__.parent, "base"),
    "BinaryFileError": (__spec__.parent, "delimiter"),
    "Boundary": (__spec__.parent, "delimiter_model"),
    "ChunkerSelector": (__spec__.parent, "selector"),
    "ChunkGovernor": (__spec__.parent, "base"),
    "ChunkingError": (__spec__.parent, "delimiter"),
    "ChunkingTimeoutError": (__spec__.parent, "exceptions"),
    "ChunkLimitExceededError": (__spec__.parent, "delimiter"),
    "CodeWeaverError": (__spec__.parent, "exceptions"),
    "Delimiter": (__spec__.parent, "delimiter_model"),
    "DelimiterChunker": (__spec__.parent, "delimiter"),
    "DelimiterMatch": (__spec__.parent, "delimiter_model"),
    "GracefulChunker": (__spec__.parent, "selector"),
    "MappingProxyType": (__spec__.parent, "delimiters"),
    "OversizedChunkError": (__spec__.parent, "exceptions"),
    "ParseError": (__spec__.parent, "delimiter"),
    "ResourceGovernor": (__spec__.parent, "governance"),
    "SemanticChunker": (__spec__.parent, "semantic"),
    "SettingsDep": (__spec__.parent, "delimiters.custom"),
    "SourceIdRegistry": (__spec__.parent, "registry"),
    "StatisticsDep": (__spec__.parent, "semantic"),
    "StringParseState": (__spec__.parent, "delimiter"),
    "ASTDepthExceededError": (__spec__.parent, "exceptions"),
    "chunk_files_parallel": (__spec__.parent, "parallel"),
    "chunk_files_parallel_dict": (__spec__.parent, "parallel"),
    "detect_family_characteristics": (__spec__.parent, "delimiters.families"),
    "detect_language_family": (__spec__.parent, "delimiters.families"),
    "expand_pattern": (__spec__.parent, "delimiters.patterns"),
    "get_family_patterns": (__spec__.parent, "delimiters.families"),
    "get_name": (__spec__.parent, "_logging"),
    "log_chunking_completed": (__spec__.parent, "_logging"),
    "log_chunking_deduplication": (__spec__.parent, "_logging"),
    "log_chunking_edge_case": (__spec__.parent, "_logging"),
    "log_chunking_failed": (__spec__.parent, "_logging"),
    "log_chunking_fallback": (__spec__.parent, "_logging"),
    "log_chunking_performance_warning": (__spec__.parent, "_logging"),
    "log_chunking_resource_limit": (__spec__.parent, "_logging"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "ACCEPTABLE_OVERAGE_RATIO",
    "CHARS_PER_TOKEN",
    "FLOOR_RATIO",
    "MIN_FLOOR",
    "MIN_LINES_FOR_PARAGRAPH_SPLIT",
    "MIN_VIABLE_CHUNK",
    "ONE_MEGABYTE",
    "PERFORMANCE_THRESHOLD_MS",
    "RETRIEVAL_OPTIMAL",
    "SAFETY_MARGIN",
    "SLIDING_WINDOW_OVERLAP",
    "SMALL_MODEL_RATIO",
    "TRANSITION_POINT",
    "ASTDepthExceededError",
    "AdaptiveChunkBehavior",
    "Any",
    "BaseChunker",
    "BinaryFileError",
    "Boundary",
    "ChunkGovernor",
    "ChunkLimitExceededError",
    "ChunkerSelector",
    "ChunkingError",
    "ChunkingTimeoutError",
    "CodeWeaverError",
    "Delimiter",
    "DelimiterChunker",
    "DelimiterMatch",
    "GracefulChunker",
    "MappingProxyType",
    "OversizedChunkError",
    "ParseError",
    "PatternKey",
    "ResourceGovernor",
    "SemanticChunker",
    "SettingsDep",
    "SourceIdRegistry",
    "StatisticsDep",
    "StringParseState",
    "chunk_files_parallel",
    "chunk_files_parallel_dict",
    "detect_family_characteristics",
    "detect_language_family",
    "expand_pattern",
    "get_family_patterns",
    "get_name",
    "log_chunking_completed",
    "log_chunking_deduplication",
    "log_chunking_edge_case",
    "log_chunking_failed",
    "log_chunking_fallback",
    "log_chunking_performance_warning",
    "log_chunking_resource_limit",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
