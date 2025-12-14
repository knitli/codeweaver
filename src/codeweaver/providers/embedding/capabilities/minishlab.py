# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for minishlab/model2vec embedding models."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from codeweaver.providers.embedding.capabilities.types import (
    EmbeddingCapabilitiesDict,
    PartialCapabilities,
)
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

type MinishlabProvider = Literal[Provider.SENTENCE_TRANSFORMERS]

CAP_MAP: dict[
    Literal[
        "minishlab/M2V_base_glove",
        "minishlab/M2V_base_glove_subword",
        "minishlab/M2V_base_output",
        "minishlab/M2V_multilingual_output",
        "minishlab/potion-base-2M",
        "minishlab/potion-base-4M",
        "minishlab/potion-base-8M",
    ],
    tuple[MinishlabProvider, ...],
] = {
    "minishlab/M2V_base_glove": (Provider.SENTENCE_TRANSFORMERS,),
    "minishlab/M2V_base_glove_subword": (Provider.SENTENCE_TRANSFORMERS,),
    "minishlab/M2V_base_output": (Provider.SENTENCE_TRANSFORMERS,),
    "minishlab/M2V_multilingual_output": (Provider.SENTENCE_TRANSFORMERS,),
    "minishlab/potion-base-2M": (Provider.SENTENCE_TRANSFORMERS,),
    "minishlab/potion-base-4M": (Provider.SENTENCE_TRANSFORMERS,),
    "minishlab/potion-base-8M": (Provider.SENTENCE_TRANSFORMERS,),
}


MINISHLAB_M2V_BASE_GLOVE_CAPABILITIES: PartialCapabilities = {
    "name": "minishlab/M2V_base_glove",
    "default_dimension": 256,
    # static embedding models effectively have no context window
    # practically, this limits chunk size to the bounds of the reranking model's context window or the length of the document, whichever is smaller
    "context_window": 1_000_000,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "minishlab/M2V_base_glove",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "BAAI/bge-base-en-v1.5",
        "framework": ["NumPy", "Sentence Transformers"],
        "license": "mit",
        "memory_usage_mb": 391,
        "modalities": ["text"],
        "n_parameters": 102000000,
        "open_weights": True,
        "reference": "https://huggingface.co/minishlab/M2V_base_glove",
        "release_date": "2024-09-21",
        "revision": "38ebd7f10f71e67fa8db898290f92b82e9cfff2b",
        "memory_usage_gb": 0.39,
        "public_training_code": "https://github.com/MinishLab/model2vec",
        "citation": "@software{minishlab2024model2vec,\n      authors = {Stephan Tulkens, Thomas van Dongen},\n      title = {Model2Vec: Turn any Sentence Transformer into a Small Fast Model},\n      year = {2024},\n      url = {https://github.com/MinishLab/model2vec}\n}",
    },
}

MINISHLAB_M2V_BASE_GLOVE_SUBWORD_CAPABILITIES: PartialCapabilities = {
    "name": "minishlab/M2V_base_glove_subword",
    "default_dimension": 256,
    "context_window": 1_000_000,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "minishlab/M2V_base_glove_subword",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "BAAI/bge-base-en-v1.5",
        "framework": ["NumPy", "Sentence Transformers"],
        "license": "mit",
        "memory_usage_mb": 391,
        "modalities": ["text"],
        "n_parameters": 103000000,
        "open_weights": True,
        "reference": "https://huggingface.co/minishlab/M2V_base_glove_subword",
        "release_date": "2024-09-21",
        "revision": "5f4f5ca159b7321a8b39739bba0794fa0debddf4",
        "memory_usage_gb": 0.39,
        "public_training_code": "https://github.com/MinishLab/model2vec",
        "citation": "@software{minishlab2024model2vec,\n      authors = {Stephan Tulkens, Thomas van Dongen},\n      title = {Model2Vec: Turn any Sentence Transformer into a Small Fast Model},\n      year = {2024},\n      url = {https://github.com/MinishLab/model2vec}\n}",
    },
}

MINISHLAB_M2V_BASE_OUTPUT_CAPABILITIES: PartialCapabilities = {
    "name": "minishlab/M2V_base_output",
    "default_dimension": 256,
    "context_window": 1_000_000,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "minishlab/M2V_base_output",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "BAAI/bge-base-en-v1.5",
        "framework": ["NumPy", "Sentence Transformers"],
        "license": "mit",
        "memory_usage_mb": 29,
        "modalities": ["text"],
        "n_parameters": 7560000,
        "open_weights": True,
        "reference": "https://huggingface.co/minishlab/M2V_base_output",
        "release_date": "2024-09-21",
        "revision": "02460ae401a22b09d2c6652e23371398329551e2",
        "memory_usage_gb": 0.03,
        "public_training_code": "https://github.com/MinishLab/model2vec",
        "citation": "@software{minishlab2024model2vec,\n      authors = {Stephan Tulkens, Thomas van Dongen},\n      title = {Model2Vec: Turn any Sentence Transformer into a Small Fast Model},\n      year = {2024},\n      url = {https://github.com/MinishLab/model2vec}\n}",
    },
}

