# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reranking model capabilities for BAAI models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


def get_baai_reranking_capabilities() -> Sequence[RerankingModelCapabilities]:
    """Get the BAAI reranking model capabilities."""
    from codeweaver.providers.provider import Provider
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
    from codeweaver.providers.reranking.capabilities.types import PartialRerankingCapabilities

    shared_capabilities: PartialRerankingCapabilities = {
        "name": "BAAI/bge-reranking-",
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
