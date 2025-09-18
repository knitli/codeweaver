# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for jinaai embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations

from typing import Literal

from codeweaver.embedding.capabilities.base import (
    EmbeddingCapabilities,
    EmbeddingModelCapabilities,
    PartialCapabilities,
)
from codeweaver.provider import Provider


type JinaaiProvider = Literal[Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS]

CAP_MAP: dict[
    Literal[
        "jinaai/jina-embeddings-v2-base-code",
        "jinaai/jina-embeddings-v3",
        "jinaai/jina-embeddings-v4",
    ],
    tuple[JinaaiProvider, ...],
] = {
    "jinaai/jina-embeddings-v2-base-code": (Provider.FASTEMBED,),
    "jinaai/jina-embeddings-v3": (Provider.FASTEMBED,),
    "jinaai/jina-embeddings-v4": (Provider.SENTENCE_TRANSFORMERS,),
}


JINAAI_JINA_EMBEDDINGS_V2_BASE_CODE_CAPABILITIES: PartialCapabilities = {
    "name": "jinaai/jina-embeddings-v2-base-code",
    "default_dimension": 768,
    "context_window": 8192,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "jinaai/jina-embeddings-v2-base-code",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 2,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "jina-bert-base-en-v1",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model": "jinaai/jina-embeddings-v2-base-en",
            "revision": "6e85f575bc273f1fd840a658067d0157933c83f0",
            "trust_remote_code": True,
        },
        "memory_usage_mb": 262,
        "modalities": ["text"],
        "n_parameters": 137000000,
        "open_weights": True,
        "reference": "https://huggingface.co/jinaai/jina-embeddings-v2-base-en",
        "release_date": "2023-09-27",
        "revision": "6e85f575bc273f1fd840a658067d0157933c83f0",
        "memory_usage_gb": 0.26,
    },
}

JINAAI_JINA_EMBEDDINGS_V3_CAPABILITIES: PartialCapabilities = {
    "name": "jinaai/jina-embeddings-v3",
    "default_dimension": 1024,
    "context_window": 8194,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "jinaai/jina-embeddings-v3",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 3,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "XLM-RoBERTa",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "cc-by-nc-4.0",
        "loader": {
            "model": "jinaai/jina-embeddings-v3",
            "model_prompts": {
                "BitextMining": "text-matching",
                "Classification": "classification",
                "Clustering": "separation",
                "MultilabelClassification": "classification",
                "PairClassification": "classification",
                "Reranking": "separation",
                "Retrieval-document": "retrieval.passage",
                "Retrieval-query": "retrieval.query",
                "STS": "text-matching",
                "Summarization": "text-matching",
            },
            "revision": "215a6e121fa0183376388ac6b1ae230326bfeaed",
            "trust_remote_code": True,
        },
        "memory_usage_mb": 1092,
        "modalities": ["text"],
        "n_parameters": 572000000,
        "open_weights": True,
        "reference": "https://huggingface.co/jinaai/jina-embeddings-v3",
        "release_date": "2024-09-18",
        "revision": "215a6e121fa0183376388ac6b1ae230326bfeaed",
        "memory_usage_gb": 1.07,
    },
    "output_dimensions": (1024, 512, 256, 128, 64, 32),
}

JINAAI_JINA_EMBEDDINGS_V4_CAPABILITIES: PartialCapabilities = {
    "name": "jinaai/jina-embeddings-v4",
    "default_dimension": 2048,
    "context_window": 32768,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "jinaai/jina-embeddings-v4",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 4,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "Qwen/Qwen2.5-VL-3B-Instruct",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "qwen-research-license",
        "loader": {
            "model": "jinaai/jina-embeddings-v4",
            "model_prompts": {
                "DocumentUnderstanding": "retrieval.query",
                "Retrieval-document": "retrieval.passage",
                "Retrieval-query": "retrieval.query",
                "STS": "text-matching",
            },
            "revision": "4a58ca57710c49f51896e4bc820e202fbf64904b",
            "trust_remote_code": True,
        },
        "memory_usage_mb": 7500,
        "modalities": ["image", "text"],
        "n_parameters": 3800000000,
        "open_weights": True,
        "reference": "https://huggingface.co/jinaai/jina-embeddings-v4",
        "release_date": "2025-06-24",
        "revision": "4a58ca57710c49f51896e4bc820e202fbf64904b",
        "memory_usage_gb": 7.32,
    },
    "output_dimensions": (2048, 1024, 512, 256, 128),
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    JINAAI_JINA_EMBEDDINGS_V2_BASE_CODE_CAPABILITIES,
    JINAAI_JINA_EMBEDDINGS_V3_CAPABILITIES,
    JINAAI_JINA_EMBEDDINGS_V4_CAPABILITIES,
)


def get_jinaai_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for jinaai embedding models."""
    capabilities: list[EmbeddingCapabilities] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilities({**cap, "provider": provider})  # pyright: ignore[reportArgumentType]
            for provider in CAP_MAP[cap["name"]]  # pyright: ignore[reportArgumentType]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)


__all__ = ("get_jinaai_embedding_capabilities",)
