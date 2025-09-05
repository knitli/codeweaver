# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Cohere reranking model capabilities."""

from codeweaver._settings import Provider
from codeweaver.reranking.capabilities.base import RerankingModelCapabilities


def get_amazon_reranking_capabilities() -> tuple[RerankingModelCapabilities, ...]:
    """Get the capabilities of the Amazon reranking model."""
    return (
        RerankingModelCapabilities.model_validate({
            "name": "amazon.rerank-v1:0",
            "provider": Provider.BEDROCK,
            "max_input": 4096,  # we actually have no idea, Amazon doesn't provide any info on model capabilities and limits
            "supports_custom_prompt": False,
            # we'll default to tiktoken/cl100k_base because Amazon doesn't provide any info on tokenizer
            "tokenizer": "tiktoken",
            "tokenizer_model": "cl100k_base",
        }),
    )
