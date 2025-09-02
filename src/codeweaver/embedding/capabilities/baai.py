# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for BAAI embedding models."""

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


type BaaiProvider = Literal[
    Provider.FASTEMBED,
    Provider.HUGGINGFACE_INFERENCE,
    Provider.SENTENCE_TRANSFORMERS,
    Provider.TOGETHER,
]

CAP_MAP: dict[
    Literal[
        "BAAI/bge-base-en-v1.5",
        "BAAI/bge-large-en-v1",
        "BAAI/bge-large-en-v1.5",
        "BAAI/bge-m3",
        "BAAI/bge-small-en-v1.5",
    ],
    tuple[BaaiProvider, ...],
] = {
    "BAAI/bge-base-en-v1.5": (
        Provider.FASTEMBED,
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
        Provider.TOGETHER,
    ),
    "BAAI/bge-large-en-v1": (Provider.HUGGINGFACE_INFERENCE, Provider.SENTENCE_TRANSFORMERS),
    "BAAI/bge-large-en-v1.5": (
        Provider.FASTEMBED,
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
        Provider.TOGETHER,
    ),
    "BAAI/bge-m3": (
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
        Provider.FASTEMBED,
    ),
    "BAAI/bge-small-en-v1.5": (
        Provider.FASTEMBED,
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
    ),
}


BAAI_BGE_BASE_EN_V1_5_CAPABILITIES: PartialCapabilities = {
    "name": "BAAI/bge-base-en-v1.5",
    "default_dimension": 768,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "BAAI/bge-base-en-v1.5",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 1.5,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "mit",
        "loader": {
            "model_name": "BAAI/bge-base-en-v1.5",
            "model_prompts": {"query": "Represent this sentence for searching relevant passages: "},
            "revision": "a5beb1e3e68b9ab74eb54cfd186867f64f240e1a",
        },
        "memory_usage_mb": 390,
        "modalities": ["text"],
        "n_parameters": 109000000,
        "open_weights": True,
        "public_training_data": "https://data.baai.ac.cn/details/BAAI-MTP",
        "reference": "https://huggingface.co/BAAI/bge-base-en-v1.5",
        "release_date": "2023-09-11",
        "revision": "a5beb1e3e68b9ab74eb54cfd186867f64f240e1a",
        "memory_usage_gb": 0.38,
    },
}

BGE_LARGE_EN_335M_CAPABILITIES: PartialCapabilities = {
    "name": "BAAI/bge-large-en-v1.5",
    "default_dimension": 1024,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "BAAI/bge-large-en-v1.5",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 1.5,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "mit",
        "loader": {
            "model_name": "BAAI/bge-large-en-v1.5",
            "model_prompts": {"query": "Represent this sentence for searching relevant passages: "},
            "revision": "d4aa6901d3a41ba39fb536a557fa166f842b0e09",
        },
        "memory_usage_mb": 1242,
        "modalities": ["text"],
        "n_parameters": 335000000,
        "open_weights": True,
        "public_training_data": "https://data.baai.ac.cn/details/BAAI-MTP",
        "reference": "https://huggingface.co/BAAI/bge-large-en-v1.5",
        "release_date": "2023-09-12",
        "revision": "d4aa6901d3a41ba39fb536a557fa166f842b0e09",
        "memory_usage_gb": 1.21,
    },
    "hf_name": "BAAI/bge-large-en-v1.5",
}

BAAI_BGE_SMALL_EN_V1_5_CAPABILITIES: PartialCapabilities = {
    "name": "BAAI/bge-small-en-v1.5",
    "default_dimension": 512,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "BAAI/bge-small-en-v1.5",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 1.5,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "mit",
        "loader": {
            "model_name": "BAAI/bge-small-en-v1.5",
            "model_prompts": {"query": "Represent this sentence for searching relevant passages: "},
            "revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
        },
        "memory_usage_mb": 127,
        "modalities": ["text"],
        "n_parameters": 33400000,
        "open_weights": True,
        "public_training_data": "https://data.baai.ac.cn/details/BAAI-MTP",
        "reference": "https://huggingface.co/BAAI/bge-small-en-v1.5",
        "release_date": "2023-09-12",
        "revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
        "memory_usage_gb": 0.12,
    },
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    BAAI_BGE_BASE_EN_V1_5_CAPABILITIES,
    BGE_LARGE_EN_335M_CAPABILITIES,
    BAAI_BGE_SMALL_EN_V1_5_CAPABILITIES,
)


def get_baai_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for BAAI embedding models."""
    capabilities: list[EmbeddingCapabilities] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilities({**cap, "provider": provider})  # pyright: ignore[reportArgumentType]
            for provider in CAP_MAP[cap["name"]]  # pyright: ignore[reportArgumentType]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)
