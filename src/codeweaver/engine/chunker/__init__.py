# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Chunker services for embeddings and vector storage."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
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
    from codeweaver.engine.chunker.parallel import chunk_files_parallel, chunk_files_parallel_dict
    from codeweaver.engine.chunker.registry import (
        SourceIdRegistry,
        clear_store,
        get_store,
        source_id_for,
    )
    from codeweaver.engine.chunker.selector import ChunkerSelector, GracefulChunker
    from codeweaver.engine.chunker.semantic import SemanticChunker

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ASTDepthExceededError": (__spec__.parent, "exceptions"),
    "BinaryFileError": (__spec__.parent, "exceptions"),
    "Boundary": (__spec__.parent, "delimiter_model"),
    "ChunkGovernor": (__spec__.parent, "base"),
    "ChunkLimitExceededError": (__spec__.parent, "exceptions"),
    "ChunkerSelector": (__spec__.parent, "selector"),
    "ChunkingError": (__spec__.parent, "exceptions"),
    "ChunkingTimeoutError": (__spec__.parent, "exceptions"),
    "Delimiter": (__spec__.parent, "delimiter_model"),
    "DelimiterChunker": (__spec__.parent, "delimiter"),
    "DelimiterMatch": (__spec__.parent, "delimiter_model"),
    "DelimiterPattern": (__spec__.parent, "delimiters"),
    "GracefulChunker": (__spec__.parent, "selector"),
    "LanguageFamily": (__spec__.parent, "delimiters"),
    "OversizedChunkError": (__spec__.parent, "exceptions"),
    "ParseError": (__spec__.parent, "exceptions"),
    "ResourceGovernor": (__spec__.parent, "governance"),
    "SemanticChunker": (__spec__.parent, "semantic"),
    "SourceIdRegistry": (__spec__.parent, "registry"),
    "chunk_files_parallel": (__spec__.parent, "parallel"),
    "chunk_files_parallel_dict": (__spec__.parent, "parallel"),
    "clear_store": (__spec__.parent, "registry"),
    "detect_language_family": (__spec__.parent, "delimiters"),
    "expand_pattern": (__spec__.parent, "delimiters"),
    "get_store": (__spec__.parent, "registry"),
    "source_id_for": (__spec__.parent, "registry"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the chunker package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


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


def __dir__() -> list[str]:
    """List available attributes for the chunker package."""
    return list(__all__)
