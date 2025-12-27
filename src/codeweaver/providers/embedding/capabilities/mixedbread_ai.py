# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for mixedbread-ai embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from codeweaver.core.types.provider import Provider
from codeweaver.providers.embedding.capabilities.types import PartialCapabilities


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities


type MixedbreadAiProvider = Literal[Provider.OLLAMA]

CAP_MAP: dict[Literal["mixedbread-ai/mxbai-embed-large-v1"], tuple[MixedbreadAiProvider, ...]] = {
    "mixedbread-ai/mxbai-embed-large-v1": (Provider.OLLAMA,)
}


MXBAI_EMBED_LARGE_CAPABILITIES: PartialCapabilities = {
    "name": "mixedbread-ai/mxbai-embed-large-v1",
    "provider": CAP_MAP["mixedbread-ai/mxbai-embed-large-v1"][0],
    "default_dimension": 1024,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "mixedbread-ai/mxbai-embed-large-v1",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 1,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "mixedbread-ai/mxbai-embed-large-v1",
            "model_prompts": {"query": "Represent this sentence for searching relevant passages: "},
            "revision": "990580e27d329c7408b3741ecff85876e128e203",
        },
        "memory_usage_mb": 639,
        "modalities": ["text"],
        "n_parameters": 335000000,
        "open_weights": True,
        "reference": "https://huggingface.co/mixedbread-ai/mxbai-embed-large-v1",
        "release_date": "2024-03-07",
        "revision": "990580e27d329c7408b3741ecff85876e128e203",
        "memory_usage_gb": 0.62,
    },
    "hf_name": "mixedbread-ai/mxbai-embed-large-v1",
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (MXBAI_EMBED_LARGE_CAPABILITIES,)


def get_mixedbread_ai_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for mixedbread-ai embedding models."""
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    return (EmbeddingModelCapabilities.model_validate(MXBAI_EMBED_LARGE_CAPABILITIES),)


__all__ = ("get_mixedbread_ai_embedding_capabilities",)
