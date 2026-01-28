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

import logging
import math

from abc import ABC, abstractmethod
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, Annotated, Any, cast

from pydantic import ConfigDict, Field, PositiveInt, PrivateAttr, computed_field

from codeweaver.core import BasedModel, CodeChunk


if TYPE_CHECKING:
    from codeweaver.core import DiscoveredFile
    from codeweaver.engine.config import ChunkerSettings

from codeweaver.providers import (
    EmbeddingModelCapabilities,
    ProviderSettingsDict,
    RerankingModelCapabilities,
)


logger = logging.getLogger(__name__)


SAFETY_MARGIN = 0.1
"""A safety margin to apply to chunk sizes to account for metadata and tokenization variability."""

# Adaptive chunking constants
RETRIEVAL_OPTIMAL = 600
"""LongEmbed benchmark sweet spot for retrieval quality (tokens)."""

MIN_VIABLE_CHUNK = 100
"""Minimum chunk size below which content becomes noise (tokens)."""

SMALL_MODEL_RATIO = 0.80
"""Use 80% of context window for small models."""

TRANSITION_POINT = 512
"""Context window size where we start transitioning to optimal (tokens)."""

ACCEPTABLE_OVERAGE_RATIO = 1.67
"""How much larger than optimal is acceptable before splitting (ratio)."""

FLOOR_RATIO = 0.15
"""Floor as percentage of optimal (ratio)."""

MIN_FLOOR = 50
"""Absolute minimum floor regardless of optimal (tokens)."""


class AdaptiveChunkBehavior(str, Enum):
    """Actions for adaptive chunk sizing.

    The adaptive chunking system classifies each chunk by size and determines
    the appropriate action:

    - KEEP: Chunk is within acceptable range, use as-is
    - MERGE: Chunk is too small, should combine with neighbors
    - TRY_CHILDREN: Chunk exceeds optimal, try semantic split first
    - FORCE_SPLIT: Chunk exceeds hard limit, must split mechanically
    """

    KEEP = "keep"
    MERGE = "merge"
    TRY_CHILDREN = "try_children"
    FORCE_SPLIT = "force_split"


