"""Capabilities for WhereIsAI embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations
from typing import Any
from codeweaver.embedding.capabilities.base import PartialCapabilities


WHEREISAI_UAE_LARGE_V1_CAPABILITIES: PartialCapabilities = {
    "name": "WhereIsAI/UAE-Large-V1",
    "default_dimension": 1024,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot_product", "euclidean"),
    "supports_context_chunk_embedding": False,
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
        "memory_usage_gb": 1.248046875,
    },
}
