"""Capabilities for ibm-granite embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations
from typing import Any
from codeweaver.embedding.capabilities.base import PartialCapabilities


IBM_GRANITE_GRANITE_EMBEDDING_278M_MULTILINGUAL_CAPABILITIES: PartialCapabilities = {
    "name": "ibm-granite/granite-embedding-278m-multilingual",
    "default_dimension": 768,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot_product", "euclidean"),
    "supports_context_chunk_embedding": False,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
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
        "memory_usage_gb": 0.517578125,
    },
}
