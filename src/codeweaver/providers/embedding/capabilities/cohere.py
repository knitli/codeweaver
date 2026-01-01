# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Capabilities for Cohere embedding models."""

from __future__ import annotations

from types import MappingProxyType
from typing import ClassVar, Literal

from codeweaver.core import Provider
from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    EmbeddingModelSpec,
)
from codeweaver.providers.embedding.capabilities.types import PartialCapabilities


MODEL_MAP: MappingProxyType[Provider, tuple[str, ...]] = MappingProxyType({
    # Cohere SDK:
    Provider.AZURE: ("embed-english-v3.0", "embed-multilingual-v3.0", "embed-v4.0"),
    Provider.COHERE: (
        "embed-english-v3.0",
        "embed-multilingual-v3.0",
        "embed-multilingual-light-v3.0",
        "embed-v4.0",
    ),
    # Bedrock SDK:
    Provider.BEDROCK: ("cohere.embed-english-v3.0", "cohere.embed-multilingual-v3.0"),
    # OpenAI SDK:
    Provider.GITHUB: ("cohere/Cohere-embed-v3-english", "cohere/Cohere-embed-v3-multilingual"),
    Provider.HEROKU: ("cohere-embed-multilingual",),  # this is v3.0, they just don't say it.
    Provider.LITELLM: ("cohere/embed-english-v3.0", "cohere/embed-multilingual-v3.0"),
})


def _get_shared_cohere_embedding_capabilities() -> PartialCapabilities:
    return {
        "name": MODEL_MAP[Provider.COHERE],
        "provider": Provider.COHERE,
        "supports_context_chunk_embedding": False,
        "default_dtype": "float",
        "preferred_metrics": ("cosine", "dot", "euclidean"),
        "is_normalized": False,
        "tokenizer": "tokenizers",
        "output_dtypes": ("float",),
    }


def get_cohere_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:
    """Get the capabilities for cohere embedding models."""
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    shared_caps = _get_shared_cohere_embedding_capabilities()
    base_capabilities: dict[str, PartialCapabilities] = {
        "embed-english-v3.0": {
            **shared_caps,
            "version": 3,
            "default_dimension": 1024,
            "output_dimensions": (1024,),
            "context_window": 512,
        },
        "embed-multilingual-v3.0": {
            **shared_caps,
            "version": 3,
            "default_dimension": 1024,
            "output_dimensions": (1024,),
            "context_window": 512,
        },
        "embed-multilingual-light-v3.0": {
            **shared_caps,
            "version": 3,
            "default_dimension": 384,
            "output_dimensions": (384,),
            "context_window": 512,
        },
        "embed-v4.0": {
            **shared_caps,
            "version": 4,
            "default_dimension": 1536,
            "output_dimensions": (1536, 1024, 512, 256),
            "context_window": 128_000,
        },
    }
    output_models: list[EmbeddingModelCapabilities] = []
    for model, caps in base_capabilities.items():
        for provider, models in MODEL_MAP.items():
            if provider == Provider.GITHUB and model in (
                "embed-multilingual-v3.0",
                "embed-english-v3.0",
            ):
                model = models[0] if model == "embed-multilingual-v3.0" else models[1]
            elif provider == Provider.HEROKU and model == "embed-multilingual-v3.0":
                model = models[0]
            if model in models:
                output_models.append(
                    EmbeddingModelCapabilities.model_validate({
                        **caps,
                        "name": model,
                        "provider": provider,
                    })
                )
    return tuple(EmbeddingModelCapabilities.model_validate(m) for m in output_models)


class BaseCohereEmbeddingSpec(EmbeddingModelSpec):
    """Base spec for Cohere embedding models."""

    model_map: ClassVar[MappingProxyType[Provider, tuple[str, ...]]] = MODEL_MAP

    model_maker: ClassVar[Literal["cohere"]] = "cohere"

    mapped_names: MappingProxyType[str, str]
    """Map from Cohere model names to provider-specific model names."""

    @classmethod
    def models(cls) -> tuple[str, ...]:
        """Get the models available for this provider."""
        return cls.model_map[cls.provider]


class CohereAzureEmbeddingSpec(BaseCohereEmbeddingSpec):
    """Spec for Cohere embedding models on Azure."""

    provider: ClassVar[Provider] = Provider.AZURE

    mapped_names: MappingProxyType[str, str] = MappingProxyType(
        zip(MODEL_MAP[Provider.AZURE], MODEL_MAP[Provider.AZURE], strict=True)
    )

    capabilities: tuple[EmbeddingModelCapabilities, ...] = tuple(
        cap for cap in get_cohere_embedding_capabilities() if cap.provider == Provider.AZURE
    )


__all__ = ("get_cohere_embedding_capabilities",)
