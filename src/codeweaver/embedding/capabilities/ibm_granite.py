# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for ibm-granite embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations

from typing import Literal

from codeweaver._settings import Provider
from codeweaver.embedding.capabilities.base import (
    EmbeddingCapabilities,
    EmbeddingModelCapabilities,
    PartialCapabilities,
)


type IbmGraniteProvider = Literal[
    Provider.HUGGINGFACE_INFERENCE, Provider.OLLAMA, Provider.SENTENCE_TRANSFORMERS
]

CAP_MAP: dict[
    Literal[
        "ibm-granite/granite-embedding-278m-multilingual",
        "ibm-granite/granite-embedding-30m-english",
        "ibm-granite/granite-embedding:278m",
        "ibm-granite/granite-embedding:30m",
    ],
    tuple[IbmGraniteProvider, ...],
] = {
    "ibm-granite/granite-embedding-278m-multilingual": (
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
    ),
    "ibm-granite/granite-embedding-30m-english": (Provider.SENTENCE_TRANSFORMERS,),
    "ibm-granite/granite-embedding:278m": (Provider.OLLAMA,),
    "ibm-granite/granite-embedding:30m": (Provider.OLLAMA,),
}


GRANITE_EMBEDDING_278M_CAPABILITIES: PartialCapabilities = {
    "name": "ibm-granite/granite-embedding-278m-multilingual",
    "default_dimension": 768,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "ibm-granite/granite-embedding-278m-multilingual",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "ibm-granite/granite-embedding-278m-multilingual",
            "revision": "84e3546b88b0cb69f8078608a1df558020bcbf1f",
        },
        "memory_usage_mb": 530,
        "modalities": ["text"],
        "n_parameters": 278000000,
        "open_weights": True,
        "reference": "https://huggingface.co/ibm-granite/granite-embedding-278m-multilingual",
        "release_date": "2024-12-18",
        "revision": "84e3546b88b0cb69f8078608a1df558020bcbf1f",
        "memory_usage_gb": 0.52,
    },
    "hf_name": "ibm-granite/granite-embedding-278m-multilingual",
}

GRANITE_EMBEDDING_30M_CAPABILITIES: PartialCapabilities = {
    "name": "ibm-granite/granite-embedding-30m-english",
    "default_dimension": 384,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "ibm-granite/granite-embedding-30m-english",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "ibm-granite/granite-embedding-30m-english",
            "revision": "eddbb57470f896b5f8e2bfcb823d8f0e2d2024a5",
        },
        "memory_usage_mb": 58,
        "modalities": ["text"],
        "n_parameters": 30000000,
        "open_weights": True,
        "reference": "https://huggingface.co/ibm-granite/granite-embedding-30m-english",
        "release_date": "2024-12-18",
        "revision": "eddbb57470f896b5f8e2bfcb823d8f0e2d2024a5",
        "memory_usage_gb": 0.06,
    },
    "hf_name": "ibm-granite/granite-embedding-30m-english",
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    GRANITE_EMBEDDING_278M_CAPABILITIES,
    GRANITE_EMBEDDING_30M_CAPABILITIES,
)


def get_ibm_granite_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for ibm-granite embedding models."""
    capabilities: list[EmbeddingCapabilities] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilities({**cap, "provider": provider})  # pyright: ignore[reportArgumentType]
            for provider in CAP_MAP[cap["name"]]  # pyright: ignore[reportArgumentType]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)
