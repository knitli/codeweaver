# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reranking model capabilities for BAAI models."""

from collections.abc import Sequence

from codeweaver.provider import Provider
from codeweaver.reranking.capabilities.base import (
    PartialRerankingCapabilities,
    RerankingModelCapabilities,
)


def get_baai_reranking_capabilities() -> Sequence[RerankingModelCapabilities]:
    """Get the BAAI reranking model capabilities."""
    shared_capabilities: PartialRerankingCapabilities = {
        "name": "BAAI/bge-reranker-",
        "tokenizer": "tokenizers",
        "supports_custom_prompt": False,
    }
    models = ("base", "large", "v2-m3")
    return [
        RerankingModelCapabilities.model_validate({
            **shared_capabilities,
            "name": f"{shared_capabilities['name']}{model}",
            "max_input": 8192 if model == "v2-m3" else 512,
            "context_window": 8192 if model == "v2-m3" else 512,
            "tokenizer_model": f"{shared_capabilities['name']}{model}",
            "provider": Provider.FASTEMBED if model == "base" else Provider.SENTENCE_TRANSFORMERS,
        })
        for model in models
    ]


__all__ = ("get_baai_reranking_capabilities",)
