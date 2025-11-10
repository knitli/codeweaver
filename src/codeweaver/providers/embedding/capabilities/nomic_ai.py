# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for nomic-ai embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from codeweaver.providers.embedding.capabilities.types import EmbeddingCapabilitiesDict
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
    from codeweaver.providers.embedding.capabilities.types import PartialCapabilities

type NomicAiProvider = Literal[
    Provider.FASTEMBED,
    Provider.FIREWORKS,
    Provider.HUGGINGFACE_INFERENCE,
    Provider.SENTENCE_TRANSFORMERS,
]

CAP_MAP: dict[
    Literal[
        "nomic-ai/modernbert-embed-base",
        "nomic-ai/nomic-embed-text-v1.5",
        "nomic-ai/nomic-embed-text-v1.5-GGUF",
        "nomic-ai/nomic-embed-text-v2-moe",
    ],
    tuple[NomicAiProvider, ...],
] = {
    "nomic-ai/modernbert-embed-base": (
        Provider.FIREWORKS,
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
    ),
    "nomic-ai/nomic-embed-text-v1.5": (Provider.FIREWORKS, Provider.FASTEMBED),
    "nomic-ai/nomic-embed-text-v1.5-GGUF": (Provider.FASTEMBED,),
    "nomic-ai/nomic-embed-text-v2-moe": (Provider.FIREWORKS, Provider.SENTENCE_TRANSFORMERS),
}


NOMIC_AI_MODERNBERT_EMBED_BASE_CAPABILITIES: PartialCapabilities = {
    "name": "nomic-ai/modernbert-embed-base",
    "default_dimension": 256,
    "context_window": 8192,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "nomic-ai/modernbert-embed-base",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "answerdotai/ModernBERT-base",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_kwargs": {"torch_dtype": "torch.float16"},
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
        "memory_usage_gb": 0.55,
    },
}

NOMIC_AI_NOMIC_EMBED_TEXT_V2_MOE_CAPABILITIES: PartialCapabilities = {
    "name": "nomic-ai/nomic-embed-text-v2-moe",
    "default_dimension": 768,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "nomic-ai/nomic-embed-text-v2-moe",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 2,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["PyTorch", "Sentence Transformers"],
        "license": "apache-2.0",
        "loader": {"trust_remote_code": True},
        "modalities": ["text"],
        "open_weights": True,
    },
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    NOMIC_AI_MODERNBERT_EMBED_BASE_CAPABILITIES,
    NOMIC_AI_NOMIC_EMBED_TEXT_V2_MOE_CAPABILITIES,
)


def get_nomic_ai_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for nomic-ai embedding models."""
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    capabilities: list[EmbeddingCapabilitiesDict] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilitiesDict({**cap, "provider": provider})  # type: ignore[missing-typeddict-key]
            for provider in CAP_MAP[cap["name"]]  # ty: ignore[invalid-argument-type]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)


__all__ = ("get_nomic_ai_embedding_capabilities",)
