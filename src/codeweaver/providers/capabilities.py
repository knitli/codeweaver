# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Metadata about provider capabilities for all provider kinds in CodeWeaver.

This module's capabilities are high-level and not specific to any model or version, focused on overall provider services. For more granular capabilities,
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Literal, cast

from codeweaver.providers.provider import Provider, ProviderKind


type LiteralProviderKind = Literal[
    ProviderKind.AGENT,
    ProviderKind.DATA,
    ProviderKind.EMBEDDING,
    ProviderKind.RERANKING,
    ProviderKind.SPARSE_EMBEDDING,
    ProviderKind.VECTOR_STORE,
]
type LiteralProvider = Literal[
    Provider.ANTHROPIC,
    Provider.AZURE,
    Provider.BEDROCK,
    Provider.CEREBRAS,
    Provider.COHERE,
    Provider.DEEPSEEK,
    Provider.DUCKDUCKGO,
    Provider.FASTEMBED,
    Provider.FIREWORKS,
    Provider.GITHUB,
    Provider.GOOGLE,
    Provider.GROQ,
    Provider.HEROKU,
    Provider.HUGGINGFACE_INFERENCE,
    Provider.LITELLM,
    Provider.MISTRAL,
    Provider.MOONSHOT,
    Provider.OLLAMA,
    Provider.OPENAI,
    Provider.OPENROUTER,
    Provider.PERPLEXITY,
    Provider.QDRANT,
    Provider.SENTENCE_TRANSFORMERS,
    Provider.TAVILY,
    Provider.TOGETHER,
    Provider.VERCEL,
    Provider.VOYAGE,
    Provider.X_AI,
]

# TODO: Add more vector providers as they are supported.
# TODO: Add QDRANT-CLOUD as an embedding provider (and add support).

# TODO: The vector provider capabilities aren't what they need to be.... it needs to be things like sparse vectors, quantization, etc.
VECTOR_PROVIDER_CAPABILITIES: MappingProxyType[LiteralProvider, str] = cast(
    MappingProxyType[LiteralProvider, str], MappingProxyType({Provider.QDRANT: "placeholder"})
)

PROVIDER_CAPABILITIES: MappingProxyType[LiteralProvider, tuple[LiteralProviderKind, ...]] = cast(
    MappingProxyType[LiteralProvider, tuple[LiteralProviderKind, ...]],
    MappingProxyType({
        Provider.ANTHROPIC: (ProviderKind.AGENT,),
        Provider.AZURE: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.BEDROCK: (ProviderKind.EMBEDDING, ProviderKind.RERANKING, ProviderKind.AGENT),
        Provider.CEREBRAS: (ProviderKind.AGENT,),
        Provider.COHERE: (ProviderKind.EMBEDDING, ProviderKind.RERANKING, ProviderKind.AGENT),
        Provider.DEEPSEEK: (ProviderKind.AGENT,),
        Provider.DUCKDUCKGO: (ProviderKind.DATA,),
        Provider.FASTEMBED: (
            ProviderKind.EMBEDDING,
            ProviderKind.RERANKING,
            ProviderKind.SPARSE_EMBEDDING,
        ),
        Provider.FIREWORKS: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.GITHUB: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.GOOGLE: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.X_AI: (ProviderKind.AGENT,),
        Provider.GROQ: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.HEROKU: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.HUGGINGFACE_INFERENCE: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.MISTRAL: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.MOONSHOT: (ProviderKind.AGENT,),
        Provider.OLLAMA: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.OPENAI: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.OPENROUTER: (ProviderKind.AGENT,),
        Provider.PERPLEXITY: (ProviderKind.AGENT,),
        Provider.QDRANT: (ProviderKind.VECTOR_STORE,),
        Provider.SENTENCE_TRANSFORMERS: (
            ProviderKind.EMBEDDING,
            ProviderKind.RERANKING,
            ProviderKind.SPARSE_EMBEDDING,
        ),
        Provider.TAVILY: (ProviderKind.DATA,),
        Provider.TOGETHER: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.VERCEL: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
        Provider.VOYAGE: (ProviderKind.EMBEDDING, ProviderKind.RERANKING),
    }),
)


def get_provider_kinds(provider: LiteralProvider) -> tuple[LiteralProviderKind, ...]:
    """Get capabilities for a provider."""
    return PROVIDER_CAPABILITIES.get(provider, (ProviderKind.DATA,))


__all__ = ("PROVIDER_CAPABILITIES", "VECTOR_PROVIDER_CAPABILITIES", "get_provider_kinds")