class ChunkGovernor(BasedModel):
    """Configuration for chunking behavior."""

    model_config = BasedModel.model_config | ConfigDict(validate_assignment=True, defer_build=True)

    capabilities: Annotated[
        tuple[()]
        | tuple[EmbeddingModelCapabilities]
        | tuple[EmbeddingModelCapabilities, RerankingModelCapabilities],
        Field(description="""The model capabilities to infer chunking behavior from."""),
    ] = ()  # type: ignore[assignment]

    settings: Annotated[
        ChunkerSettings | None,
        Field(default=None, description="""Chunker configuration settings."""),
    ] = None

    _limit: Annotated[PositiveInt, PrivateAttr()] = 512

    _limit_established: Annotated[bool, PrivateAttr()] = False

    @computed_field
    @property
    def chunk_limit(self) -> PositiveInt:
        """The absolute maximum chunk size in tokens."""
        # Use default of 512 tokens when capabilities aren't available
        if not self._limit_established and self.capabilities:
            self._limit_established = True
            self._limit = min(
                capability.context_window
                for capability in self.capabilities
                if hasattr(capability, "context_window")
            )
        return self._limit

    @computed_field
    @cached_property
    def simple_overlap(self) -> int:
        """A simple overlap value to use for chunking without context or external factors.

        Calculates as 20% of the chunk_limit, clamped between 50 and 200 tokens. Practically, we only use this value when we can't determine a better overlap based on the tokenizer or other factors. `ChunkGovernor` may override this value based on more complex logic, aiming to identify and encapsulate logical boundaries within the text with no need for overlap.
        """
        return int(max(50, min(200, self.chunk_limit * 0.2)))

    @computed_field
    @cached_property
    def optimal_chunk_tokens(self) -> PositiveInt:
        """Target chunk size for best retrieval quality.

        Based on LongEmbed benchmarks, retrieval quality peaks around 500-800 tokens
        regardless of model context window. Larger context windows let you *accept*
        more tokens, but don't improve *retrieval* of relevant content.

        Scaling:
        - Small models (≤512 context): 80% of context window
        - Medium models (512-8192): logarithmic curve toward 600
        - Large models (8192+): capped at 600

        Examples:
        - all-MiniLM-L6-v2 (256 context) → 205 optimal
        - bge-small (512 context) → 410 optimal
        - bge-base (1024 context) → 457 optimal
        - voyage-code-3 (8192 context) → 600 optimal
        - voyage-3-large (32000 context) → 600 optimal
        - cohere-embed-v4 (128000 context) → 600 optimal
        """
        # Check for user override first
        if (
            self.settings is not None
            and hasattr(self.settings, "target_chunk_tokens")
            and (target := getattr(self.settings, "target_chunk_tokens", None)) is not None
        ):
            # Respect override but cap at context window
            return min(target, self.chunk_limit)

        context = self.chunk_limit

        if context <= TRANSITION_POINT:
            # Small models: use 80% of available context
            return max(MIN_VIABLE_CHUNK, int(context * SMALL_MODEL_RATIO))

        # Logarithmic transition from 410 (512*0.8) to 600
        # log2(1024/512) = 1, log2(8192/512) = 4
        log_factor = math.log2(context / TRANSITION_POINT)

        # Scale from 410 toward 600, reaching 600 at log_factor=4 (8192 tokens)
        base = int(TRANSITION_POINT * SMALL_MODEL_RATIO)  # 410
        headroom = RETRIEVAL_OPTIMAL - base  # 190

        scaled = base + headroom * min(1.0, log_factor / 4)

        return min(int(scaled), RETRIEVAL_OPTIMAL)

    @computed_field
    @cached_property
    def floor_tokens(self) -> PositiveInt:
        """Minimum viable chunk size.

        Chunks smaller than this are likely noise and should be merged with
        neighbors. Calculated as ~15% of optimal, with a minimum of 50 tokens.
        """
        return max(MIN_FLOOR, int(self.optimal_chunk_tokens * FLOOR_RATIO))

    @computed_field
    @cached_property
    def acceptable_max_tokens(self) -> PositiveInt:
        """Maximum chunk size before trying to split.

        Chunks larger than this should attempt semantic splitting (finding child
        boundaries). This is ~1.67x optimal, capped at the hard context limit.

        The 1.67x ratio allows capturing complete "context units" (e.g., a function
        that's slightly larger than optimal) without forcing unnecessary splits.
        """
        return min(int(self.optimal_chunk_tokens * ACCEPTABLE_OVERAGE_RATIO), self.chunk_limit)

    def classify_chunk_size(self, tokens: int) -> AdaptiveChunkBehavior:
        """Determine what action to take for a chunk of given size.

        Args:
            tokens: Estimated token count of the chunk

        Returns:
            AdaptiveChunkBehavior indicating the recommended action:
            - MERGE: tokens < floor_tokens (too small, combine with neighbors)
            - KEEP: floor_tokens <= tokens <= acceptable_max_tokens (good size)
            - TRY_CHILDREN: acceptable_max_tokens < tokens <= chunk_limit (try semantic split)
            - FORCE_SPLIT: tokens > chunk_limit (must split mechanically)
        """
        if tokens < self.floor_tokens:
            return AdaptiveChunkBehavior.MERGE
        if tokens <= self.acceptable_max_tokens:
            return AdaptiveChunkBehavior.KEEP
        if tokens <= self.chunk_limit:
            return AdaptiveChunkBehavior.TRY_CHILDREN
        return AdaptiveChunkBehavior.FORCE_SPLIT

    def _telemetry_keys(self) -> None:
        return None

    @staticmethod
    def _get_caps() -> (
        tuple[()]
        | tuple[EmbeddingModelCapabilities]
        | tuple[EmbeddingModelCapabilities, RerankingModelCapabilities]
    ):
        """Retrieve capabilities from provider settings."""
        capabilities = _get_capabilities()
        embedding_caps = next(
            (cap for cap in capabilities if isinstance(cap, EmbeddingModelCapabilities)), None
        )
        reranking_caps = next(
            (cap for cap in capabilities if isinstance(cap, RerankingModelCapabilities)), None
        )
        return (
            (embedding_caps, reranking_caps)
            if embedding_caps and reranking_caps
            else (embedding_caps,)
            if embedding_caps
            else ()
        )

    @classmethod
    def from_settings(cls, settings: ChunkerSettings) -> ChunkGovernor:
        """Create a ChunkGovernor from ChunkerSettings.

        Args:
            settings: The ChunkerSettings to create the governor from.

        Returns:
            A ChunkGovernor instance.
        """
        from codeweaver.providers import RerankingModelCapabilities

        capabilities = _get_capabilities()
        if len(capabilities) == 2:
            embedding_caps, reranking_caps = cast(
                tuple[EmbeddingModelCapabilities, RerankingModelCapabilities], capabilities
            )
            logger.debug(
                "Creating ChunkGovernor with embedding caps: %s and reranking caps: %s",
                embedding_caps,
                reranking_caps,
            )
            return cls(capabilities=(embedding_caps, reranking_caps), settings=settings)
        if len(capabilities) == 1:
            embedding_caps = cast(EmbeddingModelCapabilities, capabilities[0])  # ty: ignore[index-out-of-bounds]
            logger.debug("Creating ChunkGovernor with embedding caps: %s", embedding_caps)
            return cls(capabilities=(embedding_caps,), settings=settings)
        logger.warning("Could not determine capabilities from settings, using default chunk limits")
        return cls(capabilities=(), settings=settings)

    @classmethod
    def from_backup_profile(
        cls, backup_profile: ProviderSettingsDict, settings: ChunkerSettings | None = None
    ) -> ChunkGovernor:
        """Create a ChunkGovernor from backup profile settings.

        This method creates a governor with capabilities derived from the backup
        profile's embedding and reranking model settings. This is used to ensure
        chunks are sized appropriately for the backup models.

        Args:
            backup_profile: ProviderSettingsDict from get_profile("backup", "local")
            settings: Optional ChunkerSettings to use

        Returns:
            A ChunkGovernor instance configured for backup model constraints.
        """
        from codeweaver.engine.config import ChunkerSettings
        from codeweaver.providers.embedding.capabilities import EmbeddingCapabilityResolver
        from codeweaver.providers.reranking.capabilities import RerankingCapabilityResolver

        embedding_resolver = EmbeddingCapabilityResolver()
        reranking_resolver = RerankingCapabilityResolver()

        embedding_caps: EmbeddingModelCapabilities | None = None
        reranking_caps: RerankingModelCapabilities | None = None

        # Extract embedding model name from profile
        if (
            (embedding_settings := backup_profile.get("embedding"))
            and isinstance(embedding_settings, tuple)
            and len(embedding_settings) > 0
        ):
            first_setting = embedding_settings[0]
            if (model_settings := getattr(first_setting, "model_settings", None)) and (
                model_name := getattr(model_settings, "model", None)
            ):
                # Resolve capability by model name (returns None if not found)
                embedding_caps = cast(
                    EmbeddingModelCapabilities, embedding_resolver.resolve(model_name)
                )

        # Extract reranking model name from profile
        if (
            (reranking_settings := backup_profile.get("reranking"))
            and isinstance(reranking_settings, tuple)
            and len(reranking_settings) > 0
        ):
            first_setting = reranking_settings[0]
            if (model_settings := getattr(first_setting, "model_settings", None)) and (
                model_name := getattr(model_settings, "model", None)
            ):
                # Resolve capability by model name (returns None if not found)
                reranking_caps = reranking_resolver.resolve(model_name)

        # Build capabilities tuple
        if embedding_caps and reranking_caps:
            capabilities: (
                tuple[()]
                | tuple[EmbeddingModelCapabilities]
                | tuple[EmbeddingModelCapabilities, RerankingModelCapabilities]
            ) = (embedding_caps, reranking_caps)
            logger.debug(
                "Creating backup ChunkGovernor with embedding caps: %s (ctx: %d) "
                "and reranking caps: %s (ctx: %d)",
                embedding_caps.name,
                embedding_caps.context_window,
                reranking_caps.name,
                reranking_caps.context_window,
            )
        elif embedding_caps:
            capabilities = (embedding_caps,)
            logger.debug(
                "Creating backup ChunkGovernor with embedding caps only: %s (ctx: %d)",
                embedding_caps.name,
                embedding_caps.context_window,
            )
        else:
            capabilities = ()
            logger.warning(
                "Could not determine backup capabilities from profile, using default chunk limits"
            )

        return cls(capabilities=capabilities, settings=settings or ChunkerSettings())


class BaseChunker(ABC):
    """Base class for chunkers."""

    _governor: ChunkGovernor

    def __init__(self, governor: ChunkGovernor) -> None:
        """Initialize the chunker."""
        self._governor = governor

    @abstractmethod
    def chunk(
        self,
        content: str,
        *,
        file: DiscoveredFile | None = None,
        context: dict[str, Any] | None = None,
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


__all__ = ("AdaptiveChunkBehavior", "BaseChunker", "ChunkGovernor")


def _get_capabilities() -> tuple[Any, ...]:
    """Retrieve all configured model capabilities."""
    # TODO: Implement capability retrieval from provider registry
    return ()
