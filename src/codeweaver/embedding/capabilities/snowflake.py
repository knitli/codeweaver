"""Capabilities for Snowflake embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations
from typing import Any
from codeweaver.embedding.capabilities.base import PartialCapabilities


SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_L_V2_0_CAPABILITIES: PartialCapabilities = {
    "name": "Snowflake/snowflake-arctic-embed-l-v2.0",
    "default_dimension": 1024,
    "context_window": 8192,
    "preferred_metrics": ("cosine", "dot_product", "euclidean"),
    "supports_context_chunk_embedding": False,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "BAAI/bge-m3-retromae",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "Snowflake/snowflake-arctic-embed-l-v2.0",
            "revision": "edc2df7b6c25794b340229ca082e7c78782e6374",
        },
        "memory_usage_mb": 2166,
        "modalities": ["text"],
        "n_parameters": 568000000,
        "open_weights": True,
        "reference": "https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0",
        "release_date": "2024-12-04",
        "revision": "edc2df7b6c25794b340229ca082e7c78782e6374",
        "memory_usage_gb": 2.115234375,
    },
}
