"""Capabilities for BAAI embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations
from typing import Any
from codeweaver.embedding.capabilities.base import PartialCapabilities


BAAI_BGE_SMALL_EN_V1_5_CAPABILITIES: PartialCapabilities = {
    "name": "BAAI/bge-small-en-v1.5",
    "default_dimension": 512,
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
            "model_name": "BAAI/bge-small-en-v1.5",
            "model_prompts": {
                "query": "Represent this sentence for searching relevant passages: ",
            },
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
        "memory_usage_gb": 0.1240234375,
    },
}

BAAI_BGE_BASE_EN_V1_5_CAPABILITIES: PartialCapabilities = {
    "name": "BAAI/bge-base-en-v1.5",
    "default_dimension": 768,
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
            "model_name": "BAAI/bge-base-en-v1.5",
            "model_prompts": {
                "query": "Represent this sentence for searching relevant passages: ",
            },
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
        "memory_usage_gb": 0.380859375,
    },
}

BAAI_BGE_LARGE_EN_V1_5_CAPABILITIES: PartialCapabilities = {
    "name": "BAAI/bge-large-en-v1.5",
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
            "model_name": "BAAI/bge-large-en-v1.5",
            "model_prompts": {
                "query": "Represent this sentence for searching relevant passages: ",
            },
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
        "memory_usage_gb": 1.212890625,
    },
}

BAAI_BGE_M3_CAPABILITIES: PartialCapabilities = {
    "name": "BAAI/bge-m3",
    "default_dimension": 1024,
    "context_window": 8194,
    "preferred_metrics": ("cosine", "dot_product", "euclidean"),
    "supports_context_chunk_embedding": False,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "mit",
        "loader": {
            "model_name": "BAAI/bge-m3",
            "revision": "5617a9f61b028005a4858fdac845db406aefb181",
        },
        "memory_usage_mb": 2167,
        "modalities": ["text"],
        "n_parameters": 568000000,
        "open_weights": True,
        "public_training_data": "https://huggingface.co/datasets/cfli/bge-full-data",
        "reference": "https://huggingface.co/BAAI/bge-m3",
        "release_date": "2024-06-28",
        "revision": "5617a9f61b028005a4858fdac845db406aefb181",
        "memory_usage_gb": 2.1162109375,
    },
}
