# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Types for providers."""

from __future__ import annotations

from typing import Literal

from codeweaver.core.types.provider import Provider, ProviderKind


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

__all__ = ("LiteralProvider", "LiteralProviderKind")
