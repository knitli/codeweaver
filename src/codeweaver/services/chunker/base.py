# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Base chunker service definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Annotated

from pydantic import ConfigDict, Field, PositiveInt, computed_field

from codeweaver._common import BasedModel
from codeweaver._data_structures import CodeChunk
from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.reranking.capabilities.base import RerankingModelCapabilities


class ChunkGovernor(BasedModel):
    """Configuration for chunking behavior."""

    model_config = BasedModel.model_config | ConfigDict(validate_assignment=True, defer_build=True)

    capabilities: Annotated[
        tuple[EmbeddingModelCapabilities | RerankingModelCapabilities, ...],
        Field(default=(), description="The model capabilities to infer chunking behavior from."),
    ]

    @computed_field
    @property
    def chunk_limit(self) -> PositiveInt:
        """The absolute maximum chunk size in tokens."""
        return min(capability.context_window for capability in self.capabilities)

    @computed_field
    @property
    def simple_overlap(self) -> int:
        """A simple overlap value to use for chunking without context or external factors.

        Calculates as 20% of the chunk_limit, clamped between 50 and 200 tokens. Practically, we only use this value when we can't determine a better overlap based on the tokenizer or other factors. `ChunkMicroManager` may override this value based on more complex logic, aiming to identify and encapsulate logical boundaries within the text with no need for overlap.
        """
        return int(max(50, min(200, self.chunk_limit * 0.2)))


class ChunkMicroManager:
    """Handles decision logic based on factors like chunk size and type, max chunk_size, etc. Deciding on where definitive splits should occur at a per-chunk basis."""

    def __init__(self, governor: ChunkGovernor) -> None:
        """Initialize the ChunkMicroManager with a ChunkGovernor. The governor provides the limits and settings for chunking."""
        self._governor = governor

    def governor(self) -> ChunkGovernor:
        """Get the ChunkGovernor instance."""
        return self._governor

    def decide_chunking(self, text: str) -> list[str]:
        """Decide how to chunk the text based on the governor's settings."""
        # Implement decision logic here
        return []


class BaseChunkerService(ABC):
    """Abstract base class for chunker services."""

    @abstractmethod
    def chunk(self, text: str) -> tuple[CodeChunk, ...]:
        """Chunk the input into smaller segments."""

    @abstractmethod
    def get_chunk_size(self) -> int:
        """Get the size of each chunk."""
