# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Backup embedding model selection for failover scenarios.

This module provides hardcoded backup embedding model selection for vector reconciliation.
It handles fallback from cloud providers to local embedding models with automatic
dependency checking.

Models:
- Primary: minishlab/potion-base-8M (sentence-transformers)
- Fallback: jinaai/jina-embeddings-v2-small-en (fastembed)
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING, Literal

from codeweaver.core.constants import (
    BACKUP_EMBEDDING_MODEL_FALLBACK,
    BACKUP_EMBEDDING_MODEL_PRIMARY,
)
from codeweaver.core.types import ModelName, Provider
from codeweaver.core.utils import has_package


if TYPE_CHECKING:
    from codeweaver.providers.config import EmbeddingProviderSettings
    from codeweaver.providers.embedding.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)


def _check_sentence_transformers_available() -> bool:
    """Check if sentence-transformers is installed.

    Returns:
        True if sentence-transformers is available, False otherwise
    """
    return has_package("sentence_transformers") is not None


def _check_fastembed_available() -> bool:
    """Check if fastembed is installed.

    Returns:
        True if fastembed is available, False otherwise
    """
    return has_package("fastembed") is not None and has_package("fastembed_gpu") is not None


async def get_backup_embedding_config(
    config_provider: Literal["sentence-transformers", "fastembed"],
) -> EmbeddingProviderSettings:
    """
    Get backup embedding configuration based on available dependencies.

    This function attempts to create a backup embedding provider using:
    1. Primary: sentence-transformers with minishlab/potion-base-8M
    2. Fallback: fastembed with jinaai/jina-embeddings-v2-small-en

    Returns:
        EmbeddingProviderSettings instance if successful, None if no suitable provider available

    Raises:
        ConfigurationError: If provider creation fails unexpectedly
    """
    if config_provider == "sentence-transformers":
        from codeweaver.providers.config.clients import SentenceTransformersClientOptions
        from codeweaver.providers.config.embedding import SentenceTransformersEmbeddingConfig
        from codeweaver.providers.config.kinds import EmbeddingProviderSettings

        return EmbeddingProviderSettings(
            provider=Provider.SENTENCE_TRANSFORMERS,
            model_name=ModelName(BACKUP_EMBEDDING_MODEL_PRIMARY),
            connection=None,
            embedding_config=SentenceTransformersEmbeddingConfig(
                model_name=ModelName(BACKUP_EMBEDDING_MODEL_PRIMARY)
            ),
            client_options=SentenceTransformersClientOptions(
                model_name_or_path=BACKUP_EMBEDDING_MODEL_PRIMARY
            ),
        )
    if config_provider == "fastembed":
        from codeweaver.providers.config.clients import FastEmbedClientOptions
        from codeweaver.providers.config.embedding import FastEmbedEmbeddingConfig
        from codeweaver.providers.config.kinds import FastEmbedEmbeddingProviderSettings

        return FastEmbedEmbeddingProviderSettings(
            provider=Provider.FASTEMBED,
            model_name=ModelName(BACKUP_EMBEDDING_MODEL_FALLBACK),
            connection=None,
            embedding_config=FastEmbedEmbeddingConfig(
                model_name=ModelName(BACKUP_EMBEDDING_MODEL_FALLBACK)
            ),
            client_options=FastEmbedClientOptions(model_name=BACKUP_EMBEDDING_MODEL_FALLBACK),
        )
    raise ValueError(f"Unknown config provider: {config_provider}")


