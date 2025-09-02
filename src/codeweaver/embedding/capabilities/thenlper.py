# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for thenlper embedding models."""

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


type ThenlperProvider = Literal[Provider.FASTEMBED, Provider.FIREWORKS]

CAP_MAP: dict[Literal["thenlper/gte-base", "thenlper/gte-large"], tuple[ThenlperProvider, ...]] = {
    "thenlper/gte-base": (Provider.FASTEMBED, Provider.FIREWORKS),
    "thenlper/gte-large": (Provider.FASTEMBED, Provider.FIREWORKS),
}


THENLPER_GTE_BASE_CAPABILITIES: PartialCapabilities = {
    "name": "thenlper/gte-base",
    "default_dimension": 768,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "thenlper/gte-base",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["PyTorch"],
        "license": "mit",
        "loader": {},
        "memory_usage_mb": 209,
        "modalities": ["text"],
        "n_parameters": 109482752,
        "open_weights": True,
        "reference": "https://huggingface.co/thenlper/gte-base",
        "release_date": "2023-07-27",
        "revision": "c078288308d8dee004ab72c6191778064285ec0c",
        "memory_usage_gb": 0.2,
    },
}

THENLPER_GTE_LARGE_CAPABILITIES: PartialCapabilities = {
    "name": "thenlper/gte-large",
    "default_dimension": 1024,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "thenlper/gte-large",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["PyTorch"],
        "license": "mit",
        "loader": {},
        "memory_usage_mb": 639,
        "modalities": ["text"],
        "n_parameters": 335122400,
        "open_weights": True,
        "reference": "https://huggingface.co/thenlper/gte-large",
        "release_date": "2023-07-27",
        "revision": "4bef63f39fcc5e2d6b0aae83089f307af4970164",
        "memory_usage_gb": 0.62,
    },
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    THENLPER_GTE_BASE_CAPABILITIES,
    THENLPER_GTE_LARGE_CAPABILITIES,
)


def get_thenlper_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for thenlper embedding models."""
    capabilities: list[EmbeddingCapabilities] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilities({**cap, "provider": provider})  # pyright: ignore[reportArgumentType]
            for provider in CAP_MAP[cap["name"]]  # pyright: ignore[reportArgumentType]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)
