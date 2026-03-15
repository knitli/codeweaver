# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""
Settings for Voyage AI embedding models.

Voyage AI models are CodeWeaver's recommended embedding models. They're high quality, low latency, and cost-effective (first 200M tokens are free).
Our default model is currently `voyage-4-large`, which can be queried with `voyage-4-nano` (see `SentenceTransformersEmbeddingCapabilities` for voyage-4-nano information), as well as every other member of the Voyage-4 family.

Voyage's models provide best-in-class performance, and even more interesting, they maintain that performance when heavily quantized. Performance when quantized to binary 256-dimensions still significantly exceeds openai's `text-embedding-3-large` at **1/384th** the storage size (and cost).

We take the unusual approach here of defaulting to output at int8 1024-dimensions, which provides identical performance to float 1024-dimensions, but at 1/4th the storage size and cost. This is a good default for most use cases, but you can change the output dimensions and data type in your profile if you need to.  Note though that Qdrant requires float *input* but can quantize down to int8 or binary. So we don't pass the 'int8' request to Voyage.
You can see the [performance comparisons here](https://docs.google.com/spreadsheets/d/1Q5GDXOXueHuBT9demPrL9bz3_LMgajcZs_-GPeawrYk/edit?gid=105010523#gid=105010523).

We think the other models are worth trying out too, because every codebase is different, and you might find that one of the other models works better for your specific use case.
We particularly think `voyage-context-3` is worth trying out. Unlike nearly all other embedding models, it produces embeddings that represent not just the chunk of text you provide, but also *the chunks of text as a whole*.
This means that it can produce embeddings that are more representative of the overall context of the document, rather than just the individual chunks.

Nevertheless, because we use semantic chunking for most code, you're not likely to see a significant difference in performance between `voyage-code-3` and `voyage-context-3` for most codebases. It may be more useful for codebases with languages we *don't* support for semantic chunking (hello Cobol!).

"""

from __future__ import annotations

from codeweaver.core import Provider, dependency_provider
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities, ModelFamily
from codeweaver.providers.embedding.capabilities.types import PartialCapabilities


def _get_shared_capabilities() -> PartialCapabilities:
    """Get the shared capabilities for all Voyage AI embedding models."""
    return {
        "provider": Provider.VOYAGE,
        "default_dimension": 1024,
        "output_dimensions": (256, 512, 1024, 2048),
        "default_dtype": "uint8",
        "output_dtypes": ("float", "uint8", "int8", "ubinary", "binary"),
        "is_normalized": True,
        "context_window": 32_000,
        "tokenizer": "tokenizers",
        "tokenizer_model": "voyageai/",
        "max_batch_tokens": 120_000,
        "preferred_metrics": ("dot",),
        # All voyageai models are normalized to length 1, so dot product will produce identical results to cosine similarity or Euclidean distance -- but is faster to compute.
    }


class Voyage4ModelFamily(ModelFamily):
    """Voyage-4 model family specification."""

    family_id: str = "voyage-4"
    default_dimension: int = 1024
    default_dtype: str = "uint8"
    is_normalized: bool = True
    preferred_metrics: tuple[str, ...] = ("dot",)
    member_models: frozenset[str] = frozenset({
        "voyage-4-large",
        "voyage-4",
        "voyage-4-lite",
        "voyage-4-nano",
        "voyageai/voyage-4-nano",  # the huggingface name for voyage-4-nano
        "onnx-community/voyage-4-nano-ONNX",  # the fastembed/ONNX name for voyage-4-nano
    })
    asymmetric_query_models: frozenset[str] = frozenset({
        "voyageai/voyage-4-nano",
        "voyage-4-nano",
        "voyage-4-lite",
        "voyage-4",
        "onnx-community/voyage-4-nano-ONNX",  # the fastembed/ONNX name for voyage-4-nano
    })
    cross_provider_compatible: bool = True


VOYAGE_4_FAMILY = Voyage4ModelFamily()
"""Voyage-4 model family specification.

The Voyage-4 family represents the fourth generation of Voyage AI's embedding models,
featuring a unified vector space. The models don't suffer a noticeable performance drop
with uint8 quantization, so we default to that to save on storage and compute costs.
All models in this family produce embeddings that can be directly compared and stored
together, enabling flexible model selection and migration strategies.

The most common strategy, which promotes excellent quality and cost savings, is to use `voyage-4-large` or `voyage-4` for embedding generation of your data (your codebase for CodeWeaver), and `voyage-4-nano`
to query it locally for free.

Key characteristics:
- Normalized embeddings (unit length) enable efficient dot product similarity
- Native uint8 output reduces storage by 75% vs float32 with minimal quality loss
- Cross-model compatibility allows mixing models (e.g., voyage-4-large for docs,
  voyage-4-nano for queries)
- voyage-4-nano is specialized for query-time use in asymmetric search scenarios

The family's cross-provider compatibility flag indicates these embeddings maintain
their properties even when accessed through different API providers (e.g., VoyageAI
native API vs third-party providers).
"""


class VoyageEmbeddingCapabilities(EmbeddingModelCapabilities):
    """Capabilities for Voyage AI embedding models."""


@dependency_provider(VoyageEmbeddingCapabilities, scope="singleton", collection=True)
def get_voyage_embedding_capabilities() -> tuple[VoyageEmbeddingCapabilities, ...]:
    """Get the capabilities for Voyage AI embedding models."""
    models = (
        "voyage-3-large",
        "voyage-3.5",
        "voyage-3.5-lite",
        "voyage-code-3",
        "voyage-context-3",
        "voyage-4-large",
        "voyage-4",
        "voyage-4-lite",
        "voyage-4-nano",
        "onnx-community/voyage-4-nano-ONNX",
    )
    settings = [{**_get_shared_capabilities()} for _ in models]
    for i, model in enumerate(models):
        settings[i]["name"] = model
        settings[i]["version"] = "3" if "3.5" not in model else "3.5"
        settings[i]["tokenizer_model"] = f"{settings[i]['tokenizer_model']}{model}"
        settings[i]["version"] = "3" if "3" in model else "4"
        # Assign model family for voyage-4 models
        if model.startswith("voyage-4"):
            settings[i]["model_family"] = VOYAGE_4_FAMILY

    return tuple(VoyageEmbeddingCapabilities.model_validate({**s}) for s in settings)


__all__ = ("Voyage4ModelFamily", "VoyageEmbeddingCapabilities", "get_voyage_embedding_capabilities")
