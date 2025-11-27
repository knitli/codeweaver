# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for ibm-granite embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from codeweaver.providers.embedding.capabilities.types import (
    EmbeddingCapabilitiesDict,
    PartialCapabilities,
)
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

type IbmGraniteProvider = Literal[
    Provider.HUGGINGFACE_INFERENCE, Provider.OLLAMA, Provider.SENTENCE_TRANSFORMERS
]

CAP_MAP: dict[
    Literal[
        "ibm-granite/granite-embedding-english-r2",
        "ibm-granite/granite-embedding-small-english-r2",
        "ibm-granite/granite-embedding-278m-multilingual",
        "ibm-granite/granite-embedding-30m-english",
        "ibm-granite/granite-embedding:278m",
        "ibm-granite/granite-embedding:30m",
    ],
    tuple[IbmGraniteProvider, ...],
] = {
    "ibm-granite/granite-embedding-english-r2": (Provider.SENTENCE_TRANSFORMERS,),
    "ibm-granite/granite-embedding-small-english-r2": (Provider.SENTENCE_TRANSFORMERS,),
    "ibm-granite/granite-embedding-278m-multilingual": (
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
    ),
    "ibm-granite/granite-embedding-30m-english": (Provider.SENTENCE_TRANSFORMERS,),
    "ibm-granite/granite-embedding:278m": (Provider.OLLAMA,),
    "ibm-granite/granite-embedding:30m": (Provider.OLLAMA,),
}

GRANITE_EMBEDDING_SMALL_ENGLISH_R2_CAPABILITIES: PartialCapabilities = {
    "name": "ibm-granite/granite-embedding-small-english-r2",
    "default_dimension": 384,
    "context_window": 8192,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "ibm-granite/granite-embedding-small-english-r2",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 2,
    "other": {
        "revision": "54a8d2616a0844355a5164432d3f6dafb37b17a3",
        "release_date": "2025-08-15",
        "loader": {},
        "n_parameters": 47000000,
        "memory_usage_mb": 91,
        "license": "apache-2.0",
        "open_weights": True,
        "framework": ["Sentence Transformers", "PyTorch"],
        "reference": "https://huggingface.co/ibm-granite/granite-embedding-small-english-r2",
        "modalities": ["text"],
        "memory_usage_gb": 0.09,
    },
}

GRANITE_EMBEDDING_ENGLISH_R2_CAPABILITIES: PartialCapabilities = {
    "name": "ibm-granite/granite-embedding-english-r2",
    "default_dimension": 768,
    "context_window": 8192,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "ibm-granite/granite-embedding-english-r2",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 2,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "ibm-granite/granite-embedding-english-r2",
            "revision": "84e3546b88b0cb69f8078608a1df558020bcbf1f",
        },
        "memory_usage_mb": 530,
        "modalities": ["text"],
        "n_parameters": 278000000,
        "open_weights": True,
        "reference": "https://huggingface.co/ibm-granite/granite-embedding-english-r2",
        "release_date": "2024-12-18",
        "revision": "84e3546b88b0cb69f8078608a1df558020bcbf1f",
        "memory_usage_gb": 0.52,
    },
    "hf_name": "ibm-granite/granite-embedding-english-r2",
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
    GRANITE_EMBEDDING_ENGLISH_R2_CAPABILITIES,
)


def get_ibm_granite_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for ibm-granite embedding models."""
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    capabilities: list[EmbeddingCapabilitiesDict] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilitiesDict({**cap, "provider": provider})  # type: ignore[missing-typeddict-key]
            for provider in CAP_MAP[cap["name"]]  # ty: ignore[invalid-argument-type]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)


__all__ = ("get_ibm_granite_embedding_capabilities",)
