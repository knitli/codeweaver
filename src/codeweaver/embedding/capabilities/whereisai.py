# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for WhereIsAI embedding models."""

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


type WhereisaiProvider = Literal[
    Provider.FASTEMBED,
    Provider.FIREWORKS,
    Provider.HUGGINGFACE_INFERENCE,
    Provider.SENTENCE_TRANSFORMERS,
    Provider.TOGETHER,
]

CAP_MAP: dict[
    Literal["WhereIsAI/UAE-Code-Large-V1", "WhereIsAI/UAE-Large-V1"], tuple[WhereisaiProvider, ...]
] = {
    "WhereIsAI/UAE-Code-Large-V1": (Provider.SENTENCE_TRANSFORMERS,),
    "WhereIsAI/UAE-Large-V1": (
        Provider.FASTEMBED,
        Provider.FIREWORKS,
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
        Provider.TOGETHER,
    ),
}


WHEREISAI_UAE_CODE_LARGE_V1_CAPABILITIES: PartialCapabilities = {
    "name": "WhereIsAI/UAE-Code-Large-V1",
    "default_dimension": 1024,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "WhereIsAI/UAE-Code-Large-V1",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 1,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "mit",
        "loader": {
            "model": "WhereIsAI/UAE-Code-Large-V1",
            "model_prompts": {
                "query": "Represent this sentence for searching relevant passages: {text}",
                "Summarization": 'Summarize sentence "{text}" in one word:"',
            },
            "revision": "369c368f70f16a613f19f5598d4f12d9f44235d4",
        },
        "memory_usage_mb": 1278,
        "modalities": ["text"],
        "n_parameters": 335000000,
        "open_weights": True,
        "reference": "https://huggingface.co/WhereIsAI/UAE-Code-Large-V1",
        "release_date": "2023-12-04",
        "revision": "c601ffcfd22c0956a0f97eeada84b27634a7afc8",
        "memory_usage_gb": 1.25,
    },
}

WHEREISAI_UAE_LARGE_V1_CAPABILITIES: PartialCapabilities = {
    "name": "WhereIsAI/UAE-Large-V1",
    "default_dimension": 1024,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "WhereIsAI/UAE-Large-V1",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 1,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "mit",
        "loader": {
            "model": "WhereIsAI/UAE-Large-V1",
            "model_prompts": {
                "query": "Represent this sentence for searching relevant passages: {text}",
                "Summarization": 'Summarize sentence "{text}" in one word:"',
            },
            "revision": "369c368f70f16a613f19f5598d4f12d9f44235d4",
        },
        "memory_usage_mb": 1278,
        "modalities": ["text"],
        "n_parameters": 335000000,
        "open_weights": True,
        "reference": "https://huggingface.co/WhereIsAI/UAE-Large-V1",
        "release_date": "2023-12-04",
        "revision": "369c368f70f16a613f19f5598d4f12d9f44235d4",
        "memory_usage_gb": 1.25,
    },
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    WHEREISAI_UAE_CODE_LARGE_V1_CAPABILITIES,
    WHEREISAI_UAE_LARGE_V1_CAPABILITIES,
)


def get_whereisai_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for WhereIsAI embedding models."""
    capabilities: list[EmbeddingCapabilities] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilities({**cap, "provider": provider})  # type: ignore
            for provider in CAP_MAP[cap["name"]]  # pyright: ignore[reportArgumentType]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)
