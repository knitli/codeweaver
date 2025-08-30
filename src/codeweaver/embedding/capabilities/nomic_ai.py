"""Capabilities for nomic-ai embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations
from typing import Any
from codeweaver.embedding.capabilities.base import PartialCapabilities


NOMIC_AI_MODERNBERT_EMBED_BASE_CAPABILITIES: PartialCapabilities = {
    "name": "nomic-ai/modernbert-embed-base",
    "default_dimension": 768,
    "context_window": 8192,
    "preferred_metrics": ("cosine", "dot_product", "euclidean"),
    "supports_context_chunk_embedding": False,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "answerdotai/ModernBERT-base",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_kwargs": {
                "torch_dtype": "torch.float16",
            },
            "model_name": "nomic-ai/modernbert-embed-base",
            "model_prompts": {
                "Classification": "classification: ",
                "Clustering": "clustering: ",
                "document": "search_document: ",
                "MultilabelClassification": "classification: ",
                "PairClassification": "classification: ",
                "query": "search_query: ",
                "Reranking": "classification: ",
                "STS": "classification: ",
                "Summarization": "classification: ",
            },
            "revision": "5960f1566fb7cb1adf1eb6e816639cf4646d9b12",
        },
        "memory_usage_mb": 568,
        "modalities": ["text"],
        "n_parameters": 149000000,
        "open_weights": True,
        "public_training_code": "https://github.com/nomic-ai/contrastors/blob/5f7b461e5a13b5636692d1c9f1141b27232fe966/src/contrastors/configs/train/contrastive_pretrain_modernbert.yaml",
        "reference": "https://huggingface.co/nomic-ai/modernbert-embed-base",
        "release_date": "2024-12-29",
        "revision": "5960f1566fb7cb1adf1eb6e816639cf4646d9b12",
        "memory_usage_gb": 0.5546875,
    },
}
