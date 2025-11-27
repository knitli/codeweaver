# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Settings for Google embedding models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities


def get_google_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the embedding capabilities for Google models.

    Note: Our default dimension for `gemini-embedding-001` is 768. Gemini-embedding-001 is capable of, and defaults to (for google, not us) 3072, but we prefer the smaller size for most use cases. The relevance hit is tiny (1% in our benchmarks), and the size reduction is significant (4x smaller).

    """
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    return (
        EmbeddingModelCapabilities(
            name="gemini-embedding-001",
            provider=Provider.GOOGLE,
            version=1,
            default_dimension=768,
            # We take the unusual step of defaulting to the smallest recommended dimension (768). The search performance hit is tiny -- 1% -- and you get a 4x smaller embedding size.
            output_dimensions=(3072, 1536, 768, 512, 256, 128),
            default_dtype="float",
            output_dtypes=("float",),
            is_normalized=False,  # only at 3072, otherwise needs to be normalized
            context_window=2048,
            supports_context_chunk_embedding=False,
            # Google uses an undisclosed tokenizer through an API call. We will use tiktoken as a *fallback* if API calls fail.
            tokenizer="tiktoken",
            tokenizer_model="cl100k_base",
            preferred_metrics=("cosine", "euclidean"),
            hf_name=None,
            other={},
        ),
    )


__all__ = ("get_google_embedding_capabilities",)