async def get_backup_embedding_provider() -> EmbeddingProvider | None:
    """Get backup embedding provider based on available dependencies.

    This function attempts to create a backup embedding provider using:
    1. Primary: sentence-transformers with minishlab/potion-base-8M
    2. Fallback: fastembed with jinaai/jina-embeddings-v2-small-en

    Returns:
        EmbeddingProvider instance if successful, None if no suitable provider available

    Raises:
        ConfigurationError: If provider creation fails unexpectedly
    """
    from codeweaver.core.di.container import get_container
    from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager
    from codeweaver.providers.embedding.registry import EmbeddingRegistry

    container = get_container()
    registry = await container.resolve(EmbeddingRegistry)
    cache_manager = await container.resolve(EmbeddingCacheManager)
    # Try sentence-transformers first (preferred)
    if _check_sentence_transformers_available():
        try:
            logger.info(
                "Creating backup embedding provider with sentence-transformers: %s",
                BACKUP_EMBEDDING_MODEL_PRIMARY,
            )
            from codeweaver.providers.embedding.capabilities.minishlab import (
                get_minishlab_embedding_capabilities,
            )
            from codeweaver.providers.embedding.providers.sentence_transformers import (
                SentenceTransformersEmbeddingProvider,
            )

            # Create provider with minimal configuration
            config = await get_backup_embedding_config("sentence-transformers")
            client = await config.get_client()
            provider = SentenceTransformersEmbeddingProvider(
                client=client,  # Will be created internally
                config=config,
                caps=next(
                    cap
                    for cap in get_minishlab_embedding_capabilities()
                    if cap.name == BACKUP_EMBEDDING_MODEL_PRIMARY
                ),
                cache_manager=cache_manager,
                registry=registry,
            )

            # Initialize the provider
            await provider.initialize_async()

            logger.info(
                "Successfully created backup embedding provider: sentence-transformers/%s",
                BACKUP_EMBEDDING_MODEL_PRIMARY,
            )
        except Exception as e:
            logger.warning(
                "Failed to create sentence-transformers backup provider: %s. Trying fallback.", e
            )
        else:
            return provider

    # Try fastembed as fallback
    if _check_fastembed_available():
        try:
            logger.info(
                "Creating backup embedding provider with fastembed: %s",
                BACKUP_EMBEDDING_MODEL_FALLBACK,
            )
            from codeweaver.providers.embedding.capabilities.jinaai import (
                get_jinaai_embedding_capabilities,
            )
            from codeweaver.providers.embedding.providers.fastembed import (
                FastEmbedEmbeddingProvider,
            )

            # create the config
            config = await get_backup_embedding_config("fastembed")
            client = await config.get_client()

            provider = FastEmbedEmbeddingProvider(
                client=client,
                config=config,
                caps=next(
                    cap
                    for cap in get_jinaai_embedding_capabilities()
                    if cap.name == BACKUP_EMBEDDING_MODEL_FALLBACK
                ),
                cache_manager=cache_manager,
                registry=await registry,
            )

            # Initialize the provider
            await provider.initialize_async()

            logger.info(
                "Successfully created backup embedding provider: fastembed/%s",
                BACKUP_EMBEDDING_MODEL_FALLBACK,
            )

        except Exception as e:
            logger.warning("Failed to create fastembed backup provider: %s", e)
        else:
            return provider
    # No backup provider available
    logger.warning(
        "No backup embedding provider available. Install sentence-transformers or fastembed."
    )
    return None


async def create_backup_embeddings(text: str | list[str]) -> list[list[float]] | None:
    """Create backup embeddings for given text(s).

    This is a convenience function that creates a provider and generates embeddings
    in a single call. For better performance with multiple calls, use
    get_backup_embedding_provider() and reuse the provider instance.

    Args:
        text: Single text or list of texts to embed

    Returns:
        List of embedding vectors, or None if provider unavailable

    Example:
        >>> embeddings = await create_backup_embeddings("example text")
        >>> if embeddings:
        ...     print(f"Generated {len(embeddings)} embeddings")
    """
    provider = await get_backup_embedding_provider()
    if provider is None:
        return None

    try:
        # Normalize input to list
        texts = [text] if isinstance(text, str) else text

        # Generate embeddings
        result = await provider.embed_query(texts)

        # Handle potential error response
        if isinstance(result, dict) and "error" in result:
            logger.warning("Backup embedding failed: %s", result.get("error"))
            return None
    except Exception as e:
        logger.warning("Failed to create backup embeddings: %s", e)
        return None
    else:
        return result  # ty:ignore[invalid-return-type]

    finally:
        # Cleanup provider resources
        if hasattr(provider, "cleanup"):
            await provider.cleanup()


def get_backup_model_info() -> dict[str, str | bool]:
    """Get information about configured backup models.

    Returns:
        Dictionary with backup model configuration details

    Example:
        >>> info = get_backup_model_info()
        >>> print(f"Primary: {info['primary_model']}")
        Primary: minishlab/potion-base-8M
    """
    return {
        "primary_model": BACKUP_EMBEDDING_MODEL_PRIMARY,
        "primary_framework": "sentence-transformers",
        "fallback_model": BACKUP_EMBEDDING_MODEL_FALLBACK,
        "fallback_framework": "fastembed",
        "sentence_transformers_available": _check_sentence_transformers_available(),
        "fastembed_available": _check_fastembed_available(),
    }


__all__ = ("get_backup_embedding_provider",)
