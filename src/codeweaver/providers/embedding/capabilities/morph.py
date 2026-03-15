# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""MorphLLM embedding capability implementation."""

from __future__ import annotations

from codeweaver.core.types import Provider
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.capabilities.types import EmbeddingCapabilitiesDict


MORPH_LLM_EMBEDDING_V4_CAPABILITIES = EmbeddingCapabilitiesDict(
    name="morph-embedding-v4",
    provider=Provider.MORPH,
    version=4,
    default_dimension=1536,
    output_dimensions=(1536,),
    default_dtype="float",
    output_dtypes=("float",),
    is_normalized=False,
    context_window=4096,  # They don't specify context window, except saying it's large, this is the low limit of "large"
    max_batch_tokens=100_000,
    supports_context_chunk_embedding=False,
    preferred_metrics=("cosine", "dot", "euclidean"),
)


def get_morph_embedding_capabilities() -> tuple[EmbeddingModelCapabilities]:
    """Get the MorphLLM embedding capabilities.

    Returns:
        A list of MorphLLM embedding capabilities.
    """
    return (EmbeddingModelCapabilities.model_construct(**MORPH_LLM_EMBEDDING_V4_CAPABILITIES),)


__all__ = ("get_morph_embedding_capabilities",)