MINISHLAB_M2V_MULTILINGUAL_OUTPUT_CAPABILITIES: PartialCapabilities = {
    "name": "minishlab/M2V_multilingual_output",
    "default_dimension": 256,
    "context_window": 1_000_000,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "minishlab/M2V_multilingual_output",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "sentence-transformers/LaBSE",
        "framework": ["NumPy", "Sentence Transformers"],
        "license": "mit",
        "memory_usage_mb": 489,
        "modalities": ["text"],
        "n_parameters": 128000000,
        "open_weights": True,
        "reference": "https://huggingface.co/minishlab/M2V_multilingual_output",
        "release_date": "2024-09-21",
        "revision": "2cf4ec4e1f51aeca6c55cf9b93097d00711a6305",
        "memory_usage_gb": 0.49,
        "public_training_code": "https://github.com/MinishLab/model2vec",
        "citation": "@software{minishlab2024model2vec,\n      authors = {Stephan Tulkens, Thomas van Dongen},\n      title = {Model2Vec: Turn any Sentence Transformer into a Small Fast Model},\n      year = {2024},\n      url = {https://github.com/MinishLab/model2vec}\n}",
    },
}

MINISHLAB_POTION_BASE_2M_CAPABILITIES: PartialCapabilities = {
    "name": "minishlab/potion-base-2M",
    "default_dimension": 64,
    "context_window": 1_000_000,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "minishlab/potion-base-2M",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "BAAI/bge-base-en-v1.5",
        "framework": ["NumPy", "Sentence Transformers"],
        "license": "mit",
        "memory_usage_mb": 7,
        "modalities": ["text"],
        "n_parameters": 2000000,
        "open_weights": True,
        "reference": "https://huggingface.co/minishlab/potion-base-2M",
        "release_date": "2024-10-29",
        "revision": "86db093558fbced2072b929eb1690bce5272bd4b",
        "memory_usage_gb": 0.01,
        "public_training_code": "https://github.com/MinishLab/model2vec",
        "citation": "@software{minishlab2024model2vec,\n      authors = {Stephan Tulkens, Thomas van Dongen},\n      title = {Model2Vec: Turn any Sentence Transformer into a Small Fast Model},\n      year = {2024},\n      url = {https://github.com/MinishLab/model2vec}\n}",
    },
}

MINISHLAB_POTION_BASE_4M_CAPABILITIES: PartialCapabilities = {
    "name": "minishlab/potion-base-4M",
    "default_dimension": 128,
    "context_window": 1_000_000,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "minishlab/potion-base-4M",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "BAAI/bge-base-en-v1.5",
        "framework": ["NumPy", "Sentence Transformers"],
        "license": "mit",
        "memory_usage_mb": 14,
        "modalities": ["text"],
        "n_parameters": 3780000,
        "open_weights": True,
        "reference": "https://huggingface.co/minishlab/potion-base-4M",
        "release_date": "2024-10-29",
        "revision": "81b1802ada41afcd0987a37dc15e569c9fa76f04",
        "memory_usage_gb": 0.01,
        "public_training_code": "https://github.com/MinishLab/model2vec",
        "citation": "@software{minishlab2024model2vec,\n      authors = {Stephan Tulkens, Thomas van Dongen},\n      title = {Model2Vec: Turn any Sentence Transformer into a Small Fast Model},\n      year = {2024},\n      url = {https://github.com/MinishLab/model2vec}\n}",
    },
}

MINISHLAB_POTION_BASE_8M_CAPABILITIES: PartialCapabilities = {
    "name": "minishlab/potion-base-8M",
    "default_dimension": 256,
    "context_window": 1_000_000,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "minishlab/potion-base-8M",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": False,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "BAAI/bge-base-en-v1.5",
        "framework": ["NumPy", "Sentence Transformers"],
        "license": "mit",
        "memory_usage_mb": 29,
        "modalities": ["text"],
        "n_parameters": 7560000,
        "open_weights": True,
        "reference": "https://huggingface.co/minishlab/potion-base-8M",
        "release_date": "2024-10-29",
        "revision": "dcbec7aa2d52fc76754ac6291803feedd8c619ce",
        "memory_usage_gb": 0.03,
        "public_training_code": "https://github.com/MinishLab/model2vec",
        "citation": "@software{minishlab2024model2vec,\n      authors = {Stephan Tulkens, Thomas van Dongen},\n      title = {Model2Vec: Turn any Sentence Transformer into a Small Fast Model},\n      year = {2024},\n      url = {https://github.com/MinishLab/model2vec}\n}",
    },
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    MINISHLAB_M2V_BASE_GLOVE_CAPABILITIES,
    MINISHLAB_M2V_BASE_GLOVE_SUBWORD_CAPABILITIES,
    MINISHLAB_M2V_BASE_OUTPUT_CAPABILITIES,
    MINISHLAB_M2V_MULTILINGUAL_OUTPUT_CAPABILITIES,
    MINISHLAB_POTION_BASE_2M_CAPABILITIES,
    MINISHLAB_POTION_BASE_4M_CAPABILITIES,
    MINISHLAB_POTION_BASE_8M_CAPABILITIES,
)


def get_minishlab_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for minishlab/model2vec embedding models."""
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    capabilities: list[EmbeddingCapabilitiesDict] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilitiesDict({**cap, "provider": provider})  # type: ignore[missing-typeddict-key]
            for provider in CAP_MAP[cap["name"]]  # type: ignore[invalid-argument-type]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)


__all__ = ("get_minishlab_embedding_capabilities",)
