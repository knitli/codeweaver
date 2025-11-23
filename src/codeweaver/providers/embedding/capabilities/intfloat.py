# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for intfloat embedding models."""

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

type IntfloatProvider = Literal[
    Provider.FASTEMBED,
    Provider.HUGGINGFACE_INFERENCE,
    Provider.SENTENCE_TRANSFORMERS,
    Provider.TOGETHER,
]

CAP_MAP: dict[
    Literal["intfloat/multilingual-e5-large", "intfloat/multilingual-e5-large-instruct"],
    tuple[IntfloatProvider, ...],
] = {
    "intfloat/multilingual-e5-large": (
        Provider.HUGGINGFACE_INFERENCE,
        Provider.FASTEMBED,
        Provider.SENTENCE_TRANSFORMERS,
    ),
    "intfloat/multilingual-e5-large-instruct": (
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
        Provider.TOGETHER,
    ),
}


INTFLOAT_MULTILINGUAL_E5_LARGE_CAPABILITIES: PartialCapabilities = {
    "name": "intfloat/multilingual-e5-large",
    "default_dimension": 1024,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "intfloat/multilingual-e5-large",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "FacebookAI/xlm-roberta-large",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "mit",
        "loader": {
            "model_name": "intfloat/multilingual-e5-large",
            "model_prompts": {"document": "passage: ", "query": "query: "},
            "revision": "ab10c1a7f42e74530fe7ae5be82e6d4f11a719eb",
        },
        "memory_usage_mb": 2136,
        "modalities": ["text"],
        "n_parameters": 560000000,
        "open_weights": True,
        "reference": "https://huggingface.co/intfloat/multilingual-e5-large",
        "release_date": "2024-02-08",
        "revision": "ab10c1a7f42e74530fe7ae5be82e6d4f11a719eb",
        "memory_usage_gb": 2.09,
    },
}

INTFLOAT_MULTILINGUAL_E5_LARGE_INSTRUCT_CAPABILITIES: PartialCapabilities = {
    "name": "intfloat/multilingual-e5-large-instruct",
    "default_dimension": 1024,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "intfloat/multilingual-e5-large-instruct",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "FacebookAI/xlm-roberta-large",
        "framework": ["GritLM", "PyTorch", "Sentence Transformers"],
        "license": "mit",
        "loader": {
            "attn": "cccc",
            "instruction_template": "Instruct: {instruction}\nQuery: ",
            "mode": "embedding",
            "model_name_or_path": "intfloat/multilingual-e5-large-instruct",
            "normalized": True,
            "pooling_method": "mean",
            "torch_dtype": "torch.float16",
        },
        "memory_usage_mb": 1068,
        "modalities": ["text"],
        "n_parameters": 560000000,
        "open_weights": True,
        "reference": "https://huggingface.co/intfloat/multilingual-e5-large-instruct",
        "release_date": "2024-02-08",
        "revision": "baa7be480a7de1539afce709c8f13f833a510e0a",
        "memory_usage_gb": 1.04,
    },
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    INTFLOAT_MULTILINGUAL_E5_LARGE_CAPABILITIES,
    INTFLOAT_MULTILINGUAL_E5_LARGE_INSTRUCT_CAPABILITIES,
)


def get_intfloat_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for intfloat embedding models."""
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    capabilities: list[EmbeddingCapabilitiesDict] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilitiesDict({**cap, "provider": provider})  # type: ignore[missing-typeddict-key]
            for provider in CAP_MAP[cap["name"]]  # ty: ignore[invalid-argument-type]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)


__all__ = ("get_intfloat_embedding_capabilities",)
