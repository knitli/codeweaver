# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Base chunker services and definitions.

CodeWeaver has a robust chunking system that allows it to extract meaningful information from any codebase. Chunks are created based on a graceful degradation strategy:

1. **Semantic Chunking**: When we have a tree-sitter grammar for a language (there are currently 26 supported languages, see `codeweaver.language.SemanticSearchLanguage`), semantic chunking is the primary strategy.

2. **Delimiter Chunking**: If semantic chunking isn't available or fails (e.g., parse errors, oversized nodes without chunkable children), we fall back to delimiter-based chunking using language-specific patterns.

3. **Generic Fallback**: If delimiter patterns don't match, we use generic delimiters (braces, newlines, etc.) to ensure we can always produce chunks.

This multi-tiered approach ensures reliable chunking across 170+ languages while maintaining semantic quality for supported languages.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import ConfigDict, Field, PositiveInt, computed_field

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.types.models import BasedModel
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities

if TYPE_CHECKING:
    from codeweaver.config.chunker import ChunkerSettings
    from codeweaver.core.discovery import DiscoveredFile


SAFETY_MARGIN = 0.1
"""A safety margin to apply to chunk sizes to account for metadata and tokenization variability."""


class ChunkGovernor(BasedModel):
    """Configuration for chunking behavior."""

    model_config = BasedModel.model_config | ConfigDict(validate_assignment=True, defer_build=True)

    capabilities: Annotated[
        tuple[EmbeddingModelCapabilities | RerankingModelCapabilities, ...],
        Field(description="""The model capabilities to infer chunking behavior from."""),
    ] = ()

    settings: Annotated[
        "ChunkerSettings | None",
        Field(default=None, description="""Chunker configuration settings."""),
    ] = None

    @computed_field
    @cached_property
    def chunk_limit(self) -> PositiveInt:
        """The absolute maximum chunk size in tokens."""
        return min(capability.context_window for capability in self.capabilities)

    @computed_field
    @cached_property
    def simple_overlap(self) -> int:
        """A simple overlap value to use for chunking without context or external factors.

        Calculates as 20% of the chunk_limit, clamped between 50 and 200 tokens. Practically, we only use this value when we can't determine a better overlap based on the tokenizer or other factors. `ChunkGovernor` may override this value based on more complex logic, aiming to identify and encapsulate logical boundaries within the text with no need for overlap.
        """
        return int(max(50, min(200, self.chunk_limit * 0.2)))

    def _telemetry_keys(self) -> None:
        return None


class BaseChunker(ABC):
    """Base class for chunkers."""

    _governor: ChunkGovernor

    def __init__(self, governor: ChunkGovernor) -> None:
        """Initialize the chunker."""
        self._governor = governor

    @abstractmethod
    def chunk(
        self, content: str, *, file: DiscoveredFile | None = None, context: dict[str, Any] | None = None
    ) -> list[CodeChunk]:
        """Chunk the given content into code chunks using `self._governor` settings.

        Args:
            content: The text content to chunk.
            file: The DiscoveredFile object containing file metadata and source_id.
            context: Additional context for chunking.

        Returns:
            List of CodeChunk objects with source_id from the DiscoveredFile.
        """

    @property
    def governor(self) -> ChunkGovernor:
        """Get the ChunkGovernor instance."""
        return self._governor

    @property
    def chunk_limit(self) -> PositiveInt:
        """Get the chunk limit from the governor."""
        return self._governor.chunk_limit

    @property
    def simple_overlap(self) -> int:
        """Get the simple overlap from the governor."""
        return self._governor.simple_overlap


__all__ = ("BaseChunker", "ChunkGovernor")

# Rebuild models to resolve forward references after all types are imported
# This is done at module import time to ensure ChunkerSettings is available
def _rebuild_models() -> None:
    """Rebuild pydantic models after all types are defined."""
    try:
        # Import ChunkerSettings to make it available for model rebuild
        from codeweaver.config.chunker import ChunkerSettings  # noqa: F401

        ChunkGovernor.model_rebuild(force=True)
    except Exception:
        # If rebuild fails, model will still work but may have issues with ChunkerSettings
        pass


_rebuild_models()
