# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Settings for Google embedding models."""

from codeweaver._settings import Provider
from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities


def get_google_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the embedding capabilities for Google models.

    Note: Our default dimension for `gemini-embedding-001` is 768. It's capable of, and defaults to (for google, not us) 3072, but we prefer the smaller size for most use cases. The performance hit is tiny (1% in our benchmarks), and the size reduction is significant (4x smaller).

    """
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
            tokenizer="tokenizers",
            tokenizer_model="google/bert-base-uncased",
            preferred_metrics=("cosine", "euclidean"),
            hf_name=None,
            other={},
        ),
    )
