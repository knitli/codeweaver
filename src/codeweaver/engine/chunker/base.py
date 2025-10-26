# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Base chunker services and definitions.

CodeWeaver has a robust chunking system that allows it to extract meaningful information from any codebase. Chunks are created based on a few factors:

1. The kind of chunk available.

    - When we have a tree-sitter grammar for a language (there are currently 26 supported languages, see `codeweaver.language.SemanticSearchLanguage`), then semantic chunking is the primary strategy.
    - If semantic chunking isn't available, we fall back to specialized chunkers for the language, if we have one. These come from `langchain_text_splitters` and include chunkers for markdown, latex, protobuf, restructuredtext, perl, powershell, and visualbasic6.
    - If one of those isn't available, we again fall back to a set of chunkers defined in
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
    from codeweaver.config.settings import ChunkerSettings


SAFETY_MARGIN = 0.1
"""A safety margin to apply to chunk sizes to account for metadata and tokenization variability."""

SPLITTER_AVAILABLE = {
    "protobuf": "proto",
    "restructuredtext": "rst",
    "markdown": "markdown",
    "latex": "latex",
    "perl": "perl",
    "powershell": "powershell",
    "visualbasic6": "visualbasic6",
}
"""Languages with langchain_text_splitters support that don't have semantic search support. The keys are the name of the language as defined in `codeweaver._supported_languages.SecondarySupportedLanguage`, and the values are the name of the language as defined in `langchain_text_splitters.Language`."""


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

        Calculates as 20% of the chunk_limit, clamped between 50 and 200 tokens. Practically, we only use this value when we can't determine a better overlap based on the tokenizer or other factors. `ChunkMicroManager` may override this value based on more complex logic, aiming to identify and encapsulate logical boundaries within the text with no need for overlap.
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
        self, content: str, *, file_path: Path | None = None, context: dict[str, Any] | None = None
    ) -> list[CodeChunk]:
        """Chunk the given content into code chunks using `self._governor` settings."""

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
