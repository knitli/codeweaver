# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reranking model capabilities for JinaAI models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


def get_jinaai_reranking_capabilities() -> Sequence[RerankingModelCapabilities]:
    """Get the JinaAI reranking model capabilities."""
    from codeweaver.providers.provider import Provider
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities

    capabilities = {
        "jinaai/jina-reranking-v2-base-multilingual": {
            "provider": Provider.FASTEMBED,
            "max_input": 8192,
            "context_window": 8192,
            "max_query_length": 512,
            "tokenizer": "tokenizers",
            "tokenizer_model": "jinaai/jina-reranking-v2-base-multilingual",
            "supports_custom_prompt": False,
        },
        "jinaai/jina-reranking-m0": {
            "provider": Provider.SENTENCE_TRANSFORMERS,
            "max_input": 10_240,
            "context_window": 10_240,
            "tokenizer": "tokenizers",
            "tokenizer_model": "jinaai/jina-reranking-m0",
            "supports_custom_prompt": False,
        },
    }
    return [
        RerankingModelCapabilities.model_validate({**cap, "name": name})
        for name, cap in capabilities.items()
    ]


__all__ = ("get_jinaai_reranking_capabilities",)
