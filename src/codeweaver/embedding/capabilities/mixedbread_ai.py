"""Capabilities for mixedbread-ai embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations
from typing import Any
from codeweaver.embedding.capabilities.base import PartialCapabilities


MIXEDBREAD_AI_MXBAI_EMBED_LARGE_V1_CAPABILITIES: PartialCapabilities = {
    "name": "mixedbread-ai/mxbai-embed-large-v1",
    "default_dimension": 1024,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot_product", "euclidean"),
    "supports_context_chunk_embedding": False,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "mixedbread-ai/mxbai-embed-large-v1",
            "model_prompts": {
                "query": "Represent this sentence for searching relevant passages: ",
            },
            "revision": "990580e27d329c7408b3741ecff85876e128e203",
        },
        "memory_usage_mb": 639,
        "modalities": ["text"],
        "n_parameters": 335000000,
        "open_weights": True,
        "reference": "https://huggingface.co/mixedbread-ai/mxbai-embed-large-v1",
        "release_date": "2024-03-07",
        "revision": "990580e27d329c7408b3741ecff85876e128e203",
        "memory_usage_gb": 0.6240234375,
    },
}
