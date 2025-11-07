# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for Qwen embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from codeweaver.providers.embedding.capabilities.types import (
    EmbeddingCapabilities,
    PartialCapabilities,
)
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities


type QwenProvider = Literal[Provider.SENTENCE_TRANSFORMERS]

CAP_MAP: dict[
    Literal["Qwen/Qwen3-Embedding-0.6B", "Qwen/Qwen3-Embedding-4B", "Qwen/Qwen3-Embedding-8B"],
    tuple[QwenProvider, ...],
] = {
    "Qwen/Qwen3-Embedding-0.6B": (Provider.SENTENCE_TRANSFORMERS,),
    "Qwen/Qwen3-Embedding-4B": (Provider.SENTENCE_TRANSFORMERS,),
    "Qwen/Qwen3-Embedding-8B": (Provider.SENTENCE_TRANSFORMERS,),
}


QWEN_QWEN3_EMBEDDING_0_6B_CAPABILITIES: PartialCapabilities = {
    "name": "Qwen/Qwen3-Embedding-0.6B",
    "default_dimension": 1024,
    "context_window": 32768,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Qwen/Qwen3-Embedding-0.6B",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 3.0,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {"model_name_or_path": "Qwen/Qwen3-Embedding-0.6B"},
        "memory_usage_mb": 2272,
        "modalities": ["text"],
        "n_parameters": 595776512,
        "open_weights": True,
        "reference": "https://huggingface.co/Qwen/Qwen3-Embedding-0.6B",
        "release_date": "2025-06-05",
        "revision": "b22da495047858cce924d27d76261e96be6febc0",
        "memory_usage_gb": 2.22,
    },
}

QWEN_QWEN3_EMBEDDING_4B_CAPABILITIES: PartialCapabilities = {
    "name": "Qwen/Qwen3-Embedding-4B",
    "default_dimension": 2560,
    "context_window": 32768,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Qwen/Qwen3-Embedding-4B",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 3.0,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {"model_name_or_path": "Qwen/Qwen3-Embedding-4B"},
        "memory_usage_mb": 15341,
        "modalities": ["text"],
        "n_parameters": 4021774336,
        "open_weights": True,
        "reference": "https://huggingface.co/Qwen/Qwen3-Embedding-4B",
        "release_date": "2025-06-05",
        "revision": "636cd9bf47d976946cdbb2b0c3ca0cb2f8eea5ff",
        "memory_usage_gb": 14.98,
    },
}

QWEN_QWEN3_EMBEDDING_8B_CAPABILITIES: PartialCapabilities = {
    "name": "Qwen/Qwen3-Embedding-8B",
    "default_dimension": 4096,
    "context_window": 32768,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Qwen/Qwen3-Embedding-8B",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 3.0,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {"model_name_or_path": "Qwen/Qwen3-Embedding-8B"},
        "memory_usage_mb": 28866,
        "modalities": ["text"],
        "n_parameters": 7567295488,
        "open_weights": True,
        "reference": "https://huggingface.co/Qwen/Qwen3-Embedding-8B",
        "release_date": "2025-06-05",
        "revision": "4e423935c619ae4df87b646a3ce949610c66241c",
        "memory_usage_gb": 28.19,
        "prefix": "",
    },
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    QWEN_QWEN3_EMBEDDING_0_6B_CAPABILITIES,
    QWEN_QWEN3_EMBEDDING_4B_CAPABILITIES,
    QWEN_QWEN3_EMBEDDING_8B_CAPABILITIES,
)


def get_qwen_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for Qwen embedding models."""
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    capabilities: list[EmbeddingCapabilities] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilities({**cap, "provider": provider})
            for provider in CAP_MAP[cap["name"]]
        ])
    return tuple(
        EmbeddingModelCapabilities.model_validate(
            cap
            | {
                "other": {
                    "model": {
                        "instruction": "Given search results containing code snippets, tree-sitter parse trees, documentation and code comments from a codebase, retrieve relevant Documents that answer the Query."
                    }
                }
            }
        )
        for cap in capabilities
    )


__all__ = ("get_qwen_embedding_capabilities",)
