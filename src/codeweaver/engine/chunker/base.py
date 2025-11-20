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

import contextlib
import logging

from abc import ABC, abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Annotated, Any, cast

from pydantic import ConfigDict, Field, PositiveInt, PrivateAttr, computed_field

# Import ChunkerSettings at runtime for model rebuild to work
from codeweaver.config.chunker import ChunkerSettings
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import InitializationError
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


if TYPE_CHECKING:
    from codeweaver.core.discovery import DiscoveredFile


logger = logging.getLogger(__name__)


def _get_chunker_settings() -> ChunkerSettings:
    """Retrieve the chunker settings."""
    from codeweaver.config.settings import get_settings

    cw_settings = get_settings()
    return (
        cw_settings.chunker
        if isinstance(cw_settings.chunker, ChunkerSettings)
        else ChunkerSettings()
    )


def _get_capabilities() -> (
    tuple[()]
    | tuple[EmbeddingModelCapabilities]
    | tuple[EmbeddingModelCapabilities, RerankingModelCapabilities]
):
    """Retrieve the capabilities."""
    from codeweaver.common.registry.models import get_model_registry
    from codeweaver.providers.provider import ProviderKind

    registry = get_model_registry()
    embedding_caps = registry.configured_models_for_kind(ProviderKind.EMBEDDING)
    reranking_caps = registry.configured_models_for_kind(ProviderKind.RERANKING)
    if embedding_caps and reranking_caps:
        return (embedding_caps[0], reranking_caps[0])
    if embedding_caps:
        return (embedding_caps[0],)
    raise InitializationError(
        "Could not determine capabilities for embedding.",
        details={"embedding_caps": embedding_caps, "reranking_caps": reranking_caps},
        suggestions=[
            "If you have providers configured, submit an issue. It's probably a bug -- this is an alpha release :)"
        ],
    )


SAFETY_MARGIN = 0.1
"""A safety margin to apply to chunk sizes to account for metadata and tokenization variability."""


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

    def _telemetry_keys(self) -> None:
        return None

    def model_post_init(self, /, __context: Any) -> None:
        """Ensure models are rebuilt on first instantiation."""
        _rebuild_models()
        super().model_post_init(__context)

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
        from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities

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
        cls, backup_profile: dict[str, Any], settings: ChunkerSettings | None = None
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
        from codeweaver.providers.embedding.capabilities import (
            load_default_capabilities as load_embedding_caps,
        )
        from codeweaver.providers.reranking.capabilities import (
            load_default_capabilities as load_reranking_caps,
        )

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
                # Find matching capability
                for cap in load_embedding_caps():
                    if cap.name == model_name:
                        embedding_caps = cap
                        break

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
                # Find matching capability
                for cap in load_reranking_caps():
                    if cap.name == model_name:
                        reranking_caps = cap
                        break

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
            # Import ChunkerSettings to ensure it's available for rebuild
            # The import is safe here because ChunkerSettings imports are already resolved
            from codeweaver.config.chunker import ChunkerSettings as _ChunkerSettings
            from codeweaver.engine.chunker.delimiters.families import LanguageFamily
            from codeweaver.engine.chunker.delimiters.patterns import DelimiterPattern

            # Build namespace for model rebuild with all required types
            # ChunkGovernor needs ChunkerSettings, and BaseChunker methods use CodeChunk
            namespace = {
                "ChunkerSettings": _ChunkerSettings,
                "CodeChunk": CodeChunk,
                "DelimiterPattern": DelimiterPattern,
                "EmbeddingModelCapabilities": EmbeddingModelCapabilities,
                "LanguageFamily": LanguageFamily,
                "RerankingModelCapabilities": RerankingModelCapabilities,
            }
            _ = ChunkGovernor.model_rebuild(_types_namespace=namespace)
        _models_rebuilt = True
    except Exception as e:
        # If rebuild fails, model will still work but may have issues with ChunkerSettings
        logger.debug("Failed to rebuild ChunkGovernor model: %s", e, exc_info=True)


# Attempt to rebuild models at module level to resolve forward references
# This ensures models are ready before first instantiation in most cases
# NOTE: This happens after module-level imports are complete, but ChunkerSettings
# may rebuild itself during its module initialization, which would invalidate our rebuild.
# To handle this, we also call rebuild in model_post_init as a fallback.
with contextlib.suppress(Exception):
    _rebuild_models()

__all__ = ("BaseChunker", "ChunkGovernor")
