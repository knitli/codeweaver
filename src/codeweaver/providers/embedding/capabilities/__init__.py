# SPDX-FileCopyrightText: (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Entrypoint for CodeWeaver's embedding model capabilities.

This module now delegates storage and lookup to the global ModelRegistry.
It lazily registers built-in capabilities once and exposes simple helpers
to query by name/provider.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from importlib.util import find_spec
from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.alibaba_nlp import (
        get_alibaba_nlp_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.amazon import get_amazon_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.baai import get_baai_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.base import (
        EmbeddingModelCapabilities,
        SparseEmbeddingModelCapabilities,
    )
    from codeweaver.providers.embedding.capabilities.cohere import get_cohere_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.google import get_google_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.ibm_granite import (
        get_ibm_granite_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.intfloat import (
        get_intfloat_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.jinaai import get_jinaai_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.minishlab import (
        get_minishlab_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.mistral import (
        get_mistral_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.mixedbread_ai import (
        get_mixedbread_ai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.nomic_ai import (
        get_nomic_ai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.openai import get_openai_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.qwen import get_qwen_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.sentence_transformers import (
        get_sentence_transformers_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.snowflake import (
        get_snowflake_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.thenlper import (
        get_thenlper_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.types import (
        EmbeddingCapabilitiesDict,
        EmbeddingSettingsDict,
        PartialCapabilities,
    )
    from codeweaver.providers.embedding.capabilities.voyage import get_voyage_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.whereisai import (
        get_whereisai_embedding_capabilities,
    )


dependency_map = {
    "azure:embed": "cohere",
    "azure:text-embedding": "openai",
    "bedrock": "boto3",
    "cerebras": "openai",
    "cohere": "cohere",
    "fastembed": "fastembed",
    "fireworks": "openai",
    "github": "openai",
    "google": "genai",
    "heroku": "openai",
    "groq": "openai",
    "hf-inference": "huggingface_hub[inference]",
    "litellm": "openai",
    "minishlab": "sentence_transformers",
    "mistral": "mistralai",
    "ollama": "openai",
    "openai": "openai",
    "sentence_transformers": "sentence_transformers",
    "together": "openai",
    "vercel": "openai",
    "voyage": "voyageai",
}


def is_available(model: EmbeddingModelCapabilities) -> bool:
    """Check if a model is available for use."""
    model_string = f"{model.provider!s}:{model.name}"
    # custom fastembed models temporarily disabled until we can resolve issues
    if model.provider.variable == "fastembed" and model.name in {
        "Alibaba-NLP/gte-modernbert-base",
        "BAAI/bge-m3",
        "WhereIsAI/UAE-Large-V1",
        "snowflake/snowflake-arctic-embed-l-v2.0",
        "snowflake/snowflake-arctic-embed-m-v2.0",
    }:
        return False
    if dependency := next(
        (dep for key, dep in dependency_map.items() if model_string.startswith(key)), None
    ):
        return bool(find_spec(dependency))
    return False


def filter_unimplemented(
    models: tuple[EmbeddingModelCapabilities, ...],
) -> Generator[EmbeddingModelCapabilities]:
    """Removes models that are not yet implemented."""
    _unimplemented = {
        "heroku:cohere-embed-multilingual",
        "github:cohere/Cohere-embed-v3-english",
        "github:cohere/Cohere-embed-v3-multilingual",
    }
    for model in models:
        if is_available(model) and f"{model.provider!s}:{model.name}" not in _unimplemented:
            model._available = True  # type: ignore[attr-defined]
        # models are False by default so we don't need to set that
        yield model


def load_default_capabilities() -> Generator[EmbeddingModelCapabilities]:
    """Import and collect all built-in capabilities (once)."""
    from codeweaver.providers.embedding.capabilities.alibaba_nlp import (
        get_alibaba_nlp_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.amazon import get_amazon_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.baai import get_baai_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.cohere import get_cohere_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.google import get_google_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.ibm_granite import (
        get_ibm_granite_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.intfloat import (
        get_intfloat_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.jinaai import get_jinaai_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.minishlab import (
        get_minishlab_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.mistral import (
        get_mistral_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.mixedbread_ai import (
        get_mixedbread_ai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.nomic_ai import (
        get_nomic_ai_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.openai import get_openai_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.qwen import get_qwen_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.sentence_transformers import (
        get_sentence_transformers_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.snowflake import (
        get_snowflake_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.thenlper import (
        get_thenlper_embedding_capabilities,
    )
    from codeweaver.providers.embedding.capabilities.voyage import get_voyage_embedding_capabilities
    from codeweaver.providers.embedding.capabilities.whereisai import (
        get_whereisai_embedding_capabilities,
    )

    def fetch_caps(
        caller: Callable[..., tuple[EmbeddingModelCapabilities, ...]],
    ) -> Generator[EmbeddingModelCapabilities, None, None]:
        yield from filter_unimplemented(caller())

    for item in (
        get_alibaba_nlp_embedding_capabilities,
        get_amazon_embedding_capabilities,
        get_baai_embedding_capabilities,
        get_cohere_embedding_capabilities,
        get_google_embedding_capabilities,
        get_ibm_granite_embedding_capabilities,
        get_intfloat_embedding_capabilities,
        get_jinaai_embedding_capabilities,
        get_minishlab_embedding_capabilities,
        get_mistral_embedding_capabilities,
        get_mixedbread_ai_embedding_capabilities,
        get_nomic_ai_embedding_capabilities,
        get_openai_embedding_capabilities,
        get_qwen_embedding_capabilities,
        get_sentence_transformers_embedding_capabilities,
        get_snowflake_embedding_capabilities,
        get_thenlper_embedding_capabilities,
        get_voyage_embedding_capabilities,
        get_whereisai_embedding_capabilities,
    ):
        if item is None:
            continue
        yield from fetch_caps(item)


def load_sparse_capabilities() -> Generator[SparseEmbeddingModelCapabilities]:
    """Load all sparse embedding model capabilities."""
    from codeweaver.providers.embedding.capabilities.base import get_sparse_caps

    yield from (get_sparse_caps())


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "SparseEmbeddingModelCapabilities": (__spec__.parent, "base"),
    "EmbeddingModelCapabilities": (__spec__.parent, "base"),
    "get_alibaba_nlp_embedding_capabilities": (__spec__.parent, "alibaba_nlp"),
    "get_amazon_embedding_capabilities": (__spec__.parent, "amazon"),
    "get_baai_embedding_capabilities": (__spec__.parent, "baai"),
    "get_cohere_embedding_capabilities": (__spec__.parent, "cohere"),
    "get_google_embedding_capabilities": (__spec__.parent, "google"),
    "get_ibm_granite_embedding_capabilities": (__spec__.parent, "ibm_granite"),
    "get_intfloat_embedding_capabilities": (__spec__.parent, "intfloat"),
    "get_jinaai_embedding_capabilities": (__spec__.parent, "jinaai"),
    "get_minishlab_embedding_capabilities": (__spec__.parent, "minishlab"),
    "get_mistral_embedding_capabilities": (__spec__.parent, "mistral"),
    "get_mixedbread_ai_embedding_capabilities": (__spec__.parent, "mixedbread_ai"),
    "get_nomic_ai_embedding_capabilities": (__spec__.parent, "nomic_ai"),
    "get_openai_embedding_capabilities": (__spec__.parent, "openai"),
    "get_qwen_embedding_capabilities": (__spec__.parent, "qwen"),
    "get_sentence_transformers_embedding_capabilities": (__spec__.parent, "sentence_transformers"),
    "get_snowflake_embedding_capabilities": (__spec__.parent, "snowflake"),
    "get_thenlper_embedding_capabilities": (__spec__.parent, "thenlper"),
    "get_voyage_embedding_capabilities": (__spec__.parent, "voyage"),
    "get_whereisai_embedding_capabilities": (__spec__.parent, "whereisai"),
    "EmbeddingCapabilitiesDict": (__spec__.parent, "types"),
    "PartialCapabilities": (__spec__.parent, "types"),
    "EmbeddingSettingsDict": (__spec__.parent, "types"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "EmbeddingCapabilitiesDict",
    "EmbeddingModelCapabilities",
    "EmbeddingSettingsDict",
    "PartialCapabilities",
    "SparseEmbeddingModelCapabilities",
    "get_alibaba_nlp_embedding_capabilities",
    "get_amazon_embedding_capabilities",
    "get_baai_embedding_capabilities",
    "get_cohere_embedding_capabilities",
    "get_google_embedding_capabilities",
    "get_ibm_granite_embedding_capabilities",
    "get_intfloat_embedding_capabilities",
    "get_jinaai_embedding_capabilities",
    "get_minishlab_embedding_capabilities",
    "get_mistral_embedding_capabilities",
    "get_mixedbread_ai_embedding_capabilities",
    "get_nomic_ai_embedding_capabilities",
    "get_openai_embedding_capabilities",
    "get_qwen_embedding_capabilities",
    "get_sentence_transformers_embedding_capabilities",
    "get_snowflake_embedding_capabilities",
    "get_thenlper_embedding_capabilities",
    "get_voyage_embedding_capabilities",
    "get_whereisai_embedding_capabilities",
    "load_default_capabilities",
    "load_sparse_capabilities",
)


def __dir__() -> list[str]:
    return list(__all__)
