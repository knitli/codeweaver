# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reranking model capabilities for BAAI models."""

from __future__ import annotations

from codeweaver.core import dependency_provider
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


class BaaiRerankingCapabilities(RerankingModelCapabilities):
    """Capabilities for BAAI reranking models."""


@dependency_provider(BaaiRerankingCapabilities, scope="singleton", collection=True)
def get_baai_reranking_capabilities() -> tuple[BaaiRerankingCapabilities, ...]:
    """Get the BAAI reranking model capabilities."""
    from codeweaver.core import Provider
    from codeweaver.providers.reranking.capabilities.types import PartialRerankingCapabilitiesDict

    shared_capabilities: PartialRerankingCapabilitiesDict = {
        "name": "BAAI/bge-reranking-",
        "tokenizer": "tokenizers",
        "supports_custom_prompt": False,
    }
    models = ("base", "large", "v2-m3")
    return tuple(
        BaaiRerankingCapabilities.model_validate({
            **shared_capabilities,
            "name": f"{shared_capabilities['name']}{model}",
            "max_input": 8192 if model == "v2-m3" else 512,
            "context_window": 8192 if model == "v2-m3" else 512,
            "tokenizer_model": f"{shared_capabilities['name']}{model}",
            "provider": Provider.FASTEMBED if model == "base" else Provider.SENTENCE_TRANSFORMERS,
        })
        for model in models
    )


__all__ = ("get_baai_reranking_capabilities",)
