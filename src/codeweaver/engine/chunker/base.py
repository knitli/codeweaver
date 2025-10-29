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

from abc import ABC, abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Annotated, Any, cast

from pydantic import ConfigDict, Field, PositiveInt, computed_field

from codeweaver.config.providers import EmbeddingProviderSettings, RerankingProviderSettings
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.types.models import BasedModel
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.provider import Provider
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
        tuple[EmbeddingModelCapabilities]
        | tuple[EmbeddingModelCapabilities, RerankingModelCapabilities],
        Field(description="""The model capabilities to infer chunking behavior from."""),
    ] = ()  # type: ignore[assignment]

    settings: Annotated[
        ChunkerSettings | None,
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

    def model_post_init(self, __context: Any) -> None:
        """Ensure models are rebuilt on first instantiation."""
        _rebuild_models()
        super().model_post_init(__context)

    @staticmethod
    def _get_provider_settings() -> tuple[
        EmbeddingProviderSettings, RerankingProviderSettings | None
    ]:
        from codeweaver.common.registry import get_provider_registry
        from codeweaver.providers.provider import ProviderKind

        registry = get_provider_registry()
        return (
            cast(
                EmbeddingProviderSettings,
                registry.get_configured_provider_settings(ProviderKind.EMBEDDING),
            ),
            cast(
                RerankingProviderSettings | None,
                registry.get_configured_provider_settings(ProviderKind.RERANKING),
            ),
        )

    @staticmethod
    def _get_providers(
        settings: EmbeddingProviderSettings | RerankingProviderSettings | None,
    ) -> Provider:
        from codeweaver.providers.provider import Provider

        return Provider.UNSET if settings is None else settings["provider"]

    @staticmethod
    def _get_caps_for_provider(
        settings: EmbeddingProviderSettings | RerankingProviderSettings, provider: Provider
    ) -> EmbeddingModelCapabilities | RerankingModelCapabilities | None:
        from codeweaver.common.registry import get_model_registry

        model_registry = get_model_registry()
        if (
            settings
            and (model_settings := settings.get("model_settings"))
            and (model_name := model_settings.get("model"))
        ):
            from codeweaver.common.registry import get_model_registry

            model_registry = get_model_registry()
            model_name = model_name
            if (
                any(
                    item
                    for item in ("dimension", "data_type", "model_kwargs")
                    if item in model_settings
                )
                and (caps := model_registry.get_embedding_capabilities(provider, model_name))
            ) or (
                not any(
                    item
                    for item in ("dimension", "data_type", "model_kwargs")
                    if item in model_settings
                )
                and (caps := model_registry.get_reranking_capabilities(provider, model_name))
            ):
                return caps[0]
        return None

    @classmethod
    def from_settings(cls, settings: ChunkerSettings) -> ChunkGovernor:
        """Create a ChunkGovernor from ChunkerSettings.

        Args:
            settings: The ChunkerSettings to create the governor from.

        Returns:
            A ChunkGovernor instance.
        """
        embedding_settings, reranking_settings = cls._get_provider_settings()
        embedding_provider = cls._get_providers(embedding_settings)
        reranking_provider = cls._get_providers(reranking_settings)
        embedding_caps = cls._get_caps_for_provider(embedding_settings, embedding_provider)
        if (
            reranking_settings
            and reranking_provider is not Provider.UNSET
            and (
                reranking_caps := cls._get_caps_for_provider(reranking_settings, reranking_provider)
            )
        ):
            caps = (embedding_caps, reranking_caps)
            if not embedding_caps or not reranking_caps:
                raise RuntimeError(
                    "Could not determine capabilities for embedding or reranking models."
                )
        elif embedding_caps:
            caps = (embedding_caps,)
        else:
            raise RuntimeError("Could not determine capabilities for embedding model.")
        return cls(
            capabilities=cast(
                tuple[EmbeddingModelCapabilities, RerankingModelCapabilities]
                | tuple[EmbeddingModelCapabilities],
                caps,
            ),
            settings=settings,
        )


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


__all__ = ("BaseChunker", "ChunkGovernor")


# Rebuild models to resolve forward references after all types are imported
# This is done lazily on first use to avoid circular import with settings module
_models_rebuilt = False


def _rebuild_models() -> None:
    """Rebuild pydantic models after all types are defined.

    This is called lazily on first use to avoid circular imports with the settings module.
    """
    global _models_rebuilt
    if _models_rebuilt:
        return

    logger = logging.getLogger(__name__)
    try:
        if not ChunkGovernor.__pydantic_complete__:
            from codeweaver.config.settings import get_settings

            chunk_settings = get_settings().chunker
            if not type(chunk_settings).__pydantic_complete__:
                _ = chunk_settings.model_rebuild()
            _ = ChunkGovernor.model_rebuild()
        _models_rebuilt = True
    except Exception as e:
        # If rebuild fails, model will still work but may have issues with ChunkerSettings
        logger.debug("Failed to rebuild ChunkGovernor model: %s", e, exc_info=True)
