# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for sentence-transformers embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from codeweaver.core.types.provider import Provider
from codeweaver.providers.embedding.capabilities.types import (
    EmbeddingCapabilitiesDict,
    PartialCapabilities,
)


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

type SentenceTransformersProvider = Literal[
    Provider.FASTEMBED, Provider.HUGGINGFACE_INFERENCE, Provider.SENTENCE_TRANSFORMERS
]

CAP_MAP: dict[
    Literal[
        "sentence-transformers/all-MiniLM-L12-v2",
        "sentence-transformers/all-MiniLM-L6-v2",
        "sentence-transformers/all-mpnet-base-v2",
        "sentence-transformers/gtr-t5-base",
        "sentence-transformers/LaBSE",
        "sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    ],
    tuple[SentenceTransformersProvider, ...],
] = {
    "sentence-transformers/all-MiniLM-L12-v2": (
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
    ),
    "sentence-transformers/all-MiniLM-L6-v2": (
        Provider.FASTEMBED,
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
    ),
    "sentence-transformers/all-mpnet-base-v2": (
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
    ),
    "sentence-transformers/gtr-t5-base": (
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
    ),
    "sentence-transformers/LaBSE": (Provider.HUGGINGFACE_INFERENCE, Provider.SENTENCE_TRANSFORMERS),
    "sentence-transformers/multi-qa-MiniLM-L6-cos-v1": (
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
    ),
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": (
        Provider.FASTEMBED,
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
    ),
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": (
        Provider.FASTEMBED,
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
    ),
}


SENTENCE_TRANSFORMERS_ALL_MINILM_L6_V2_CAPABILITIES: PartialCapabilities = {
    "name": "sentence-transformers/all-MiniLM-L6-v2",
    "default_dimension": 384,
    "context_window": 256,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "sentence-transformers/all-MiniLM-L6-v2",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 2,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "memory_usage_mb": 90,
        "modalities": ["text"],
        "n_parameters": 22700000,
        "open_weights": True,
        "reference": "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2",
        "release_date": "2021-08-30",
        "revision": "8b3219a92973c328a8e22fadcfa821b5dc75636a",
        "memory_usage_gb": 0.09,
    },
}

SENTENCE_TRANSFORMERS_ALL_MINILM_L12_V2_CAPABILITIES: PartialCapabilities = {
    "name": "sentence-transformers/all-MiniLM-L12-v2",
    "default_dimension": 384,
    "context_window": 256,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "sentence-transformers/all-MiniLM-L12-v2",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 2,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "memory_usage_mb": 127,
        "modalities": ["text"],
        "n_parameters": 33400000,
        "open_weights": True,
        "reference": "https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2",
        "release_date": "2021-08-30",
        "revision": "364dd28d28dcd3359b537f3cf1f5348ba679da62",
        "memory_usage_gb": 0.12,
    },
}

SENTENCE_TRANSFORMERS_ALL_MPNET_BASE_V2_CAPABILITIES: PartialCapabilities = {
    "name": "sentence-transformers/all-mpnet-base-v2",
    "default_dimension": 768,
    "context_window": 384,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "sentence-transformers/all-mpnet-base-v2",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 2,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "memory_usage_mb": 418,
        "modalities": ["text"],
        "n_parameters": 109000000,
        "open_weights": True,
        "reference": "https://huggingface.co/sentence-transformers/all-mpnet-base-v2",
        "release_date": "2021-08-30",
        "revision": "9a3225965996d404b775526de6dbfe85d3368642",
        "memory_usage_gb": 0.41,
    },
}

SENTENCE_TRANSFORMERS_GTR_T5_BASE_CAPABILITIES: PartialCapabilities = {
    "name": "sentence-transformers/gtr-t5-base",
    "default_dimension": 768,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "sentence-transformers/gtr-t5-base",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "memory_usage_mb": 209,
        "modalities": ["text"],
        "n_parameters": 110000000,
        "open_weights": True,
        "reference": "https://huggingface.co/sentence-transformers/gtr-t5-base",
        "release_date": "2022-02-09",
        "revision": "7027e9594267928589816394bdd295273ddc0739",
        "memory_usage_gb": 0.2,
    },
}


SENTENCE_TRANSFORMERS_MULTI_QA_MINILM_L6_COS_V1_CAPABILITIES: PartialCapabilities = {
    "name": "sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
    "default_dimension": 384,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 1,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "nreimers/MiniLM-L6-H384-uncased",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "memory_usage_mb": 87,
        "modalities": ["text"],
        "n_parameters": 22700000,
        "open_weights": True,
        "reference": "https://huggingface.co/sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
        "release_date": "2021-08-30",
        "revision": "b207367332321f8e44f96e224ef15bc607f4dbf0",
        "memory_usage_gb": 0.08,
    },
}

SENTENCE_TRANSFORMERS_PARAPHRASE_MULTILINGUAL_MINILM_L12_V2_CAPABILITIES: PartialCapabilities = {
    "name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "default_dimension": 768,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 2,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "memory_usage_mb": 449,
        "modalities": ["text"],
        "n_parameters": 118000000,
        "open_weights": True,
        "reference": "https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "release_date": "2019-11-01",
        "revision": "bf3bf13ab40c3157080a7ab344c831b9ad18b5eb",
        "memory_usage_gb": 0.44,
    },
}

SENTENCE_TRANSFORMERS_PARAPHRASE_MULTILINGUAL_MPNET_BASE_V2_CAPABILITIES: PartialCapabilities = {
    "name": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "default_dimension": 768,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 2,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "memory_usage_mb": 1061,
        "modalities": ["text"],
        "n_parameters": 278000000,
        "open_weights": True,
        "reference": "https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "release_date": "2019-11-01",
        "revision": "79f2382ceacceacdf38563d7c5d16b9ff8d725d6",
        "memory_usage_gb": 1.04,
    },
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    SENTENCE_TRANSFORMERS_ALL_MINILM_L6_V2_CAPABILITIES,
    SENTENCE_TRANSFORMERS_ALL_MINILM_L12_V2_CAPABILITIES,
    SENTENCE_TRANSFORMERS_ALL_MPNET_BASE_V2_CAPABILITIES,
    SENTENCE_TRANSFORMERS_GTR_T5_BASE_CAPABILITIES,
    SENTENCE_TRANSFORMERS_MULTI_QA_MINILM_L6_COS_V1_CAPABILITIES,
    SENTENCE_TRANSFORMERS_PARAPHRASE_MULTILINGUAL_MINILM_L12_V2_CAPABILITIES,
    SENTENCE_TRANSFORMERS_PARAPHRASE_MULTILINGUAL_MPNET_BASE_V2_CAPABILITIES,
)


def get_sentence_transformers_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for sentence-transformers embedding models."""
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    capabilities: list[EmbeddingCapabilitiesDict] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilitiesDict({**cap, "provider": provider})  # type: ignore[missing-typeddict-key]
            for provider in CAP_MAP[cap["name"]]  # ty: ignore[invalid-argument-type]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)


__all__ = ("get_sentence_transformers_embedding_capabilities",)
