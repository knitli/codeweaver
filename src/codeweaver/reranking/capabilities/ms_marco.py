# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reranking capabilities for MS-Marco trained MiniLM models."""

import re

from collections.abc import Sequence

from codeweaver.provider import Provider
from codeweaver.reranking.capabilities.base import (
    PartialRerankingCapabilities,
    RerankingModelCapabilities,
)


def get_marco_reranking_capabilities() -> Sequence[RerankingModelCapabilities]:
    """
    Get the MS-Marco MiniLM reranking capabilities.
    """
    shared_capabilities: PartialRerankingCapabilities = {
        "name": "Xenova/ms-marco-MiniLM-",
        "max_input": 512,
        "context_window": 512,
        "tokenizer": "tokenizers",
        "tokenizer_model": "cross-encoder/ms-marco-MiniLM-L6-v2",
        "supports_custom_prompt": False,
    }
    fastembed_models = ("L-6-v2", "L-12-v2")
    sentence_transformers_models = ("L6-v2", "L12-v2")

    assembled_capabilities: list[RerankingModelCapabilities] = []
    assembled_capabilities.extend(
        RerankingModelCapabilities.model_validate({
            **shared_capabilities,
            "name": f"{shared_capabilities['name']}{model}"
            if re.match(r"^L-[61].*", model)
            else f"{shared_capabilities['name']}{model.replace('Xenova', 'cross-encoder')}",
            "provider": Provider.FASTEMBED
            if re.match(r"^L-[61].*", model)
            else Provider.SENTENCE_TRANSFORMERS,
            "tokenizer_model": shared_capabilities["tokenizer_model"]
            if shared_capabilities["name"] in {"L-6-v2", "L6-V2"}
            else "cross-encoder/ms-marco-MiniLM-L12-v2",
        })
        for model in fastembed_models + sentence_transformers_models
    )
    return assembled_capabilities


__all__ = ("get_marco_reranking_capabilities",)
