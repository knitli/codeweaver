# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Cohere reranking model capabilities."""

from collections.abc import Sequence

from pydantic import NonNegativeInt

from codeweaver._data_structures import CodeChunk
from codeweaver.reranking.capabilities.base import (
    PartialRerankingCapabilities,
    Provider,
    RerankingModelCapabilities,
)
from codeweaver.tokenizers import get_tokenizer


def cohere_max_input(chunks: Sequence[CodeChunk], query: str) -> tuple[bool, NonNegativeInt]:
    """Determine the maximum input length for the Cohere model."""
    tokenizer = get_tokenizer("tokenizers", "Cohere/rerank-v3.5")
    sizes = [
        tokenizer.estimate(chunk.serialize_for_embedding()) + tokenizer.estimate(query)  # pyright: ignore[reportArgumentType]
        for chunk in chunks
    ]
    if all(size <= 4096 for size in sizes):
        return True, 4096
    return False, next(i - 1 for i, size in enumerate(sizes) if size > 4096)


def _get_common_capabilities() -> PartialRerankingCapabilities:
    """
    Get the common capabilities for Cohere models.
    """
    return {
        "max_input": cohere_max_input,
        "context_window": 4096,
        "supports_custom_prompt": False,
        "tokenizer": "tokenizers",
    }


def get_cohere_reranking_capabilities() -> tuple[RerankingModelCapabilities, ...]:
    """Get the capabilities of the Cohere reranking model."""
    base_capabilities = _get_common_capabilities()
    capabilities: list[RerankingModelCapabilities] = [
        RerankingModelCapabilities.model_validate({
            **base_capabilities,
            "name": model,
            "provider": Provider.COHERE,
            "tokenizer_model": f"Cohere/{model}",
        })
        for model in ("rerank-v3.5", "rerank-english-v3.0", "rerank-multilingual-v3.0")
    ]
    return (
        *capabilities,
        RerankingModelCapabilities.model_validate({
            **base_capabilities,
            "name": "rerank-v3-5:0",
            "provider": Provider.BEDROCK,
            "tokenizer_model": "Cohere/rerank-v3.5",
        }),
    )


__all__ = ("get_cohere_reranking_capabilities",)
