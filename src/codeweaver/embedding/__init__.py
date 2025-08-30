# Copyright (c) 2024 to present Pydantic Services Inc
# SPDX-License-Identifier: MIT
# Applies to original code in this directory (`src/codeweaver/embedding/`) from `pydantic_ai`.
#
# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding/`)
"""Entrypoint for CodeWeaver's heavily-pydantic-ai-inspired embedding model system."""

# sourcery skip: avoid-global-variables
from __future__ import annotations

from typing import Any, Literal

from codeweaver._settings import EmbeddingModelSettings, EmbeddingProviderSettings, Provider


def _add_compatible_keys(
    model_settings: EmbeddingModelSettings, compatible_keys: dict[str, str]
) -> dict[str, Any]:
    """Add any keys in settings that are compatible with the provider.

    Args:
        model_settings: The model settings to process.
        compatible_keys: A mapping of keys in the model settings to keys expected by the provider.
    """
    compatible_settings: dict[str, Any] = {
        compatible_keys[key]: value
        for key, value in model_settings.items()
        if key in compatible_keys
    }
    return compatible_settings


def _process_model_settings(model_settings: EmbeddingModelSettings) -> dict[str, Any]:
    """Process model settings to ensure they are valid."""
    provider = Provider.from_string(model_settings["model"].split(":")[0])
    processed_settings = {
        "provider": provider,
        "model": "".join(model_settings["model"].split(":")[1:]),
    }
    match provider:
        case Provider.VOYAGE:
            return processed_settings | _add_compatible_keys(
                model_settings,
                {
                    "dimension": "output_dimension",
                    "data_type": "output_dtype",
                    "client_kwargs": "kwargs",
                },
            )
        case _:
            return processed_settings | _add_compatible_keys(
                model_settings, {"client_kwargs": "kwargs"}
            )

    return processed_settings


def user_settings_to_provider_settings(
    user_settings: EmbeddingProviderSettings,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Convert user settings to provider settings."""
    model_settings: EmbeddingModelSettings | tuple[EmbeddingModelSettings, ...] = user_settings[
        "model_settings"
    ]
    return (
        [_process_model_settings(ms) for ms in model_settings]
        if isinstance(model_settings, tuple)
        else _process_model_settings(model_settings)
    )


def get_embedding_model_provider() -> None:  # -> EmbeddingProvider[Any]:
    """Get embedding model provider."""


type KnownEmbeddingModelName = Literal[
    "azure:embed-v-4-0",  # cohere v4
    "azure:text-embedding-3-large",
    "azure:text-embedding-3-small",
    "bedrock:amazon.titan-embed-text-v2:0",
    "bedrock:cohere.embed-english-v3.0",
    "bedrock:cohere.embed-multilingual-v3.0",
    "cohere:embed-english-v3.0",
    "cohere:embed-multilingual-light-v3.0",
    "cohere:embed-multilingual-v3.0",
    "cohere:embed-v4.0",
    "fastembed:BAAI/bge-base-en-v1.5",
    "fastembed:BAAI/bge-large-en-v1.5",
    "fastembed:BAAI/bge-small-en-v1.5",
    "fastembed:jinaai/jina-embeddings-v2-base-code",
    "fastembed:jinaai/jina-embeddings-v3",
    "fastembed:nomic-ai/nomic-embed-text-v1.5",
    "fastembed:nomic-ai/nomic-embed-text-v1.5-Q",
    "fastembed:sentence-transformers/all-MiniLM-L6-v2",
    "fastembed:snowflake/snowflake-arctic-embed-l",  # hf lists these without the snowflake in the name
    "fastembed:snowflake/snowflake-arctic-embed-m",
    "fastembed:snowflake/snowflake-arctic-embed-m-long",
    "fastembed:snowflake/snowflake-arctic-embed-s",
    "fastembed:snowflake/snowflake-arctic-embed-xs",
    "fastembed:thenlper/gte-base",
    "fastembed:thenlper/gte-large",
    "fireworks:WhereIsAI/UAE-Large-V1",
    "fireworks:nomic-ai/nomic-embed-text-v1.5",
    "fireworks:thenlper/gte-base",
    "fireworks:thenlper/gte-large",
    "github:cohere/Cohere-embed-v3-english",
    "github:cohere/Cohere-embed-v3-multilingual",
    "github:openai/text-embedding-3-large",
    "github:openai/text-embedding-3-small",
    "google:gemini-embedding-001",
    "google:gemini-embedding-exp-03-07",
    "groq:Alibaba-NLP/gte-modernbert-base",
    "heroku:cohere-embed-multilingual",
    "hf-inference:Alibaba-NLP/gte-modernbert-base",
    "hf-inference:BAAI/bge-small-en-v1.5",
    "hf-inference:BAAI/bge-base-en-v1.5",
    "hf-inference:BAAI/bge-large-en-v1.5",
    "hf-inference:BAAI/bge-m3",
    "hf-inference:ibm-granite/granite-embedding-278m-multilingual",
    "hf-inference:intfloat/multilingual-e5-large",
    "hf-inference:nomic-ai/modernbert-embed-base",
    "hf-inference:sentence-transformers/all-MiniLM-L6-v2",
    "hf-inference:sentence-transformers/all-MiniLM-L12-v2",
    "hf-inference:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "hf-inference:sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "hf-inference:sentence-transformers/LaBSE",
    "hf-inference:sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
    "hf-inference:sentence-transformers/all-mpnet-base-v2",
    "hf-inference:sentence-transformers/gtr-t5-base",
    "hf-inference:Snowflake/snowflake-arctic-embed-l-v2.0",
    "hf-inference:WhereIsAI/UAE-Large-V1mistral:codestral-embed",
    "mistral:mistral-embed",
    "ollama:all-minilm",
    "ollama:mxbai-embed-large",
    "ollama:nomic-embed-text",
    "openai:text-embedding-3-large",
    "openai:text-embedding-3-small",
    "sentence-transformers:Alibaba-NLP/gte-multilingual-base",
    "sentence-transformers:Alibaba-NLP/gte-modernbert-base",
    "sentence-transformers:BAAI/bge-m3",
    "sentence-transformers:Qwen/Qwen3-Embedding-0.6B",
    "sentence-transformers:Qwen/Qwen3-Embedding-4B",
    "sentence-transformers:Qwen/Qwen3-Embedding-8B",
    "sentence-transformers:sentence-transformers/all-MiniLM-L12-v2",
    "sentence-transformers:sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers:jinaai/jina-embeddings-v4",
    "together:Alibaba-NLP/gte-modernbert-base",
    "together:BAAI/bge-base-en-v1.5",
    "together:BAAI/bge-large-en-v1.5",
    "together:intfloat/multilingual-e5-large-instruct",
    "vercel:text-embedding-3-large",
    "vercel:text-embedding-3-small",
    "voyage:voyage-3-large",
    "voyage:voyage-3.5",
    "voyage:voyage-3.5-lite",
    "voyage:voyage-code-3",
    "voyage:voyage-context-3",
]


type KnownSparseEmbeddingModelName = Literal[
    "fastembed:prithivida/Splade_PP_en_v2",
    "fastembed:Qdrant/bm42-all-minilm-l6-v2-attentions",
    "fastembed:Qdrant/bm25",
    "sentence-transformers:prithivida/Splade_PP_en_v2",
    "sentence-transformers:ibm-granite/granite-embedding-30m-sparse",
    "sentence-transformers:opensearch-project/opensearch-neural-sparse-encoding-doc-v2-mini",
]
