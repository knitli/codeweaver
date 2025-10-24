# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Mistral embedding capabilities."""

from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    PartialCapabilities,
)
from codeweaver.providers.provider import Provider


def get_mistral_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get Mistral embedding capabilities.

    NOTE: Like with the `voyage-code-3` model, we set the default dtype to `int8` for `codestral-embed`. Mistral's default, of course, is `float`.
    Like with voyage's model, codestral gets virtually no loss of retrieval quality when quantizing to int8, while getting a 4x reduction in storage and memory bandwidth.
    """
    shared: PartialCapabilities = {
        "provider": Provider.MISTRAL,
        "preferred_metrics": ("dot", "cosine", "euclidean"),
        "is_normalized": True,
        # Mistral uses its own `tekken` tokenizers, *but* they also return token counts from their API
        # So we will only fall back to tiktoken if we need to estimate token counts locally.
        # We didn't want to add another dependency just to get backup token counts.
        "tokenizer": "tiktoken",
        "tokenizer_model": "cl100k_base",
        "context_window": 8192,
        "supports_context_chunk_embedding": False,
        "hf_name": None,
        "other": {},
        "supports_custom_prompts": False,
        "custom_document_prompt": None,
        "custom_query_prompt": None,
    }
    base_mistral = {
        "name": "mistral-embed",
        "default_dimension": 1024,
        "output_dimensions": (1024,),
        "default_dtype": "float",
        "output_dtypes": ("float",),
    }
    codestral_caps = {
        "name": "codestral-embed",
        "default_dimension": 1536,
        "output_dimensions": (3072, 1536, 1024, 512),
        "output_dtypes": ("float", "int8", "uint8", "binary", "ubinary"),
        "default_dtype": "int8",
    }
    return tuple(
        EmbeddingModelCapabilities.model_validate({**shared, **d})
        for d in (base_mistral, codestral_caps)
    )


__all__ = ("get_mistral_embedding_capabilities",)
