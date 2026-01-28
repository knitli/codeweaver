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

import importlib

import logging

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.embedding.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)

# Hardcoded backup models - these are small, efficient models for local backup
BACKUP_MODEL_PRIMARY = "minishlab/potion-base-8M"
BACKUP_MODEL_FALLBACK = "jinaai/jina-embeddings-v2-small-en"


def _check_sentence_transformers_available() -> bool:
    """Check if sentence-transformers is installed.

    Returns:
        True if sentence-transformers is available, False otherwise
    """
    return importlib.util.find_spec("sentence_transformers") is not None


def _check_fastembed_available() -> bool:
    """Check if fastembed is installed.

    Returns:
        True if fastembed is available, False otherwise
    """
    return (
        importlib.util.find_spec("fastembed") is not None
        and importlib.util.find_spec("fastembed_gpu") is not None
    )


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
    # Try sentence-transformers first (preferred)
    if _check_sentence_transformers_available():
        try:
            logger.info(
                "Creating backup embedding provider with sentence-transformers: %s",
                BACKUP_MODEL_PRIMARY,
            )
            from codeweaver.providers.embedding.providers.sentence_transformers import (
                SentenceTransformersEmbeddingProvider,
            )
            from codeweaver.providers.config.clients import SentenceTransformersClientOptions

            # Create provider with minimal configuration
            provider = SentenceTransformersEmbeddingProvider(
                client=None,  # Will be created internally
                config={
                    "model_name": BACKUP_MODEL_PRIMARY,
                    "device": "cpu",  # Force CPU for backup to avoid GPU contention
                    "normalize_embeddings": True,
                },
                caps=None,  # Will auto-detect from model
            )

            # Initialize the provider
            await provider.initialize()

            logger.info(
                "Successfully created backup embedding provider: sentence-transformers/%s",
                BACKUP_MODEL_PRIMARY,
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
                "Creating backup embedding provider with fastembed: %s", BACKUP_MODEL_FALLBACK
            )
            from codeweaver.providers.embedding.providers.fastembed import (
                FastEmbedEmbeddingProvider,
            )
            from codeweaver.providers.config.clients import FastEmbedClientOptions

            # Create provider with minimal configuration
            provider = FastEmbedProvider(
                client=None,  # Will be created internally
                config={
                    "model_name": BACKUP_MODEL_FALLBACK,
                    "cache_dir": None,  # Use default cache
                },
                caps=None,  # Will auto-detect from model
            )

            # Initialize the provider
            await provider.initialize()

            logger.info(
                "Successfully created backup embedding provider: fastembed/%s",
                BACKUP_MODEL_FALLBACK,
            )
            return provider

        except Exception as e:
            logger.warning("Failed to create fastembed backup provider: %s", e)

    # No backup provider available
    logger.error(
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
        return await provider.embed_batch(texts)

    except Exception as e:
        logger.exception("Failed to create backup embeddings: %s", e)
        return None

    finally:
        # Cleanup provider resources
        if hasattr(provider, "cleanup"):
            await provider.cleanup()


def get_backup_model_info() -> dict[str, str]:
    """Get information about configured backup models.

    Returns:
        Dictionary with backup model configuration details

    Example:
        >>> info = get_backup_model_info()
        >>> print(f"Primary: {info['primary_model']}")
        Primary: minishlab/potion-base-8M
    """
    return {
        "primary_model": BACKUP_MODEL_PRIMARY,
        "primary_framework": "sentence-transformers",
        "fallback_model": BACKUP_MODEL_FALLBACK,
        "fallback_framework": "fastembed",
        "sentence_transformers_available": _check_sentence_transformers_available(),
        "fastembed_available": _check_fastembed_available(),
    }
