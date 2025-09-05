# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Capabilities for Amazon embedding models."""

from codeweaver._settings import Provider
from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities


def get_amazon_embedding_capabilities() -> tuple[EmbeddingModelCapabilities]:
    """Get the capabilities for Amazon embedding models."""
    return (
        EmbeddingModelCapabilities.model_validate({
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
            "tokenizer_model": "cl100k_base",  # just our default if we need to guess; it'll be close enough
            "preferred_metrics": (
                "dot",
                "cosine",
            ),  # we normalize by default, so dot and cosine are equivalent
        }),
    )
