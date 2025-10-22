# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for Alibaba-NLP embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations

from typing import Literal

from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingCapabilities,
    EmbeddingModelCapabilities,
    PartialCapabilities,
)
from codeweaver.providers.provider import Provider


type AlibabaNlpProvider = Literal[
    Provider.GROQ, Provider.HUGGINGFACE_INFERENCE, Provider.SENTENCE_TRANSFORMERS, Provider.TOGETHER
]

CAP_MAP: dict[
    Literal["Alibaba-NLP/gte-modernbert-base", "Alibaba-NLP/gte-multilingual-base"],
    tuple[AlibabaNlpProvider, ...],
] = {
    "Alibaba-NLP/gte-modernbert-base": (
        Provider.GROQ,
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
        Provider.TOGETHER,
    ),
    "Alibaba-NLP/gte-multilingual-base": (Provider.SENTENCE_TRANSFORMERS,),
}


ALIBABA_NLP_GTE_MODERNBERT_BASE_CAPABILITIES: PartialCapabilities = {
    "name": "Alibaba-NLP/gte-modernbert-base",
    "default_dimension": 768,
    "context_window": 8192,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Alibaba-NLP/gte-modernbert-base",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "Alibaba-NLP/gte-modernbert-base",
            "revision": "7ca8b4ca700621b67618669f5378fe5f5820b8e4",
        },
        "memory_usage_mb": 284,
        "modalities": ["text"],
        "n_parameters": 149000000,
        "open_weights": True,
        "reference": "https://huggingface.co/Alibaba-NLP/gte-modernbert-base",
        "release_date": "2025-01-21",
        "revision": "7ca8b4ca700621b67618669f5378fe5f5820b8e4",
        "memory_usage_gb": 0.28,
    },
}

ALIBABA_NLP_GTE_MULTILINGUAL_BASE_CAPABILITIES: PartialCapabilities = {
    "name": "Alibaba-NLP/gte-multilingual-base",
    "default_dimension": 768,
    "context_window": 8192,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Alibaba-NLP/gte-multilingual-base",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "Alibaba-NLP/gte-multilingual-base",
            "revision": "ca1791e0bcc104f6db161f27de1340241b13c5a4",
        },
        "memory_usage_mb": 582,
        "modalities": ["text"],
        "n_parameters": 305000000,
        "open_weights": True,
        "reference": "https://huggingface.co/Alibaba-NLP/gte-multilingual-base",
        "release_date": "2024-07-20",
        "revision": "ca1791e0bcc104f6db161f27de1340241b13c5a4",
        "memory_usage_gb": 0.57,
    },
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    ALIBABA_NLP_GTE_MODERNBERT_BASE_CAPABILITIES,
    ALIBABA_NLP_GTE_MULTILINGUAL_BASE_CAPABILITIES,
)


def get_alibaba_nlp_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for Alibaba-NLP embedding models."""
    capabilities: list[EmbeddingCapabilities] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilities({**cap, "provider": provider})  # pyright: ignore[reportArgumentType]
            for provider in CAP_MAP[cap["name"]]  # pyright: ignore[reportArgumentType]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)


__all__ = ("get_alibaba_nlp_embedding_capabilities",)
