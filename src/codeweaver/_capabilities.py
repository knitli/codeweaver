# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Metadata about provider capabilities for all provider kinds in CodeWeaver."""

from types import MappingProxyType

from codeweaver.provider import LiteralProvider, LiteralProviderKind, Provider, ProviderKind


# TODO: The vector provider capabilities aren't what they need to be.... it needs to be things like sparse vectors, quantization, etc.
VECTOR_PROVIDER_CAPABILITIES: MappingProxyType[LiteralProvider, str] = MappingProxyType({
    Provider.QDRANT: "placeholder"
})

PROVIDER_CAPABILITIES: MappingProxyType[LiteralProvider, frozenset[LiteralProviderKind]] = (
    MappingProxyType({
        Provider.ANTHROPIC: frozenset({ProviderKind.AGENT}),
        Provider.AZURE: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.BEDROCK: frozenset({
            ProviderKind.EMBEDDING,
            ProviderKind.RERANKING,
            ProviderKind.AGENT,
        }),
        Provider.COHERE: frozenset({
            ProviderKind.EMBEDDING,
            ProviderKind.RERANKING,
            ProviderKind.AGENT,
        }),
        Provider.DEEPSEEK: frozenset({ProviderKind.AGENT}),
        Provider.DUCKDUCKGO: frozenset({ProviderKind.DATA}),
        Provider.FASTEMBED: frozenset({
            ProviderKind.EMBEDDING,
            ProviderKind.RERANKING,
            ProviderKind.SPARSE_EMBEDDING,
        }),
        Provider.FIREWORKS: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.GITHUB: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.GOOGLE: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.X_AI: frozenset({ProviderKind.AGENT}),
        Provider.GROQ: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.HEROKU: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.HUGGINGFACE_INFERENCE: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.MISTRAL: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.MOONSHOT: frozenset({ProviderKind.AGENT}),
        Provider.OLLAMA: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.OPENAI: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.OPENROUTER: frozenset({ProviderKind.AGENT}),
        Provider.PERPLEXITY: frozenset({ProviderKind.AGENT}),
        Provider.QDRANT: frozenset({ProviderKind.VECTOR_STORE}),
        Provider.SENTENCE_TRANSFORMERS: frozenset({
            ProviderKind.EMBEDDING,
            ProviderKind.RERANKING,
            ProviderKind.SPARSE_EMBEDDING,
        }),
        Provider.TAVILY: frozenset({ProviderKind.DATA}),
        Provider.TOGETHER: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.VERCEL: frozenset({ProviderKind.AGENT, ProviderKind.EMBEDDING}),
        Provider.VOYAGE: frozenset({ProviderKind.EMBEDDING, ProviderKind.RERANKING}),
    })
)


def get_provider_kinds(provider: LiteralProvider) -> frozenset[LiteralProviderKind]:
    """Get capabilities for a provider."""
    return PROVIDER_CAPABILITIES.get(provider, frozenset()).union({ProviderKind.DATA})


__all__ = ("PROVIDER_CAPABILITIES", "VECTOR_PROVIDER_CAPABILITIES", "get_provider_kinds")
