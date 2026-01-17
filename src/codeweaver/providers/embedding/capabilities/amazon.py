# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Capabilities for Amazon embedding models."""

from __future__ import annotations

from codeweaver.core import Provider, dependency_provider
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities


class AmazonEmbeddingCapabilities(EmbeddingModelCapabilities):
    """Capabilities for Amazon embedding models."""


@dependency_provider(AmazonEmbeddingCapabilities, scope="singleton", collection=True)
def get_amazon_embedding_capabilities() -> tuple[AmazonEmbeddingCapabilities, ...]:
    """Get the capabilities for Amazon embedding models."""
    return (
        AmazonEmbeddingCapabilities.model_validate({
            "name": "amazon.titan-embed-text-v2:0",
            "provider": Provider.BEDROCK,
            "version": 2,
            "default_dimension": 1024,
            "output_dimensions": (1024, 512, 256),
            "default_dtype": "float",
            "output_dtypes": (
                "float",
                "binary",
            ),  # In this context, "binary" means "integer" -- probably "uint8"
            "supports_custom_prompts": False,
            "is_normalized": False,  # it can be, but isn't by default
            "context_window": 8192,
            "supports_context_chunk_embedding": True,
            # we don't know what tokenizer they use, but they do return token counts
            "tokenizer": "tiktoken",
            "tokenizer_model": "o200k_base",  # just our default if we need to guess; it'll be close enough
            "preferred_metrics": (
                "dot",
                "cosine",
            ),  # we normalize by default, so dot and cosine are equivalent
        }),
    )


__all__ = ("get_amazon_embedding_capabilities",)
