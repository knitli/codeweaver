# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.
"""Capabilities for Snowflake embedding models."""

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


type SnowflakeProvider = Literal[
    Provider.FASTEMBED,
    Provider.HUGGINGFACE_INFERENCE,
    Provider.OLLAMA,
    Provider.SENTENCE_TRANSFORMERS,
]

CAP_MAP: dict[
    Literal[
        "Snowflake/snowflake-arctic-embed-l",
        "Snowflake/snowflake-arctic-embed-l-v2.0",
        "snowflake-arctic-embed2:568m",
        "Snowflake/snowflake-arctic-embed-m",
        "Snowflake/snowflake-arctic-embed-m-long",
        "Snowflake/snowflake-arctic-embed-m-v2.0",
        "Snowflake/snowflake-arctic-embed-s",
        "Snowflake/snowflake-arctic-embed-xs",
    ],
    tuple[SnowflakeProvider, ...],
] = {
    "Snowflake/snowflake-arctic-embed-l": (Provider.FASTEMBED,),
    "Snowflake/snowflake-arctic-embed-l-v2.0": (
        Provider.HUGGINGFACE_INFERENCE,
        Provider.SENTENCE_TRANSFORMERS,
        Provider.FASTEMBED,
    ),
    "snowflake-arctic-embed2:568m": (Provider.OLLAMA,),
    "Snowflake/snowflake-arctic-embed-m": (Provider.FASTEMBED,),
    "Snowflake/snowflake-arctic-embed-m-long": (Provider.FASTEMBED,),
    "Snowflake/snowflake-arctic-embed-m-v2.0": (Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS),
    "Snowflake/snowflake-arctic-embed-s": (Provider.FASTEMBED,),
    "Snowflake/snowflake-arctic-embed-xs": (Provider.FASTEMBED,),
}


SNOWFLAKE_ARCTIC_EMBED2_568M_CAPABILITIES: PartialCapabilities = {
    "name": "snowflake-arctic-embed2:568m",
    "default_dimension": 1024,
    "context_window": 8192,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "snowflake-arctic-embed-l-v2.0",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
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
        "memory_usage_gb": 2.12,
    },
    "hf_name": "Snowflake/snowflake-arctic-embed-l-v2.0",
}

SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_L_CAPABILITIES: PartialCapabilities = {
    "name": "Snowflake/snowflake-arctic-embed-l",
    "default_dimension": 1024,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Snowflake/snowflake-arctic-embed-l",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "intfloat/e5-base-unsupervised",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "Snowflake/snowflake-arctic-embed-l",
            "revision": "9a9e5834d2e89cdd8bb72b64111dde496e4fe78c",
        },
        "memory_usage_mb": 1274,
        "modalities": ["text"],
        "n_parameters": 335000000,
        "open_weights": True,
        "reference": "https://huggingface.co/Snowflake/snowflake-arctic-embed-l",
        "release_date": "2024-04-12",
        "revision": "9a9e5834d2e89cdd8bb72b64111dde496e4fe78c",
        "superseded_by": "Snowflake/snowflake-arctic-embed-l-v2.0",
        "memory_usage_gb": 1.24,
    },
}

SNOWFLAKE_ARCTIC_EMBED_L_V2_0_CAPABILITIES: PartialCapabilities = {
    "name": "Snowflake/snowflake-arctic-embed-l-v2.0",
    "default_dimension": 1024,
    "context_window": 8192,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Snowflake/snowflake-arctic-embed-l-v2.0",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 2.0,
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
        "memory_usage_gb": 2.12,
    },
    "hf_name": "Snowflake/snowflake-arctic-embed-l-v2.0",
}

SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_CAPABILITIES: PartialCapabilities = {
    "name": "Snowflake/snowflake-arctic-embed-m",
    "default_dimension": 768,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Snowflake/snowflake-arctic-embed-m",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "intfloat/e5-base-unsupervised",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "Snowflake/snowflake-arctic-embed-m",
            "revision": "cc17beacbac32366782584c8752220405a0f3f40",
        },
        "memory_usage_mb": 415,
        "modalities": ["text"],
        "n_parameters": 109000000,
        "open_weights": True,
        "reference": "https://huggingface.co/Snowflake/snowflake-arctic-embed-m",
        "release_date": "2024-04-12",
        "revision": "cc17beacbac32366782584c8752220405a0f3f40",
        "superseded_by": "Snowflake/snowflake-arctic-embed-m-v1.5",
        "memory_usage_gb": 0.41,
    },
}

SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_LONG_CAPABILITIES: PartialCapabilities = {
    "name": "Snowflake/snowflake-arctic-embed-m-long",
    "default_dimension": 768,
    "context_window": 2048,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Snowflake/snowflake-arctic-embed-m-long",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "nomic-ai/nomic-embed-text-v1-unsupervised",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "Snowflake/snowflake-arctic-embed-m-long",
            "revision": "89d0f6ab196eead40b90cb6f9fefec01a908d2d1",
            "trust_remote_code": True,
        },
        "memory_usage_mb": 522,
        "modalities": ["text"],
        "n_parameters": 137000000,
        "open_weights": True,
        "reference": "https://huggingface.co/Snowflake/snowflake-arctic-embed-m-long",
        "release_date": "2024-04-12",
        "revision": "89d0f6ab196eead40b90cb6f9fefec01a908d2d1",
        "superseded_by": "Snowflake/snowflake-arctic-embed-m-v2.0",
        "memory_usage_gb": 0.51,
    },
}

SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_V2_0_CAPABILITIES: PartialCapabilities = {
    "name": "Snowflake/snowflake-arctic-embed-m-v2.0",
    "default_dimension": 768,
    "context_window": 8192,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Snowflake/snowflake-arctic-embed-m-v2.0",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": 2.0,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "Alibaba-NLP/gte-multilingual-base",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "Snowflake/snowflake-arctic-embed-m-v2.0",
            "revision": "f2a7d59d80dfda5b1d14f096f3ce88bb6bf9ebdc",
            "trust_remote_code": True,
        },
        "memory_usage_mb": 1165,
        "modalities": ["text"],
        "n_parameters": 305000000,
        "open_weights": True,
        "reference": "https://huggingface.co/Snowflake/snowflake-arctic-embed-m-v2.0",
        "release_date": "2024-12-04",
        "revision": "f2a7d59d80dfda5b1d14f096f3ce88bb6bf9ebdc",
        "memory_usage_gb": 1.14,
    },
}

SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_S_CAPABILITIES: PartialCapabilities = {
    "name": "Snowflake/snowflake-arctic-embed-s",
    "default_dimension": 384,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Snowflake/snowflake-arctic-embed-s",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "intfloat/e5-small-unsupervised",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "Snowflake/snowflake-arctic-embed-s",
            "revision": "d3c1d2d433dd0fdc8e9ca01331a5f225639e798f",
        },
        "memory_usage_mb": 127,
        "modalities": ["text"],
        "n_parameters": 32200000,
        "open_weights": True,
        "reference": "https://huggingface.co/Snowflake/snowflake-arctic-embed-s",
        "release_date": "2024-04-12",
        "revision": "d3c1d2d433dd0fdc8e9ca01331a5f225639e798f",
        "memory_usage_gb": 0.12,
    },
}

SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_XS_CAPABILITIES: PartialCapabilities = {
    "name": "Snowflake/snowflake-arctic-embed-xs",
    "default_dimension": 384,
    "context_window": 512,
    "preferred_metrics": ("cosine", "dot", "euclidean"),
    "supports_context_chunk_embedding": False,
    "tokenizer": "tokenizers",
    "tokenizer_model": "Snowflake/snowflake-arctic-embed-xs",
    "default_dtype": "float",
    "output_dtypes": ("float",),
    "version": None,
    "supports_custom_prompts": True,
    "custom_query_prompt": None,
    "custom_document_prompt": None,
    "other": {
        "adapted_from": "sentence-transformers/all-MiniLM-L6-v2",
        "framework": ["Sentence Transformers", "PyTorch"],
        "license": "apache-2.0",
        "loader": {
            "model_name": "Snowflake/snowflake-arctic-embed-xs",
            "revision": "742da4f66e1823b5b4dbe6c320a1375a1fd85f9e",
        },
        "memory_usage_mb": 86,
        "modalities": ["text"],
        "n_parameters": 22600000,
        "open_weights": True,
        "reference": "https://huggingface.co/Snowflake/snowflake-arctic-embed-xs",
        "release_date": "2024-07-08",
        "revision": "742da4f66e1823b5b4dbe6c320a1375a1fd85f9e",
        "memory_usage_gb": 0.08,
    },
}


ALL_CAPABILITIES: tuple[PartialCapabilities, ...] = (
    SNOWFLAKE_ARCTIC_EMBED2_568M_CAPABILITIES,
    SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_L_CAPABILITIES,
    SNOWFLAKE_ARCTIC_EMBED_L_V2_0_CAPABILITIES,
    SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_CAPABILITIES,
    SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_LONG_CAPABILITIES,
    SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_M_V2_0_CAPABILITIES,
    SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_S_CAPABILITIES,
    SNOWFLAKE_SNOWFLAKE_ARCTIC_EMBED_XS_CAPABILITIES,
)


def get_snowflake_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for Snowflake embedding models."""
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    capabilities: list[EmbeddingCapabilities] = []
    for cap in ALL_CAPABILITIES:
        capabilities.extend([
            EmbeddingCapabilities({**cap, "provider": provider})
            for provider in CAP_MAP[cap["name"]]
        ])
    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)


__all__ = ("get_snowflake_embedding_capabilities",)
